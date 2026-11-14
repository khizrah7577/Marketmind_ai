from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components.charts import competitor_established_bars
from ui.components.theme import hero


def render() -> None:
    hero("Competitor Intelligence", "Attribute coverage from evidence — gaps stay Not established.")
    state = st.session_state.get("current_state")
    if state is None:
        st.markdown(
            '<div class="mm-empty">No active run loaded. Complete Research Studio or open History.</div>',
            unsafe_allow_html=True,
        )
        return
    matrix = state.comparison_matrix or []
    if state.draft_report and state.draft_report.competitor_analysis.matrix:
        matrix = [c.model_dump() for c in state.draft_report.competitor_analysis.matrix]
    if not matrix:
        st.warning("No comparison matrix available for this run.")
        return
    fig = competitor_established_bars(matrix)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
    df = pd.DataFrame(matrix)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Every cell is established only when evidence supports it; otherwise Not established.")
