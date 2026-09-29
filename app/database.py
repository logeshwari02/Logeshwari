from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

if settings.database_url.startswith("sqlite"):
    Path("data").mkdir(parents=True, exist_ok=True)

# Normalize the default async URL from older PocketSmart copies to standard SQLite.
database_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite+pysqlite")
engine = create_engine(
    database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def get_db():
    with SessionLocal() as session:
        yield session


def init_db() -> None:
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
