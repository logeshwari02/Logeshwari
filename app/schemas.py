from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)


PlannerType = Literal["home", "party", "jewelry"]


# ---------------------------------------------------------------------------
# Small normalization helpers
# ---------------------------------------------------------------------------


def _clean_text(value: Any, default: str = "unknown") -> str:
    """Convert loose model output into a safe, trimmed string."""
    if value is None:
        return default

    if isinstance(value, str):
        cleaned = " ".join(value.split()).strip()
        return cleaned or default

    try:
        cleaned = " ".join(str(value).split()).strip()
    except Exception:
        return default

    return cleaned or default


def _clean_color_list(value: Any) -> list[str]:
    """Normalize Gemini's possible color formats into list[str]."""
    if value is None:
        return []

    if isinstance(value, str):
        # Gemini may return either a single color or a comma/semicolon list.
        parts = re.split(r"[,;|]", value)
        return [
            cleaned
            for item in parts
            if (cleaned := _clean_text(item, ""))
        ]

    if isinstance(value, (tuple, set, list)):
        result: list[str] = []
        for item in value:
            cleaned = _clean_text(item, "")
            if cleaned:
                result.append(cleaned)
        return result

    return [_clean_text(value, "unknown")]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Full name is required")
        return value


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserPublic


# ---------------------------------------------------------------------------
# Home planner
# ---------------------------------------------------------------------------


class HomeItemRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    quantity: int = Field(default=1, ge=1, le=50)
    preferred_style: str | None = Field(default=None, max_length=80)


class HomePlannerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    budget: float = Field(gt=0, le=100_000_000)
    rooms: list[str] = Field(min_length=1, max_length=20)
    items: list[HomeItemRequest] = Field(min_length=1, max_length=100)
    city: str | None = Field(default=None, max_length=100)
    style: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)

    @field_validator("rooms")
    @classmethod
    def clean_rooms(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(room.split()) for room in value if room.strip()]
        if not cleaned:
            raise ValueError("At least one room is required")
        return cleaned


# ---------------------------------------------------------------------------
# Party planner
# ---------------------------------------------------------------------------


class PartyPlannerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    budget: float = Field(gt=0, le=100_000_000)
    guest_count: int = Field(gt=0, le=100_000)
    event_type: str = Field(min_length=2, max_length=80)
    venue: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=100)
    food_preference: str | None = Field(default=None, max_length=120)
    decoration_style: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2_000)


# ---------------------------------------------------------------------------
# Jewelry planner
# ---------------------------------------------------------------------------


class JewelryPlannerRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    budget: float = Field(gt=0, le=100_000_000)
    occasion: str = Field(min_length=2, max_length=100)
    style: str | None = Field(default=None, max_length=120)
    metal_preference: str | None = Field(default=None, max_length=100)
    outfit_color: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2_000)


# ---------------------------------------------------------------------------
# Gemini outfit analysis
# ---------------------------------------------------------------------------


class OutfitVisualAnalysis(BaseModel):
    """
    Tolerant representation of Gemini's outfit analysis.

    Gemini is an LLM, so this model deliberately accepts small variations in
    its output instead of allowing harmless formatting differences to turn a
    successful multimodal call into a ValueError/fallback.
    """

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    dominant_colors: list[str] = Field(
        default_factory=list,
        max_length=8,
    )
    garment_style: str = "unknown"
    formality: str = "unknown"
    overall_style: str = "unknown"
    jewelry_guidance: str = (
        "Use the outfit's colors, style, and formality to coordinate jewelry."
    )

    @field_validator("dominant_colors", mode="before")
    @classmethod
    def normalize_colors(cls, value: Any) -> list[str]:
        cleaned = _clean_color_list(value)
        # Keep a hard upper bound even if an unexpected model response is large.
        return cleaned[:8]

    @field_validator(
        "garment_style",
        "formality",
        "overall_style",
        "jewelry_guidance",
        mode="before",
    )
    @classmethod
    def normalize_analysis_text(cls, value: Any) -> str:
        return _clean_text(value)


# ---------------------------------------------------------------------------
# Gemini planner response
# ---------------------------------------------------------------------------


class BudgetAllocation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(min_length=1, max_length=120)
    allocated_amount: float = Field(ge=0)
    percentage: float = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=2_000)


class AIRecommendation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(min_length=1, max_length=120)
    item_name: str = Field(min_length=1, max_length=240)
    estimated_price: float = Field(ge=0)
    quantity: int = Field(default=1, ge=1, le=10_000)
    platform: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=2_000)
    priority: Literal["high", "medium", "low"] = "medium"
    search_url: str | None = None


class PlannerAIResponse(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
    )

    summary: str = Field(min_length=1, max_length=5_000)
    budget_allocations: list[BudgetAllocation] = Field(default_factory=list)
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("warnings", mode="before")
    @classmethod
    def normalize_warnings(cls, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return [value.strip()] if value.strip() else []

        if isinstance(value, (list, tuple, set)):
            result: list[str] = []
            for item in value:
                cleaned = _clean_text(item, "")
                if cleaned:
                    result.append(cleaned)
            return result

        return [_clean_text(value)]


# ---------------------------------------------------------------------------
# Public planner response
# ---------------------------------------------------------------------------


class PlannerResponse(PlannerAIResponse):
    planner_type: PlannerType
    budget: float
    estimated_total: float
    remaining_budget: float
    ai_used: bool
    generated_at: datetime
    history_id: int | None = None


# ---------------------------------------------------------------------------
# History / session / health
# ---------------------------------------------------------------------------


class HistoryItem(BaseModel):
    id: int
    planner_type: PlannerType
    budget: float
    created_at: datetime
    response: PlannerResponse


class HistoryListResponse(BaseModel):
    items: list[HistoryItem]
    total: int


class SessionInfoResponse(BaseModel):
    user: UserPublic
    token_expires_at: datetime
    history_count: int


class HealthResponse(BaseModel):
    status: str
    app: str
    gemini_configured: bool
    gemini_model: str
    database: str
