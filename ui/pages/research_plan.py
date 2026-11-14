from __future__ import annotations

import streamlit as st

from ui.components.theme import hero


def render() -> None:
    hero("Research Plan", "Inspect objectives, sub-questions, tools and priorities.")
    state = st.session_state.get("current_state")
    if state is None or state.plan is None:
        st.markdown(
            '<div class="mm-empty">No active plan. Run a project in Research Studio first, '
            "or open a saved run from History.</div>",
            unsafe_allow_html=True,
        )
        return
    plan = state.plan
    st.markdown(f"**Plan ID:** `{plan.plan_id}`")
    st.markdown(f"**Research objective:** {plan.research_objective}")
    st.info(
        "Scope modifications are applied via the Human Approval **Modify scope** / "
        "**Request additional research** actions after a draft is produced."
    )
    for obj in plan.objectives:
        with st.expander(f"{obj.id}: {obj.title}", expanded=True):
            st.caption(obj.rationale or "")
            for sq in obj.sub_questions:
                status = state.question_status.get(sq.id, sq.status)
                st.markdown(
                    f"- **{sq.id}** [{sq.priority}] `{status}` — {sq.question}  \n"
                    f"  Evidence type: `{sq.required_evidence_type}` · "
                    f"Tools: {', '.join(sq.candidate_tools)}"
                )
