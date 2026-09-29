from fastapi import APIRouter

from app.config import get_settings
from app.schemas import HealthResponse
from app.services.gemini import get_gemini_service

router = APIRouter(tags=["System"])


@router.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    gemini = get_gemini_service()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        gemini_configured=gemini.enabled,
        gemini_model=settings.gemini_model,
        database="sqlite" if settings.database_url.startswith("sqlite") else "configured",
    )
