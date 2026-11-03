"""Research Planner — structured plan with code validation."""

from __future__ import annotations

import logging
from uuid import uuid4

from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.schemas.plan import (
    PLAN_JSON_SCHEMA,
    ResearchPlan,
    validate_plan_invariants,
)
from src.state.research_state import ResearchState

logger = logging.getLogger(__name__)

AVAILABLE_TOOLS = {
    "search_information",
    "retrieve_document",
    "calculate_metric",
    "compare_companies",
    "save_research",
    "generate_report",
}


def create_plan(client: LLMClient, state: ResearchState) -> ResearchPlan:
    assert state.scope is not None
    state.stage = "planner"
    system = load_prompt("planner")
    user = (
        "SCOPE_JSON:\n"
        f"{state.scope.model_dump_json(indent=2)}\n"
        "Create a rigorous research plan. plan_id should be a short slug."
    )

    def _validate(obj: dict) -> None:
        plan = ResearchPlan(**obj)
        defects = validate_plan_invariants(plan, AVAILABLE_TOOLS)
        if defects:
            raise ValueError("; ".join(defects))

    data = client.chat_json(
        stage="planner",
        system=system,
        user=user,
        json_schema=PLAN_JSON_SCHEMA,
        schema_name="research_plan",
        validate_fn=_validate,
    )
    defect = data.pop("_validation_defect", None)
    if defect or not data.get("objectives"):
        logger.error("planner fallback due to validation defect: %s", defect)
        data = _fallback_plan(state)
        state.defect_list.append({"type": "planner_fallback", "detail": str(defect)})

    plan = ResearchPlan(**data)
    # Ensure statuses
    for obj in plan.objectives:
        for sq in obj.sub_questions:
            sq.status = "open"
    state.plan = plan
    state.init_question_status()
    state.model_versions["planner"] = client.settings.model_for("planner")
    state.log_event(
        "plan",
        {
            "objectives": len(plan.objectives),
            "questions": sum(len(o.sub_questions) for o in plan.objectives),
        },
    )
    return plan


def _fallback_plan(state: ResearchState) -> dict:
    cat = state.scope.category if state.scope else "target category"
    return {
        "plan_id": f"plan_{uuid4().hex[:8]}",
        "research_objective": f"Map vendors, pricing, positioning, and gaps in {cat}",
        "objectives": [
            {
                "id": "obj_1",
                "title": "Identify major vendors",
                "rationale": "Establish competitive set",
                "sub_questions": [
                    {
                        "id": "q1_1",
                        "question": f"Which vendors compete in {cat} according to corpus sources?",
                        "required_evidence_type": "positioning",
                        "candidate_tools": ["search_information", "retrieve_document", "save_research"],
                        "priority": "high",
                    },
                    {
                        "id": "q1_2",
                        "question": "What segments does each major vendor primarily target?",
                        "required_evidence_type": "customer_segment",
                        "candidate_tools": ["search_information", "retrieve_document", "save_research"],
                        "priority": "high",
                    },
                ],
            },
            {
                "id": "obj_2",
                "title": "Compare published pricing",
                "rationale": "Pricing drives entry strategy",
                "sub_questions": [
                    {
                        "id": "q2_1",
                        "question": "Which vendors publish per-seat or entry pricing below $50/month, and what is included?",
                        "required_evidence_type": "pricing",
                        "candidate_tools": ["search_information", "retrieve_document", "save_research"],
                        "priority": "high",
                    },
                    {
                        "id": "q2_2",
                        "question": "Which vendors use resolution-based or custom enterprise pricing instead of public seats?",
                        "required_evidence_type": "pricing",
                        "candidate_tools": ["search_information", "retrieve_document", "save_research"],
                        "priority": "medium",
                    },
                ],
            },
            {
                "id": "obj_3",
                "title": "Trends, risks, and gaps",
                "rationale": "Synthesis inputs",
                "sub_questions": [
                    {
                        "id": "q3_1",
                        "question": "What market size figures are stated in the corpus, and do sources agree?",
                        "required_evidence_type": "market_size",
                        "candidate_tools": ["search_information", "retrieve_document", "calculate_metric", "save_research"],
                        "priority": "high",
                    },
                    {
                        "id": "q3_2",
                        "question": "What key risks and generative-AI trends are documented for buyers?",
                        "required_evidence_type": "other",
                        "candidate_tools": ["search_information", "retrieve_document", "save_research"],
                        "priority": "medium",
                    },
                ],
            },
        ],
    }
