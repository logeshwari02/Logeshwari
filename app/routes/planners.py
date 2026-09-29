from __future__ import annotations

from datetime import datetime, timezone
import mimetypes
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import User
from app.schemas import (
    HomePlannerRequest,
    JewelryPlannerRequest,
    PartyPlannerRequest,
    PlannerResponse,
)
from app.services.gemini import get_gemini_service
from app.services.history import save_history
from app.services.recommendations import build_context

router = APIRouter(prefix="/planners", tags=["Planners"])
compat_router = APIRouter(tags=["Planners"])
settings = get_settings()


async def _run_planner(
    planner_type: str,
    payload,
    current_user: User,
    db: Session,
    image_bytes: bytes | None = None,
    image_mime: str | None = None,
) -> PlannerResponse:
    """Run one planner, persist its result, and return a stable API response."""
    context = build_context(planner_type, payload)

    gemini_result = await get_gemini_service().generate(
        payload,
        context,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )

    ai_result = gemini_result.response.model_dump(mode="json")

    # Build the API response in one dictionary so route-controlled fields
    # (budget, totals, ai_used, timestamp) cannot be accidentally overwritten
    # by fields returned by the model.
    recommendations = gemini_result.response.recommendations
    estimated_total = round(
        sum(item.estimated_price * item.quantity for item in recommendations),
        2,
    )

    response_data = {
        **ai_result,
        "planner_type": planner_type,
        "budget": payload.budget,
        "estimated_total": estimated_total,
        "remaining_budget": round(payload.budget - estimated_total, 2),
        "ai_used": gemini_result.ai_used,
        "generated_at": datetime.now(timezone.utc),
    }
    response = PlannerResponse(**response_data)

    request_data = payload.model_dump(mode="json")
    if planner_type == "jewelry":
        request_data["outfit_image_uploaded"] = image_bytes is not None

    history_id = save_history(
        db,
        current_user,
        planner_type,
        payload.budget,
        request_data,
        response,
    )
    response.history_id = history_id

    return response


async def _read_outfit_image(
    outfit_image: UploadFile | None,
) -> tuple[bytes | None, str | None]:
    if outfit_image is None:
        return None, None

    allowed_mimes = {"image/jpeg", "image/png", "image/webp"}

    content_type = (outfit_image.content_type or "").lower().strip()
    guessed_type = mimetypes.guess_type(outfit_image.filename or "")[0]

    if content_type in allowed_mimes:
        image_mime = content_type
    elif guessed_type in allowed_mimes:
        image_mime = guessed_type
    else:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image type. Use JPEG, PNG or WEBP.",
        )

    max_bytes = settings.max_image_size_mb * 1024 * 1024
    image_bytes = await outfit_image.read(max_bytes + 1)

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="The uploaded image is empty.",
        )

    if len(image_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image exceeds {settings.max_image_size_mb} MB limit",
        )

    return image_bytes, image_mime

# ---------------------------------------------------------------------------
# Primary JSON planner routes
# ---------------------------------------------------------------------------

@router.post("/home", response_model=PlannerResponse)
async def generate_home(
    payload: HomePlannerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PlannerResponse:
    return await _run_planner("home", payload, current_user, db)


@router.post("/party", response_model=PlannerResponse)
async def generate_party(
    payload: PartyPlannerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PlannerResponse:
    return await _run_planner("party", payload, current_user, db)


@router.post("/jewelry", response_model=PlannerResponse)
async def generate_jewelry_json(
    payload: JewelryPlannerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PlannerResponse:
    return await _run_planner("jewelry", payload, current_user, db)


# ---------------------------------------------------------------------------
# Optional multimodal Jewelry route
# ---------------------------------------------------------------------------

@router.post("/jewelry-upload", response_model=PlannerResponse)
async def generate_jewelry_upload(
    budget: float = Form(...),
    occasion: str = Form(...),
    style: str | None = Form(default=None),
    metal_preference: str | None = Form(default=None),
    outfit_color: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    outfit_image: UploadFile | None = File(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlannerResponse:
    payload = JewelryPlannerRequest(
        budget=budget,
        occasion=occasion,
        style=style,
        metal_preference=metal_preference,
        outfit_color=outfit_color,
        notes=notes,
    )

    image_bytes, image_mime = await _read_outfit_image(outfit_image)

    return await _run_planner(
        "jewelry",
        payload,
        current_user,
        db,
        image_bytes=image_bytes,
        image_mime=image_mime,
    )


# ---------------------------------------------------------------------------
# Compatibility aliases from the project specification
# ---------------------------------------------------------------------------

@compat_router.post(
    "/generate-home",
    response_model=PlannerResponse,
    include_in_schema=False,
)
async def generate_home_alias(
    payload: HomePlannerRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PlannerResponse:
    return await _run_planner("home", payload, current_user, db)