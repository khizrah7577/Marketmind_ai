"""Final report schema (Section 6.1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.evidence import ClaimType, Confidence, EvidenceRecord, Finding


class MatrixCell(BaseModel):
    entity: str
    attribute: str
    value: str | None = None
    status: Literal["established", "not_established"] = "not_established"
    evidence_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class CompetitorAnalysis(BaseModel):
    matrix: list[MatrixCell] = Field(default_factory=list)
    narratives: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class Recommendation(BaseModel):
    statement: str
    motivating_evidence_ids: list[str] = Field(default_factory=list)
    claim_type: ClaimType = "recommendation"

    model_config = {"extra": "forbid"}


class ApprovalRecord(BaseModel):
    approver_id: str
    decision: Literal["approve", "reject", "expand", "rescope"]
    timestamp: str
    notes: str = ""

    model_config = {"extra": "forbid"}


class FinalReport(BaseModel):
    report_id: str
    generated_at: str
    model_versions: dict[str, str] = Field(default_factory=dict)
    run_cost: float = 0.0
    incomplete: bool = False
    research_objective: str
    assumptions: list[str] = Field(default_factory=list)
    executive_summary: str = ""
    market_overview: Finding | None = None
    key_trends: list[Finding] = Field(default_factory=list)
    competitor_analysis: CompetitorAnalysis = Field(default_factory=CompetitorAnalysis)
    opportunities: list[Finding] = Field(default_factory=list)
    risks: list[Finding] = Field(default_factory=list)
    evidence_appendix: list[EvidenceRecord] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    confidence_level: Confidence = "medium"
    confidence_rationale: str = ""
    limitations_and_gaps: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    approval: ApprovalRecord | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def gaps_required_unless_complete(self) -> FinalReport:
        # Soft check — hard enforcement is in QC / report generator
        return self


REPORT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "executive_summary",
        "market_overview_statement",
        "market_overview_claim_type",
        "market_overview_evidence_ids",
        "market_overview_confidence",
        "key_trends",
        "opportunities",
        "risks",
        "recommendations",
        "confidence_level",
        "confidence_rationale",
        "limitations_and_gaps",
    ],
    "properties": {
        "executive_summary": {"type": "string"},
        "market_overview_statement": {"type": "string"},
        "market_overview_claim_type": {
            "type": "string",
            "enum": ["fact", "inference", "recommendation", "uncertainty"],
        },
        "market_overview_evidence_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "market_overview_confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
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
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
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
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
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
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
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
        "confidence_level": {
            "type": "string",
            "enum": ["high", "medium", "low"],
        },
        "confidence_rationale": {"type": "string"},
        "limitations_and_gaps": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}
