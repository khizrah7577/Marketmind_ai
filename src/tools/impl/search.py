from __future__ import annotations

from typing import Any

from src.tools import corpus


def handle(
    query: str,
    source_type: str = "any",
    max_results: int = 5,
    recency_window: str = "any",
    **_: Any,
) -> dict[str, Any]:
    hits = corpus.search(
        query=query,
        source_type=source_type,
        max_results=max_results,
        recency_window=recency_window or "any",
    )
    return {
        "ok": True,
        "query": query,
        "count": len(hits),
        "hits": hits,
        "message": "no matches" if not hits else "ok",
    }
