"""Report Generator — schema-validated report; formats, does not research."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.schemas.evidence import Finding
from src.schemas.report import (
    REPORT_JSON_SCHEMA,
    CompetitorAnalysis,
    FinalReport,
    MatrixCell,
    Recommendation,
)
from src.state.research_state import ResearchState

logger = logging.getLogger(__name__)


def generate_report(client: LLMClient, state: ResearchState) -> FinalReport:
    state.stage = "report"
    syn = state.synthesis

    def as_finding(obj: dict | None) -> Finding | None:
        if not obj:
            return None
        return Finding(**obj)

    market = as_finding(syn.get("market_overview"))
    trends = [Finding(**t) for t in syn.get("key_trends", [])]
    opps = [Finding(**t) for t in syn.get("opportunities", [])]
    risks = [Finding(**t) for t in syn.get("risks", [])]
    recs = [
        Recommendation(
            statement=r["statement"],
            motivating_evidence_ids=r.get("motivating_evidence_ids", []),
        )
        for r in syn.get("recommendations", [])
    ]

    matrix = [MatrixCell(**c) for c in state.comparison_matrix]

    gaps = list(state.limitations)
    for d in state.defect_list:
        if d.get("type") in {"coverage_gap", "contradiction", "unsupported_claim"}:
            gaps.append(f"QC: {d.get('detail')}")
    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq_gaps = []
    for g in gaps:
        if g not in seen:
            seen.add(g)
            uniq_gaps.append(g)
    if not uniq_gaps:
        uniq_gaps = [
            "Within the local corpus, residual uncertainty remains on unsourced enterprise commercial terms."
        ]

    objective = ""
    assumptions: list[str] = []
    if state.scope:
        objective = (
            f"{state.scope.category} | segment={state.scope.segment} | "
            f"geo={state.scope.geography} | horizon={state.scope.time_horizon}"
        )
        assumptions = list(state.scope.assumptions)
    if state.plan:
        objective = state.plan.research_objective + f" ({objective})"

    # Executive summary written last via model, constrained
    body_statements = []
    if market:
        body_statements.append(market.statement)
    body_statements.extend(t.statement for t in trends)
    body_statements.extend(o.statement for o in opps)
    body_statements.extend(r.statement for r in risks)

    system = load_prompt("report")
    user = (
        "Write executive_summary and confidence fields from THESE findings only:\n"
        + "\n".join(f"- {s}" for s in body_statements[:30])
        + "\nAlso list limitations_and_gaps incorporating:\n"
        + "\n".join(f"- {g}" for g in uniq_gaps[:20])
    )
    data = client.chat_json(
        stage="report",
        system=system,
        user=user,
        json_schema=REPORT_JSON_SCHEMA,
        schema_name="report_fields",
    )
    data.pop("_validation_defect", None)

    exec_sum = data.get("executive_summary", "")
    # Soft check: flag claims in summary not substring-overlapping body
    for sentence in exec_sum.split("."):
        s = sentence.strip()
        if len(s) < 40:
            continue
        if not any(s[:30].lower() in b.lower() or b[:30].lower() in s.lower() for b in body_statements):
            # don't fail — note limitation
            uniq_gaps.append(
                f"Executive summary sentence may lack direct body overlap: {s[:100]}"
            )
            break

    # Prefer synthesised sections over re-parsed duplicates from schema helper fields
    if not market and data.get("market_overview_statement"):
        market = Finding(
            statement=data["market_overview_statement"],
            claim_type=data.get("market_overview_claim_type", "inference"),
            evidence_ids=data.get("market_overview_evidence_ids", []),
            confidence=data.get("market_overview_confidence", "medium"),
        )

    report = FinalReport(
        report_id=f"rpt_{uuid4().hex[:10]}",
        generated_at=datetime.now(timezone.utc).isoformat(),
        model_versions=dict(state.model_versions),
        run_cost=round(state.usage_cost_usd, 6),
        incomplete=state.incomplete,
        research_objective=objective,
        assumptions=assumptions,
        executive_summary=exec_sum,
        market_overview=market,
        key_trends=trends or [Finding(**t) for t in data.get("key_trends", [])],
        competitor_analysis=CompetitorAnalysis(matrix=matrix, narratives={}),
        opportunities=opps or [Finding(**t) for t in data.get("opportunities", [])],
        risks=risks or [Finding(**t) for t in data.get("risks", [])],
        evidence_appendix=list(state.evidence),
        recommendations=recs
        or [
            Recommendation(
                statement=r["statement"],
                motivating_evidence_ids=r.get("motivating_evidence_ids", []),
            )
            for r in data.get("recommendations", [])
        ],
        confidence_level=data.get("confidence_level", "medium"),
        confidence_rationale=data.get("confidence_rationale", ""),
        limitations_and_gaps=data.get("limitations_and_gaps") or uniq_gaps,
        sources=sorted(
            {
                e.source_detail or e.source_ref
                for e in state.evidence
                if e.source_detail or e.source_ref
            }
        ),
        metadata={
            "run_id": state.run_id,
            "tool_call_count": state.tool_call_count,
            "iterations": state.iteration,
            "incomplete_reason": state.incomplete_reason,
        },
    )
    # Validate via pydantic (already)
    state.draft_report = report
    state.model_versions["report"] = client.settings.model_for("report")
    state.log_event("report", {"report_id": report.report_id, "incomplete": report.incomplete})
    logger.info("report_id=%s incomplete=%s", report.report_id, report.incomplete)
    return report
