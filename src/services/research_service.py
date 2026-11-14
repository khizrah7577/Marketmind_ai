"""Orchestrate research runs for the Streamlit Research Studio."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from src.config import Settings, get_settings
from src.llm.usage import UsageTracker
from src.pipeline import Pipeline
from src.services.history_service import persist_research_state
from src.state.research_state import ResearchState

StageCallback = Callable[[str, dict[str, Any]], None]


def build_request_text(
    *,
    topic: str,
    business_objective: str = "",
    industry: str = "",
    geography: str = "",
    segment: str = "",
    time_horizon: str = "",
    additional: str = "",
) -> str:
    parts = [topic.strip()]
    if business_objective:
        parts.append(f"Business objective: {business_objective.strip()}")
    if industry:
        parts.append(f"Industry: {industry.strip()}")
    if geography:
        parts.append(f"Geography: {geography.strip()}")
    if segment:
        parts.append(f"Target segment: {segment.strip()}")
    if time_horizon:
        parts.append(f"Time horizon: {time_horizon.strip()}")
    if additional:
        parts.append(f"Additional instructions: {additional.strip()}")
    return "\n".join(parts)


def run_research(
    request: str,
    *,
    api_key: str,
    settings: Settings | None = None,
    auto_assume: bool = True,
    on_stage: StageCallback | None = None,
) -> tuple[ResearchState, UsageTracker]:
    """Execute analyse→plan→research→QC→report without CLI approval."""

    def emit(stage: str, payload: dict[str, Any] | None = None) -> None:
        if on_stage:
            on_stage(stage, payload or {})

    base = settings or get_settings()
    pipe = Pipeline(base, api_key=api_key)
    emit("request_analysis", {})
    # Monkey-patch light stage hooks via wrapping run_until_approval internals
    # by calling pipeline steps with emissions around the public API.
    state, usage, client, dispatcher = _run_with_emits(pipe, request, auto_assume, emit)
    emit("report_generation", {"run_id": state.run_id})
    persist_research_state(state, usage.summary(), topic=request[:200])
    emit("awaiting_human_approval", {"run_id": state.run_id})
    return state, usage


def _run_with_emits(
    pipe: Pipeline,
    request: str,
    auto_assume: bool,
    emit: StageCallback,
) -> tuple[ResearchState, UsageTracker, Any, Any]:
    from uuid import uuid4

    from src.agents.comparison import run_comparison
    from src.agents.planner import create_plan
    from src.agents.quality_control import run_quality_control
    from src.agents.report_generator import generate_report
    from src.agents.request_analyser import analyse_request
    from src.agents.researcher import run_research_loop
    from src.agents.synthesis import run_synthesis
    from src.llm.client import LLMClient
    from src.llm.usage import UsageTracker
    from src.state.research_state import ResearchState
    from src.tools.dispatcher import ToolDispatcher
    from src.tools.registry import build_default_registry

    usage = UsageTracker(run_id=f"run_{uuid4().hex[:12]}")
    client = LLMClient(pipe.settings, usage)
    state = ResearchState(
        run_id=usage.run_id,
        raw_request=request,
        max_iterations=pipe.settings.max_iterations,
        max_tool_calls=pipe.settings.max_tool_calls,
        budget_usd=pipe.settings.run_budget_usd,
    )
    dispatcher = ToolDispatcher(build_default_registry(), state)

    emit("request_analysis", {"run_id": state.run_id})
    scope = analyse_request(client, state)
    if scope.needs_clarification and auto_assume and not scope.assumptions:
        scope.assumptions.append("Proceeding with analyser defaults (Studio auto-assume).")
    emit("scope_validation", {"assumptions": scope.assumptions})

    emit("research_planning", {})
    create_plan(client, state)
    emit(
        "question_decomposition",
        {
            "objectives": len(state.plan.objectives) if state.plan else 0,
            "questions": len(state.question_status),
        },
    )

    emit("information_retrieval", {"open": len(state.open_questions())})
    run_research_loop(client, state, dispatcher)
    emit(
        "evidence_extraction",
        {"evidence": len(state.evidence), "tools": state.tool_call_count},
    )

    emit("competitor_analysis", {})
    run_comparison(client, state, dispatcher)

    emit("market_synthesis", {})
    run_synthesis(client, state)

    generate_report(client, state)
    assert state.draft_report is not None

    emit("quality_control", {})
    while state.repair_round < pipe.settings.max_repair_rounds:
        verdict = run_quality_control(client, state, state.draft_report)
        if verdict.get("pass"):
            break
        state.repair_round += 1
        gaps = verdict.get("gap_questions") or []
        if not gaps:
            break
        pipe._append_gap_questions(state, gaps[:4])
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

    if state.qc_verdict and not state.qc_verdict.get("pass") and state.draft_report:
        for d in state.qc_verdict.get("defects", []):
            note = f"Unresolved QC defect ({d.get('type')}): {d.get('detail')}"
            if note not in state.draft_report.limitations_and_gaps:
                state.draft_report.limitations_and_gaps.append(note)

    state.usage_cost_usd = usage.total_cost_usd
    if state.draft_report:
        state.draft_report.run_cost = round(state.usage_cost_usd, 6)

    return state, usage, client, dispatcher
