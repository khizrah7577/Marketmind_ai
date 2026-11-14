from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from src.pipeline import Pipeline
from src.schemas.report import ApprovalRecord
from src.services.history_service import persist_research_state
from src.services.report_service import export_markdown, export_pdf
from ui.components.auth_gate import is_connected
from ui.components.theme import hero


def render() -> None:
    hero("Report Studio", "Preview, export, and human-approve market intelligence briefs.")
    state = st.session_state.get("current_state")
    if state is None or state.draft_report is None:
        st.markdown(
            '<div class="mm-empty">No draft report loaded. Run Research Studio first.</div>',
            unsafe_allow_html=True,
        )
        return
    report = state.draft_report
    st.markdown(f"**Report:** `{report.report_id}` · confidence **{report.confidence_level}**")
    if report.incomplete:
        st.warning(f"Incomplete: {state.incomplete_reason}")

    tabs = st.tabs(["Preview", "Export", "Human approval"])
    with tabs[0]:
        st.subheader("Executive summary")
        st.write(report.executive_summary or "_(empty)_")
        st.subheader("Market overview")
        if report.market_overview:
            st.write(f"[{report.market_overview.claim_type}] {report.market_overview.statement}")
        st.subheader("Key trends")
        for t in report.key_trends:
            st.markdown(f"- [{t.claim_type}] {t.statement}")
        st.subheader("Limitations")
        for g in report.limitations_and_gaps:
            st.markdown(f"- {g}")

    with tabs[1]:
        if st.button("Export Markdown"):
            path = export_markdown(state)
            st.success(f"Wrote {path}")
            st.download_button(
                "Download Markdown",
                path.read_text(encoding="utf-8"),
                file_name=f"{state.run_id}.md",
            )
        if st.button("Export PDF"):
            try:
                pdf = export_pdf(state)
                st.success(f"Wrote {pdf}")
                st.download_button(
                    "Download PDF",
                    pdf.read_bytes(),
                    file_name=f"{state.run_id}.pdf",
                    mime="application/pdf",
                )
            except Exception as e:
                st.error(str(e))

    with tabs[2]:
        st.caption("Absence of a decision is not approval.")
        qc = state.qc_verdict or {}
        st.write(
            {
                "objective": report.research_objective,
                "assumptions": report.assumptions,
                "qc_pass": qc.get("pass"),
                "confidence": report.confidence_level,
                "defects": len(qc.get("defects") or []),
            }
        )
        approver = st.text_input("Your name / ID", value="")
        decision = st.radio(
            "Decision",
            ["approve", "reject", "expand", "rescope"],
            horizontal=True,
        )
        notes = st.text_area(
            "Notes / extra questions / scope amendment",
            placeholder=(
                "approve/reject: optional notes\n"
                "expand: question 1; question 2\n"
                "rescope: e.g. limit to SMB North America"
            ),
            height=100,
        )
        if st.button("Submit decision", type="primary", use_container_width=True):
            if not approver.strip():
                st.warning("Approver identity is required.")
                st.stop()
            if decision == "reject" and not notes.strip():
                st.warning("Rejection requires a reason.")
                st.stop()
            if decision in {"expand", "rescope"} and not notes.strip():
                st.warning("Provide questions or scope amendment.")
                st.stop()
            if not is_connected() and decision in {"expand", "rescope"}:
                st.error("Connect an API key to expand or rescope.")
                st.stop()

            report.approval = ApprovalRecord(
                approver_id=approver.strip(),
                decision=decision,  # type: ignore[arg-type]
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes=notes.strip(),
            )
            state.log_event(
                "approval",
                {"decision": decision, "approver": approver.strip(), "notes": notes.strip()},
            )

            usage = st.session_state.get("current_usage")
            if decision in {"expand", "rescope"} and usage is not None:
                pipe = Pipeline(api_key=st.session_state.openai_api_key)
                # Rebuild dispatcher bound to state
                from src.tools.dispatcher import ToolDispatcher
                from src.tools.registry import build_default_registry
                from src.llm.client import LLMClient

                client = LLMClient(pipe.settings, usage)
                dispatcher = ToolDispatcher(build_default_registry(), state)
                if decision == "expand":
                    state = pipe._handle_expand(client, state, dispatcher, usage, notes.strip())
                else:
                    state = pipe._handle_rescope(client, state, dispatcher, usage, notes.strip())
                if state.draft_report:
                    state.draft_report.approval = None
                st.session_state.current_state = state
                persist_research_state(state, usage.summary())
                st.info(f"{decision.title()} complete — review updated draft and approve explicitly.")
                st.rerun()

            persist_research_state(
                state, usage.summary() if usage else None
            )
            st.session_state.current_state = state
            if decision == "approve":
                st.success("Approved and persisted.")
            elif decision == "reject":
                st.warning("Rejected — nothing published as approved.")
            else:
                st.info(f"Decision recorded: {decision}")
