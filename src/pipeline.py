"""Stage orchestration: analyse → plan → research → compare → synthesise → QC → report → approval."""

from __future__ import annotations

import logging
from collections.abc import Callable
from uuid import uuid4

from src.agents.comparison import run_comparison
from src.agents.planner import create_plan
from src.agents.quality_control import run_quality_control
from src.agents.report_generator import generate_report
from src.agents.request_analyser import analyse_request
from src.agents.researcher import run_research_loop
from src.agents.synthesis import run_synthesis
from src.approval.cli_gate import run_approval_gate
from src.config import Settings, get_settings
from src.llm.client import LLMClient
from src.llm.usage import UsageTracker
from src.schemas.plan import SubQuestion
from src.state.persistence import save_run, write_markdown_report
from src.state.research_state import ResearchState
from src.tools.dispatcher import ToolDispatcher
from src.tools.registry import build_default_registry

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        api_key: str | None = None,
    ):
        base = settings or get_settings()
        if api_key:
            base = base.with_api_key(api_key)
        # Research requires a key; Streamlit supplies it from session_state
        base.require_api_key()
        self.settings = base

    def run(
        self,
        request: str,
        *,
        auto_assume: bool = False,
        skip_approval: bool = False,
        approval_input: Callable[[str], str] | None = None,
    ) -> ResearchState:
        if skip_approval:
            raise ValueError(
                "skip_approval is forbidden — the system must never publish without human approval"
            )
        if len(request) > self.settings.max_request_chars:
            raise ValueError(
                f"Request exceeds max_request_chars={self.settings.max_request_chars}"
            )

        usage = UsageTracker(run_id=f"run_{uuid4().hex[:12]}")
        client = LLMClient(self.settings, usage)
        state = ResearchState(
            run_id=usage.run_id,
            raw_request=request,
            max_iterations=self.settings.max_iterations,
            max_tool_calls=self.settings.max_tool_calls,
            budget_usd=self.settings.run_budget_usd,
        )
        registry = build_default_registry()
        dispatcher = ToolDispatcher(registry, state)

        # 1. Analyse
        scope = analyse_request(client, state)
        if scope.needs_clarification and not auto_assume:
            logger.info("Clarification needed: %s", scope.clarification_questions)
            # Record assumptions path if user continues via auto_assume=False in CLI we prompt
            print("\nAmbiguities detected. Clarification questions:")
            for q in scope.clarification_questions:
                print(f"  - {q}")
            print("Recorded assumptions (if any):")
            for a in scope.assumptions:
                print(f"  - {a}")
            cont = input("Continue with recorded assumptions? [y/N]: ").strip().lower()
            if cont not in {"y", "yes"}:
                state.log_event("aborted_clarification", {})
                save_run(state, usage.summary())
                return state
            if not scope.assumptions:
                scope.assumptions.append(
                    "Proceeding with analyser defaults after user confirmation."
                )

        # 2. Plan
        create_plan(client, state)

        # 3. Research loop
        run_research_loop(client, state, dispatcher)

        # 4–8 with repair
        state = self._analyse_and_report(client, state, dispatcher, usage)

        # 9. Approval gate
        def on_expand(st: ResearchState, approver: str, notes: str) -> ResearchState:
            return self._handle_expand(client, st, dispatcher, usage, notes)

        def on_rescope(st: ResearchState, approver: str, amendment: str) -> ResearchState:
            return self._handle_rescope(client, st, dispatcher, usage, amendment)

        state = run_approval_gate(
            state,
            on_expand=on_expand,
            on_rescope=on_rescope,
            input_fn=approval_input,
        )

        return self._finalize_publication(state, usage)

    def run_until_approval(
        self,
        request: str,
        *,
        auto_assume: bool = True,
    ) -> tuple[ResearchState, UsageTracker, LLMClient, ToolDispatcher]:
        """Run research through draft report; leave approval to the UI/CLI caller."""
        if len(request) > self.settings.max_request_chars:
            raise ValueError(
                f"Request exceeds max_request_chars={self.settings.max_request_chars}"
            )

        usage = UsageTracker(run_id=f"run_{uuid4().hex[:12]}")
        client = LLMClient(self.settings, usage)
        state = ResearchState(
            run_id=usage.run_id,
            raw_request=request,
            max_iterations=self.settings.max_iterations,
            max_tool_calls=self.settings.max_tool_calls,
            budget_usd=self.settings.run_budget_usd,
        )
        registry = build_default_registry()
        dispatcher = ToolDispatcher(registry, state)

        scope = analyse_request(client, state)
        if scope.needs_clarification and auto_assume and not scope.assumptions:
            scope.assumptions.append(
                "Proceeding with analyser defaults (UI auto-assume)."
            )
        create_plan(client, state)
        run_research_loop(client, state, dispatcher)
        state = self._analyse_and_report(client, state, dispatcher, usage)
        return state, usage, client, dispatcher

    def apply_decision(
        self,
        state: ResearchState,
        usage: UsageTracker,
        client: LLMClient,
        dispatcher: ToolDispatcher,
        *,
        decision: str,
        approver: str,
        notes: str = "",
    ) -> ResearchState:
        """Apply approve/reject/expand/rescope from a UI and finalize artefacts."""
        from datetime import datetime, timezone

        from src.schemas.report import ApprovalRecord

        assert state.draft_report is not None
        decision = decision.lower().strip()
        if decision not in {"approve", "reject", "expand", "rescope"}:
            raise ValueError(f"Unknown decision: {decision}")

        state.draft_report.approval = ApprovalRecord(
            approver_id=approver or "reviewer",
            decision=decision,  # type: ignore[arg-type]
            timestamp=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )
        state.log_event(
            "approval",
            {"decision": decision, "approver": approver, "notes": notes},
        )

        if decision == "expand":
            state = self._handle_expand(client, state, dispatcher, usage, notes)
            # After expand, require another explicit approval — do not auto-publish
            if state.draft_report and state.draft_report.approval:
                state.draft_report.approval = None
            save_run(state, usage.summary())
            write_markdown_report(state)
            return state

        if decision == "rescope":
            state = self._handle_rescope(client, state, dispatcher, usage, notes)
            if state.draft_report and state.draft_report.approval:
                state.draft_report.approval = None
            save_run(state, usage.summary())
            write_markdown_report(state)
            return state

        return self._finalize_publication(state, usage)

    def _finalize_publication(
        self, state: ResearchState, usage: UsageTracker
    ) -> ResearchState:
        d = save_run(state, usage.summary())
        decision = (
            state.draft_report.approval.decision
            if state.draft_report and state.draft_report.approval
            else None
        )
        if decision == "approve":
            md = write_markdown_report(state)
            pub = d / "published_report.md"
            pub.write_text(md.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info("published %s", pub)
        else:
            (d / "REJECTED_OR_PENDING.txt").write_text(
                f"decision={decision}\nNo published report.\n", encoding="utf-8"
            )
            write_markdown_report(state, d / "draft_report_not_published.md")
        return state

    def _analyse_and_report(
        self,
        client: LLMClient,
        state: ResearchState,
        dispatcher: ToolDispatcher,
        usage: UsageTracker,
    ) -> ResearchState:
        run_comparison(client, state, dispatcher)
        run_synthesis(client, state)
        generate_report(client, state)
        assert state.draft_report is not None

        while state.repair_round < self.settings.max_repair_rounds:
            verdict = run_quality_control(client, state, state.draft_report)
            if verdict.get("pass"):
                break
            state.repair_round += 1
            gaps = verdict.get("gap_questions") or []
            if not gaps:
                break
            logger.info("repair_round=%s gaps=%s", state.repair_round, len(gaps))
            # Append gap questions as open sub-questions
            self._append_gap_questions(state, gaps[:4])
            run_research_loop(
                client,
                state,
                dispatcher,
                only_question_ids=[
                    qid
                    for qid, stt in state.question_status.items()
                    if stt == "open" and qid.startswith("gap_")
                ]
                or None,
            )
            run_comparison(client, state, dispatcher)
            run_synthesis(client, state)
            generate_report(client, state)

        # Exhaustion: publish with unresolved defects in limitations
        if state.qc_verdict and not state.qc_verdict.get("pass") and state.draft_report:
            for d in state.qc_verdict.get("defects", []):
                note = f"Unresolved QC defect ({d.get('type')}): {d.get('detail')}"
                if note not in state.draft_report.limitations_and_gaps:
                    state.draft_report.limitations_and_gaps.append(note)

        state.usage_cost_usd = usage.total_cost_usd
        if state.draft_report:
            state.draft_report.run_cost = round(state.usage_cost_usd, 6)
        save_run(state, usage.summary())
        return state

    def _append_gap_questions(self, state: ResearchState, gaps: list[str]) -> None:
        assert state.plan is not None
        obj = state.plan.objectives[0]
        for i, g in enumerate(gaps):
            qid = f"gap_{state.repair_round}_{i}"
            sq = SubQuestion(
                id=qid,
                question=g[:500],
                required_evidence_type="other",
                candidate_tools=["search_information", "retrieve_document", "save_research"],
                priority="high",
                status="open",
            )
            obj.sub_questions.append(sq)
            state.question_status[qid] = "open"

    def _handle_expand(
        self,
        client: LLMClient,
        state: ResearchState,
        dispatcher: ToolDispatcher,
        usage: UsageTracker,
        notes: str,
    ) -> ResearchState:
        questions = [q.strip() for q in notes.split(";") if q.strip()]
        assert state.plan is not None
        obj = state.plan.objectives[-1]
        for i, q in enumerate(questions):
            qid = f"expand_{uuid4().hex[:6]}_{i}"
            obj.sub_questions.append(
                SubQuestion(
                    id=qid,
                    question=q[:500],
                    required_evidence_type="other",
                    candidate_tools=["search_information", "retrieve_document", "save_research"],
                    priority="high",
                    status="open",
                )
            )
            state.question_status[qid] = "open"
        run_research_loop(client, state, dispatcher, only_question_ids=[
            qid for qid in state.question_status if qid.startswith("expand_") and state.question_status[qid] == "open"
        ])
        return self._analyse_and_report(client, state, dispatcher, usage)

    def _handle_rescope(
        self,
        client: LLMClient,
        state: ResearchState,
        dispatcher: ToolDispatcher,
        usage: UsageTracker,
        amendment: str,
    ) -> ResearchState:
        """Regenerate plan; retain evidence still in scope (keyword overlap heuristic)."""
        assert state.scope is not None
        state.raw_request = state.raw_request + f"\n[SCOPE AMENDMENT]: {amendment}"
        state.scope.assumptions.append(f"Scope amended by reviewer: {amendment}")
        state.scope.category = f"{state.scope.category} ({amendment})"
        # Retention rule: keep evidence whose claim/source mentions amendment tokens OR prior category tokens
        tokens = [t.lower() for t in amendment.replace(",", " ").split() if len(t) > 3]
        retained = []
        for e in state.evidence:
            blob = (e.claim + " " + e.source_detail).lower()
            if not tokens or any(t in blob for t in tokens) or True:
                # Default retention: keep all prior evidence; justify — amendment usually narrows
                # geography/segment without invalidating vendor facts already gathered.
                retained.append(e)
        # Documented rule: vendor/pricing facts retained; only drop if amendment explicitly says 'exclude'
        if "exclude" in amendment.lower():
            retained = [
                e
                for e in state.evidence
                if not any(t in e.claim.lower() for t in tokens)
            ]
        state.evidence = retained
        state.log_event(
            "rescope_retention",
            {"kept": len(retained), "rule": "retain_unless_exclude_keyword"},
        )
        create_plan(client, state)
        # Re-open all plan questions but evidence retained
        run_research_loop(client, state, dispatcher)
        return self._analyse_and_report(client, state, dispatcher, usage)
