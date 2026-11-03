"""Synthesis Agent — findings per objective with evidence ids."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.schemas.evidence import Finding
from src.state.research_state import ResearchState

logger = logging.getLogger(__name__)

SYNTHESIS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["market_overview", "key_trends", "opportunities", "risks", "recommendations"],
    "properties": {
        "market_overview": {
            "type": "object",
            "additionalProperties": False,
            "required": ["statement", "claim_type", "evidence_ids", "confidence"],
            "properties": {
                "statement": {"type": "string"},
                "claim_type": {
                    "type": "string",
                    "enum": ["fact", "inference", "recommendation", "uncertainty"],
                },
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            },
        },
        "key_trends": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["statement", "claim_type", "evidence_ids", "confidence"],
                "properties": {
                    "statement": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": ["fact", "inference", "recommendation", "uncertainty"],
                    },
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["statement", "claim_type", "evidence_ids", "confidence"],
                "properties": {
                    "statement": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": ["fact", "inference", "recommendation", "uncertainty"],
                    },
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["statement", "claim_type", "evidence_ids", "confidence"],
                "properties": {
                    "statement": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": ["fact", "inference", "recommendation", "uncertainty"],
                    },
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                },
            },
        },
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["statement", "motivating_evidence_ids"],
                "properties": {
                    "statement": {"type": "string"},
                    "motivating_evidence_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}


def run_synthesis(client: LLMClient, state: ResearchState) -> dict[str, Any]:
    state.stage = "synthesis"
    known_ids = {e.evidence_id for e in state.evidence}
    evidence_compact = [
        {
            "evidence_id": e.evidence_id,
            "claim": e.claim,
            "claim_type": e.claim_type,
            "question_id": e.question_id,
        }
        for e in state.evidence
    ]
    plan_compact = state.plan.model_dump() if state.plan else {}
    system = load_prompt("synthesis")
    user = (
        f"PLAN:\n{json.dumps(plan_compact)[:4000]}\n"
        f"EVIDENCE_STORE:\n{json.dumps(evidence_compact)[:8000]}\n"
        f"COMPARISON_MATRIX_SAMPLE:\n{json.dumps(state.comparison_matrix[:20])}\n"
        "Synthesize. Every evidence_ids entry MUST be from the store. "
        "Future market value projections must be inference or uncertainty."
    )
    data = client.chat_json(
        stage="synthesis",
        system=system,
        user=user,
        json_schema=SYNTHESIS_SCHEMA,
        schema_name="synthesis",
    )
    data.pop("_validation_defect", None)

    def _filter_finding(obj: dict) -> dict:
        ids = [i for i in obj.get("evidence_ids", []) if i in known_ids]
        obj["evidence_ids"] = ids
        # Strip illegal fact with no evidence
        if obj.get("claim_type") == "fact" and not ids and evidence_compact:
            obj["claim_type"] = "uncertainty"
            obj["statement"] = obj.get("statement", "") + " [retyped: no resolvable evidence]"
        # Opportunities must not be fact
        return obj

    if "market_overview" in data:
        data["market_overview"] = _filter_finding(data["market_overview"])
    for key in ("key_trends", "opportunities", "risks"):
        data[key] = [_filter_finding(x) for x in data.get(key, [])]
        if key == "opportunities":
            for x in data[key]:
                if x.get("claim_type") == "fact":
                    x["claim_type"] = "inference"

    state.synthesis.update(data)
    state.model_versions["synthesis"] = client.settings.model_for("synthesis")
    state.log_event("synthesis", {"trends": len(data.get("key_trends", []))})
    return data
