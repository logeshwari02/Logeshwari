from __future__ import annotations

import json
import secrets
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_generated_secret_key: str | None = None


class Settings(BaseSettings):
    app_name: str = "PocketSmart AI Backend"
    environment: str = "development"
    debug: bool = True

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_timeout_seconds: int = 60
    gemini_temperature: float = 0.25
    gemini_image_retries: int = 3
    gemini_request_retries: int = 2

    database_url: str = "sqlite:///./data/pocketsmart.db"
    secret_key: str = ""
    access_token_expire_minutes: int = 120

    # Keep this as a string so Pydantic Settings does not pre-parse it as JSON.
    # We accept both comma-separated values and JSON arrays for convenience.
    cors_origins: str = ""
    max_image_size_mb: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def get_cors_origins(self) -> list[str]:
        raw = self.cors_origins.strip()
        if not raw:
            return []

        # Also accept a JSON list such as ["http://localhost:3000", "http://localhost:5173"]
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except json.JSONDecodeError:
                pass

        # Default/documented form: comma-separated origins.
        return [item.strip() for item in raw.split(",") if item.strip()]

    def ensure_secret_key(self) -> str:
        global _generated_secret_key
        if self.secret_key.strip():
            return self.secret_key
        # Development-only fallback. It is generated once per server process so a token
        # remains verifiable during that process. Set SECRET_KEY in .env for persistence.
        if _generated_secret_key is None:
            _generated_secret_key = secrets.token_urlsafe(48)
        return _generated_secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
