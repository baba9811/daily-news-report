"""MarkdownMemoryStore — write/read MemoryNode as markdown files with YAML frontmatter."""

from __future__ import annotations

import os
import tempfile
from datetime import date as date_type
from pathlib import Path

import yaml

from daily_scheduler.domain.entities.memory_node import MemoryKind, MemoryNode

_DELIM = "---\n"


class MarkdownMemoryStore:
    """File IO for memory markdown files."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        """Root directory where markdown files are stored."""
        return self._root

    def write(self, node: MemoryNode) -> None:
        """Atomically write a MemoryNode to its computed markdown path."""
        target = self._root / node.relative_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        content = self._render(node)
        fd, tmp_path = tempfile.mkstemp(dir=target.parent, prefix=".memory_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(content)
            os.replace(tmp_path, target)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

    def read(self, relative_path: str) -> MemoryNode:
        """Read and parse a memory markdown file into a MemoryNode."""
        target = self._root / relative_path
        raw = target.read_text(encoding="utf-8")
        return self._parse(raw)

    def update_outcome(self, relative_path: str, outcome: str) -> None:
        """Rewrite a memory file with an updated outcome field."""
        node = self.read(relative_path)
        new_node = MemoryNode(
            id=node.id,
            kind=node.kind,
            date=node.date,
            summary=node.summary,
            body=node.body,
            symbol=node.symbol,
            sector=node.sector,
            strategy=node.strategy,
            outcome=outcome,
            debate_id=node.debate_id,
        )
        self.write(new_node)

    def _render(self, node: MemoryNode) -> str:
        fm = node.frontmatter()
        yaml_text = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
        return _DELIM + yaml_text + _DELIM + node.body

    def _parse(self, raw: str) -> MemoryNode:
        if not raw.startswith(_DELIM):
            raise ValueError("file is not in frontmatter format")
        rest = raw[len(_DELIM) :]
        end = rest.find("\n" + _DELIM)
        if end == -1:
            raise ValueError("frontmatter not closed")
        yaml_text = rest[:end]
        body = rest[end + len("\n" + _DELIM) :]
        fm = yaml.safe_load(yaml_text)
        d = fm["date"]
        if isinstance(d, str):
            parsed = date_type.fromisoformat(d)
        elif isinstance(d, date_type):
            parsed = d
        else:
            raise ValueError(f"bad date type: {type(d)}")
        return MemoryNode(
            id=fm["id"],
            kind=MemoryKind(fm["kind"]),
            date=parsed,
            summary=fm["summary"],
            body=body,
            symbol=fm.get("symbol"),
            sector=fm.get("sector"),
            strategy=fm.get("strategy"),
            outcome=fm.get("outcome"),
            debate_id=fm.get("debate_id"),
        )
