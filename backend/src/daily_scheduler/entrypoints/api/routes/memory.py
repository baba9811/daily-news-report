"""Memory API routes — hierarchical tree, keyword search, file read."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from daily_scheduler.database import get_db
from daily_scheduler.infrastructure.dependencies import get_memory_store_for_request

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/tree")
def get_tree(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the hierarchical memory tree (sector / date / strategy / patterns / lessons)."""
    store = get_memory_store_for_request(db)
    return store.tree.load()


@router.get("/search")
def search(
    q: str = "",
    limit: int = 20,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Keyword search across memory nodes via FTS5."""
    store = get_memory_store_for_request(db)
    results = store.query_keyword(q, limit=limit) if q else []
    return {
        "items": [
            {
                "id": node.id,
                "summary": node.summary,
                "symbol": node.symbol,
                "sector": node.sector,
                "date": node.date.isoformat(),
                "outcome": node.outcome,
                "kind": node.kind.value,
            }
            for node in results
        ],
    }


@router.get("/file")
def read_file(path: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return the raw markdown content of a memory file by relative path."""
    if ".." in path:
        raise HTTPException(status_code=404, detail="file not found")
    store = get_memory_store_for_request(db)
    target = store.markdown.root / path
    if not target.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return {"path": path, "content": target.read_text(encoding="utf-8")}
