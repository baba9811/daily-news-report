"""JSONTreeIndex — derives a hierarchical tree.json from memory_node rows."""

from __future__ import annotations

import json
import os
import tempfile
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from daily_scheduler.constants import MEMORY_TREE_MAX_BYTES
from daily_scheduler.infrastructure.adapters.memory.models import MemoryNodeModel


class JSONTreeIndex:
    """Build and persist tree.json from memory_node rows."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        tree_path: Path,
        max_bytes: int = MEMORY_TREE_MAX_BYTES,
    ) -> None:
        self._session_factory = session_factory
        self._tree_path = tree_path
        self._max_bytes = max_bytes

    @property
    def tree_path(self) -> Path:
        """Filesystem path where the tree.json is persisted."""
        return self._tree_path

    def rebuild(self) -> None:
        """Rebuild the JSON tree from current memory_node rows."""
        with self._session_factory() as session:
            rows = session.query(MemoryNodeModel).all()
        tree = self._build_tree(rows)
        self._write_atomic(tree)

    def load(self) -> dict[str, Any]:
        """Load the tree from disk, returning an empty root if absent."""
        if not self._tree_path.exists():
            return {"root": {"title": "memory", "children": []}}
        return json.loads(self._tree_path.read_text(encoding="utf-8"))

    def _build_tree(self, rows: list[MemoryNodeModel]) -> dict[str, Any]:
        by_sector: dict[str, dict[str, list[MemoryNodeModel]]] = {}
        by_date: dict[str, dict[str, dict[str, list[MemoryNodeModel]]]] = {}
        by_strategy: dict[str, list[MemoryNodeModel]] = defaultdict(list)
        patterns: list[MemoryNodeModel] = []
        lessons: list[MemoryNodeModel] = []

        for r in rows:
            if r.kind == "decision":
                sector = r.sector or "uncategorized"
                symbol = r.symbol or "general"
                by_sector.setdefault(sector, {}).setdefault(symbol, []).append(r)
                y, m, d = r.date.split("-")
                by_date.setdefault(y, {}).setdefault(m, {}).setdefault(d, []).append(r)
                if r.strategy:
                    by_strategy[r.strategy].append(r)
            elif r.kind == "pattern":
                patterns.append(r)
            elif r.kind == "lesson":
                lessons.append(r)

        children: list[dict[str, Any]] = []

        sector_children = [
            {
                "title": sector,
                "children": [
                    {"title": symbol, "children": [self._leaf(r) for r in rs]}
                    for symbol, rs in symbols.items()
                ],
            }
            for sector, symbols in sorted(by_sector.items())
        ]
        children.append({"title": "by-sector", "children": sector_children})

        date_children = [
            {
                "title": y,
                "children": [
                    {
                        "title": m,
                        "children": [
                            {"title": d, "children": [self._leaf(r) for r in rs]}
                            for d, rs in sorted(months.items())
                        ],
                    }
                    for m, months in sorted(years.items())
                ],
            }
            for y, years in sorted(by_date.items())
        ]
        children.append({"title": "by-date", "children": date_children})

        strat_children = [
            {"title": s, "children": [self._leaf(r) for r in rs]}
            for s, rs in sorted(by_strategy.items())
        ]
        children.append({"title": "by-strategy", "children": strat_children})

        children.append({"title": "patterns", "children": [self._leaf(r) for r in patterns]})
        children.append({"title": "lessons", "children": [self._leaf(r) for r in lessons]})

        return {"root": {"title": "memory", "children": children}}

    @staticmethod
    def _leaf(r: MemoryNodeModel) -> dict[str, Any]:
        return {
            "id": r.id,
            "title": r.symbol or r.date,
            "summary": r.summary,
            "file_path": r.file_path,
            "outcome": r.outcome,
            "date": r.date,
            "kind": r.kind,
        }

    def _write_atomic(self, tree: dict[str, Any]) -> None:
        data = self._serialize_with_cap(tree)
        self._tree_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=self._tree_path.parent, prefix=".tree_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(data)
            os.replace(tmp_path, self._tree_path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def _serialize_with_cap(self, tree: dict[str, Any]) -> str:
        data = json.dumps(tree, ensure_ascii=False, indent=2)
        if len(data.encode("utf-8")) <= self._max_bytes:
            return data
        cap_summary = 60
        while cap_summary > 10:
            self._truncate_summaries(tree, cap_summary)
            data = json.dumps(tree, ensure_ascii=False, indent=2)
            if len(data.encode("utf-8")) <= self._max_bytes:
                return data
            cap_summary -= 10
        # Summary truncation alone is insufficient — prune leaves (and empty
        # intermediate containers below the top-5 branches) until under budget.
        max_leaves = self._count_leaves(tree)
        while max_leaves >= 0:
            pruned = json.loads(json.dumps(tree))
            self._prune_leaves(pruned, [max_leaves])
            self._prune_empty_intermediates(pruned)
            data = json.dumps(pruned, ensure_ascii=False, indent=2)
            if len(data.encode("utf-8")) <= self._max_bytes:
                return data
            if max_leaves == 0:
                break
            max_leaves = max(0, max_leaves - max(1, max_leaves // 4))
        return data

    def _truncate_summaries(self, node: dict[str, Any], cap: int) -> None:
        if isinstance(node.get("summary"), str) and len(node["summary"]) > cap:
            node["summary"] = node["summary"][:cap] + "…"
        for child in node.get("children", []) or []:
            self._truncate_summaries(child, cap)
        if "root" in node:
            self._truncate_summaries(node["root"], cap)

    def _count_leaves(self, node: dict[str, Any]) -> int:
        if "root" in node:
            return self._count_leaves(node["root"])
        children = node.get("children") or []
        if not children and "file_path" in node:
            return 1
        return sum(self._count_leaves(c) for c in children)

    def _prune_leaves(self, node: dict[str, Any], budget: list[int]) -> None:
        """Walk tree depth-first, keeping leaves only while budget > 0."""
        if "root" in node:
            self._prune_leaves(node["root"], budget)
            return
        children = node.get("children") or []
        if children and "file_path" in children[0]:
            # This node's children are leaves.
            if budget[0] <= 0:
                node["children"] = []
                return
            keep = min(len(children), budget[0])
            node["children"] = children[:keep]
            budget[0] -= keep
            return
        for child in children:
            self._prune_leaves(child, budget)

    def _prune_empty_intermediates(self, tree: dict[str, Any]) -> None:
        """Drop intermediate container nodes that have no leaves under them.

        Preserves the five top-level branches (by-sector, by-date, by-strategy,
        patterns, lessons) even when empty, but trims deeper empties.
        """
        root = tree.get("root") or tree
        for branch in root.get("children", []) or []:
            branch["children"] = [c for c in (branch.get("children") or []) if self._has_leaves(c)]
            for child in branch["children"]:
                self._compact(child)

    def _compact(self, node: dict[str, Any]) -> None:
        children = node.get("children") or []
        if children and "file_path" in children[0]:
            return
        node["children"] = [c for c in children if self._has_leaves(c)]
        for child in node["children"]:
            self._compact(child)

    def _has_leaves(self, node: dict[str, Any]) -> bool:
        if "file_path" in node:
            return True
        for child in node.get("children", []) or []:
            if self._has_leaves(child):
                return True
        return False
