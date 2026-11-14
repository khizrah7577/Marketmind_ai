from __future__ import annotations

import streamlit as st

from ui.components.theme import hero


def render() -> None:
    hero("Quality Control Center", "Diagnose defects — QC never silently rewrites the report.")
    state = st.session_state.get("current_state")
    if state is None:
        st.markdown(
            '<div class="mm-empty">No active run. Complete Research Studio first.</div>',
            unsafe_allow_html=True,
        )
        return
    verdict = state.qc_verdict or {}
    passed = bool(verdict.get("pass"))
    st.markdown(
        f'<span class="mm-pill {"mm-pill-ok" if passed else "mm-pill-bad"}">'
        f'QC {"PASS" if passed else "FAIL"}</span>',
        unsafe_allow_html=True,
    )
    defects = verdict.get("defects") or state.defect_list or []
    st.metric("Total defects", len(defects))
    st.metric("Repair rounds used", state.repair_round)
    if not defects:
        st.success("No QC defects recorded for this draft.")
        return
    for d in defects:
        st.markdown(
            f"- **[{d.get('severity', '?')}] {d.get('type', 'defect')}** @ "
            f"`{d.get('location', '')}` — {d.get('detail', '')}  \n"
            f"  Suggested gap question: {d.get('gap_question', '—')}"
        )
