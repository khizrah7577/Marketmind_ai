"""MarketMind AI — Streamlit UI (opens in your browser)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.config import get_settings
from src.logging_setup import setup_logging
from src.pipeline import Pipeline
from src.state.persistence import write_markdown_report

st.set_page_config(
    page_title="MarketMind AI",
    page_icon="📊",
    layout="wide",
)

DEFAULT_REQUEST = (
    "Research the market for AI-powered customer support software "
    "and prepare a business intelligence report."
)


def _init_state() -> None:
    defaults = {
        "phase": "input",  # input | running | review | done
        "research_state": None,
        "usage": None,
        "client": None,
        "dispatcher": None,
        "error": None,
        "message": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _claim_counts(state) -> dict[str, int]:
    counts = {"fact": 0, "inference": 0, "recommendation": 0, "uncertainty": 0}
    for e in state.evidence:
        counts[e.claim_type] = counts.get(e.claim_type, 0) + 1
    return counts


def main() -> None:
    _init_state()
    st.title("MarketMind AI")
    st.caption(
        "Autonomous business research agent — plan, gather evidence, QC, then human approval."
    )

    with st.sidebar:
        st.header("Settings")
        try:
            settings = get_settings()
            st.success(f"API key loaded: `{settings.masked_key()}`")
            st.write(f"Budget: **${settings.run_budget_usd:.2f}**")
            st.write(f"Max iterations: **{settings.max_iterations}**")
        except SystemExit as e:
            st.error(str(e))
            st.stop()
        except Exception as e:
            st.error(f"Config error: {e}")
            st.stop()

        if st.button("Reset app", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    if st.session_state.error:
        st.error(st.session_state.error)

    if st.session_state.message:
        st.info(st.session_state.message)

    # -------- INPUT --------
    if st.session_state.phase == "input":
        request = st.text_area(
            "Research request",
            value=DEFAULT_REQUEST,
            height=120,
        )
        auto_assume = st.checkbox(
            "Auto-assume on ambiguous scope (recommended for UI)",
            value=True,
        )
        if st.button("Start research", type="primary", use_container_width=True):
            if not request.strip():
                st.warning("Enter a research request.")
                st.stop()
            st.session_state.phase = "running"
            st.session_state._pending_request = request.strip()
            st.session_state._auto_assume = auto_assume
            st.rerun()

    # -------- RUNNING --------
    if st.session_state.phase == "running":
        st.warning(
            "Research is running — this can take several minutes and uses API credits."
        )
        progress = st.progress(0, text="Starting pipeline…")
        try:
            setup_logging(get_settings().log_level)
            pipe = Pipeline()
            progress.progress(15, text="Analysing request & planning…")
            state, usage, client, dispatcher = pipe.run_until_approval(
                st.session_state._pending_request,
                auto_assume=st.session_state.get("_auto_assume", True),
            )
            progress.progress(100, text="Draft ready for review")
            st.session_state.research_state = state
            st.session_state.usage = usage
            st.session_state.client = client
            st.session_state.dispatcher = dispatcher
            st.session_state.pipeline = pipe
            st.session_state.phase = "review"
            st.session_state.error = None
            st.rerun()
        except Exception as e:
            st.session_state.phase = "input"
            st.session_state.error = f"Run failed: {e}"
            st.rerun()

    # -------- REVIEW / APPROVAL --------
    if st.session_state.phase in {"review", "done"}:
        state = st.session_state.research_state
        report = state.draft_report
        if report is None:
            st.error("No draft report available.")
            st.stop()

        st.subheader("Approval packet")
        c1, c2, c3, c4 = st.columns(4)
        qc = state.qc_verdict or {}
        c1.metric("QC", "PASS" if qc.get("pass") else "FAIL")
        c2.metric("Confidence", report.confidence_level)
        c3.metric("Evidence", len(state.evidence))
        c4.metric("Cost USD", f"{report.run_cost:.4f}")

        st.markdown(f"**Objective:** {report.research_objective}")
        if report.assumptions:
            st.markdown("**Assumptions:**")
            for a in report.assumptions:
                st.markdown(f"- {a}")

        st.markdown(f"**Claim mix:** `{_claim_counts(state)}`")
        if report.incomplete:
            st.warning(f"Incomplete run: {state.incomplete_reason}")

        with st.expander("Limitations & gaps", expanded=True):
            for g in report.limitations_and_gaps:
                st.markdown(f"- {g}")

        if qc.get("defects"):
            with st.expander("QC defects", expanded=not qc.get("pass")):
                for d in qc["defects"]:
                    st.markdown(
                        f"- **[{d.get('severity')}] {d.get('type')}** — {d.get('detail')}"
                    )

        tabs = st.tabs(
            [
                "Executive summary",
                "Evidence",
                "Comparison",
                "Full draft",
                "Plan / tools",
            ]
        )
        with tabs[0]:
            st.write(report.executive_summary or "_(empty)_")
            if report.market_overview:
                st.markdown(
                    f"**Overview [{report.market_overview.claim_type}]:** "
                    f"{report.market_overview.statement}"
                )
            if report.key_trends:
                st.markdown("**Trends**")
                for t in report.key_trends:
                    st.markdown(f"- [{t.claim_type}] {t.statement}")
            if report.recommendations:
                st.markdown("**Recommendations**")
                for r in report.recommendations:
                    st.markdown(f"- {r.statement}")

        with tabs[1]:
            for e in state.evidence:
                st.markdown(
                    f"`{e.evidence_id}` **[{e.claim_type}]** ({e.confidence})  \n"
                    f"{e.claim}  \n"
                    f"_source: {e.source_detail or e.source_ref}_"
                )
                st.divider()

        with tabs[2]:
            if report.competitor_analysis.matrix:
                st.dataframe(
                    [
                        {
                            "entity": c.entity,
                            "attribute": c.attribute,
                            "status": c.status,
                            "value": (c.value or "")[:120],
                        }
                        for c in report.competitor_analysis.matrix
                    ],
                    use_container_width=True,
                )
            else:
                st.info("No comparison matrix yet.")

        with tabs[3]:
            try:
                md_path = write_markdown_report(state)
                st.markdown(md_path.read_text(encoding="utf-8"))
            except Exception as e:
                st.write(report.model_dump())
                st.caption(f"Markdown render note: {e}")

        with tabs[4]:
            if state.plan:
                st.json(state.plan.model_dump())
            st.write(f"Tool calls: {state.tool_call_count} | Iterations: {state.iteration}")
            st.json(state.tool_history[-20:])

        if st.session_state.phase == "review":
            st.divider()
            st.subheader("Human approval (required to publish)")
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
                    st.warning("Rejection requires a reason in Notes.")
                    st.stop()
                if decision in {"expand", "rescope"} and not notes.strip():
                    st.warning("Provide questions or a scope amendment in Notes.")
                    st.stop()

                with st.spinner("Applying decision…"):
                    try:
                        pipe: Pipeline = st.session_state.pipeline
                        new_state = pipe.apply_decision(
                            state,
                            st.session_state.usage,
                            st.session_state.client,
                            st.session_state.dispatcher,
                            decision=decision,
                            approver=approver.strip(),
                            notes=notes.strip(),
                        )
                        st.session_state.research_state = new_state
                        if decision in {"expand", "rescope"}:
                            st.session_state.phase = "review"
                            st.session_state.message = (
                                f"{decision.title()} complete — review the updated draft "
                                "and approve explicitly to publish."
                            )
                        else:
                            st.session_state.phase = "done"
                            st.session_state.message = (
                                f"Decision recorded: **{decision}**. "
                                f"Artefacts in `runs/{new_state.run_id}/`"
                            )
                        st.rerun()
                    except Exception as e:
                        st.session_state.error = str(e)
                        st.rerun()

        if st.session_state.phase == "done":
            decision = (
                report.approval.decision if report.approval else "n/a"
            )
            if decision == "approve":
                st.success(
                    f"Published. Open `runs/{state.run_id}/published_report.md`"
                )
            elif decision == "reject":
                st.warning("Rejected — nothing published.")
            else:
                st.info(f"Finished with decision: {decision}")


if __name__ == "__main__":
    main()
