"""MarketMind AI — multi-page autonomous market intelligence platform."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from database.database import init_db
from ui.components.auth_gate import ensure_session_auth_keys, is_connected
from ui.components.theme import apply_theme, brand
from ui.pages import (
    analytics,
    competitors,
    dashboard,
    evaluation,
    evidence,
    history,
    quality_control,
    reports,
    research,
    research_plan,
    settings_page,
)

st.set_page_config(
    page_title="MarketMind AI",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

PAGES = {
    "Dashboard": dashboard,
    "Research Studio": research,
    "Research Plan": research_plan,
    "Competitor Intelligence": competitors,
    "Market Analytics": analytics,
    "Evidence Explorer": evidence,
    "Quality Control": quality_control,
    "Reports": reports,
    "Research History": history,
    "Evaluation Center": evaluation,
    "Settings": settings_page,
}


def main() -> None:
    apply_theme()
    ensure_session_auth_keys()
    init_db()

    with st.sidebar:
        brand()
        page = st.radio(
            "Navigation",
            list(PAGES.keys()),
            label_visibility="collapsed",
        )
        st.divider()
        if is_connected():
            st.caption(f"OpenAI: `{st.session_state.openai_masked}`")
        else:
            st.caption("OpenAI: not connected")
        st.caption("MarketMind AI · Autonomous research")

    # Allow browsing dashboard/history without a key; gate AI pages softly
    ai_pages = {
        "Research Studio",
        "Research Plan",
        "Competitor Intelligence",
        "Reports",
        "Quality Control",
    }
    if page in ai_pages and not is_connected() and page == "Research Studio":
        # Research Studio handles its own warning; Settings/Connect still available
        pass
    if page == "Settings":
        PAGES[page].render()
        return

    # First visit without connection: still show dashboard; connect via Settings
    if not is_connected() and page not in {
        "Dashboard",
        "Evidence Explorer",
        "Research History",
        "Evaluation Center",
        "Market Analytics",
        "Settings",
    }:
        st.info("Some AI actions require an OpenAI key — open Settings to connect.")

    PAGES[page].render()


if __name__ == "__main__":
    main()
