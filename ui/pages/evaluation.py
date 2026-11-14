from __future__ import annotations

import plotly.express as px
import streamlit as st

from src.services.evaluation_service import (
    DIMENSIONS,
    catalog_with_history,
    run_automated_dispatcher_suite,
)
from ui.components.theme import hero


def render() -> None:
    hero(
        "Evaluation Center",
        "18-case catalog + automated dispatcher suite. LLM scenarios are not fabricated.",
    )
    catalog = catalog_with_history()
    st.markdown("### Test catalog (assignment §9)")
    st.dataframe(
        [
            {
                "ID": c["id"],
                "Category": c["category"],
                "Input": c["input"][:80],
                "Expected": c["expected"][:80],
                "Last verdict": c.get("last_verdict") or "—",
            }
            for c in catalog
        ],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Run automated dispatcher suite", type="primary"):
        with st.spinner("Running adversarial dispatcher cases…"):
            report = run_automated_dispatcher_suite()
        st.session_state.last_eval_report = report
        st.success(f"Automated suite: {report['pass_count']}/{report['total']} passed")

    report = st.session_state.get("last_eval_report")
    if report:
        st.markdown("### Automated results")
        st.json(report["results"])
        st.info(report["note"])
        scores = report["dimension_scores"]
        scored = [{"dimension": k, "score": v} for k, v in scores.items() if v is not None]
        if scored:
            fig = px.bar(
                scored,
                x="dimension",
                y="score",
                title="Dimension scores (automated subset only)",
                color_discrete_sequence=["#8B5CF6"],
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#F8FAFC",
            )
            st.plotly_chart(fig, use_container_width=True)
        st.markdown("### Nine evaluation dimensions")
        for d in DIMENSIONS:
            val = scores.get(d)
            st.write(f"- **{d}**: {val if val is not None else 'not scored in automated suite'}")
