"""Persist and load research runs into SQLite + filesystem artefacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from database import database as db
from src.state.persistence import load_run, save_run
from src.state.research_state import ResearchState


def persist_research_state(
    state: ResearchState,
    usage_summary: dict[str, Any] | None = None,
    *,
    topic: str | None = None,
    is_demo: bool = False,
) -> Path:
    path = save_run(state, usage_summary)
    approval = None
    if state.draft_report and state.draft_report.approval:
        approval = state.draft_report.approval.decision
    status = "partial" if state.incomplete else "completed"
    if approval:
        status = "approved" if approval == "approve" else approval
    conf = state.draft_report.confidence_level if state.draft_report else None
    qc_pass = None
    if state.qc_verdict is not None:
        qc_pass = bool(state.qc_verdict.get("pass"))
    tokens = 0
    cost = state.usage_cost_usd
    if usage_summary:
        tokens = int(usage_summary.get("total_tokens") or 0)
        cost = float(usage_summary.get("total_cost_usd") or cost)
    db.upsert_run(
        {
            "run_id": state.run_id,
            "topic": topic or state.raw_request[:200],
            "status": status,
            "evidence_count": len(state.evidence),
            "tool_calls": state.tool_call_count,
            "iterations": state.iteration,
            "cost_usd": cost,
            "tokens": tokens,
            "confidence": conf,
            "qc_pass": qc_pass,
            "approval": approval,
            "incomplete": state.incomplete,
            "is_demo": is_demo,
            "state_path": str(path / "state.json"),
            "meta": {"stage": state.stage},
        }
    )
    db.replace_evidence_for_run(
        state.run_id,
        [e.model_dump() for e in state.evidence],
        is_demo=is_demo,
    )
    db.log_activity(state.run_id, "persist", f"Saved run {state.run_id}", is_demo=is_demo)
    return path


def open_run(run_id: str) -> ResearchState:
    return load_run(run_id)


def list_history(limit: int = 50) -> list[dict[str, Any]]:
    return db.list_runs(limit=limit)
