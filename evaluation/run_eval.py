"""Lightweight evaluation harness for dispatcher/safety cases + case catalog."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.state.research_state import ResearchState
from src.tools.dispatcher import ToolDispatcher
from src.tools.registry import build_default_registry


def run_dispatcher_suite() -> list[dict]:
    state = ResearchState(run_id="eval_dispatch", max_tool_calls=100)
    d = ToolDispatcher(build_default_registry(), state)
    results = []

    def check(case_id: str, ok_pred, payload):
        passed = bool(ok_pred(payload))
        results.append({"id": case_id, "pass": passed, "detail": payload.get("error") or payload.get("ok")})
        return passed

    # T-12 variants
    check(
        "T-12a-malformed",
        lambda r: r.get("error") == "malformed_json",
        d.dispatch("search_information", "{bad"),
    )
    check(
        "T-12b-oob",
        lambda r: r.get("error") == "schema_validation",
        d.dispatch(
            "search_information",
            {"query": "pricing", "source_type": "pricing", "max_results": 500},
        ),
    )
    check(
        "T-12c-bad-enum",
        lambda r: r.get("error") == "schema_validation",
        d.dispatch(
            "search_information",
            {"query": "x", "source_type": "not_a_type", "max_results": 3},
        ),
    )
    # T-13
    check(
        "T-13-unknown",
        lambda r: r.get("error") == "unknown_tool",
        d.dispatch("not_in_registry", {}),
    )
    # Happy search + unresolvable save (fabrication defence)
    search = d.dispatch(
        "search_information",
        {"query": "market size AI support", "source_type": "any", "max_results": 5},
    )
    check("T-search-ok", lambda r: r.get("ok") is True, search)
    check(
        "T-07-fabricated-cite",
        lambda r: r.get("error") == "unresolvable_source_ref",
        d.dispatch(
            "save_research",
            {
                "question_id": "q",
                "claim": "Fake 40% share",
                "claim_type": "fact",
                "source_ref": "tr_fake",
                "confidence": "high",
            },
        ),
    )
    # Injection doc retrieve
    inj = d.dispatch(
        "retrieve_document",
        {"document_id": "injection_plant_doc"},
    )
    check(
        "T-14-injection-flag",
        lambda r: r.get("ok") is True and r.get("injection_suspect") is True,
        inj,
    )
    # Path rejection
    check(
        "T-retrieve-path-reject",
        lambda r: r.get("ok") is False,
        d.dispatch("retrieve_document", {"document_id": "../secrets.env"}),
    )
    # Calculate
    check(
        "T-calc",
        lambda r: r.get("ok") is True and "result" in r,
        d.dispatch("calculate_metric", {"operation": "average", "values": [1, 2, 3]}),
    )

    return results


def main() -> None:
    cases = json.loads((Path(__file__).parent / "test_cases.json").read_text(encoding="utf-8"))
    results = run_dispatcher_suite()
    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    report = {
        "catalog_cases": len(cases),
        "automated_dispatcher_results": results,
        "pass_count": sum(1 for r in results if r["pass"]),
        "total": len(results),
        "note": (
            "Full LLM scenario cases T-01..T-18 require live API runs; "
            "record pass rates manually in docs after demos."
        ),
    }
    (out_dir / "latest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    failed = [r for r in results if not r["pass"]]
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
