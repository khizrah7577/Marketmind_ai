"""Serializable research state across the agent pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from src.schemas.evidence import EvidenceRecord
from src.schemas.plan import ResearchPlan, ScopeObject
from src.schemas.report import FinalReport

QuestionStatus = Literal["open", "answered", "unanswerable"]


@dataclass
class ResearchState:
    run_id: str = field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    raw_request: str = ""
    stage: str = "init"
    scope: ScopeObject | None = None
    plan: ResearchPlan | None = None
    question_status: dict[str, QuestionStatus] = field(default_factory=dict)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    tool_history: list[dict[str, Any]] = field(default_factory=list)
    tool_results_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    tool_call_count: int = 0
    max_tool_calls: int = 60
    iteration: int = 0
    max_iterations: int = 25
    usage_cost_usd: float = 0.0
    budget_usd: float = 2.0
    defect_list: list[dict[str, Any]] = field(default_factory=list)
    rejections: list[dict[str, Any]] = field(default_factory=list)
    event_log: list[dict[str, Any]] = field(default_factory=list)
    comparison_matrix: list[dict[str, Any]] = field(default_factory=list)
    synthesis: dict[str, Any] = field(default_factory=dict)
    draft_report: FinalReport | None = None
    qc_verdict: dict[str, Any] | None = None
    limitations: list[str] = field(default_factory=list)
    incomplete: bool = False
    incomplete_reason: str | None = None
    repair_round: int = 0
    model_versions: dict[str, str] = field(default_factory=dict)
    recent_tool_signatures: list[str] = field(default_factory=list)

    def log_event(self, kind: str, payload: dict[str, Any]) -> None:
        self.event_log.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "kind": kind,
                "payload": payload,
            }
        )

    def init_question_status(self) -> None:
        assert self.plan is not None
        for obj in self.plan.objectives:
            for sq in obj.sub_questions:
                self.question_status[sq.id] = "open"

    def open_questions(self) -> list[str]:
        return [qid for qid, st in self.question_status.items() if st == "open"]

    def question_text(self, qid: str) -> str:
        if not self.plan:
            return qid
        for obj in self.plan.objectives:
            for sq in obj.sub_questions:
                if sq.id == qid:
                    return sq.question
        return qid

    def record_tool_signature(self, name: str, args: Any) -> bool:
        """Return True if stuck (same tool+args twice in a row)."""
        sig = f"{name}:{args}"
        self.recent_tool_signatures.append(sig)
        if len(self.recent_tool_signatures) >= 2:
            if self.recent_tool_signatures[-1] == self.recent_tool_signatures[-2]:
                return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "raw_request": self.raw_request,
            "stage": self.stage,
            "scope": self.scope.model_dump() if self.scope else None,
            "plan": self.plan.model_dump() if self.plan else None,
            "question_status": self.question_status,
            "evidence": [e.model_dump() for e in self.evidence],
            "tool_history": self.tool_history,
            "tool_results_by_id": self.tool_results_by_id,
            "tool_call_count": self.tool_call_count,
            "max_tool_calls": self.max_tool_calls,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "usage_cost_usd": self.usage_cost_usd,
            "budget_usd": self.budget_usd,
            "defect_list": self.defect_list,
            "rejections": self.rejections,
            "event_log": self.event_log,
            "comparison_matrix": self.comparison_matrix,
            "synthesis": self.synthesis,
            "draft_report": self.draft_report.model_dump() if self.draft_report else None,
            "qc_verdict": self.qc_verdict,
            "limitations": self.limitations,
            "incomplete": self.incomplete,
            "incomplete_reason": self.incomplete_reason,
            "repair_round": self.repair_round,
            "model_versions": self.model_versions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchState":
        st = cls(run_id=data["run_id"])
        st.raw_request = data.get("raw_request", "")
        st.stage = data.get("stage", "init")
        if data.get("scope"):
            st.scope = ScopeObject(raw_request=data.get("raw_request", ""), **{
                k: v for k, v in data["scope"].items() if k != "raw_request"
            }) if "raw_request" in (data.get("scope") or {}) else ScopeObject(**data["scope"])
            # Handle scope that already includes raw_request
            try:
                st.scope = ScopeObject(**data["scope"])
            except Exception:
                st.scope = ScopeObject(raw_request=st.raw_request, **{
                    k: v for k, v in data["scope"].items() if k != "raw_request"
                })
        if data.get("plan"):
            st.plan = ResearchPlan(**data["plan"])
        st.question_status = data.get("question_status", {})
        st.evidence = [EvidenceRecord(**e) for e in data.get("evidence", [])]
        st.tool_history = data.get("tool_history", [])
        st.tool_results_by_id = data.get("tool_results_by_id", {})
        st.tool_call_count = data.get("tool_call_count", 0)
        st.max_tool_calls = data.get("max_tool_calls", 60)
        st.iteration = data.get("iteration", 0)
        st.max_iterations = data.get("max_iterations", 25)
        st.usage_cost_usd = data.get("usage_cost_usd", 0.0)
        st.budget_usd = data.get("budget_usd", 2.0)
        st.defect_list = data.get("defect_list", [])
        st.rejections = data.get("rejections", [])
        st.event_log = data.get("event_log", [])
        st.comparison_matrix = data.get("comparison_matrix", [])
        st.synthesis = data.get("synthesis", {})
        if data.get("draft_report"):
            st.draft_report = FinalReport(**data["draft_report"])
        st.qc_verdict = data.get("qc_verdict")
        st.limitations = data.get("limitations", [])
        st.incomplete = data.get("incomplete", False)
        st.incomplete_reason = data.get("incomplete_reason")
        st.repair_round = data.get("repair_round", 0)
        st.model_versions = data.get("model_versions", {})
        return st
