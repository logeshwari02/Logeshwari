from __future__ import annotations

import asyncio
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.schemas import JewelryPlannerRequest, PlannerAIResponse
from app.services.gemini import GeminiService
from app.services.image_utils import normalize_image_for_gemini
from app.services.recommendations import PlannerContext, jewelry_fallback


def sample_png() -> bytes:
    out = BytesIO()
    Image.new("RGB", (40, 30), (15, 80, 45)).save(out, format="PNG")
    return out.getvalue()


def test_image_normalization():
    data, mime, width, height = normalize_image_for_gemini(sample_png())
    assert mime == "image/jpeg"
    assert width == 40
    assert height == 30
    assert data[:2] == bytes([0xFF, 0xD8])


def test_image_call_uses_plain_json_then_structured_plan():
    class FakePart:
        @classmethod
        def from_bytes(cls, data, mime_type):
            assert data[:2] == bytes([0xFF, 0xD8])
            assert mime_type == "image/jpeg"
            return {"kind": "image", "mime": mime_type}

    class FakeConfig:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class FakeTypes:
        Part = FakePart
        GenerateContentConfig = FakeConfig

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
                text='{"summary":"Mock image-aware plan","budget_allocations":[],"recommendations":[],"warnings":[]}',
                parsed=PlannerAIResponse(summary="Mock image-aware plan", budget_allocations=[], recommendations=[], warnings=[]),
            )

    async def run():
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
        assert result.response.summary == "Mock image-aware plan"
        assert len(models.calls) == 2
        assert models.calls[0][1][0]["kind"] == "image"
        assert "response_schema" not in models.calls[0][2]
        assert models.calls[1][2]["response_schema"] is PlannerAIResponse

    asyncio.run(run())
