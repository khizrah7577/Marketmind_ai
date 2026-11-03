"""Comparison Agent — entity × attribute matrix from evidence only."""

from __future__ import annotations

import logging

from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.state.research_state import ResearchState
from src.tools.dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES = [
    "Zendesk",
    "Intercom",
    "Freshdesk",
    "Ada",
    "Forethought",
    "Gorgias",
    "Help Scout",
    "Salesforce Service Cloud",
]
DEFAULT_ATTRS = [
    "pricing_entry",
    "pricing_enterprise",
    "target_segment",
    "ai_capability",
]


def run_comparison(
    client: LLMClient,
    state: ResearchState,
    dispatcher: ToolDispatcher,
) -> list[dict]:
    state.stage = "comparison"
    # Derive entities mentioned in evidence
    entities = list(DEFAULT_ENTITIES)
    for e in state.evidence:
        for name in DEFAULT_ENTITIES:
            if name.lower() in e.claim.lower() and name not in entities:
                entities.append(name)

    result = dispatcher.dispatch(
        "compare_companies",
        {"entities": entities[:10], "attributes": DEFAULT_ATTRS},
    )
    matrix = result.get("matrix", []) if result.get("ok") else []
    state.comparison_matrix = matrix

    # Optional narrative enrichment
    not_est = sum(1 for c in matrix if c.get("status") == "not_established")
    system = load_prompt("comparison")
    user = (
        f"Matrix has {len(matrix)} cells; {not_est} are not_established.\n"
        f"Sample: {matrix[:8]}\n"
        "Return a short JSON object {\"narratives\": {entity: text}} with 1-2 sentences each "
        "only from established cells. No invented facts."
    )
    # Soft call — narratives optional
    try:
        resp = client.chat(stage="comparison", system=system, user=user, temperature=0.1)
        state.synthesis.setdefault("comparison_notes", resp["content"])
    except Exception as e:
        logger.warning("comparison narrative skipped: %s", e)

    state.model_versions["comparison"] = client.settings.model_for("comparison")
    state.log_event("comparison", {"cells": len(matrix), "not_established": not_est})
    return matrix
