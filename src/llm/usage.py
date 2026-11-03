"""Token and cost accounting per call, attributed to stage and run id."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# Approximate USD per 1M tokens (gpt-4o-mini class). Adjust when models change.
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "o4-mini": (1.10, 4.40),
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = PRICE_TABLE.get(model, (0.15, 0.60))
    return (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price


@dataclass
class CallUsage:
    run_id: str
    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    latency_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UsageTracker:
    run_id: str
    calls: list[CallUsage] = field(default_factory=list)

    def record(
        self,
        *,
        stage: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
    ) -> CallUsage:
        total = prompt_tokens + completion_tokens
        cost = estimate_cost(model, prompt_tokens, completion_tokens)
        entry = CallUsage(
            run_id=self.run_id,
            stage=stage,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
        self.calls.append(entry)
        return entry

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_tokens(self) -> int:
        return sum(c.total_tokens for c in self.calls)

    def summary(self) -> dict[str, Any]:
        by_stage: dict[str, dict[str, float | int]] = {}
        models: dict[str, str] = {}
        for c in self.calls:
            bucket = by_stage.setdefault(
                c.stage, {"tokens": 0, "cost_usd": 0.0, "calls": 0}
            )
            bucket["tokens"] = int(bucket["tokens"]) + c.total_tokens
            bucket["cost_usd"] = float(bucket["cost_usd"]) + c.cost_usd
            bucket["calls"] = int(bucket["calls"]) + 1
            models[c.stage] = c.model
        return {
            "run_id": self.run_id,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "call_count": len(self.calls),
            "by_stage": by_stage,
            "models_by_stage": models,
            "calls": [c.to_dict() for c in self.calls],
        }
