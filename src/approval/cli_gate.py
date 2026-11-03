"""Human-in-the-loop approval gate — no default-yes, no timeout-approve."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.schemas.report import ApprovalRecord
from src.state.research_state import ResearchState

logger = logging.getLogger(__name__)
console = Console()


DecisionHandler = Callable[[ResearchState, str, str], ResearchState]


def run_approval_gate(
    state: ResearchState,
    *,
    on_expand: DecisionHandler | None = None,
    on_rescope: DecisionHandler | None = None,
    input_fn: Callable[[str], str] | None = None,
) -> ResearchState:
    """Present decision packet then route approve/reject/expand/rescope."""
    assert state.draft_report is not None
    report = state.draft_report
    ask = input_fn or input

    # --- Decision packet BEFORE full draft ---
    claim_counts = {"fact": 0, "inference": 0, "recommendation": 0, "uncertainty": 0}
    for e in state.evidence:
        claim_counts[e.claim_type] = claim_counts.get(e.claim_type, 0) + 1

    qc = state.qc_verdict or {}
    table = Table(title="MarketMind approval packet")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Objective", report.research_objective[:200])
    table.add_row("Assumptions", "; ".join(report.assumptions)[:300] or "(none)")
    table.add_row("QC verdict", "PASS" if qc.get("pass") else "FAIL")
    table.add_row("QC defects", str(len(qc.get("defects", []))))
    table.add_row("Confidence", f"{report.confidence_level} — {report.confidence_rationale[:160]}")
    table.add_row("Claim counts", str(claim_counts))
    table.add_row("Incomplete", str(report.incomplete))
    table.add_row("Limitations", "; ".join(report.limitations_and_gaps[:3])[:300])
    console.print(table)

    if qc.get("defects"):
        console.print(Panel("\n".join(
            f"- [{d.get('severity')}] {d.get('type')}: {d.get('detail', '')[:160]}"
            for d in qc["defects"][:8]
        ), title="Outstanding defects"))

    console.print(
        "\n[bold]Decision required[/bold] — absence of a decision is NOT approval.\n"
        "  [a] approve   [r] reject   [e] expand research   [s] modify scope\n"
    )

    while True:
        choice = ask("Enter decision [a/r/e/s]: ").strip().lower()
        if choice in {"a", "approve"}:
            approver = ask("Approver identity (required): ").strip()
            if not approver:
                console.print("[red]Approver identity required.[/red]")
                continue
            notes = ask("Notes (optional): ").strip()
            record = ApprovalRecord(
                approver_id=approver,
                decision="approve",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes=notes,
            )
            report.approval = record
            state.draft_report = report
            state.log_event(
                "approval",
                {"decision": "approve", "approver": approver, "notes": notes},
            )
            logger.info("approved by %s", approver)
            console.print("[green]Approved — publishing artefacts.[/green]")
            return state

        if choice in {"r", "reject"}:
            approver = ask("Reviewer identity (required): ").strip()
            reason = ask("Rejection reason (required): ").strip()
            if not approver or not reason:
                console.print("[red]Identity and reason required.[/red]")
                continue
            record = ApprovalRecord(
                approver_id=approver,
                decision="reject",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes=reason,
            )
            report.approval = record
            state.draft_report = report
            state.log_event(
                "approval",
                {"decision": "reject", "approver": approver, "notes": reason},
            )
            console.print("[yellow]Rejected — nothing published.[/yellow]")
            return state

        if choice in {"e", "expand"}:
            approver = ask("Reviewer identity: ").strip() or "reviewer"
            q1 = ask("Additional research question 1: ").strip()
            q2 = ask("Additional research question 2 (optional): ").strip()
            questions = [q for q in (q1, q2) if q]
            if not questions:
                console.print("[red]Provide at least one question.[/red]")
                continue
            record = ApprovalRecord(
                approver_id=approver,
                decision="expand",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes="; ".join(questions),
            )
            report.approval = record
            state.draft_report = report
            state.log_event(
                "approval",
                {"decision": "expand", "approver": approver, "questions": questions},
            )
            if on_expand:
                return on_expand(state, approver, "; ".join(questions))
            return state

        if choice in {"s", "rescope", "modify"}:
            approver = ask("Reviewer identity: ").strip() or "reviewer"
            amendment = ask(
                "Scope amendment (e.g. 'limit to SMB North America'): "
            ).strip()
            if not amendment:
                console.print("[red]Amendment required.[/red]")
                continue
            record = ApprovalRecord(
                approver_id=approver,
                decision="rescope",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes=amendment,
            )
            report.approval = record
            state.draft_report = report
            state.log_event(
                "approval",
                {"decision": "rescope", "approver": approver, "amendment": amendment},
            )
            if on_rescope:
                return on_rescope(state, approver, amendment)
            return state

        console.print("[red]Invalid choice. Enter a, r, e, or s.[/red]")
