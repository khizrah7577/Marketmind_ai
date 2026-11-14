from __future__ import annotations

import streamlit as st

from src.auth.openai_auth import mask_api_key, validate_openai_api_key
from src.config import get_settings
from ui.components.theme import brand, hero

API_KEYS_URL = "https://platform.openai.com/api-keys"


def ensure_session_auth_keys() -> None:
    defaults = {
        "openai_api_key": None,
        "openai_connected": False,
        "openai_masked": "",
        "auth_error": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def is_connected() -> bool:
    return bool(st.session_state.get("openai_connected") and st.session_state.get("openai_api_key"))


def disconnect() -> None:
    st.session_state.openai_api_key = None
    st.session_state.openai_connected = False
    st.session_state.openai_masked = ""
    st.session_state.auth_error = None


def render_connect_page() -> None:
    brand()
    hero("MarketMind AI", "Connect your OpenAI account to unlock autonomous research")
    st.markdown('<div class="mm-card">', unsafe_allow_html=True)
    st.info(
        "Your API key stays in this browser session only. "
        "It is never written to disk, GitHub, or application source code."
    )
    # Optional Streamlit secrets fallback (not required)
    secrets_key = None
    try:
        secrets_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
    except Exception:
        secrets_key = None
    if secrets_key and st.button("Use Streamlit secret key", use_container_width=True):
        _connect(str(secrets_key))
        return

    api_key = st.text_input(
        "OpenAI API Key",
        type="password",
        placeholder="sk-… or sk-proj-…",
        help="Paste a key from your OpenAI account.",
    )
    if st.button("Connect OpenAI", type="primary", use_container_width=True):
        _connect(api_key)
    if st.session_state.get("auth_error"):
        st.error(st.session_state.auth_error)
    st.caption(f"Get your API key from [{API_KEYS_URL}]({API_KEYS_URL}).")
    st.markdown("</div>", unsafe_allow_html=True)


def _connect(api_key: str) -> None:
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
        st.session_state.openai_masked = result.masked_key or mask_api_key(api_key)
        st.session_state.auth_error = None
        st.rerun()
    st.session_state.auth_error = result.message
    st.session_state.openai_api_key = None
    st.session_state.openai_connected = False
    st.rerun()
