"""Verify database migration is idempotent and creates all expected tables.

Run after schema changes — calls ``init_database`` twice on a fresh engine,
then asserts the full set of expected tables exists. Idempotency is the
core acceptance criterion (DATA-04).

Usage:
    cd backend
    uv run python scripts/verify_migration.py              # in-memory check
    uv run python scripts/verify_migration.py /tmp/dsx.db  # file-backed check
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, inspect

# Importing the persistence + memory ORM modules registers their tables
# with ``Base.metadata`` before we call ``init_database``. The memory module
# is auto-registered by ``daily_scheduler.database`` at import time; we still
# pull in the persistence models explicitly so legacy tables (reports,
# recommendations, debate, etc.) are present on a fresh engine.
from daily_scheduler.database import init_database
from daily_scheduler.infrastructure.adapters.persistence import (  # noqa: F401
    models as _persistence_models,
)

EXPECTED_TABLES: frozenset[str] = frozenset(
    {
        # Legacy tables
        "reports",
        "recommendations",
        "price_snapshots",
        "retrospectives",
        "weekly_analyses",
        # Multi-agent council
        "memory_node",
        "memory_fts",
        "agent_binding",
        "debate",
        "round",
        "speech",
    }
)


def main(db_path: str = ":memory:") -> int:
    """Create a fresh engine, run ``init_database`` twice, assert tables exist."""
    url = "sqlite:///:memory:" if db_path == ":memory:" else f"sqlite:///{db_path}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    init_database(engine)
    init_database(engine)  # idempotency — second call must not raise
    tables = set(inspect(engine).get_table_names())
    missing = EXPECTED_TABLES - tables
    if missing:
        print(f"MISSING TABLES: {sorted(missing)}", file=sys.stderr)
        return 1
    print(f"OK — {len(tables)} tables present ({len(EXPECTED_TABLES)} required)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
