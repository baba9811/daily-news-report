"""Extract the final report JSON envelope from a squad leader's comment.

The Multica squad leader is instructed to post the final daily report as a
single fenced ```json block. This helper pulls the last parseable JSON object
out of a free-text comment so the pipeline can hand it to
``parse_report_content``.
"""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_report_json(text: str) -> str | None:
    """Return the last fenced JSON object that parses, else a bare top-level object.

    Returns None when no parseable JSON object is present.
    """
    for block in reversed(_FENCE.findall(text or "")):
        if _parses(block):
            return block
    # Fallback: a bare top-level object spanning the first '{' to the last '}'.
    start, end = (text or "").find("{"), (text or "").rfind("}")
    if 0 <= start < end:
        snippet = text[start : end + 1]
        if _parses(snippet):
            return snippet
    return None


def _parses(candidate: str) -> bool:
    try:
        json.loads(candidate)
    except (ValueError, TypeError):
        return False
    return True
