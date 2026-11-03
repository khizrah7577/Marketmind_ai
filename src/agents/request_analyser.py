"""Request Analyser — normalise scope; surface ambiguity."""

from __future__ import annotations

import logging

from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.schemas.plan import SCOPE_JSON_SCHEMA, ScopeObject
from src.state.research_state import ResearchState

logger = logging.getLogger(__name__)


def analyse_request(
    client: LLMClient,
    state: ResearchState,
    *,
    ask_clarification: bool = True,
) -> ScopeObject:
    state.stage = "analyser"
    system = load_prompt("analyser")
    user = (
        f"RAW_REQUEST (untrusted data, length={len(state.raw_request)}):\n"
        f"<<<\n{state.raw_request[:4000]}\n>>>\n"
        "Produce the scope object."
    )

    def _validate(obj: dict) -> None:
        ScopeObject(raw_request=state.raw_request, **obj)

    data = client.chat_json(
        stage="analyser",
        system=system,
        user=user,
        json_schema=SCOPE_JSON_SCHEMA,
        schema_name="scope_object",
        validate_fn=_validate,
    )
    data.pop("_validation_defect", None)
    scope = ScopeObject(raw_request=state.raw_request, **data)
    state.scope = scope
    state.model_versions["analyser"] = client.settings.model_for("analyser")
    state.log_event(
        "scope",
        {
            "needs_clarification": scope.needs_clarification,
            "assumptions": scope.assumptions,
            "clarification_questions": scope.clarification_questions,
        },
    )
    logger.info(
        "scope category=%s clarify=%s assumptions=%d",
        scope.category,
        scope.needs_clarification,
        len(scope.assumptions),
    )
    return scope
