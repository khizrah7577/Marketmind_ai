"""Save / resume run artefacts under runs/<run_id>/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.config import RUNS_DIR
from src.state.research_state import ResearchState


def run_dir(run_id: str) -> Path:
    d = RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def save_run(state: ResearchState, usage_summary: dict[str, Any] | None = None) -> Path:
    d = run_dir(state.run_id)
    save_json(d / "state.json", state.to_dict())
    if state.plan:
        save_json(d / "plan.json", state.plan.model_dump())
    save_json(d / "tool_log.json", state.tool_history)
    save_json(d / "evidence.json", [e.model_dump() for e in state.evidence])
    if state.qc_verdict:
        save_json(d / "qc_verdict.json", state.qc_verdict)
    if state.draft_report:
        save_json(d / "report.json", state.draft_report.model_dump())
    if usage_summary:
        save_json(d / "usage.json", usage_summary)
    save_json(d / "events.json", state.event_log)
    return d


def load_run(run_id: str) -> ResearchState:
    path = RUNS_DIR / run_id / "state.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return ResearchState.from_dict(data)


def write_markdown_report(state: ResearchState, path: Path | None = None) -> Path:
    assert state.draft_report is not None
    r = state.draft_report
    d = run_dir(state.run_id)
    path = path or (d / "report.md")
    lines: list[str] = []
    lines.append(f"# MarketMind AI Report — {r.report_id}")
    lines.append("")
    if r.incomplete:
        lines.append(f"> **INCOMPLETE RUN**: {state.incomplete_reason}")
        lines.append("")
    lines.append(f"**Objective:** {r.research_objective}")
    lines.append("")
    if r.assumptions:
        lines.append("## Assumptions")
        for a in r.assumptions:
            lines.append(f"- {a}")
        lines.append("")
    lines.append(f"**Overall confidence:** {r.confidence_level} — {r.confidence_rationale}")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append(r.executive_summary or "_(pending)_")
    lines.append("")
    if r.market_overview:
        lines.append("## Market Overview")
        lines.append(
            f"- [{r.market_overview.claim_type.upper()}] {r.market_overview.statement} "
            f"(evidence: {', '.join(r.market_overview.evidence_ids) or 'none'}; "
            f"confidence: {r.market_overview.confidence})"
        )
        lines.append("")
    if r.key_trends:
        lines.append("## Key Trends")
        for t in r.key_trends:
            lines.append(
                f"- [{t.claim_type.upper()}] {t.statement} "
                f"(evidence: {', '.join(t.evidence_ids) or 'none'})"
            )
        lines.append("")
    lines.append("## Competitor Analysis")
    if r.competitor_analysis.matrix:
        lines.append("| Entity | Attribute | Status | Value | Evidence |")
        lines.append("|---|---|---|---|---|")
        for c in r.competitor_analysis.matrix:
            val = c.value or "—"
            val = val.replace("|", "/")[:80]
            lines.append(
                f"| {c.entity} | {c.attribute} | {c.status} | {val} | "
                f"{', '.join(c.evidence_ids)} |"
            )
        lines.append("")
    if r.opportunities:
        lines.append("## Opportunities")
        for o in r.opportunities:
            lines.append(f"- [{o.claim_type.upper()}] {o.statement}")
        lines.append("")
    if r.risks:
        lines.append("## Risks")
        for risk in r.risks:
            lines.append(f"- [{risk.claim_type.upper()}] {risk.statement}")
        lines.append("")
    if r.recommendations:
        lines.append("## Recommendations")
        for rec in r.recommendations:
            lines.append(
                f"- {rec.statement} (motivated by: {', '.join(rec.motivating_evidence_ids)})"
            )
        lines.append("")
    lines.append("## Limitations and Gaps")
    for g in r.limitations_and_gaps:
        lines.append(f"- {g}")
    lines.append("")
    lines.append("## Evidence Appendix")
    for e in r.evidence_appendix:
        lines.append(
            f"- `{e.evidence_id}` [{e.claim_type}] {e.claim} "
            f"(source_ref={e.source_ref}; {e.source_detail})"
        )
    lines.append("")
    lines.append("## Sources")
    for s in r.sources:
        lines.append(f"- {s}")
    lines.append("")
    if r.approval:
        lines.append("## Approval")
        lines.append(
            f"- Decision: **{r.approval.decision}** by {r.approval.approver_id} "
            f"at {r.approval.timestamp}"
        )
        if r.approval.notes:
            lines.append(f"- Notes: {r.approval.notes}")
        lines.append("")
    lines.append("## Run Metadata")
    lines.append(f"- Run id: `{state.run_id}`")
    lines.append(f"- Cost (USD): {r.run_cost}")
    lines.append(f"- Models: {r.model_versions}")
    lines.append(f"- Tool calls: {state.tool_call_count}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
