from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import RecommendationHistory, User
from app.schemas import HistoryItem, PlannerResponse


def save_history(
    db: Session,
    user: User,
    planner_type: str,
    budget: float,
    request_data: dict,
    response: PlannerResponse,
) -> int:
    record = RecommendationHistory(
        user_id=user.id,
        planner_type=planner_type,
        budget=budget,
        request_json=json.dumps(request_data, ensure_ascii=False),
        response_json=response.model_dump_json(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


def get_history(
    db: Session,
    user: User,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[HistoryItem], int]:
    count_result = db.execute(
        select(func.count(RecommendationHistory.id)).where(RecommendationHistory.user_id == user.id)
    )
    total = int(count_result.scalar_one() or 0)

    result = db.execute(
        select(RecommendationHistory)
        .where(RecommendationHistory.user_id == user.id)
        .order_by(RecommendationHistory.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    records = result.scalars().all()
    items = []
    for record in records:
        payload = json.loads(record.response_json)
        payload["history_id"] = record.id
        response = PlannerResponse.model_validate(payload)
        items.append(
            HistoryItem(
                id=record.id,
                planner_type=record.planner_type,
                budget=record.budget,
                created_at=record.created_at,
                response=response,
            )
        )
    return items, total
