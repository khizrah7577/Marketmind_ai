"""Evaluation Center helpers — catalog + automated dispatcher suite scores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from database import database as db
from src.config import ROOT_DIR

CASES_PATH = ROOT_DIR / "evaluation" / "test_cases.json"

# Nine dimensions from assignment §11 (names as specified in the manual)
DIMENSIONS = [
    "Evidence Quality",
    "Factual Accuracy",
    "Citation Quality",
    "Reasoning Quality",
    "Structured Output Validity",
    "Tool Usage",
    "Hallucination Rate",
    "Report Quality",
    "Safety & Human Control",  # remaining dimension covering approval/injection/budget
]


def load_cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def run_automated_dispatcher_suite() -> dict[str, Any]:
    """Re-use evaluation/run_eval logic without fabricating LLM scenario results."""
    from evaluation.run_eval import run_dispatcher_suite

    results = run_dispatcher_suite()
    for r in results:
        db.save_evaluation_result(
            r["id"],
            "pass" if r["pass"] else "fail",
            str(r.get("detail")),
            meta={"automated": True},
        )
    passed = sum(1 for r in results if r["pass"])
    # Dimension scores: only mark Tool Usage / Structured Output / Safety from automated suite
    scores = {d: None for d in DIMENSIONS}
    tool_score = round(100 * passed / max(len(results), 1), 1)
    scores["Tool Usage"] = tool_score
    scores["Structured Output Validity"] = tool_score
    scores["Safety & Human Control"] = tool_score
    return {
        "results": results,
        "pass_count": passed,
        "total": len(results),
        "dimension_scores": scores,
        "note": (
            "Automated suite covers dispatcher/security cases only. "
            "LLM scenario cases T-01..T-18 require live API runs — do not fabricate."
        ),
    }


def catalog_with_history() -> list[dict[str, Any]]:
    cases = load_cases()
    history = db.list_evaluation_results(200)
    by_case: dict[str, list] = {}
    for h in history:
        by_case.setdefault(h["case_id"], []).append(h)
    out = []
    for c in cases:
        runs = by_case.get(c["id"], [])
        out.append({**c, "history": runs[:5], "last_verdict": runs[0]["verdict"] if runs else None})
    return out
