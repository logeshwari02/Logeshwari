from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.schemas import PlannerAIResponse
from app.services.gemini import GeminiService
from app.services.recommendations import PlannerContext, jewelry_fallback
from app.schemas import JewelryPlannerRequest


def sample_png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (40, 30), (20, 90, 50)).save(out, format="PNG")
    return out.getvalue()


def test_mock_multimodal_pipeline() -> None:
    class FakePart:
        @classmethod
        def from_bytes(cls, data, mime_type):
            return {"kind": "image", "mime_type": mime_type, "data": data}

    class FakeTypes:
        Part = FakePart
        class GenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

    class FakeModels:
        def __init__(self):
            self.calls = []

        async def generate_content(self, *, model, contents, config):
            self.calls.append((model, contents, config.kwargs))
            if len(self.calls) == 1:
                return SimpleNamespace(
                    text='{"dominant_colors":["deep green"],"garment_style":"traditional","formality":"formal","overall_style":"elegant","jewelry_guidance":"Gold-toned jewelry with a restrained design."}',
                    parsed=None,
                )
            return SimpleNamespace(
                parsed=PlannerAIResponse(summary="Mock jewelry plan", budget_allocations=[], recommendations=[], warnings=[]),
                text="",
            )

    async def run() -> None:
        models = FakeModels()
        svc = object.__new__(GeminiService)
        svc.enabled = True
        svc._client = SimpleNamespace(aio=SimpleNamespace(models=models))
        svc._types = FakeTypes
        svc.model = "gemini-3.8-flash"
        svc.initialization_error = None

        req = JewelryPlannerRequest(
            budget=10000,
            occasion="Wedding",
            style="Elegant",
            metal_preference="Gold",
            outfit_color="Dark green",
        )
        ctx = PlannerContext("jewelry", req.budget, ["Amazon", "Flipkart"], jewelry_fallback(req))
        result = await svc.generate(req, ctx, image_bytes=sample_png(), image_mime="image/png")

        assert result.ai_used is True
        assert result.response.summary == "Mock jewelry plan"
        assert len(models.calls) == 2
        assert models.calls[0][1][0]["kind"] == "image"
        assert "response_schema" not in models.calls[0][2]
        assert models.calls[1][2]["response_schema"] is PlannerAIResponse

    asyncio.run(run())
