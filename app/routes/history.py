from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import RecommendationHistory, User
from app.schemas import HistoryListResponse, SessionInfoResponse
from app.services.history import get_history
import json

router = APIRouter(tags=["History & Session"])


@router.get("/history", response_model=HistoryListResponse)
async def history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    items, total = get_history(db, current_user, limit=limit, offset=offset)
    return HistoryListResponse(items=items, total=total)


@router.get("/recommendations-details", response_model=HistoryListResponse)
async def recommendations_details(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return await history(current_user, db, limit, offset)


@router.get("/session-info", response_model=SessionInfoResponse)
async def session_info(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    request: Request,
):
    result = db.execute(
        select(func.count(RecommendationHistory.id)).where(RecommendationHistory.user_id == current_user.id)
    )
    history_count = int(result.scalar_one() or 0)

    # The authentication dependency has already validated the token. Decode only its expiry
    # here so the frontend can display the actual session expiration time.
    from app.auth import decode_token
    from datetime import datetime, timezone
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else ""
    payload = decode_token(token)
    token_expires_at = datetime.fromtimestamp(float(payload["exp"]), tz=timezone.utc)

    return SessionInfoResponse(user=current_user, token_expires_at=token_expires_at, history_count=history_count)


@router.get("/session-data")
async def session_data(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    result = db.execute(
        select(RecommendationHistory)
        .where(RecommendationHistory.user_id == current_user.id)
        .order_by(RecommendationHistory.created_at.desc())
        .limit(5)
    )
    records = result.scalars().all()
    return {
        "user_id": current_user.id,
        "logged_in": True,
        "recent_planners": [record.planner_type for record in records],
        "recent_recommendations": [json.loads(record.response_json) for record in records],
    }
