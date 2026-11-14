from __future__ import annotations

import streamlit as st

from database import database as db
from ui.components.theme import hero


def render() -> None:
    hero("Evidence Explorer", "Inspect provenance-bound claims across runs.")
    c1, c2, c3 = st.columns(3)
    claim_type = c1.selectbox(
        "Claim type",
        ["all", "fact", "inference", "recommendation", "uncertainty"],
    )
    confidence = c2.selectbox("Confidence", ["all", "high", "medium", "low"])
    run_filter = c3.text_input("Run ID filter (optional)", value="")
    rows = db.list_evidence(
        run_id=run_filter.strip() or None,
        claim_type=claim_type,
        confidence=confidence,
    )
    if not rows:
        st.markdown('<div class="mm-empty">No evidence records match these filters.</div>', unsafe_allow_html=True)
        return
    for e in rows:
        demo = e.get("is_demo")
        with st.expander(
            f"{e['evidence_id']} · {e['claim_type']} · {e['confidence']}"
            + (" · DEMO" if demo else "")
        ):
            st.write(e["claim"])
            st.caption(
                f"question={e['question_id']} · credibility={e['credibility']} · "
                f"source={e['source_detail'] or e['source_ref']} · run={e['run_id']}"
            )
