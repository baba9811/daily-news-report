"""ORM model for memory_node and FTS5 virtual table creator."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column

from daily_scheduler.database import Base


class MemoryNodeModel(Base):
    """SQLAlchemy model — metadata row for a memory file."""

    __tablename__ = "memory_node"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    file_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    symbol: Mapped[str | None] = mapped_column(String, nullable=True)
    sector: Mapped[str | None] = mapped_column(String, nullable=True)
    strategy: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    date: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    debate_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


def create_memory_fts_table(engine: Engine) -> None:
    """Create the memory_fts FTS5 virtual table with trigram tokenizer.

    Trigram tokenizer is required for Korean / CJK partial matching.
    Idempotent — uses IF NOT EXISTS.
    """
    with engine.begin() as conn:
        conn.execute(
            text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                body,
                summary,
                symbol UNINDEXED,
                sector UNINDEXED,
                tokenize='trigram'
            )
        """)
        )
