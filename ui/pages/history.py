from __future__ import annotations

import streamlit as st

from src.services.history_service import list_history, open_run
from ui.components.theme import hero


def render() -> None:
    hero("Research History", "Browse, reopen, and compare persisted runs.")
    runs = list_history(100)
    if not runs:
        st.markdown('<div class="mm-empty">No saved runs yet.</div>', unsafe_allow_html=True)
        return
    st.dataframe(
        [
            {
                "Run ID": r["run_id"],
                "Topic": r["topic"],
                "Date": r.get("updated_at") or r.get("created_at"),
                "Status": r["status"],
                "Evidence": r["evidence_count"],
                "Tokens": r["tokens"],
                "Cost USD": r["cost_usd"],
                "Approval": r.get("approval"),
                "Demo": "YES" if r.get("is_demo") else "no",
            }
            for r in runs
        ],
        use_container_width=True,
        hide_index=True,
    )
    ids = [r["run_id"] for r in runs if not r.get("is_demo") or r.get("state_path")]
    # Prefer runs with state files
    openable = [r["run_id"] for r in runs if r.get("state_path")]
    choice = st.selectbox("Open previous run", options=[""] + openable)
    if choice and st.button("Load run into workspace", type="primary"):
        try:
            state = open_run(choice)
            st.session_state.current_state = state
            st.session_state.current_run_id = choice
            st.success(f"Loaded {choice}")
        except Exception as e:
            st.error(f"Could not load run: {e}")

    compare = st.multiselect("Compare research runs (select 2+)", options=[r["run_id"] for r in runs])
    if len(compare) >= 2:
        subset = [r for r in runs if r["run_id"] in compare]
        st.dataframe(
            [
                {
                    "Run": r["run_id"],
                    "Evidence": r["evidence_count"],
                    "Cost": r["cost_usd"],
                    "Tools": r["tool_calls"],
                    "Confidence": r.get("confidence"),
                    "Status": r["status"],
                }
                for r in subset
            ],
            use_container_width=True,
            hide_index=True,
        )
