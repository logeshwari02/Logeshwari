from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas import (
    AIRecommendation,
    BudgetAllocation,
    HomePlannerRequest,
    JewelryPlannerRequest,
    PartyPlannerRequest,
    PlannerAIResponse,
)
from app.services.platforms import build_search_url, normalize_platform


@dataclass(frozen=True)
class PlannerContext:
    planner_type: str
    budget: float
    allowed_platforms: list[str]
    fallback_response: PlannerAIResponse


def _allocation(category: str, amount: float, budget: float, rationale: str) -> BudgetAllocation:
    percentage = round((amount / budget * 100) if budget else 0, 2)
    return BudgetAllocation(
        category=category,
        allocated_amount=round(amount, 2),
        percentage=percentage,
        rationale=rationale,
    )


def _recommendation(
    category: str,
    item_name: str,
    price: float,
    platform: str,
    reason: str,
    quantity: int = 1,
    priority: str = "medium",
) -> AIRecommendation:
    platform = platform.title()
    return AIRecommendation(
        category=category,
        item_name=item_name,
        estimated_price=round(max(price, 0), 2),
        quantity=quantity,
        platform=platform,
        reason=reason,
        priority=priority,
        search_url=build_search_url(platform, item_name),
    )


def home_fallback(req: HomePlannerRequest) -> PlannerAIResponse:
    budget = req.budget
    shopping = budget * 0.90
    reserve = budget - shopping
    total_units = sum(item.quantity for item in req.items)
    per_item = shopping / max(total_units, 1)
    recs = []
    for item in req.items[:12]:
        recs.append(
            _recommendation(
                category=item.name,
                item_name=f"{item.name} – budget-friendly {req.style or item.preferred_style or 'versatile'} option",
                price=min(per_item, budget),
                platform="Amazon",
                reason=f"Selected as a starting point for {', '.join(req.rooms[:3])} within the overall budget.",
                quantity=item.quantity,
                priority="high" if item.quantity > 1 else "medium",
            )
        )
    return PlannerAIResponse(
        summary="A starter home setup was generated using the requested rooms, quantities and budget. Add Gemini API access for richer personalized recommendations.",
        budget_allocations=[
            _allocation("Shopping", shopping, budget, "Primary allocation for requested home items."),
            _allocation("Reserve", reserve, budget, "Kept aside for delivery, installation and small unexpected costs."),
        ],
        recommendations=recs,
        warnings=["Gemini API is not configured; this response uses the built-in deterministic fallback."],
    )


def party_fallback(req: PartyPlannerRequest) -> PlannerAIResponse:
    b = req.budget
    food = b * 0.50
    decor = b * 0.20
    entertainment = b * 0.15
    reserve = b * 0.15
    recs = [
        _recommendation("Food", f"Catering for {req.guest_count} guests", food, "Swiggy", f"Food receives the largest allocation for a {req.event_type} event.", priority="high"),
        _recommendation("Decoration", f"{req.decoration_style or 'event'} decoration package", decor, "Amazon", "A moderate decoration budget keeps the event visually cohesive."),
        _recommendation("Entertainment", "Party activity / entertainment kit", entertainment, "Amazon", "A smaller entertainment allocation leaves room for food and decor."),
    ]
    return PlannerAIResponse(
        summary=f"Starter plan for a {req.event_type} with {req.guest_count} guests in a budget of {b:.0f}.",
        budget_allocations=[
            _allocation("Food", food, b, "Largest share for catering and refreshments."),
            _allocation("Decoration", decor, b, "Covers venue styling and decorations."),
            _allocation("Entertainment", entertainment, b, "Covers activities or entertainment."),
            _allocation("Reserve", reserve, b, "Buffer for unexpected event costs."),
        ],
        recommendations=recs,
        warnings=["Gemini API is not configured; this response uses the built-in deterministic fallback."],
    )


def jewelry_fallback(req: JewelryPlannerRequest) -> PlannerAIResponse:
    b = req.budget
    recs = [
        _recommendation(
            "Earrings",
            f"{req.style or 'elegant'} earrings for {req.occasion}",
            b * 0.35,
            "Amazon",
            f"A versatile match for a {req.occasion} look{f' in {req.outfit_color}' if req.outfit_color else ''}.",
            priority="high",
        ),
        _recommendation(
            "Necklace",
            f"{req.metal_preference or 'classic'} necklace set",
            b * 0.45,
            "Flipkart",
            "Balances the main statement piece with the remaining budget.",
            priority="medium",
        ),
        _recommendation(
            "Accessories",
            "Matching bracelet / accessory",
            b * 0.15,
            "Amazon",
            "Optional finishing piece while keeping a reserve.",
            priority="low",
        ),
    ]
    return PlannerAIResponse(
        summary=f"Starter jewelry plan for a {req.occasion} occasion within the requested budget.",
        budget_allocations=[
            _allocation("Main jewelry", b * 0.80, b, "Core necklace and earring spend."),
            _allocation("Accessories", b * 0.15, b, "Optional finishing accessories."),
            _allocation("Reserve", b * 0.05, b, "Kept for delivery or small price variation."),
        ],
        recommendations=recs,
        warnings=["Gemini API is not configured; this response uses the built-in deterministic fallback."],
    )


def build_context(planner_type: str, request: Any) -> PlannerContext:
    if planner_type == "home":
        return PlannerContext("home", request.budget, ["Amazon", "IKEA", "Flipkart"], home_fallback(request))
    if planner_type == "party":
        return PlannerContext("party", request.budget, ["Swiggy", "Zomato", "OYO", "Amazon", "Flipkart"], party_fallback(request))
    if planner_type == "jewelry":
        return PlannerContext("jewelry", request.budget, ["Amazon", "Flipkart"], jewelry_fallback(request))
    raise ValueError(f"Unsupported planner type: {planner_type}")


def postprocess_ai_response(response: PlannerAIResponse, budget: float, allowed_platforms: list[str]) -> PlannerAIResponse:
    for rec in response.recommendations:
        rec.platform = normalize_platform(rec.platform, allowed_platforms)
        rec.search_url = build_search_url(rec.platform, rec.item_name)
        rec.estimated_price = round(max(rec.estimated_price, 0), 2)
        rec.quantity = max(1, rec.quantity)

    total = sum(rec.estimated_price * rec.quantity for rec in response.recommendations)
    if total > budget + 0.01:
        response.warnings.append(
            f"AI recommendation total ({total:.2f}) exceeds the requested budget ({budget:.2f}); review prices before purchase."
        )
    return response
