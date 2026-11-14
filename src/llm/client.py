"""OpenAI API client wrapper: timeouts, retries, backoff, structured outputs, tools."""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)

from src.config import Settings, StageName
from src.llm.usage import UsageTracker

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Actionable failure from the LLM layer."""

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(f"[{kind}] {message}")


class LLMClient:
    def __init__(self, settings: Settings, usage: UsageTracker):
        api_key = settings.require_api_key()
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": settings.request_timeout_seconds,
            "max_retries": 0,  # we handle retries ourselves
        }
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**kwargs)
        self.settings = settings
        self.usage = usage

    def chat(
        self,
        *,
        stage: StageName,
        system: str,
        user: str,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        """Single place every API call passes through.

        Returns dict with keys: content, tool_calls, refusal, raw, usage.
        """
        model = self.settings.model_for(stage)
        temp = (
            temperature
            if temperature is not None
            else self.settings.temperature_for(stage)
        )
        msg_list: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if messages:
            msg_list.extend(messages)
        else:
            msg_list.append({"role": "user", "content": user})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": msg_list,
            "temperature": temp,
        }
        if tools:
            kwargs["tools"] = tools
            if tool_choice is not None:
                kwargs["tool_choice"] = tool_choice
        if response_format:
            kwargs["response_format"] = response_format

        last_err: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            t0 = time.perf_counter()
            try:
                resp = self.client.chat.completions.create(**kwargs)
                latency_ms = (time.perf_counter() - t0) * 1000
                u = resp.usage
                prompt_t = u.prompt_tokens if u else 0
                completion_t = u.completion_tokens if u else 0
                call_usage = self.usage.record(
                    stage=stage,
                    model=model,
                    prompt_tokens=prompt_t,
                    completion_tokens=completion_t,
                    latency_ms=latency_ms,
                )
                choice = resp.choices[0]
                msg = choice.message
                tool_calls = []
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_calls.append(
                            {
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        )
                content = msg.content or ""
                refusal = getattr(msg, "refusal", None)
                if not content and not tool_calls and refusal:
                    logger.error("REFUSED response stage=%s refusal=%s", stage, refusal)
                    raise LLMError("refused", str(refusal))
                if not content and not tool_calls:
                    logger.error("EMPTY response stage=%s", stage)
                    raise LLMError("empty", "Model returned empty content and no tool calls")

                logger.info(
                    "llm_ok stage=%s model=%s tokens=%s cost=%.6f latency_ms=%.0f",
                    stage,
                    model,
                    call_usage.total_tokens,
                    call_usage.cost_usd,
                    latency_ms,
                )
                return {
                    "content": content,
                    "tool_calls": tool_calls,
                    "refusal": refusal,
                    "raw": resp,
                    "usage": call_usage,
                    "messages_sent": msg_list,
                    "model": model,
                }
            except AuthenticationError as e:
                logger.error("AUTH_ERROR stage=%s detail=%s", stage, _safe_err(e))
                raise LLMError(
                    "authentication",
                    "API key rejected. Reconnect with a valid OpenAI API key.",
                ) from e
            except RateLimitError as e:
                last_err = e
                wait = _backoff(attempt)
                logger.warning(
                    "RATE_LIMIT stage=%s attempt=%s sleep=%.2fs detail=%s",
                    stage,
                    attempt,
                    wait,
                    _safe_err(e),
                )
                time.sleep(wait)
            except (APITimeoutError, APIConnectionError, TimeoutError) as e:
                last_err = e
                wait = _backoff(attempt)
                logger.warning(
                    "TIMEOUT/CONN stage=%s attempt=%s sleep=%.2fs detail=%s",
                    stage,
                    attempt,
                    wait,
                    _safe_err(e),
                )
                time.sleep(wait)
            except BadRequestError as e:
                err_s = _safe_err(e)
                if "context_length" in err_s.lower() or "maximum context" in err_s.lower():
                    logger.error("CONTEXT_LENGTH stage=%s detail=%s", stage, err_s)
                    raise LLMError("context_length", err_s) from e
                logger.error("BAD_REQUEST stage=%s detail=%s", stage, err_s)
                raise LLMError("bad_request", err_s) from e
            except LLMError:
                raise
            except Exception as e:
                last_err = e
                wait = _backoff(attempt)
                logger.warning(
                    "TRANSIENT stage=%s attempt=%s sleep=%.2fs detail=%s",
                    stage,
                    attempt,
                    wait,
                    _safe_err(e),
                )
                time.sleep(wait)

        raise LLMError("exhausted_retries", f"Failed after retries: {_safe_err(last_err)}")

    def chat_json(
        self,
        *,
        stage: StageName,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        schema_name: str = "result",
        validate_fn: Any | None = None,
        max_schema_retries: int = 1,
    ) -> dict[str, Any]:
        """Structured output with local validation + one retry + typed fallback path."""
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": json_schema,
            },
        }
        feedback = ""
        last_obj: dict[str, Any] | None = None
        for attempt in range(max_schema_retries + 1):
            prompt = user if not feedback else f"{user}\n\nVALIDATION_ERROR:\n{feedback}\nFix and return a valid object."
            result = self.chat(
                stage=stage,
                system=system,
                user=prompt,
                response_format=response_format,
            )
            try:
                obj = json.loads(result["content"])
                last_obj = obj
                if validate_fn:
                    validate_fn(obj)
                return obj
            except Exception as e:
                feedback = str(e)
                logger.warning(
                    "schema_validation_fail stage=%s attempt=%s err=%s",
                    stage,
                    attempt,
                    feedback,
                )
        logger.error("schema_fallback stage=%s — returning last object with defect flag", stage)
        if last_obj is None:
            last_obj = {}
        last_obj["_validation_defect"] = feedback
        return last_obj


def _backoff(attempt: int) -> float:
    return min(30.0, (2**attempt) + random.uniform(0, 0.5))


def _safe_err(e: Exception | None) -> str:
    if e is None:
        return "unknown"
    text = str(e)
    # Never leak API keys if somehow present
    return text.replace("sk-", "sk-***")
