"""Runtime auth + optional API key config (no network required)."""

from src.auth.openai_auth import AuthResult, mask_api_key, validate_openai_api_key
from src.config import Settings, clear_settings_cache, get_settings


def test_get_settings_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    clear_settings_cache()
    settings = get_settings()
    assert settings.has_api_key() is False
    # App must be able to load settings without fatal exit
    assert settings.max_iterations > 0


def test_with_api_key_and_mask():
    base = Settings(OPENAI_API_KEY=None)  # type: ignore[call-arg]
    keyed = base.with_api_key("sk-testABCDEFGHIJKLMNOPQRSTUV")
    assert keyed.has_api_key()
    assert keyed.masked_key().startswith("sk-test")
    assert "QRSTUV" in keyed.masked_key() or keyed.masked_key().endswith(
        keyed.openai_api_key[-4:]  # type: ignore[index]
    )


def test_mask_api_key():
    assert mask_api_key("short") == "***"
    masked = mask_api_key("sk-proj-abcdefghijklmnop")
    assert "..." in masked
    assert "abcdefghijklmnop" not in masked


def test_validate_empty_key_no_network():
    result = validate_openai_api_key("")
    assert isinstance(result, AuthResult)
    assert result.ok is False
    assert "enter" in result.message.lower()
