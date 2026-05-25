"""SQLiteFTS5Search — BM25-ranked keyword search using the memory_fts virtual table."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine

from daily_scheduler.infrastructure.adapters.memory.models import MemoryNodeModel


@dataclass(frozen=True, slots=True)
class FTS5Hit:
    """A single ranked hit from the memory_fts BM25 search."""

    id: str
    file_path: str
    symbol: str | None
    sector: str | None
    score: float


class SQLiteFTS5Search:
    """BM25 search over memory_fts virtual table."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._ensure_map_table()

    def _ensure_map_table(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS memory_fts_map ("
                    "  memory_id TEXT PRIMARY KEY, "
                    "  rowid INTEGER NOT NULL UNIQUE)"
                )
            )

    def index(self, row: MemoryNodeModel, body: str) -> None:
        """Insert or replace a memory row's body into the FTS5 table."""
        rowid = self._rowid_for(row.id)
        with self._engine.begin() as conn:
            conn.execute(
                text("DELETE FROM memory_fts WHERE rowid = :rid"),
                {"rid": rowid},
            )
            conn.execute(
                text(
                    "INSERT INTO memory_fts(rowid, body, summary, symbol, sector) "
                    "VALUES (:rid, :body, :summary, :symbol, :sector)"
                ),
                {
                    "rid": rowid,
                    "body": body,
                    "summary": row.summary,
                    "symbol": row.symbol or "",
                    "sector": row.sector or "",
                },
            )
            conn.execute(
                text("INSERT OR REPLACE INTO memory_fts_map(memory_id, rowid) VALUES (:mid, :rid)"),
                {"mid": row.id, "rid": rowid},
            )

    def delete(self, memory_id: str) -> None:
        """Remove a memory's entry from the FTS5 table."""
        with self._engine.begin() as conn:
            rid = conn.execute(
                text("SELECT rowid FROM memory_fts_map WHERE memory_id = :mid"),
                {"mid": memory_id},
            ).scalar_one_or_none()
            if rid is None:
                return
            conn.execute(text("DELETE FROM memory_fts WHERE rowid = :rid"), {"rid": rid})
            conn.execute(
                text("DELETE FROM memory_fts_map WHERE memory_id = :mid"),
                {"mid": memory_id},
            )

    def search(self, query: str, limit: int = 10) -> list[FTS5Hit]:
        """Return BM25-ranked hits matching the FTS5 query string."""
        if not query.strip():
            return []
        with self._engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT m.memory_id, f.symbol, f.sector, bm25(memory_fts) AS s "
                    "FROM memory_fts f "
                    "JOIN memory_fts_map m ON m.rowid = f.rowid "
                    "WHERE memory_fts MATCH :q "
                    "ORDER BY s LIMIT :lim"
                ),
                {"q": query, "lim": limit},
            ).fetchall()

            out: list[FTS5Hit] = []
            for memory_id, symbol, sector, score in rows:
                fp = conn.execute(
                    text("SELECT file_path FROM memory_node WHERE id = :mid"),
                    {"mid": memory_id},
                ).scalar_one_or_none()
                if fp is None:
                    continue
                out.append(
                    FTS5Hit(
                        id=memory_id,
                        file_path=fp,
                        symbol=symbol or None,
                        sector=sector or None,
                        score=float(score),
                    )
                )
            return out

    @staticmethod
    def _rowid_for(memory_id: str) -> int:
        return int.from_bytes(memory_id.encode()[-12:].ljust(8, b"0")[:8], "big", signed=False)
