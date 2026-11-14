from __future__ import annotations

import streamlit as st

from src.tools.impl import calculate as calc
from ui.components.charts import claim_bars
from ui.components.theme import hero
from src.services import analytics_service


def render() -> None:
    hero(
        "Market Analytics",
        "Only values supported by evidence or labelled sample/demo data. No invented market sizes.",
    )
    mix = analytics_service.evidence_confidence_mix()
    fig = claim_bars(mix)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="mm-empty">No evidence yet to chart.</div>', unsafe_allow_html=True)

    st.markdown("### Deterministic metric calculator")
    st.caption("Uses calculate_metric tool logic in Python — never LLM arithmetic.")
    op = st.selectbox(
        "Operation",
        ["growth_rate", "cagr", "share", "ratio", "average", "sum", "delta"],
    )
    raw = st.text_input("Values (comma-separated numbers)", value="5.1, 8.2")
    period = st.number_input("Period (for CAGR)", min_value=0.0, value=3.0)
    if st.button("Calculate", type="primary"):
        try:
            values = [float(x.strip()) for x in raw.split(",") if x.strip()]
        except ValueError:
            st.error("Could not parse numbers.")
            st.stop()
        result = calc.handle(operation=op, values=values, period=period or None)
        if result.get("ok"):
            st.success(f"Result: {result['result']} · formula: {result['formula']}")
        else:
            st.error(result.get("message") or result.get("error"))

    state = st.session_state.get("current_state")
    if state and state.draft_report:
        st.markdown("### Opportunities & risks from current draft")
        for o in state.draft_report.opportunities:
            st.markdown(f"- [{o.claim_type}] {o.statement}")
        for r in state.draft_report.risks:
            st.markdown(f"- [{r.claim_type}] {r.statement}")
