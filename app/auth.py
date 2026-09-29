from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4
import base64
import hashlib
import hmac
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import RevokedToken, User

settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def _pwdlib_hash(password: str) -> str | None:
    try:
        from pwdlib import PasswordHash
        return PasswordHash.recommended().hash(password)
    except ImportError:
        return None


def _pwdlib_verify(password: str, hashed_password: str) -> bool | None:
    if not hashed_password.startswith(("$argon2", "$scrypt", "$bcrypt")):
        return None
    try:
        from pwdlib import PasswordHash
        return PasswordHash.recommended().verify(password, hashed_password)
    except ImportError:
        return None


def hash_password(password: str) -> str:
    modern_hash = _pwdlib_hash(password)
    if modern_hash is not None:
        return modern_hash

    # Test/runtime fallback only when pwdlib is unavailable. It still uses a salted,
    # deliberately expensive password-derived key rather than plaintext storage.
    iterations = 310_000
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$pocket$pbkdf2-sha256$%d$%s$%s" % (
        iterations,
        base64.urlsafe_b64encode(salt).decode().rstrip("="),
        base64.urlsafe_b64encode(digest).decode().rstrip("="),
    )


def verify_password(password: str, hashed_password: str) -> bool:
    modern_result = _pwdlib_verify(password, hashed_password)
    if modern_result is not None:
        return modern_result

    try:
        parts = hashed_password.split("$")
        if len(parts) != 6 or parts[1] != "pocket" or parts[2] != "pbkdf2-sha256":
            return False
        iterations = int(parts[3])
        salt = base64.urlsafe_b64decode(parts[4] + "=" * (-len(parts[4]) % 4))
        expected = base64.urlsafe_b64decode(parts[5] + "=" * (-len(parts[5]) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int) -> tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    jti = str(uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": datetime.now(timezone.utc),
        "exp": expires_at,
        "type": "access",
    }
    token = jwt.encode(payload, settings.ensure_secret_key(), algorithm="HS256")
    return token, expires_at


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.ensure_secret_key(), algorithms=["HS256"])
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access" or not payload.get("sub") or not payload.get("jti"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


def ensure_token_not_revoked(payload: dict, db: Session) -> None:
    result = db.execute(
        select(RevokedToken.id).where(RevokedToken.jti == payload["jti"])
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has been logged out",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    payload = decode_token(token)
    ensure_token_not_revoked(payload, db)

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid token subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def revoke_token(token: str, db: Session) -> datetime:
    payload = decode_token(token)
    ensure_token_not_revoked(payload, db)
    exp = payload.get("exp")
    if not isinstance(exp, (int, float)):
        raise HTTPException(status_code=401, detail="Invalid token expiry")
    expires_at = datetime.fromtimestamp(exp, tz=timezone.utc).replace(tzinfo=None)
    db.add(RevokedToken(jti=payload["jti"], expires_at=expires_at))
    # Clean up old entries while we're here.
    db.execute(delete(RevokedToken).where(RevokedToken.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)))
    db.commit()
    return expires_at
