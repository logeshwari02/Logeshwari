from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes.auth import compat_router as auth_compat_router
from app.routes.auth import router as auth_router
from app.routes.history import router as history_router
from app.routes.health import router as health_router
from app.routes.planners import compat_router as planner_compat_router
from app.routes.planners import router as planner_router
from app.services.gemini import close_gemini_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
    await close_gemini_service()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="FastAPI backend for PocketSmart AI budget-aware recommendations.",
    debug=settings.debug,
    lifespan=lifespan,
)

origins = settings.get_cors_origins() or ["http://localhost:3000", "http://localhost:5173"]
allow_credentials = "*" not in origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(auth_compat_router)
app.include_router(planner_router)
app.include_router(planner_compat_router)
app.include_router(history_router)


@app.get("/", tags=["System"])
async def root():
    return {
        "name": settings.app_name,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
