"""Evidence record schema — epistemic typing and provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

ClaimType = Literal["fact", "inference", "recommendation", "uncertainty"]
SourceKind = Literal[
    "retrieved_document",
    "search_result",
    "calculation",
    "model_generated",
]
Credibility = Literal["high", "medium", "low", "unknown"]
Confidence = Literal["high", "medium", "low"]
RecencyBucket = Literal["current", "1y", "3y", "5y", "unknown"]


class EvidenceRecord(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:10]}")
    question_id: str
    claim: str = Field(..., min_length=5)
    claim_type: ClaimType
    source_ref: str = Field(..., description="Must resolve to a prior tool result id")
    source_kind: SourceKind
    source_detail: str = ""
    credibility: Credibility = "unknown"
    recency: RecencyBucket = "unknown"
    corroboration: list[str] = Field(default_factory=list)
    confidence: Confidence = "medium"
    analyst_notes: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    model_config = {"extra": "forbid"}


class Finding(BaseModel):
    statement: str
    claim_type: ClaimType
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence = "medium"

    model_config = {"extra": "forbid"}


EVIDENCE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "claims",
    ],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "claim",
                    "claim_type",
                    "source_ref",
                    "source_kind",
                    "credibility",
                    "recency",
                    "confidence",
                    "analyst_notes",
                    "decision",
                ],
                "properties": {
                    "claim": {"type": "string"},
                    "claim_type": {
                        "type": "string",
                        "enum": ["fact", "inference", "recommendation", "uncertainty"],
                    },
                    "source_ref": {"type": "string"},
                    "source_kind": {
                        "type": "string",
                        "enum": [
                            "retrieved_document",
                            "search_result",
                            "calculation",
                            "model_generated",
                        ],
                    },
                    "credibility": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "unknown"],
                    },
                    "recency": {
                        "type": "string",
                        "enum": ["current", "1y", "3y", "5y", "unknown"],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "analyst_notes": {"type": "string"},
                    "decision": {
                        "type": "string",
                        "enum": ["accept", "flag", "reject"],
                    },
                },
            },
        }
    },
}
