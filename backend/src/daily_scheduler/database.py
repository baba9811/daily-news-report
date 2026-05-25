"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from daily_scheduler.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


def get_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine."""
    url = database_url or get_settings().database_url
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        from daily_scheduler.config import PROJECT_ROOT

        relative_path = url.replace("sqlite:///", "")
        url = f"sqlite:///{PROJECT_ROOT / relative_path}"
    return create_engine(url, echo=False, connect_args={"check_same_thread": False})


def get_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    """Create a session factory bound to an engine."""
    engine = get_engine(database_url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session with proper commit/rollback."""
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _register_memory_models() -> None:
    """Import memory ORM models so they attach to Base.metadata."""
    from daily_scheduler.infrastructure.adapters.memory import (
        models as _memory_models,  # noqa: F401
    )


_register_memory_models()


def init_database(engine: Engine) -> None:
    """Create all ORM tables + the FTS5 virtual table. Idempotent."""
    from daily_scheduler.infrastructure.adapters.memory.models import (
        create_memory_fts_table,
    )

    Base.metadata.create_all(engine)
    create_memory_fts_table(engine)
