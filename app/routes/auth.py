from __future__ import annotations

from typing import Annotated
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, revoke_token, verify_password, oauth2_scheme
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _find_user(email: str, db: Session) -> User | None:
    result = db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    email = str(payload.email).lower()
    existing = _find_user(email, db)
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    db.refresh(user)
    return user


def _login(email: str, password: str, db: Session) -> TokenResponse:
    user = _find_user(email, db)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is inactive")

    token, expires_at = create_access_token(user.id)
    expires_in = max(1, int(expires_at.timestamp() - time.time()))
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserPublic.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    return _login(str(payload.email), payload.password, db)


@router.post("/token", response_model=TokenResponse)
def token(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[Session, Depends(get_db)]):
    return _login(form.username, form.password, db)


@router.post("/logout")
def logout(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    revoke_token(token, db)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserPublic)
def me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user


# Compatibility aliases matching the original project specification.
compat_router = APIRouter(tags=["Authentication"])


@compat_router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def register_alias(payload: RegisterRequest, db: Annotated[Session, Depends(get_db)]):
    return register(payload, db)


@compat_router.post("/login", response_model=TokenResponse, include_in_schema=False)
def login_alias(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    return login(payload, db)


@compat_router.post("/logout", include_in_schema=False)
def logout_alias(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    return logout(token, db)
