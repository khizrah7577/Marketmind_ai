"""Tool argument JSON schemas (strict)."""

from __future__ import annotations

from typing import Any

SEARCH_ARGS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["query", "source_type", "max_results"],
    "properties": {
        "query": {"type": "string", "minLength": 2, "maxLength": 300},
        "source_type": {
            "type": "string",
            "enum": ["vendor", "pricing", "press", "review", "analyst", "any"],
        },
        "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
        "recency_window": {
            "type": "string",
            "enum": ["1y", "3y", "5y", "any"],
        },
    },
}

RETRIEVE_ARGS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["document_id"],
    "properties": {
        "document_id": {"type": "string", "minLength": 2, "maxLength": 80},
        "section": {"type": ["string", "null"], "maxLength": 80},
    },
}

CALCULATE_ARGS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["operation", "values"],
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["growth_rate", "cagr", "share", "ratio", "average", "sum", "delta"],
        },
        "values": {
            "type": "array",
            "minItems": 1,
            "maxItems": 20,
            "items": {"type": "number"},
        },
        "period": {"type": ["number", "null"]},
    },
}

COMPARE_ARGS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["entities", "attributes"],
    "properties": {
        "entities": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {"type": "string", "minLength": 1, "maxLength": 80},
        },
        "attributes": {
            "type": "array",
            "minItems": 1,
            "maxItems": 10,
            "items": {
                "type": "string",
                "enum": [
                    "pricing_entry",
                    "pricing_enterprise",
                    "target_segment",
                    "ai_capability",
                    "channels",
                    "integrations",
                    "funding",
                    "hq",
                    "market_share_claim",
                ],
            },
        },
    },
}

SAVE_ARGS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["question_id", "claim", "claim_type", "source_ref", "confidence"],
    "properties": {
        "question_id": {"type": "string"},
        "claim": {"type": "string", "minLength": 5, "maxLength": 1000},
        "claim_type": {
            "type": "string",
            "enum": ["fact", "inference", "recommendation", "uncertainty"],
        },
        "source_ref": {"type": "string"},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
}

GENERATE_REPORT_ARGS: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["run_id"],
    "properties": {
        "run_id": {"type": "string"},
        "sections": {
            "type": ["array", "null"],
            "items": {
                "type": "string",
                "enum": [
                    "executive_summary",
                    "market_overview",
                    "key_trends",
                    "competitor_analysis",
                    "opportunities",
                    "risks",
                    "recommendations",
                    "limitations",
                ],
            },
        },
    },
}
