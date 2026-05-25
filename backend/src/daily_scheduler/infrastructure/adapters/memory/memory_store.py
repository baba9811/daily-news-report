"""MemoryStore — atomic composite over markdown + JSON tree + FTS5."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode
from daily_scheduler.domain.ports.memory_store import MemoryQuery, MemoryStorePort
from daily_scheduler.infrastructure.adapters.memory.json_tree_index import (
    JSONTreeIndex,
)
from daily_scheduler.infrastructure.adapters.memory.markdown_store import (
    MarkdownMemoryStore,
)
from daily_scheduler.infrastructure.adapters.memory.models import MemoryNodeModel
from daily_scheduler.infrastructure.adapters.memory.sqlite_fts5_search import (
    SQLiteFTS5Search,
)


class MemoryStore(MemoryStorePort):
    """Atomic ingest across markdown, FTS5, and DB; reads from DB."""

    def __init__(
        self,
        markdown: MarkdownMemoryStore,
        tree: JSONTreeIndex,
        fts: SQLiteFTS5Search,
        session_factory: Callable[[], Session],
    ) -> None:
        self._md = markdown
        self._tree = tree
        self._fts = fts
        self._sf = session_factory

    @property
    def markdown(self) -> MarkdownMemoryStore:
        """Expose the underlying markdown store for read-only callers."""
        return self._md

    @property
    def tree(self) -> JSONTreeIndex:
        """Expose the underlying JSON tree index for read-only callers."""
        return self._tree

    def ingest(self, node: MemoryNode) -> None:
        rel = node.relative_path()
        file_target = self._md.root / rel
        wrote_file = False
        wrote_db = False
        try:
            self._md.write(node)
            wrote_file = True
            now = datetime.now()
            with self._sf() as session:
                row = MemoryNodeModel(
                    id=node.id,
                    file_path=rel,
                    kind=node.kind.value,
                    symbol=node.symbol,
                    sector=node.sector,
                    strategy=node.strategy,
                    outcome=node.outcome,
                    date=node.date.isoformat(),
                    summary=node.summary,
                    debate_id=node.debate_id,
                    created_at=now,
                    updated_at=now,
                )
                session.merge(row)
                session.commit()
                wrote_db = True
                self._fts.index(row, body=node.body)
            self._tree.rebuild()
        except Exception:
            if wrote_db:
                with self._sf() as session:
                    session.execute(
                        sql_text("DELETE FROM memory_node WHERE id = :id"),
                        {"id": node.id},
                    )
                    session.commit()
            if wrote_file and file_target.exists():
                file_target.unlink()
            raise

    def update_outcome(self, memory_id: str, outcome: str) -> None:
        with self._sf() as session:
            row = session.get(MemoryNodeModel, memory_id)
            if row is None:
                raise KeyError(memory_id)
            file_path = row.file_path
            row.outcome = outcome
            row.updated_at = datetime.now()
            session.commit()
        self._md.update_outcome(file_path, outcome)
        self._tree.rebuild()

    def query_metadata(self, q: MemoryQuery) -> list[MemoryNode]:
        with self._sf() as session:
            qry = session.query(MemoryNodeModel)
            if q.symbol:
                qry = qry.filter(MemoryNodeModel.symbol == q.symbol)
            if q.sector:
                qry = qry.filter(MemoryNodeModel.sector == q.sector)
            if q.strategy:
                qry = qry.filter(MemoryNodeModel.strategy == q.strategy)
            if q.outcome:
                qry = qry.filter(MemoryNodeModel.outcome == q.outcome)
            if q.date_from:
                qry = qry.filter(MemoryNodeModel.date >= q.date_from.isoformat())
            if q.date_to:
                qry = qry.filter(MemoryNodeModel.date <= q.date_to.isoformat())
            rows = qry.order_by(MemoryNodeModel.date.desc()).limit(q.limit).all()
        return [self._row_to_node(r) for r in rows]

    def query_keyword(self, text: str, limit: int = 10) -> list[MemoryNode]:
        hits = self._fts.search(text, limit=limit)
        if not hits:
            return []
        ids = [h.id for h in hits]
        with self._sf() as session:
            rows_by_id = {
                r.id: r
                for r in session.query(MemoryNodeModel).filter(MemoryNodeModel.id.in_(ids)).all()
            }
        return [self._row_to_node(rows_by_id[i]) for i in ids if i in rows_by_id]

    def traverse_tree(self, query: str, max_depth: int = 3) -> list[MemoryNode]:
        # Default implementation returns most recent decisions.
        # An LLM-driven traversal lives in the use case layer.
        return self.query_metadata(MemoryQuery(limit=10))

    def _row_to_node(self, r: MemoryNodeModel) -> MemoryNode:
        body = ""
        try:
            loaded = self._md.read(r.file_path)
            body = loaded.body
        except FileNotFoundError:
            pass
        return MemoryNode(
            id=r.id,
            kind=MemoryKind(r.kind),
            date=date_type.fromisoformat(r.date),
            summary=r.summary,
            body=body,
            symbol=r.symbol,
            sector=r.sector,
            strategy=r.strategy,
            outcome=r.outcome,
            debate_id=r.debate_id,
        )
