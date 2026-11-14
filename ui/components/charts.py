from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go


DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#F8FAFC"),
    margin=dict(l=20, r=20, t=40, b=20),
)


def activity_line(rows: list[dict[str, Any]]):
    if not rows:
        return None
    fig = px.line(rows, x="day", y="count", markers=True, title="Research activity over time")
    fig.update_traces(line_color="#38BDF8")
    fig.update_layout(**DARK_LAYOUT)
    return fig


def status_donut(rows: list[dict[str, Any]]):
    if not rows:
        return None
    fig = px.pie(
        rows,
        names="status",
        values="count",
        hole=0.55,
        title="Research status distribution",
        color_discrete_sequence=["#8B5CF6", "#38BDF8", "#22C55E", "#F59E0B", "#EF4444"],
    )
    fig.update_layout(**DARK_LAYOUT)
    return fig


def claim_bars(rows: list[dict[str, Any]]):
    if not rows:
        return None
    fig = px.bar(
        rows,
        x="claim_type",
        y="count",
        title="Evidence claim-type mix",
        color="claim_type",
        color_discrete_sequence=["#38BDF8", "#8B5CF6", "#22C55E", "#F59E0B"],
    )
    fig.update_layout(**DARK_LAYOUT, showlegend=False)
    return fig


def competitor_established_bars(matrix: list[dict[str, Any]]):
    if not matrix:
        return None
    # Count established vs not_established per entity
    tallies: dict[str, dict[str, int]] = {}
    for cell in matrix:
        ent = cell.get("entity") or "Unknown"
        tallies.setdefault(ent, {"established": 0, "not_established": 0})
        st = cell.get("status") or "not_established"
        if st == "established":
            tallies[ent]["established"] += 1
        else:
            tallies[ent]["not_established"] += 1
    entities = list(tallies.keys())
    fig = go.Figure(
        data=[
            go.Bar(
                name="Established",
                x=entities,
                y=[tallies[e]["established"] for e in entities],
                marker_color="#22C55E",
            ),
            go.Bar(
                name="Not established",
                x=entities,
                y=[tallies[e]["not_established"] for e in entities],
                marker_color="#EF4444",
            ),
        ]
    )
    fig.update_layout(barmode="stack", title="Competitor attribute coverage", **DARK_LAYOUT)
    return fig
