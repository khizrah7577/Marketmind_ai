from __future__ import annotations

import streamlit as st

from src.config import get_settings
from ui.components.auth_gate import disconnect, is_connected, render_connect_page
from ui.components.theme import hero


def render() -> None:
    hero("Settings", "Models, budgets, logging — and OpenAI connection.")
    settings = get_settings()

    st.markdown("### OpenAI connection")
    if is_connected():
        st.success(f"Connected: `{st.session_state.openai_masked}`")
        if st.button("Disconnect API key"):
            disconnect()
            st.rerun()
    else:
        render_connect_page()

    st.markdown("### Current configuration (read from environment / defaults)")
    st.json(
        {
            "models": {
                "analyser": settings.model_analyser,
                "planner": settings.model_planner,
                "researcher": settings.model_researcher,
                "evidence": settings.model_evidence,
                "comparison": settings.model_comparison,
                "synthesis": settings.model_synthesis,
                "qc": settings.model_qc,
                "report": settings.model_report,
            },
            "temperatures": {
                "analyser": settings.temp_analyser,
                "planner": settings.temp_planner,
                "researcher": settings.temp_researcher,
                "evidence": settings.temp_evidence,
                "comparison": settings.temp_comparison,
                "synthesis": settings.temp_synthesis,
                "qc": settings.temp_qc,
                "report": settings.temp_report,
            },
            "limits": {
                "max_iterations": settings.max_iterations,
                "max_tool_calls": settings.max_tool_calls,
                "max_repair_rounds": settings.max_repair_rounds,
                "run_budget_usd": settings.run_budget_usd,
                "request_timeout_seconds": settings.request_timeout_seconds,
                "max_retries": settings.max_retries,
                "log_level": settings.log_level,
            },
        }
    )
    st.caption(
        "Override via environment variables or Streamlit secrets for deployment. "
        "Research Studio can override iteration/tool/budget caps per run."
    )
