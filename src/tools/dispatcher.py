"""Validate → authorise → budget → execute → normalise → provenance → log."""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from src.state.research_state import ResearchState
from src.tools.registry import ToolSpec

logger = logging.getLogger(__name__)


class ToolDispatcher:
    def __init__(
        self,
        registry: dict[str, ToolSpec],
        state: ResearchState,
        allowed_permissions: set[str] | None = None,
    ):
        self.registry = registry
        self.state = state
        self.allowed_permissions = allowed_permissions or {"read", "compute", "write"}
        self._call_counts: dict[str, int] = {n: 0 for n in registry}

    def dispatch(self, name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
        result_id = f"tr_{uuid4().hex[:12]}"
        t0 = time.perf_counter()

        # 1. Resolve
        spec = self.registry.get(name)
        if spec is None:
            err = {
                "ok": False,
                "error": "unknown_tool",
                "message": f"Unknown tool '{name}'. Available: {sorted(self.registry)}",
                "result_id": result_id,
            }
            self._log(name, arguments, err, t0)
            return err

        # 2. Parse
        try:
            if isinstance(arguments, str):
                args = json.loads(arguments) if arguments.strip() else {}
            else:
                args = dict(arguments)
        except json.JSONDecodeError as e:
            err = {
                "ok": False,
                "error": "malformed_json",
                "message": f"Malformed JSON arguments: {e}",
                "result_id": result_id,
            }
            self._log(name, arguments, err, t0)
            return err

        # 3. Validate schema
        try:
            Draft202012Validator(spec.parameters).validate(args)
        except ValidationError as e:
            err = {
                "ok": False,
                "error": "schema_validation",
                "message": f"Invalid argument: {e.message}",
                "path": list(e.path),
                "result_id": result_id,
            }
            self._log(name, args, err, t0)
            return err

        # 4. Authorise permission
        if spec.permission not in self.allowed_permissions:
            err = {
                "ok": False,
                "error": "permission_denied",
                "message": (
                    f"Tool '{name}' requires permission '{spec.permission}' "
                    f"not allowed in this stage ({sorted(self.allowed_permissions)})"
                ),
                "result_id": result_id,
            }
            self._log(name, args, err, t0)
            return err

        # 5. Budget check
        if self._call_counts[name] >= spec.call_budget:
            err = {
                "ok": False,
                "error": "tool_budget_exceeded",
                "message": f"Call budget for '{name}' exhausted ({spec.call_budget})",
                "result_id": result_id,
            }
            self._log(name, args, err, t0)
            return err
        if self.state.tool_call_count >= self.state.max_tool_calls:
            err = {
                "ok": False,
                "error": "global_tool_cap",
                "message": "Global max_tool_calls reached",
                "result_id": result_id,
            }
            self._log(name, args, err, t0)
            return err

        # 6–8. Execute with timeout, catch, normalise
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(spec.handler, state=self.state, **args)
                raw = fut.result(timeout=spec.timeout_seconds)
        except FuturesTimeout:
            err = {
                "ok": False,
                "error": "timeout",
                "message": f"Tool '{name}' timed out after {spec.timeout_seconds}s",
                "result_id": result_id,
            }
            self._log(name, args, err, t0)
            return err
        except Exception as e:
            err = {
                "ok": False,
                "error": "execution_error",
                "message": f"Tool '{name}' failed: {e}",
                "result_id": result_id,
            }
            self._log(name, args, err, t0)
            return err

        if not isinstance(raw, dict):
            raw = {"ok": True, "data": raw}
        raw.setdefault("ok", True)
        raw["result_id"] = result_id
        raw["tool"] = name
        raw["provenance"] = {
            "tool": name,
            "result_id": result_id,
            "args": args,
        }

        self._call_counts[name] += 1
        self.state.tool_call_count += 1
        self.state.tool_results_by_id[result_id] = {"name": name, "args": args, "result": raw}
        self._log(name, args, raw, t0)
        return raw

    def dispatch_many(
        self, calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Handle parallel tool calls from one model response (sequential execute, parallel-ready API)."""
        return [
            {
                "tool_call_id": c.get("id"),
                "name": c["name"],
                "result": self.dispatch(c["name"], c.get("arguments", {})),
            }
            for c in calls
        ]

    def _log(self, name: str, args: Any, result: dict[str, Any], t0: float) -> None:
        latency = (time.perf_counter() - t0) * 1000
        entry = {
            "tool": name,
            "args": args,
            "ok": result.get("ok"),
            "error": result.get("error"),
            "result_id": result.get("result_id"),
            "latency_ms": round(latency, 2),
        }
        self.state.tool_history.append(entry)
        self.state.log_event("tool_call", entry)
        level = logging.INFO if result.get("ok") else logging.WARNING
        logger.log(
            level,
            "tool name=%s ok=%s err=%s latency_ms=%.1f",
            name,
            result.get("ok"),
            result.get("error"),
            latency,
        )
