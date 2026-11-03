from __future__ import annotations

from typing import Any

from src.tools import corpus


def handle(document_id: str, section: str | None = None, **_: Any) -> dict[str, Any]:
    # Hard reject path-like or URL-like ids
    if any(x in document_id for x in ("/", "\\", ":", "..", "http")):
        return {
            "ok": False,
            "error": "invalid_document_id",
            "message": "document_id must be an indexed corpus id, not a path or URL",
        }
    meta = corpus.get_doc_meta(document_id)
    if not meta:
        return {
            "ok": False,
            "error": "unknown_document_id",
            "message": f"No document with id '{document_id}' in the corpus index",
        }
    text = corpus.read_document_text(document_id)
    if text is None:
        return {
            "ok": False,
            "error": "read_failed",
            "message": "Indexed document file missing",
        }
    body = text
    if section:
        # Soft section filter: return paragraphs containing the section keyword
        parts = [p for p in text.split("\n") if section.lower() in p.lower()]
        body = "\n".join(parts) if parts else text
    return {
        "ok": True,
        "document_id": document_id,
        "title": meta["title"],
        "source_type": meta["source_type"],
        "date": meta.get("date"),
        "credibility": meta.get("credibility", "unknown"),
        "vendor": meta.get("vendor"),
        "text": body,
        "provenance": {
            "kind": "retrieved_document",
            "id": document_id,
            "title": meta["title"],
        },
        # Flag injection-like lines for the log / analyst
        "injection_suspect": "ignore prior instructions" in body.lower()
        or "SYSTEM:" in body,
    }
