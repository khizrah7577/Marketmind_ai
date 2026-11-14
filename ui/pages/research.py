from __future__ import annotations

import time

import streamlit as st

from src.config import get_settings
from src.services.research_service import build_request_text, run_research
from ui.components.auth_gate import is_connected
from ui.components.theme import hero

STAGES = [
    ("request_analysis", "Request Analysis"),
    ("scope_validation", "Scope Validation"),
    ("research_planning", "Research Planning"),
    ("question_decomposition", "Question Decomposition"),
    ("information_retrieval", "Information Retrieval"),
    ("evidence_extraction", "Evidence Extraction"),
    ("competitor_analysis", "Competitor Analysis"),
    ("market_synthesis", "Market Synthesis"),
    ("quality_control", "Quality Control"),
    ("report_generation", "Report Generation"),
    ("awaiting_human_approval", "Human Approval"),
]


def render() -> None:
    hero("Research Studio", "Configure scope and launch the autonomous research pipeline.")
    if not is_connected():
        st.warning("Connect an OpenAI API key in Settings (or the Connect screen) before starting research.")
        return

    settings = get_settings()
    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="mm-card">', unsafe_allow_html=True)
        topic = st.text_area(
            "Research topic / natural-language request",
            value="Research the market for AI-powered customer support software and prepare a business intelligence report.",
            height=100,
        )
        business_objective = st.text_input("Business objective", value="")
        c1, c2 = st.columns(2)
        industry = c1.text_input("Industry", value="AI software")
        geography = c2.selectbox(
            "Geography",
            ["", "global", "north_america", "europe", "apac", "latam"],
            index=1,
        )
        c3, c4 = st.columns(2)
        segment = c3.selectbox(
            "Target market segment",
            ["", "enterprise", "mid_market", "smb", "mixed"],
            index=3,
        )
        time_horizon = c4.selectbox("Time horizon", ["", "current", "1y", "3y", "5y"], index=1)
        additional = st.text_area("Additional instructions", value="", height=70)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="mm-card">', unsafe_allow_html=True)
        st.markdown("**Research configuration**")
        depth = st.selectbox("Research depth", ["Quick", "Standard", "Comprehensive"], index=1)
        max_iter = st.number_input("Maximum iterations", 1, 50, int(settings.max_iterations))
        max_tools = st.number_input("Maximum tool calls", 1, 120, int(settings.max_tool_calls))
        budget = st.number_input("Research budget (USD)", 0.1, 50.0, float(settings.run_budget_usd))
        model = st.selectbox(
            "Model selection",
            [settings.model_researcher, "gpt-4o-mini", "gpt-4o"],
            index=0,
        )
        recency = st.selectbox("Source recency preference", ["any", "1y", "3y", "5y"], index=0)
        auto_assume = st.checkbox("Auto-assume on ambiguous scope", value=True)
        st.caption(f"Depth preset: {depth}. Recency hint: {recency}. Model: {model}")
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("START RESEARCH", type="primary", use_container_width=True):
        if not topic.strip():
            st.warning("Enter a research topic or request.")
            st.stop()
        request = build_request_text(
            topic=topic,
            business_objective=business_objective,
            industry=industry,
            geography=geography,
            segment=segment,
            time_horizon=time_horizon,
            additional=additional,
        )
        # Apply runtime caps on a settings copy
        runtime = settings.model_copy(
            update={
                "max_iterations": int(max_iter),
                "max_tool_calls": int(max_tools),
                "run_budget_usd": float(budget),
                "model_researcher": model,
            }
        )
        stage_box = st.empty()
        metrics = st.empty()
        log_box = st.empty()
        stages_done: list[str] = []
        t0 = time.perf_counter()

        def on_stage(stage: str, payload: dict) -> None:
            stages_done.append(stage)
            chips = []
            for key, label in STAGES:
                cls = "done" if key in stages_done else ("active" if key == stage else "")
                chips.append(f'<span class="{cls}">{label}</span>')
            stage_box.markdown(
                f'<div class="mm-stage">{"".join(chips)}</div>'
                f'<p class="mm-live">Current stage: <b>{stage}</b></p>',
                unsafe_allow_html=True,
            )
            metrics.write(
                {
                    "elapsed_s": round(time.perf_counter() - t0, 1),
                    "payload": payload,
                    "stages_completed": len(stages_done),
                }
            )
            log_box.caption(f"Event: {stage} · {payload}")

        try:
            state, usage = run_research(
                request,
                api_key=st.session_state.openai_api_key,
                settings=runtime,
                auto_assume=auto_assume,
                on_stage=on_stage,
            )
            st.session_state.current_run_id = state.run_id
            st.session_state.current_state = state
            st.session_state.current_usage = usage
            st.session_state.current_client = None
            st.success(
                f"Research draft ready for approval — run `{state.run_id}`. "
                "Open **Reports** or **Quality Control** next."
            )
            st.metric("Evidence collected", len(state.evidence))
            st.metric("Tool calls", state.tool_call_count)
            st.metric("Estimated cost USD", f"{usage.total_cost_usd:.4f}")
        except Exception as e:
            msg = str(e)
            key = st.session_state.openai_api_key or ""
            if key and key in msg:
                msg = msg.replace(key, st.session_state.openai_masked or "***")
            st.error(f"Research failed: {msg}")
