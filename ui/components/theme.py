from __future__ import annotations

from pathlib import Path

import streamlit as st

THEME = Path(__file__).resolve().parent.parent / "styles" / "theme.css"


def apply_theme() -> None:
    if THEME.exists():
        st.markdown(f"<style>{THEME.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="mm-hero">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def brand() -> None:
    st.markdown(
        """
        <div class="mm-brand">
          <div class="mm-brand-mark">Autonomous Intelligence</div>
          <div class="mm-brand-title">MarketMind AI</div>
          <div class="mm-brand-sub">Market intelligence platform</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
