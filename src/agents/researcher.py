"""Bounded plan–act–observe research loop (no agent framework)."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.evidence_analyst import analyse_tool_result
from src.llm.client import LLMClient
from src.prompts import load_prompt
from src.state.research_state import ResearchState
from src.tools.dispatcher import ToolDispatcher
from src.tools.registry import openai_tool_schemas

logger = logging.getLogger(__name__)

# Tools allowed inside the research loop (write generate_report deferred)
RESEARCH_TOOLS = {
    "search_information",
    "retrieve_document",
    "calculate_metric",
    "compare_companies",
    "save_research",
}


def run_research_loop(
    client: LLMClient,
    state: ResearchState,
    dispatcher: ToolDispatcher,
    *,
    only_question_ids: list[str] | None = None,
) -> ResearchState:
    state.stage = "researcher"
    registry = {k: v for k, v in dispatcher.registry.items() if k in RESEARCH_TOOLS}
    tools = openai_tool_schemas(registry)
    system = load_prompt("researcher")
    state.model_versions["researcher"] = client.settings.model_for("researcher")

    while True:
        # Termination checks
        reason = _termination_reason(state, client)
        if reason:
            _mark_incomplete_if_needed(state, reason)
            logger.info("loop_terminate reason=%s", reason)
            state.log_event("loop_terminate", {"reason": reason})
            break

        open_qs = only_question_ids or state.open_questions()
        open_qs = [q for q in open_qs if state.question_status.get(q) == "open"]
        if not open_qs:
            logger.info("all_questions_resolved")
            state.log_event("loop_terminate", {"reason": "all_resolved"})
            break

        # Selection policy: highest priority first, then id order
        qid = _select_next_question(state, open_qs)
        state.iteration += 1
        logger.info(
            "iteration=%s question=%s cost=%.4f tools=%s",
            state.iteration,
            qid,
            state.usage_cost_usd,
            state.tool_call_count,
        )

        context = _build_context_slice(state, qid)
        user = (
            f"RUN_ID={state.run_id}\n"
            f"FOCUS_QUESTION_ID={qid}\n"
            f"FOCUS_QUESTION={state.question_text(qid)}\n"
            f"{context}\n"
            "Use tools to gather evidence. Save claims with save_research. "
            "When done for this question reply DONE or DONE_UNANSWERABLE."
        )

        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        # Inner tool-calling turns for this question (bounded)
        for _inner in range(6):
            if _termination_reason(state, client):
                break
            result = client.chat(
                stage="researcher",
                system=system,
                user="",
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            state.usage_cost_usd = client.usage.total_cost_usd

            if result["tool_calls"]:
                messages.append(
                    {
                        "role": "assistant",
                        "content": result["content"] or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in result["tool_calls"]
                        ],
                    }
                )
                for tc in result["tool_calls"]:
                    stuck = state.record_tool_signature(tc["name"], tc["arguments"])
                    if stuck:
                        state.incomplete = True
                        state.incomplete_reason = "stuck_loop_detected"
                        state.question_status[qid] = "unanswerable"
                        state.limitations.append(
                            f"Stuck loop on {tc['name']} for {qid}; marked unanswerable."
                        )
                        break
                    tr = dispatcher.dispatch(tc["name"], tc["arguments"])
                    # Route non-save results through evidence analyst
                    if tc["name"] in {
                        "search_information",
                        "retrieve_document",
                        "calculate_metric",
                    } and tr.get("ok"):
                        try:
                            analyse_tool_result(
                                client, state, question_id=qid, tool_result=tr
                            )
                        except Exception as e:
                            logger.warning("evidence_analyst_error: %s", e)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(tr, default=str)[:8000],
                        }
                    )
                if state.incomplete_reason == "stuck_loop_detected":
                    break
                continue

            # Text response — check termination words
            text = (result["content"] or "").strip().upper()
            if "DONE_UNANSWERABLE" in text:
                state.question_status[qid] = "unanswerable"
                state.limitations.append(
                    f"Could not establish an answer for {qid}: {state.question_text(qid)}"
                )
                break
            if text.startswith("DONE") or "DONE" in text.split():
                # If evidence exists for question, mark answered; else keep open once more
                if any(e.question_id == qid for e in state.evidence):
                    state.question_status[qid] = "answered"
                else:
                    state.question_status[qid] = "unanswerable"
                    state.limitations.append(
                        f"No evidence saved for {qid}; marked unanswerable."
                    )
                break
            # Model answered in prose without DONE — nudge once then close
            messages.append({"role": "assistant", "content": result["content"]})
            messages.append(
                {
                    "role": "user",
                    "content": "If finished, reply DONE or DONE_UNANSWERABLE. Otherwise call tools.",
                }
            )
        else:
            # Inner cap hit
            if state.question_status.get(qid) == "open":
                state.question_status[qid] = "unanswerable"
                state.limitations.append(f"Inner-turn cap reached for {qid}.")

    return state


def _select_next_question(state: ResearchState, open_qs: list[str]) -> str:
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    scored: list[tuple[int, str]] = []
    for qid in open_qs:
        pr = 1
        if state.plan:
            for obj in state.plan.objectives:
                for sq in obj.sub_questions:
                    if sq.id == qid:
                        pr = priority_rank.get(sq.priority, 1)
        scored.append((pr, qid))
    scored.sort()
    return scored[0][1]


def _build_context_slice(state: ResearchState, qid: str) -> str:
    """Per-question context — not the full transcript."""
    related = [e for e in state.evidence if e.question_id == qid][-5:]
    recent_tools = state.tool_history[-6:]
    open_count = len(state.open_questions())
    return (
        f"OPEN_QUESTION_COUNT={open_count}\n"
        f"BUDGET_USD_USED={state.usage_cost_usd:.4f}/{state.budget_usd}\n"
        f"TOOL_CALLS={state.tool_call_count}/{state.max_tool_calls}\n"
        f"ITERATION={state.iteration}/{state.max_iterations}\n"
        f"EVIDENCE_FOR_QUESTION={json.dumps([e.model_dump() for e in related], default=str)[:3000]}\n"
        f"RECENT_TOOLS={json.dumps(recent_tools, default=str)[:2000]}\n"
        "Known vendors in corpus often include Zendesk, Intercom, Freshdesk, Ada, "
        "Forethought, Gorgias, Help Scout, Salesforce Service Cloud, Kustomer, Capacity.\n"
        "Do not invent vendors absent from tool results."
    )


def _termination_reason(state: ResearchState, client: LLMClient) -> str | None:
    state.usage_cost_usd = client.usage.total_cost_usd
    if state.incomplete_reason == "stuck_loop_detected":
        return "stuck_loop"
    if state.iteration >= state.max_iterations:
        return "iteration_cap"
    if state.tool_call_count >= state.max_tool_calls:
        return "tool_call_cap"
    if state.usage_cost_usd >= state.budget_usd:
        return "budget_ceiling"
    return None


def _mark_incomplete_if_needed(state: ResearchState, reason: str) -> None:
    still_open = state.open_questions()
    if still_open:
        state.incomplete = True
        state.incomplete_reason = reason
        for qid in still_open:
            state.question_status[qid] = "unanswerable"
            state.limitations.append(
                f"Unanswered due to {reason}: {qid} — {state.question_text(qid)}"
            )
