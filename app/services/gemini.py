from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.config import get_settings
from app.schemas import OutfitVisualAnalysis, PlannerAIResponse
from app.services.image_utils import normalize_image_for_gemini
from app.services.recommendations import PlannerContext, postprocess_ai_response

settings = get_settings()
logger = logging.getLogger("pocketsmart.gemini")


@dataclass(frozen=True)
class GeminiResult:
    response: PlannerAIResponse
    ai_used: bool


class GeminiService:
    """
    Reliable Gemini integration for PocketSmart.

    Design goals:
    - Keep the existing GeminiService.generate() interface.
    - Support Home, Party and Jewelry planners.
    - Support optional Jewelry outfit-image analysis.
    - Accept both JSON and labeled prose from Gemini's image-analysis stage.
    - Fail over from the primary Gemini model to a secondary model for
      transient 429/5xx conditions.
    - Never convert a successful image-analysis stage into a false failure
      just because the final structured recommendation call failed.
    - Preserve deterministic local fallback behavior as the final safety net.

    The final recommendation result is considered AI-generated when the
    final recommendation stage succeeds, even when optional image analysis
    had to be skipped. A warning is added in that case.
    """

    def __init__(self) -> None:
        self.enabled = bool(settings.gemini_api_key.strip())
        self.model = (settings.gemini_model or "gemini-3.5-flash").strip()
        self.fallback_model = (
            getattr(settings, "gemini_fallback_model", None)
            or "gemini-3.5-flash-lite"
        ).strip()

        self._client: Any | None = None
        self._types: Any | None = None
        self.initialization_error: str | None = None

        if self.enabled:
            try:
                from google import genai
                from google.genai import types

                timeout_ms = max(1, int(settings.gemini_timeout_seconds)) * 1000

                self._types = types
                self._client = genai.Client(
                    api_key=settings.gemini_api_key,
                    http_options=types.HttpOptions(timeout=timeout_ms),
                )

            except Exception as exc:
                self.initialization_error = (
                    "Gemini SDK initialization failed: "
                    f"{type(exc).__name__}"
                )
                self._client = None

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _system_instruction(self, context: PlannerContext) -> str:
        return f"""You are PocketSmart AI, a budget-aware recommendation assistant.

Planner type: {context.planner_type}
User budget: {context.budget}
Allowed platforms: {', '.join(context.allowed_platforms)}

Rules:
1. Never claim that you verified live inventory, current price, ratings, stock, or availability unless live data is actually provided.
2. Treat estimated prices as estimates unless a live data source is supplied.
3. Keep recommendations practical and budget-conscious.
4. Return JSON matching the requested schema.
5. Prefer the allowed platforms listed above.
6. Keep the recommendation total at or below the user's budget where reasonably possible.
7. Explain recommendations using the user's requirements.
8. Never invent that a product is currently in stock.
"""

    def _prompt(
        self,
        request: Any,
        context: PlannerContext,
        visual_context: str | None = None,
    ) -> str:
        data = request.model_dump(mode="json")

        prompt = (
            f"Create a {context.planner_type} plan for the user.\n"
            f"Input JSON:\n{json.dumps(data, indent=2, ensure_ascii=False)}\n\n"
            "Return only the structured response. Make the recommendations realistic, "
            "explain trade-offs, and keep the plan within the budget as closely as possible."
        )

        if visual_context:
            prompt += (
                "\n\nThe Jewelry Planner includes an outfit image that was analyzed separately. "
                "Use this visual analysis as additional context. Do not claim exact measurements, "
                "fabric composition, brand, or other details that cannot be confidently observed.\n"
                f"Outfit visual analysis:\n{visual_context}"
            )

        return prompt

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_markdown(text: str) -> str:
        cleaned = (text or "").strip()
        cleaned = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        return cleaned.strip()

    @classmethod
    def _extract_json_object(cls, text: str) -> dict[str, Any] | None:
        cleaned = cls._clean_markdown(text)
        if not cleaned:
            return None

        try:
            value = json.loads(cleaned)
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            return None

        try:
            value = json.loads(cleaned[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_section(text: str, labels: list[str]) -> str | None:
        label_pattern = "|".join(re.escape(label) for label in labels)

        pattern = re.compile(
            rf"(?:\*{{0,2}})?(?:{label_pattern})(?:\*{{0,2}})?\s*:\s*"
            rf"(.+?)(?=\n\s*\n|\n\s*(?:\*{{0,2}})[A-Z][A-Za-z0-9 /&'-]{{1,60}}(?:\*{{0,2}}):|\Z)",
            flags=re.IGNORECASE | re.DOTALL,
        )

        match = pattern.search(text)
        if not match:
            return None

        value = match.group(1).strip()
        value = re.sub(r"^[*•-]+\s*", "", value)
        value = re.sub(r"\s*[*]+$", "", value)
        return value.strip() or None

    @classmethod
    def _parse_outfit_analysis(cls, text: str) -> OutfitVisualAnalysis:
        """
        Parse Gemini outfit analysis from either JSON or labeled prose.

        This fixes the exact failure observed in testing: Gemini can return
        a useful labeled response even when the prompt requests a JSON-like
        structure. Such a response must not be treated as a failed Gemini call.
        """
        cleaned = cls._clean_markdown(text)
        if not cleaned:
            raise ValueError("Gemini returned an empty outfit-analysis response")

        json_data = cls._extract_json_object(cleaned)
        if json_data is not None:
            try:
                return OutfitVisualAnalysis.model_validate(json_data)
            except Exception as exc:
                logger.warning(
                    "Gemini returned JSON for outfit analysis but validation failed: %s",
                    type(exc).__name__,
                )

        dominant_colors_text = cls._extract_section(
            cleaned,
            ["Dominant Colors", "Dominant Colours"],
        )
        garment_style = cls._extract_section(cleaned, ["Garment Style"])
        formality = cls._extract_section(cleaned, ["Formality"])
        overall_style = cls._extract_section(cleaned, ["Overall Style"])
        jewelry_guidance = cls._extract_section(
            cleaned,
            [
                "Jewelry Direction",
                "Jewellery Direction",
                "Jewelry Guidance",
                "Jewellery Guidance",
            ],
        )

        dominant_colors: list[str] = []
        if dominant_colors_text:
            dominant_colors = [
                item.strip(" -*•\t")
                for item in re.split(r",|;", dominant_colors_text)
                if item.strip(" -*•\t")
            ]

        if not dominant_colors:
            dominant_colors = ["unknown"]

        # Do not fail merely because Gemini changed its formatting.
        # Any non-empty vision response is valuable context for the final
        # recommendation model, so preserve the raw text when structured
        # sections cannot be extracted.
        raw_fallback = (
            "Raw Gemini outfit analysis:\n"
            + cleaned
        )

        return OutfitVisualAnalysis(
            dominant_colors=dominant_colors[:8],
            garment_style=garment_style or "unknown",
            formality=formality or "unknown",
            overall_style=overall_style or "unknown",
            jewelry_guidance=(
                jewelry_guidance
                or raw_fallback
            ),
        )

    # ------------------------------------------------------------------
    # Error / model helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        for attr in ("status_code", "code"):
            value = getattr(exc, attr, None)
            if isinstance(value, int):
                return value
        return None

    @classmethod
    def _is_retryable(cls, exc: Exception) -> bool:
        status = cls._status_code(exc)
        if isinstance(status, int):
            return status in {408, 429} or status >= 500

        name = type(exc).__name__.lower()
        message = str(exc).lower()
        retry_markers = (
            "servererror",
            "internal",
            "unavailable",
            "timeout",
            "deadline",
            "ratelimit",
            "toomanyrequests",
            "temporarily",
            "503",
            "429",
            "408",
        )
        return any(marker in name or marker in message for marker in retry_markers)

    def _model_chain(self) -> list[str]:
        models: list[str] = []
        for candidate in (self.model, self.fallback_model):
            candidate = (candidate or "").strip()
            if candidate and candidate not in models:
                models.append(candidate)
        return models

    async def _call_with_sdk_retry(
        self,
        operation: Callable[[], Awaitable[Any]],
        stage: str,
        model: str,
        backoff_attempts: int,
    ) -> Any:
        """
        Add a small application-level retry around the SDK for transient
        failures, with exponential backoff and jitter.

        The Google SDK also has its own retry handling; these bounded retries
        exist mainly to make our model failover deterministic at the service
        layer. There is no unbounded loop.
        """
        attempts = max(1, backoff_attempts)
        last_error: Exception | None = None

        for attempt in range(attempts):
            try:
                return await operation()
            except Exception as exc:
                last_error = exc

                if not self._is_retryable(exc) or attempt == attempts - 1:
                    raise

                delay = min(8.0, 0.75 * (2 ** attempt)) + random.uniform(0.0, 0.25)
                logger.warning(
                    "Gemini %s failed on %s with %s; retrying in %.2fs (%d/%d)",
                    stage,
                    model,
                    type(exc).__name__,
                    delay,
                    attempt + 1,
                    attempts,
                )
                await asyncio.sleep(delay)

        raise last_error or RuntimeError(f"Gemini {stage} failed")

    async def _generate_with_model_failover(
        self,
        stage: str,
        operation_factory: Callable[[str], Callable[[], Awaitable[Any]]],
        attempts_per_model: int,
    ) -> tuple[Any, str]:
        """
        Try the primary model, then the fallback model only when the failure
        is transient. Non-transient errors are raised immediately because a
        different model generally cannot fix an invalid request/auth issue.
        """
        errors: list[Exception] = []

        for model in self._model_chain():
            try:
                response = await self._call_with_sdk_retry(
                    operation_factory(model),
                    stage=stage,
                    model=model,
                    backoff_attempts=attempts_per_model,
                )
                return response, model
            except Exception as exc:
                errors.append(exc)
                logger.warning(
                    "Gemini %s failed on model %s: %s",
                    stage,
                    model,
                    type(exc).__name__,
                )

                if not self._is_retryable(exc):
                    raise

        primary_error = errors[0] if errors else RuntimeError(
            f"Gemini {stage} failed"
        )
        raise primary_error

    # ------------------------------------------------------------------
    # Image analysis
    # ------------------------------------------------------------------

    async def _analyze_outfit_image(
        self,
        image_bytes: bytes,
        image_mime: str,
    ) -> tuple[OutfitVisualAnalysis, str]:
        if self._types is None or self._client is None:
            raise RuntimeError("Gemini client is not initialized")

        normalized_bytes, normalized_mime, _, _ = normalize_image_for_gemini(
            image_bytes
        )

        prompt = (
            "Analyze this outfit image for jewelry coordination. "
            "Return a concise, clearly labeled analysis with these sections: "
            "Dominant Colors, Garment Style, Formality, Overall Style, "
            "Jewelry Direction. "
            "You may use plain labeled text; JSON is also acceptable. "
            "Focus only on broad visible traits. Do not identify the person "
            "or infer sensitive traits. Use 'unknown' when a trait cannot "
            "be judged confidently."
        )

        image_part = self._types.Part.from_bytes(
            data=normalized_bytes,
            mime_type=normalized_mime,
        )

        def factory(model: str) -> Callable[[], Awaitable[Any]]:
            async def call() -> Any:
                return await self._client.aio.models.generate_content(
                    model=model,
                    contents=[image_part, prompt],
                    config=self._types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=700,
                    ),
                )

            return call

        response, used_model = await self._generate_with_model_failover(
            stage="image analysis",
            operation_factory=factory,
            attempts_per_model=max(1, int(settings.gemini_image_retries)),
        )

        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini returned an empty outfit-analysis response")

        analysis = self._parse_outfit_analysis(text)
        return analysis, used_model

    # ------------------------------------------------------------------
    # Final structured recommendation
    # ------------------------------------------------------------------

    async def _generate_structured_plan(
        self,
        request: Any,
        context: PlannerContext,
        visual_context: str | None,
    ) -> tuple[PlannerAIResponse, str]:
        if self._types is None or self._client is None:
            raise RuntimeError("Gemini client is not initialized")

        def factory(model: str) -> Callable[[], Awaitable[Any]]:
            async def call() -> Any:
                return await self._client.aio.models.generate_content(
                    model=model,
                    contents=self._prompt(
                        request,
                        context,
                        visual_context,
                    ),
                    config=self._types.GenerateContentConfig(
                        system_instruction=self._system_instruction(context),
                        temperature=max(0.0, min(1.0, float(settings.gemini_temperature))),
                        max_output_tokens=5000,
                        response_mime_type="application/json",
                        response_schema=PlannerAIResponse,
                    ),
                )

            return call

        response, used_model = await self._generate_with_model_failover(
            stage="structured recommendation generation",
            operation_factory=factory,
            attempts_per_model=max(1, int(settings.gemini_request_retries)),
        )

        parsed = getattr(response, "parsed", None)

        if isinstance(parsed, PlannerAIResponse):
            result = parsed
        elif parsed is not None:
            result = PlannerAIResponse.model_validate(parsed)
        else:
            text = getattr(response, "text", None)
            if not text:
                raise ValueError("Gemini returned an empty structured response")
            result = PlannerAIResponse.model_validate_json(
                self._clean_markdown(text)
            )

        return (
            postprocess_ai_response(
                result,
                context.budget,
                context.allowed_platforms,
            ),
            used_model,
        )

    # ------------------------------------------------------------------
    # Public API used by planners.py
    # ------------------------------------------------------------------

    async def generate(
        self,
        request: Any,
        context: PlannerContext,
        image_bytes: bytes | None = None,
        image_mime: str | None = None,
    ) -> GeminiResult:
        if not self.enabled or self._client is None:
            fallback = context.fallback_response.model_copy(deep=True)
            fallback.warnings = [
                warning
                for warning in fallback.warnings
                if "Gemini API is not configured" not in warning
            ]
            fallback.warnings.append(
                "Gemini API is not configured; deterministic fallback recommendations were returned."
            )
            if self.initialization_error:
                fallback.warnings.append(self.initialization_error)
            return GeminiResult(response=fallback, ai_used=False)

        visual_context: str | None = None
        image_analysis_warning: str | None = None
        image_analysis_model: str | None = None

        # --------------------------------------------------------------
        # Optional image stage.
        # --------------------------------------------------------------
        if image_bytes:
            try:
                analysis, image_analysis_model = await self._analyze_outfit_image(
                    image_bytes,
                    image_mime or "image/jpeg",
                )
                visual_context = analysis.model_dump_json(indent=2)
            except Exception as exc:
                image_analysis_warning = (
                    "Gemini outfit image analysis failed safely "
                    f"({type(exc).__name__}); the final AI recommendation "
                    "will continue without image-derived styling information."
                )
                logger.exception(
                    "Gemini outfit image analysis failed after model failover (%s)",
                    type(exc).__name__,
                )

        # --------------------------------------------------------------
        # Final recommendation stage.
        # --------------------------------------------------------------
        try:
            result, final_model = await self._generate_structured_plan(
                request,
                context,
                visual_context,
            )

            if image_bytes:
                if image_analysis_warning:
                    result.warnings.append(image_analysis_warning)
                elif image_analysis_model and image_analysis_model != self.model:
                    result.warnings.append(
                        "Outfit image was analyzed by Gemini using the fallback model "
                        "and the visual analysis was used for recommendations."
                    )
                else:
                    result.warnings.append(
                        "Outfit image was analyzed by Gemini and used as additional recommendation context."
                    )

            if final_model != self.model:
                result.warnings.append(
                    f"Final recommendations were generated using Gemini fallback model '{final_model}'."
                )

            return GeminiResult(response=result, ai_used=True)

        except Exception as exc:
            logger.exception(
                "Gemini final recommendation generation failed after model failover (%s)",
                type(exc).__name__,
            )

            fallback = context.fallback_response.model_copy(deep=True)
            fallback.warnings = [
                warning
                for warning in fallback.warnings
                if "Gemini API is not configured" not in warning
            ]

            fallback.warnings.append(
                "Gemini structured recommendation generation failed safely "
                f"({type(exc).__name__}); deterministic fallback recommendations were returned."
            )

            if image_bytes:
                if image_analysis_warning:
                    fallback.warnings.append(image_analysis_warning)
                elif visual_context is not None:
                    fallback.warnings.append(
                        "The outfit image was analyzed successfully, but final structured recommendation generation failed."
                    )
                else:
                    fallback.warnings.append(
                        "The outfit image was not available as recommendation context."
                    )

            return GeminiResult(response=fallback, ai_used=False)

    async def close(self) -> None:
        if self._client is None:
            return

        aio_client = getattr(self._client, "aio", None)
        close_method = getattr(aio_client, "aclose", None)

        if close_method is not None:
            result = close_method()
            if hasattr(result, "__await__"):
                await result


_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service


async def close_gemini_service() -> None:
    global _gemini_service
    if _gemini_service is not None:
        await _gemini_service.close()
        _gemini_service = None
