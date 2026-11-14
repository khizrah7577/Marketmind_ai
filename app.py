"""MarketMind AI — Streamlit UI with runtime OpenAI API key authentication."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from src.auth.openai_auth import mask_api_key, validate_openai_api_key
from src.config import get_settings
from src.logging_setup import setup_logging
from src.pipeline import Pipeline
from src.state.persistence import write_markdown_report

st.set_page_config(
    page_title="MarketMind AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_REQUEST = (
    "Research the market for AI-powered customer support software "
    "and prepare a business intelligence report."
)

API_KEYS_URL = "https://platform.openai.com/api-keys"
STYLES_PATH = ROOT / "assets" / "styles.css"


def _apply_theme() -> None:
    if STYLES_PATH.exists():
        st.markdown(
            f"<style>{STYLES_PATH.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def _page_header(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="mm-page-header">
          <div class="mm-page-kicker">{kicker}</div>
          <h1 class="mm-page-title">{title}</h1>
          <p class="mm-page-desc">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    defaults = {
        "openai_api_key": None,
        "openai_connected": False,
        "openai_masked": "",
        "auth_error": None,
        "phase": "input",  # input | running | review | done
        "research_state": None,
        "usage": None,
        "client": None,
        "dispatcher": None,
        "pipeline": None,
        "error": None,
        "message": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _is_connected() -> bool:
    return bool(
        st.session_state.get("openai_connected")
        and st.session_state.get("openai_api_key")
    )


def _disconnect() -> None:
    st.session_state.openai_api_key = None
    st.session_state.openai_connected = False
    st.session_state.openai_masked = ""
    st.session_state.auth_error = None
    # Drop any in-flight research that depended on the prior client
    st.session_state.client = None
    st.session_state.pipeline = None
    st.session_state.dispatcher = None


def _claim_counts(state) -> dict[str, int]:
    counts = {"fact": 0, "inference": 0, "recommendation": 0, "uncertainty": 0}
    for e in state.evidence:
        counts[e.claim_type] = counts.get(e.claim_type, 0) + 1
    return counts


def _render_sidebar_brand() -> None:
    st.markdown(
        """
        <div class="mm-brand">
          <div class="mm-brand-mark">Financial Intelligence</div>
          <div class="mm-brand-title">MarketMind AI</div>
          <div class="mm-brand-sub">Autonomous market research desk</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_connect_screen() -> None:
    _apply_theme()
    with st.sidebar:
        _render_sidebar_brand()
        st.caption("Session security")
        st.write(
            "API keys stay in this browser session only. "
            "Nothing is written to disk or source control."
        )

    st.markdown('<div class="mm-connect-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="mm-connect-hero">
          <span class="mm-badge">Secure connection</span>
          <h1>MarketMind AI</h1>
          <p>Connect your OpenAI account to continue</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="mm-card">', unsafe_allow_html=True)
    st.info(
        "Your API key stays in this browser session only. "
        "It is never written to disk, GitHub, or application source code."
    )
    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-… or sk-proj-…",
        help="Paste a key from your OpenAI account. It will not be shown after connect.",
    )
    connect = st.button("Connect OpenAI", type="primary", use_container_width=True)

    if st.session_state.auth_error:
        st.error(st.session_state.auth_error)

    st.caption(
        f"Get your API key from [{API_KEYS_URL}]({API_KEYS_URL}). "
        "OpenAI billing/credits are required on your own account."
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if connect:
        with st.spinner("Validating API key with OpenAI…"):
            base = get_settings()
            result = validate_openai_api_key(
                api_key,
                base_url=base.openai_base_url,
                timeout_seconds=min(30.0, base.request_timeout_seconds),
            )
        if result.ok:
            st.session_state.openai_api_key = api_key.strip()
            st.session_state.openai_connected = True
            st.session_state.openai_masked = result.masked_key or mask_api_key(
                api_key
            )
            st.session_state.auth_error = None
            st.rerun()
        else:
            st.session_state.auth_error = result.message
            st.session_state.openai_api_key = None
            st.session_state.openai_connected = False
            st.rerun()


def _render_app() -> None:
    _apply_theme()
    settings = get_settings()

    with st.sidebar:
        _render_sidebar_brand()
        st.markdown("**Workspace**")
        phase = st.session_state.phase
        nav_labels = {
            "input": "Research brief",
            "running": "Research running",
            "review": "Approval desk",
            "done": "Published / archived",
        }
        st.caption(f"Current stage: {nav_labels.get(phase, phase)}")

        st.divider()
        st.markdown("**Connection**")
        st.success(f"OpenAI connected: `{st.session_state.openai_masked}`")
        if st.button("Disconnect API key", use_container_width=True):
            _disconnect()
            st.rerun()

        st.divider()
        st.markdown("**Run settings**")
        st.write(f"Budget: **${settings.run_budget_usd:.2f}**")
        st.write(f"Max iterations: **{settings.max_iterations}**")
        st.caption("Models and caps can be overridden via optional env vars.")

        if st.button("Reset research session", use_container_width=True):
            key = st.session_state.openai_api_key
            masked = st.session_state.openai_masked
            connected = st.session_state.openai_connected
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            _init_state()
            st.session_state.openai_api_key = key
            st.session_state.openai_masked = masked
            st.session_state.openai_connected = connected
            st.rerun()

    phase = st.session_state.phase
    if phase in {"review", "done"}:
        _page_header(
            "Approval desk",
            "Research review packet",
            "Inspect evidence, QC status, and claim types — then approve, reject, expand, or rescope.",
        )
    elif phase == "running":
        _page_header(
            "Execution",
            "Research in progress",
            "The agent loop is gathering evidence within your budget and iteration caps.",
        )
    else:
        _page_header(
            "Research workspace",
            "MarketMind AI",
            "Autonomous business research agent — plan, gather evidence, QC, then human approval.",
        )

    if st.session_state.error:
        # Sanitize accidental key leakage in exception strings
        err = str(st.session_state.error)
        key = st.session_state.openai_api_key or ""
        if key and key in err:
            err = err.replace(key, st.session_state.openai_masked or "***")
        st.error(err)

    if st.session_state.message:
        st.info(st.session_state.message)

    # -------- INPUT --------
    if st.session_state.phase == "input":
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Budget ceiling", f"${settings.run_budget_usd:.2f}")
        m2.metric("Max iterations", f"{settings.max_iterations}")
        m3.metric("Max tool calls", f"{settings.max_tool_calls}")
        m4.metric("Repair rounds", f"{settings.max_repair_rounds}")

        st.markdown('<div class="mm-card">', unsafe_allow_html=True)
        st.markdown("### New research brief")
        st.caption(
            "Describe the market question. MarketMind will analyse scope, plan research, "
            "gather evidence from the local corpus, and prepare an approval packet."
        )
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
        st.markdown("</div>", unsafe_allow_html=True)

    # -------- RUNNING --------
    if st.session_state.phase == "running":
        st.markdown('<div class="mm-running">', unsafe_allow_html=True)
        st.warning(
            "Research is running — this can take several minutes and uses your OpenAI credits."
        )
        st.caption("Do not close this tab while the pipeline is executing.")
        st.markdown("</div>", unsafe_allow_html=True)
        progress = st.progress(0, text="Starting pipeline…")
        try:
            setup_logging(settings.log_level)
            pipe = Pipeline(api_key=st.session_state.openai_api_key)
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
            msg = str(e)
            key = st.session_state.openai_api_key or ""
            if key and key in msg:
                msg = msg.replace(key, st.session_state.openai_masked or "***")
            st.session_state.error = f"Run failed: {msg}"
            st.rerun()

    # -------- REVIEW / APPROVAL --------
    if st.session_state.phase in {"review", "done"}:
        state = st.session_state.research_state
        report = state.draft_report if state else None
        if report is None:
            st.error("No draft report available.")
            st.stop()

        st.markdown(
            '<div class="mm-section-label">Approval packet</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        qc = state.qc_verdict or {}
        qc_pass = bool(qc.get("pass"))
        c1.metric("QC", "PASS" if qc_pass else "FAIL")
        c2.metric("Confidence", report.confidence_level)
        c3.metric("Evidence", len(state.evidence))
        c4.metric("Cost USD", f"{report.run_cost:.4f}")

        qc_pill = "mm-pill-pass" if qc_pass else "mm-pill-fail"
        qc_label = "PASS" if qc_pass else "FAIL"
        claim_mix = _claim_counts(state)
        st.markdown(
            f'<span class="mm-pill {qc_pill}">QC {qc_label}</span>'
            f'<span class="mm-pill mm-pill-fact">fact {claim_mix.get("fact", 0)}</span>'
            f'<span class="mm-pill mm-pill-inference">inference {claim_mix.get("inference", 0)}</span>'
            f'<span class="mm-pill mm-pill-recommendation">recommendation {claim_mix.get("recommendation", 0)}</span>'
            f'<span class="mm-pill mm-pill-uncertainty">uncertainty {claim_mix.get("uncertainty", 0)}</span>',
            unsafe_allow_html=True,
        )

        st.markdown('<div class="mm-card">', unsafe_allow_html=True)
        st.markdown(f"**Objective:** {report.research_objective}")
        if report.assumptions:
            st.markdown("**Assumptions:**")
            for a in report.assumptions:
                st.markdown(f"- {a}")

        st.markdown(f"**Claim mix:** `{claim_mix}`")
        if report.incomplete:
            st.warning(f"Incomplete run: {state.incomplete_reason}")
        st.markdown("</div>", unsafe_allow_html=True)

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
            st.markdown('<div class="mm-card">', unsafe_allow_html=True)
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
            st.markdown("</div>", unsafe_allow_html=True)

        with tabs[1]:
            for e in state.evidence:
                pill = f"mm-pill-{e.claim_type}"
                st.markdown(
                    f"""
                    <div class="mm-evidence {e.claim_type}">
                      <span class="mm-pill {pill}">{e.claim_type}</span>
                      <span class="mm-pill mm-pill-fact">{e.confidence}</span>
                      <code>{e.evidence_id}</code>
                      <div style="margin-top:0.45rem;">{e.claim}</div>
                      <div class="mm-evidence-meta">source: {e.source_detail or e.source_ref}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

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
            st.markdown('<div class="mm-card">', unsafe_allow_html=True)
            try:
                md_path = write_markdown_report(state)
                st.markdown(md_path.read_text(encoding="utf-8"))
            except Exception as e:
                st.write(report.model_dump())
                st.caption(f"Markdown render note: {e}")
            st.markdown("</div>", unsafe_allow_html=True)

        with tabs[4]:
            st.markdown('<div class="mm-card">', unsafe_allow_html=True)
            if state.plan:
                st.json(state.plan.model_dump())
            st.write(
                f"Tool calls: {state.tool_call_count} | Iterations: {state.iteration}"
            )
            st.json(state.tool_history[-20:])
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.phase == "review":
            st.divider()
            st.markdown('<div class="mm-card">', unsafe_allow_html=True)
            st.markdown(
                '<div class="mm-section-label">Human gate</div>',
                unsafe_allow_html=True,
            )
            st.subheader("Human approval (required to publish)")
            st.caption(
                "Absence of a decision is not approval. Choose one outcome below."
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
                        msg = str(e)
                        key = st.session_state.openai_api_key or ""
                        if key and key in msg:
                            msg = msg.replace(
                                key, st.session_state.openai_masked or "***"
                            )
                        st.session_state.error = msg
                        st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.phase == "done":
            decision = report.approval.decision if report.approval else "n/a"
            if decision == "approve":
                st.success(
                    f"Published. Open `runs/{state.run_id}/published_report.md`"
                )
            elif decision == "reject":
                st.warning("Rejected — nothing published.")
            else:
                st.info(f"Finished with decision: {decision}")


def main() -> None:
    _init_state()
    # Optional local design preview: /?design_preview=1
    # Shows the research workspace chrome without requiring a real API key.
    if st.query_params.get("design_preview") == "1" and not _is_connected():
        st.session_state.openai_connected = True
        st.session_state.openai_api_key = "preview-not-a-real-key"
        st.session_state.openai_masked = "sk-prev...view"
        st.session_state.phase = "input"
    # App always starts — OpenAI features wait for a connected session key
    if not _is_connected():
        _render_connect_screen()
        return
    _render_app()


if __name__ == "__main__":
    main()
