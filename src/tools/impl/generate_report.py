from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from src.schemas.evidence import Finding
from src.schemas.report import CompetitorAnalysis, FinalReport, MatrixCell, Recommendation

if TYPE_CHECKING:
    from src.state.research_state import ResearchState


def handle(
    run_id: str,
    sections: list[str] | None = None,
    state: "ResearchState | None" = None,
    **_: Any,
) -> dict[str, Any]:
    if state is None:
        return {"ok": False, "error": "no_state", "message": "Research state required"}

    # Assemble a structural draft from state; synthesis agent may enrich later
    facts = [e for e in state.evidence if e.claim_type == "fact"]
    overview = None
    if facts:
        overview = Finding(
            statement=facts[0].claim,
            claim_type="fact",
            evidence_ids=[facts[0].evidence_id],
            confidence=facts[0].confidence,
        )

    matrix_cells: list[MatrixCell] = []
    if state.comparison_matrix:
        for cell in state.comparison_matrix:
            matrix_cells.append(MatrixCell(**cell))

    gaps = list(state.limitations)
    unanswered = [qid for qid, st in state.question_status.items() if st == "open"]
    for qid in unanswered:
        gaps.append(f"Sub-question {qid} remains open / not established from available evidence.")
    if not gaps:
        gaps.append(
            "Coverage appears complete relative to the plan within the local corpus; "
            "external market truth was not independently audited."
        )

    report = FinalReport(
        report_id=f"rpt_{uuid4().hex[:10]}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_versions=dict(state.model_versions),
        run_cost=state.usage_cost_usd,
        incomplete=state.incomplete,
        research_objective=state.scope.research_objective
        if hasattr(state.scope, "research_objective")
        else (state.scope.category if state.scope else ""),
        assumptions=list(state.scope.assumptions) if state.scope else [],
        executive_summary="",  # filled last by report generator
        market_overview=overview,
        key_trends=[
            Finding(
                statement=e.claim,
                claim_type=e.claim_type,
                evidence_ids=[e.evidence_id],
                confidence=e.confidence,
            )
            for e in state.evidence
            if "trend" in e.claim.lower() or e.claim_type == "inference"
        ][:5],
        competitor_analysis=CompetitorAnalysis(matrix=matrix_cells, narratives={}),
        opportunities=[
            Finding(
                statement=e.claim,
                claim_type=e.claim_type if e.claim_type != "fact" else "inference",
                evidence_ids=[e.evidence_id],
                confidence=e.confidence,
            )
            for e in state.evidence
            if e.claim_type in ("inference", "recommendation")
        ][:5],
        risks=[
            Finding(
                statement=e.claim,
                claim_type=e.claim_type,
                evidence_ids=[e.evidence_id],
                confidence=e.confidence,
            )
            for e in state.evidence
            if "risk" in e.claim.lower() or e.claim_type == "uncertainty"
        ][:5],
        evidence_appendix=list(state.evidence),
        recommendations=[
            Recommendation(
                statement=e.claim,
                motivating_evidence_ids=[e.evidence_id],
            )
            for e in state.evidence
            if e.claim_type == "recommendation"
        ],
        confidence_level="medium",
        confidence_rationale="Draft assembled from evidence store; pending QC and human approval.",
        limitations_and_gaps=gaps,
        sources=sorted({e.source_detail or e.source_ref for e in state.evidence if e.source_detail or e.source_ref}),
        metadata={"run_id": run_id, "tool_calls": state.tool_call_count},
    )
    state.draft_report = report
    return {"ok": True, "report_id": report.report_id, "incomplete": report.incomplete}
