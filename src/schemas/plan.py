"""Research plan and request-scope schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

EvidenceType = Literal[
    "pricing",
    "feature",
    "positioning",
    "market_size",
    "customer_segment",
    "funding",
    "review",
    "news",
    "regulatory",
    "other",
]

ToolName = Literal[
    "search_information",
    "retrieve_document",
    "calculate_metric",
    "compare_companies",
    "save_research",
    "generate_report",
]

EntityType = Literal[
    "vendor",
    "category",
    "buyer",
    "technology",
    "unknown",
]
Segment = Literal["enterprise", "mid_market", "smb", "consumer", "mixed", "unspecified"]
Geography = Literal[
    "global",
    "north_america",
    "europe",
    "apac",
    "latam",
    "unspecified",
]
TimeHorizon = Literal["current", "1y", "3y", "5y", "unspecified"]
DeliverableType = Literal[
    "market_intelligence_brief",
    "competitor_matrix",
    "acquisition_shortlist",
    "opportunity_assessment",
    "unspecified",
]


class Ambiguity(BaseModel):
    field: str
    clarification_question: str | None = None
    defaulted_assumption: str | None = None


class ScopeObject(BaseModel):
    raw_request: str
    entity_type: EntityType
    segment: Segment
    geography: Geography
    time_horizon: TimeHorizon
    deliverable_type: DeliverableType
    category: str = Field(..., description="Normalised category label")
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}


class SubQuestion(BaseModel):
    id: str
    question: str = Field(..., min_length=10, max_length=500)
    required_evidence_type: EvidenceType
    candidate_tools: list[ToolName] = Field(..., min_length=1)
    priority: Literal["high", "medium", "low"] = "medium"
    status: Literal["open", "answered", "unanswerable"] = "open"

    model_config = {"extra": "forbid"}


class Objective(BaseModel):
    id: str
    title: str = Field(..., min_length=5, max_length=200)
    rationale: str = ""
    sub_questions: list[SubQuestion] = Field(..., min_length=2, max_length=5)

    model_config = {"extra": "forbid"}


class ResearchPlan(BaseModel):
    plan_id: str
    research_objective: str
    objectives: list[Objective] = Field(..., min_length=3, max_length=6)

    model_config = {"extra": "forbid"}

    @field_validator("objectives")
    @classmethod
    def unique_questions(cls, objs: list[Objective]) -> list[Objective]:
        seen: set[str] = set()
        for o in objs:
            for sq in o.sub_questions:
                key = sq.question.strip().lower()
                if key in seen:
                    raise ValueError(f"Duplicate sub-question: {sq.question}")
                seen.add(key)
        return objs


SCOPE_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "entity_type",
        "segment",
        "geography",
        "time_horizon",
        "deliverable_type",
        "category",
        "ambiguities",
        "assumptions",
        "needs_clarification",
        "clarification_questions",
    ],
    "properties": {
        "entity_type": {
            "type": "string",
            "enum": ["vendor", "category", "buyer", "technology", "unknown"],
        },
        "segment": {
            "type": "string",
            "enum": ["enterprise", "mid_market", "smb", "consumer", "mixed", "unspecified"],
        },
        "geography": {
            "type": "string",
            "enum": ["global", "north_america", "europe", "apac", "latam", "unspecified"],
        },
        "time_horizon": {
            "type": "string",
            "enum": ["current", "1y", "3y", "5y", "unspecified"],
        },
        "deliverable_type": {
            "type": "string",
            "enum": [
                "market_intelligence_brief",
                "competitor_matrix",
                "acquisition_shortlist",
                "opportunity_assessment",
                "unspecified",
            ],
        },
        "category": {"type": "string"},
        "ambiguities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "clarification_question", "defaulted_assumption"],
                "properties": {
                    "field": {"type": "string"},
                    "clarification_question": {"type": ["string", "null"]},
                    "defaulted_assumption": {"type": ["string", "null"]},
                },
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "needs_clarification": {"type": "boolean"},
        "clarification_questions": {"type": "array", "items": {"type": "string"}},
    },
}

PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plan_id", "research_objective", "objectives"],
    "properties": {
        "plan_id": {"type": "string"},
        "research_objective": {"type": "string"},
        "objectives": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "title", "rationale", "sub_questions"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "sub_questions": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 5,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "id",
                                "question",
                                "required_evidence_type",
                                "candidate_tools",
                                "priority",
                            ],
                            "properties": {
                                "id": {"type": "string"},
                                "question": {"type": "string"},
                                "required_evidence_type": {
                                    "type": "string",
                                    "enum": [
                                        "pricing",
                                        "feature",
                                        "positioning",
                                        "market_size",
                                        "customer_segment",
                                        "funding",
                                        "review",
                                        "news",
                                        "regulatory",
                                        "other",
                                    ],
                                },
                                "candidate_tools": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "string",
                                        "enum": [
                                            "search_information",
                                            "retrieve_document",
                                            "calculate_metric",
                                            "compare_companies",
                                            "save_research",
                                            "generate_report",
                                        ],
                                    },
                                },
                                "priority": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def validate_plan_invariants(plan: ResearchPlan, available_tools: set[str]) -> list[str]:
    """Code-level plan validator (Task 04)."""
    defects: list[str] = []
    if not (3 <= len(plan.objectives) <= 6):
        defects.append(f"objectives count {len(plan.objectives)} out of [3,6]")
    for obj in plan.objectives:
        if len(obj.sub_questions) < 2:
            defects.append(f"{obj.id} has fewer than 2 sub-questions")
        for sq in obj.sub_questions:
            vague = {"analyse the market", "understand the landscape", "research competitors"}
            if sq.question.strip().lower() in vague or len(sq.question.split()) < 6:
                defects.append(f"{sq.id} may be unbounded/vague: {sq.question}")
            if not set(sq.candidate_tools) & available_tools:
                defects.append(f"{sq.id} maps to no available tool")
    return defects
