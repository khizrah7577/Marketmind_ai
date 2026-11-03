"""Curated local corpus index for search_information / retrieve_document."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import CORPUS_DIR


@lru_cache
def load_index() -> list[dict[str, Any]]:
    path = CORPUS_DIR / "index.json"
    if not path.exists():
        raise FileNotFoundError(f"Corpus index missing at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_doc_meta(document_id: str) -> dict[str, Any] | None:
    for d in load_index():
        if d["id"] == document_id:
            return d
    return None


def read_document_text(document_id: str) -> str | None:
    meta = get_doc_meta(document_id)
    if not meta:
        return None
    path = CORPUS_DIR / meta["path"]
    if not path.exists():
        return None
    # Reject path traversal attempts — only allow indexed basenames
    if Path(meta["path"]).name != meta["path"]:
        return None
    return path.read_text(encoding="utf-8")


def search(
    query: str,
    source_type: str = "any",
    max_results: int = 5,
    recency_window: str = "any",
) -> list[dict[str, Any]]:
    tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9_]+", query) if len(t) > 2]
    hits: list[tuple[int, dict[str, Any]]] = []
    for doc in load_index():
        if source_type != "any" and doc.get("source_type") != source_type:
            continue
        text = (doc.get("snippet", "") + " " + " ".join(doc.get("tags") or [])).lower()
        vendor = (doc.get("vendor") or "").lower()
        title = doc.get("title", "").lower()
        blob = f"{title} {vendor} {text} {doc['id']}"
        # Prefer full text match weight
        full = read_document_text(doc["id"]) or ""
        blob = blob + " " + full.lower()
        score = sum(1 for t in tokens if t in blob)
        if score > 0 or not tokens:
            hits.append((score, doc))
    hits.sort(key=lambda x: (-x[0], x[1]["id"]))
    results = []
    for score, doc in hits[:max_results]:
        results.append(
            {
                "id": doc["id"],
                "title": doc["title"],
                "source_identifier": doc["id"],
                "source_type": doc["source_type"],
                "date": doc.get("date"),
                "credibility": doc.get("credibility", "unknown"),
                "vendor": doc.get("vendor"),
                "snippet": doc.get("snippet", "")[:280],
                "score": score,
            }
        )
    return results
