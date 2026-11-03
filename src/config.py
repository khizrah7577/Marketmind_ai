"""Validated settings: models, temperatures, budgets, caps."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

StageName = Literal[
    "analyser",
    "planner",
    "researcher",
    "evidence",
    "comparison",
    "synthesis",
    "qc",
    "report",
]

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CORPUS_DIR = DATA_DIR / "corpus"
RUNS_DIR = ROOT_DIR / "runs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_base_url: str | None = Field(default=None, alias="OPENAI_BASE_URL")

    model_analyser: str = Field(default="gpt-4o-mini", alias="MODEL_ANALYSER")
    model_planner: str = Field(default="gpt-4o-mini", alias="MODEL_PLANNER")
    model_researcher: str = Field(default="gpt-4o-mini", alias="MODEL_RESEARCHER")
    model_evidence: str = Field(default="gpt-4o-mini", alias="MODEL_EVIDENCE")
    model_comparison: str = Field(default="gpt-4o-mini", alias="MODEL_COMPARISON")
    model_synthesis: str = Field(default="gpt-4o-mini", alias="MODEL_SYNTHESIS")
    model_qc: str = Field(default="gpt-4o-mini", alias="MODEL_QC")
    model_report: str = Field(default="gpt-4o-mini", alias="MODEL_REPORT")

    # Temperatures chosen from Task 02 experiment rationale (see docs/technical_notes.md)
    temp_analyser: float = 0.2
    temp_planner: float = 0.3
    temp_researcher: float = 0.2
    temp_evidence: float = 0.1
    temp_comparison: float = 0.1
    temp_synthesis: float = 0.4
    temp_qc: float = 0.1
    temp_report: float = 0.3

    max_iterations: int = Field(default=25, alias="MAX_ITERATIONS")
    max_tool_calls: int = Field(default=60, alias="MAX_TOOL_CALLS")
    max_repair_rounds: int = Field(default=2, alias="MAX_REPAIR_ROUNDS")
    run_budget_usd: float = Field(default=2.0, alias="RUN_BUDGET_USD")
    request_timeout_seconds: float = Field(default=60.0, alias="REQUEST_TIMEOUT_SECONDS")
    max_retries: int = Field(default=4, alias="MAX_RETRIES")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    max_request_chars: int = 4000

    @field_validator("openai_api_key")
    @classmethod
    def key_must_exist(cls, v: str) -> str:
        if not v or v.strip() in {"", "sk-your-key-here"}:
            raise ValueError(
                "OPENAI_API_KEY is missing or still the placeholder. "
                "Copy .env.example to .env and set a real key."
            )
        return v.strip()

    def model_for(self, stage: StageName) -> str:
        return getattr(self, f"model_{stage}")

    def temperature_for(self, stage: StageName) -> float:
        return getattr(self, f"temp_{stage}")

    def masked_key(self) -> str:
        k = self.openai_api_key
        if len(k) < 12:
            return "***"
        return f"{k[:7]}...{k[-4:]}"


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as exc:
        msg = str(exc)
        if "OPENAI_API_KEY" in msg or "openai_api_key" in msg:
            raise SystemExit(
                "FATAL: required environment variable OPENAI_API_KEY is missing or invalid. "
                "Create .env from .env.example and set OPENAI_API_KEY."
            ) from exc
        raise
