"""Runtime OpenAI API key validation — never log or persist the raw key."""

from __future__ import annotations

from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    message: str
    masked_key: str = ""


def mask_api_key(api_key: str) -> str:
    key = (api_key or "").strip()
    if len(key) < 12:
        return "***"
    return f"{key[:7]}...{key[-4:]}"


def validate_openai_api_key(
    api_key: str,
    *,
    base_url: str | None = None,
    timeout_seconds: float = 20.0,
) -> AuthResult:
    """Validate a user-supplied key with a lightweight models.list call."""
    key = (api_key or "").strip()
    if not key:
        return AuthResult(ok=False, message="Please enter your OpenAI API key.")
    if key.startswith("sk-") is False and not key.startswith("sk-proj-"):
        # Soft hint only — some orgs use atypical prefixes; still attempt validation
        pass

    kwargs: dict = {"api_key": key, "timeout": timeout_seconds, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url

    try:
        client = OpenAI(**kwargs)
        # Lightweight authenticated probe — does not create chat usage if key is bad
        client.models.list()
        return AuthResult(
            ok=True,
            message="Connected to OpenAI successfully.",
            masked_key=mask_api_key(key),
        )
    except AuthenticationError:
        return AuthResult(
            ok=False,
            message="Invalid OpenAI API key. Check the key and try again.",
        )
    except RateLimitError:
        # Key is recognised but rate-limited — treat as usable for app access
        return AuthResult(
            ok=True,
            message="Connected (rate limit reached on probe; key accepted).",
            masked_key=mask_api_key(key),
        )
    except (APIConnectionError, APITimeoutError, TimeoutError):
        return AuthResult(
            ok=False,
            message="OpenAI service is unavailable or timed out. Try again shortly.",
        )
    except Exception:
        # Never include exception text — it may echo request headers/key material
        return AuthResult(
            ok=False,
            message="Could not validate the API key due to an unexpected error.",
        )
