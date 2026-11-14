"""Dashboard / analytics metrics from persisted runs (never invented)."""

from __future__ import annotations

from typing import Any

from database import database as db


def kpis() -> dict[str, Any]:
    return db.dashboard_kpis()


def research_activity() -> list[dict[str, Any]]:
    return db.activity_over_time()


def status_breakdown() -> list[dict[str, Any]]:
    return db.status_distribution()


def evidence_confidence_mix() -> list[dict[str, Any]]:
    return db.claim_type_distribution()


def competitor_matrix_from_run(run: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return matrix cells from a saved report if present; else empty."""
    if not run or not run.get("state_path"):
        return []
    try:
        from src.state.persistence import load_run

        st = load_run(run["run_id"])
        if st.draft_report and st.draft_report.competitor_analysis:
            return [c.model_dump() for c in st.draft_report.competitor_analysis.matrix]
        return list(st.comparison_matrix or [])
    except Exception:
        return []
