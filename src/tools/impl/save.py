from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.schemas.evidence import EvidenceRecord

if TYPE_CHECKING:
    from src.state.research_state import ResearchState


def handle(
    question_id: str,
    claim: str,
    claim_type: str,
    source_ref: str,
    confidence: str,
    state: "ResearchState | None" = None,
    **_: Any,
) -> dict[str, Any]:
    if state is None:
        return {"ok": False, "error": "no_state", "message": "Research state required"}

    # Structural defence: source_ref must resolve to a prior tool result
    prior = state.tool_results_by_id.get(source_ref)
    if prior is None:
        state.rejections.append(
            {
                "reason": "unresolvable_source_ref",
                "source_ref": source_ref,
                "claim": claim,
            }
        )
        return {
            "ok": False,
            "error": "unresolvable_source_ref",
            "message": (
                f"source_ref '{source_ref}' does not resolve to a prior tool result. "
                "Fabricated citations are rejected."
            ),
        }

    kind = "search_result"
    detail = ""
    if isinstance(prior.get("result"), dict):
        r = prior["result"]
        if r.get("provenance", {}).get("kind") == "retrieved_document":
            kind = "retrieved_document"
            detail = r.get("title") or r.get("document_id") or ""
        elif r.get("provenance", {}).get("kind") == "calculation":
            kind = "calculation"
            detail = r.get("formula", "calculation")
        elif "hits" in r:
            kind = "search_result"
            detail = f"search:{r.get('query', '')}"
        if r.get("injection_suspect"):
            state.log_event(
                "injection_flag",
                {"source_ref": source_ref, "note": "content contained instruction-like text"},
            )

    record = EvidenceRecord(
        question_id=question_id,
        claim=claim,
        claim_type=claim_type,  # type: ignore[arg-type]
        source_ref=source_ref,
        source_kind=kind,  # type: ignore[arg-type]
        source_detail=detail,
        confidence=confidence,  # type: ignore[arg-type]
        credibility="medium",
        analyst_notes="saved via save_research tool",
    )
    state.evidence.append(record)
    if question_id in state.question_status:
        state.question_status[question_id] = "answered"
    return {
        "ok": True,
        "evidence_id": record.evidence_id,
        "record": record.model_dump(),
    }
