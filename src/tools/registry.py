"""Tool registry: name -> schema, handler, permission, budget, timeout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.schemas.tools import (
    CALCULATE_ARGS,
    COMPARE_ARGS,
    GENERATE_REPORT_ARGS,
    RETRIEVE_ARGS,
    SAVE_ARGS,
    SEARCH_ARGS,
)
from src.tools.impl import calculate, compare, generate_report, retrieve, save, search


Permission = str  # read | compute | write


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., dict[str, Any]]
    permission: Permission
    call_budget: int
    timeout_seconds: float


def build_default_registry() -> dict[str, ToolSpec]:
    tools = [
        ToolSpec(
            name="search_information",
            description=(
                "Search the approved local research corpus. Use for discovering vendors, "
                "pricing pages, press, and analyst notes. Do NOT use for arithmetic. "
                "Returns a list of hits with id, title, snippet; empty list if nothing matches."
            ),
            parameters=SEARCH_ARGS,
            handler=search.handle,
            permission="read",
            call_budget=40,
            timeout_seconds=10.0,
        ),
        ToolSpec(
            name="retrieve_document",
            description=(
                "Retrieve full text of a corpus document by its exact document_id from a prior "
                "search hit. Rejects unknown ids. Never pass file paths or URLs."
            ),
            parameters=RETRIEVE_ARGS,
            handler=retrieve.handle,
            permission="read",
            call_budget=40,
            timeout_seconds=10.0,
        ),
        ToolSpec(
            name="calculate_metric",
            description=(
                "Deterministic arithmetic: growth_rate, cagr, share, ratio, average, sum, delta. "
                "Use when you need numeric computations. Never invent formulas outside the enum."
            ),
            parameters=CALCULATE_ARGS,
            handler=calculate.handle,
            permission="compute",
            call_budget=20,
            timeout_seconds=5.0,
        ),
        ToolSpec(
            name="compare_companies",
            description=(
                "Build an entity×attribute matrix from the evidence store only. "
                "Cells without evidence are marked not_established. Do not invent values."
            ),
            parameters=COMPARE_ARGS,
            handler=compare.handle,
            permission="compute",
            call_budget=15,
            timeout_seconds=10.0,
        ),
        ToolSpec(
            name="save_research",
            description=(
                "Persist one evidence claim bound to a real prior tool result source_ref. "
                "Use after retrieving or calculating. Fabricated source_ref will be rejected."
            ),
            parameters=SAVE_ARGS,
            handler=save.handle,
            permission="write",
            call_budget=80,
            timeout_seconds=5.0,
        ),
        ToolSpec(
            name="generate_report",
            description=(
                "Assemble a draft report object from current research state. "
                "Usually called once near the end; does not publish."
            ),
            parameters=GENERATE_REPORT_ARGS,
            handler=generate_report.handle,
            permission="write",
            call_budget=3,
            timeout_seconds=30.0,
        ),
    ]
    return {t.name: t for t in tools}


def openai_tool_schemas(registry: dict[str, ToolSpec]) -> list[dict[str, Any]]:
    out = []
    for t in registry.values():
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
        )
    return out
