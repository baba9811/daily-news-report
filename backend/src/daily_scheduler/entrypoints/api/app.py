"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from daily_scheduler.config import get_settings
from daily_scheduler.database import get_engine, init_database
from daily_scheduler.entrypoints.api.routes import (
    agents,
    dashboard,
    debate,
    memory,
    multica,
    performance,
    pipeline,
    reports,
    retrospective,
    webhooks,
)
from daily_scheduler.entrypoints.api.routes import settings as settings_route


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Daily Scheduler",
        description=("AI-powered daily news & trading report system"),
        version="0.1.0",
    )

    # Idempotent migration on startup — ensures multi-agent council tables
    # (agent_binding, debate, round, speech, memory_node, memory_fts) exist
    # alongside the legacy schema. Safe to run on every boot.
    cfg = get_settings()
    init_database(get_engine(cfg.database_url))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(dashboard.router)
    app.include_router(reports.router)
    app.include_router(performance.router)
    app.include_router(retrospective.router)
    app.include_router(settings_route.router)
    app.include_router(pipeline.router)
    app.include_router(debate.router)
    app.include_router(agents.router)
    app.include_router(memory.router)
    app.include_router(multica.router)
    app.include_router(webhooks.router)

    frontend_dist = Path(__file__).resolve().parents[5] / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount(
            "/",
            StaticFiles(
                directory=str(frontend_dist),
                html=True,
            ),
            name="frontend",
        )

    return app
