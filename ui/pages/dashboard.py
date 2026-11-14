from __future__ import annotations

import streamlit as st

from src.services import analytics_service
from src.services.demo_service import seed_demo_if_empty
from ui.components.charts import activity_line, claim_bars, competitor_established_bars, status_donut
from ui.components.theme import hero
from database import database as db


def render() -> None:
    seeded = seed_demo_if_empty()
    hero(
        "Executive Dashboard",
        "Live KPIs from saved research runs — never invented statistics.",
    )
    if seeded:
        st.markdown(
            '<span class="mm-pill mm-pill-demo">DEMO DATA LOADED</span> '
            "Sample project seeded because the database was empty.",
            unsafe_allow_html=True,
        )

    k = analytics_service.kpis()
    c1, c2, c3 = st.columns(3)
    c4, c5, c6 = st.columns(3)
    c1.metric("Total Research Projects", k["total_projects"])
    c2.metric("Completed Reports", k["completed_reports"])
    c3.metric("Total Evidence Records", k["evidence_records"])
    c4.metric("Avg Confidence Score", k["average_confidence_score"])
    c5.metric("Estimated API Spend (USD)", f"${k['estimated_api_spend_usd']:.4f}")
    c6.metric("Research Success Rate", f"{k['research_success_rate_pct']}%")

    if k["total_projects"] == 0:
        st.markdown(
            '<div class="mm-empty">No research runs yet. Open <b>Research Studio</b> to start, '
            "or load demo data automatically on first visit.</div>",
            unsafe_allow_html=True,
        )
        return

    a, b = st.columns(2)
    fig1 = activity_line(analytics_service.research_activity())
    fig2 = status_donut(analytics_service.status_breakdown())
    if fig1:
        a.plotly_chart(fig1, use_container_width=True)
    if fig2:
        b.plotly_chart(fig2, use_container_width=True)

    fig3 = claim_bars(analytics_service.evidence_confidence_mix())
    if fig3:
        st.plotly_chart(fig3, use_container_width=True)

    runs = db.list_runs(8)
    latest = runs[0] if runs else None
    matrix = analytics_service.competitor_matrix_from_run(latest)
    fig4 = competitor_established_bars(matrix)
    if fig4:
        st.plotly_chart(fig4, use_container_width=True)
    elif latest:
        st.caption(
            "Competitor coverage chart appears when a saved run contains a comparison matrix."
        )

    st.markdown("### Recent research projects")
    st.dataframe(
        [
            {
                "Run": r["run_id"],
                "Topic": r["topic"],
                "Status": r["status"],
                "Evidence": r["evidence_count"],
                "Cost USD": r["cost_usd"],
                "Demo": "YES" if r.get("is_demo") else "no",
            }
            for r in runs
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Recent agent activities")
    acts = db.recent_activities(12)
    if acts:
        for arow in acts:
            demo = " [DEMO]" if arow.get("is_demo") else ""
            st.caption(f"{arow['ts']} · {arow['kind']}{demo} — {arow['message']}")
    else:
        st.caption("No activity logged yet.")
