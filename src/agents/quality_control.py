"""Quality-Control Agent — mechanical checks in code + model contradictions."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.schemas.report import FinalReport
from src.state.research_state import ResearchState

logger = logging.getLogger(__name__)


def run_quality_control(
    client: LLMClient,
    state: ResearchState,
    report: FinalReport,
) -> dict[str, Any]:
    state.stage = "qc"
    defects: list[dict[str, Any]] = []
    evidence_ids = {e.evidence_id for e in state.evidence}
    source_refs = set(state.tool_results_by_id.keys())

    def add(dtype: str, severity: str, location: str, detail: str, gap: str) -> None:
        defects.append(
            {
                "type": dtype,
                "severity": severity,
                "location": location,
                "detail": detail,
                "gap_question": gap,
            }
        )

    # --- Mechanical: unsupported claims ---
    findings = []
    if report.market_overview:
        findings.append(("market_overview", report.market_overview))
    for i, f in enumerate(report.key_trends):
        findings.append((f"key_trends[{i}]", f))
    for i, f in enumerate(report.opportunities):
        findings.append((f"opportunities[{i}]", f))
    for i, f in enumerate(report.risks):
        findings.append((f"risks[{i}]", f))

    for loc, f in findings:
        if f.claim_type == "fact":
            if not f.evidence_ids:
                add(
                    "unsupported_claim",
                    "high",
                    loc,
                    f"Fact has zero evidence_ids: {f.statement[:120]}",
                    f"Find a corpus source that supports: {f.statement[:160]}",
                )
            else:
                for eid in f.evidence_ids:
                    if eid not in evidence_ids:
                        add(
                            "unsupported_claim",
                            "high",
                            loc,
                            f"evidence_id {eid} does not resolve",
                            f"Re-establish evidence for: {f.statement[:160]}",
                        )

    # --- Mechanical: missing sources ---
    for e in report.evidence_appendix:
        if e.source_ref not in source_refs:
            add(
                "missing_source",
                "high",
                f"evidence:{e.evidence_id}",
                f"source_ref {e.source_ref} unresolvable",
                f"Re-retrieve source for claim: {e.claim[:160]}",
            )

    # --- Mechanical: coverage gaps ---
    if state.plan:
        for obj in state.plan.objectives:
            for sq in obj.sub_questions:
                has_ev = any(e.question_id == sq.id for e in state.evidence)
                mentioned = any(
                    sq.id in (f.statement + str(getattr(f, "evidence_ids", [])))
                    for _, f in findings
                )
                status = state.question_status.get(sq.id)
                if not has_ev and status != "unanswerable":
                    add(
                        "coverage_gap",
                        "medium",
                        f"plan:{sq.id}",
                        f"No evidence for sub-question: {sq.question}",
                        sq.question,
                    )
                elif status == "unanswerable" and not any(
                    sq.question[:40].lower() in g.lower() for g in report.limitations_and_gaps
                ):
                    add(
                        "coverage_gap",
                        "low",
                        f"plan:{sq.id}",
                        "Unanswerable question not listed in limitations_and_gaps",
                        f"Document limitation for: {sq.question}",
                    )

    # --- Hybrid: low-confidence ---
    low = [f for _, f in findings if f.confidence == "low"]
    if len(findings) and len(low) / max(len(findings), 1) > 0.5:
        add(
            "low_confidence",
            "medium",
            "report",
            "Over half of findings are low confidence",
            "Gather corroborating sources for low-confidence findings",
        )

    # Single-source low-cred sections
    low_cred_ids = {
        e.evidence_id for e in state.evidence if e.credibility == "low"
    }
    for loc, f in findings:
        if f.evidence_ids and all(i in low_cred_ids for i in f.evidence_ids):
            add(
                "low_confidence",
                "medium",
                loc,
                "Finding rests only on low-credibility evidence",
                f"Find higher-credibility corroboration for: {f.statement[:160]}",
            )

    # --- Model: contradictions ---
    try:
        system = load_prompt("qc")
        user = (
            "Evidence claims:\n"
            + json.dumps(
                [{"id": e.evidence_id, "claim": e.claim, "type": e.claim_type} for e in state.evidence],
                indent=2,
            )[:8000]
            + "\nList contradiction defects as JSON array under key defects, each with "
            "type='contradiction', severity, location, detail, gap_question. "
            "If none, return {\"defects\": []}."
        )
        # Use json object mode loosely
        resp = client.chat(
            stage="qc",
            system=system,
            user=user,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(resp["content"])
        for d in parsed.get("defects", []):
            d.setdefault("type", "contradiction")
            d.setdefault("severity", "medium")
            d.setdefault("location", "evidence_store")
            d.setdefault("gap_question", "Clarify conflicting figures from both sources.")
            defects.append(d)
    except Exception as e:
        logger.warning("qc model contradiction pass failed: %s", e)

    # Also detect known corpus market-size conflict mechanically
    billions = [e for e in state.evidence if "billion" in e.claim.lower()]
    if len(billions) >= 2:
        vals = set()
        for e in billions:
            for token in e.claim.replace(",", "").split():
                if token.startswith("$") or token.replace(".", "", 1).isdigit():
                    vals.add(token)
        if len(vals) >= 2 and not any(d["type"] == "contradiction" for d in defects):
            add(
                "contradiction",
                "high",
                "market_size",
                "Multiple incompatible market size figures present",
                "Retrieve both market-size sources and record an uncertainty claim covering the conflict",
            )

    high = sum(1 for d in defects if d["severity"] == "high")
    verdict = {
        "pass": high == 0 and len(defects) <= 2,
        "defects": defects,
        "gap_questions": [d["gap_question"] for d in defects if d.get("gap_question")],
    }
    # Soft pass if only low severity
    if high == 0 and all(d["severity"] == "low" for d in defects):
        verdict["pass"] = True

    state.qc_verdict = verdict
    state.defect_list.extend(defects)
    state.model_versions["qc"] = client.settings.model_for("qc")
    state.log_event("qc", {"pass": verdict["pass"], "defect_count": len(defects)})
    logger.info("qc pass=%s defects=%s", verdict["pass"], len(defects))
    return verdict
