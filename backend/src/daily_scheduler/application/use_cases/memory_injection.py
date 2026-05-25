"""Memory auto-injection — picks top-K relevant MemoryNodes for a debate."""

from __future__ import annotations

from daily_scheduler.constants import MEMORY_AUTO_INJECT_TOP_K
from daily_scheduler.domain.entities.memory_node import MemoryNode
from daily_scheduler.domain.ports.memory_store import MemoryQuery, MemoryStorePort


def build_memory_context(
    *,
    store: MemoryStorePort,
    tickers: list[str],
    pipeline: str,
    regime: str,
    top_k: int = MEMORY_AUTO_INJECT_TOP_K,
) -> list[MemoryNode]:
    """Return up to ``top_k`` memory nodes likely relevant to this debate.

    Strategy:
    1. Metadata pull: for the first 10 tickers, fetch up to 2 prior nodes each.
    2. Tree traversal: surface nodes under the current regime/pipeline branch.
    3. Dedup by ``MemoryNode.id`` while preserving first-seen order.
    4. Truncate to ``top_k``.
    """
    by_meta: list[MemoryNode] = []
    for ticker in tickers[:10]:
        by_meta.extend(store.query_metadata(MemoryQuery(symbol=ticker, limit=2)))

    by_tree = store.traverse_tree(f"{regime} {pipeline}", max_depth=3)

    seen: set[str] = set()
    out: list[MemoryNode] = []
    for node in by_meta + by_tree:
        if node.id in seen:
            continue
        seen.add(node.id)
        out.append(node)
        if len(out) >= top_k:
            break
    return out
