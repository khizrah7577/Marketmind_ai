"""CLI entry point for MarketMind AI."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import typer
from rich.console import Console

from src.config import get_settings
from src.llm.client import LLMClient
from src.llm.usage import UsageTracker
from src.logging_setup import setup_logging
from src.pipeline import Pipeline
from src.tools.dispatcher import ToolDispatcher
from src.tools.registry import build_default_registry
from src.state.research_state import ResearchState

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _require_cli_key():
    settings = get_settings()
    if not settings.has_api_key():
        console.print(
            "[red]No OpenAI API key configured.[/red] "
            "For CLI use, set OPENAI_API_KEY in the environment or a local .env file. "
            "For the web app, connect a key in the Streamlit UI instead."
        )
        raise typer.Exit(code=1)
    return settings


@app.command()
def smoke() -> None:
    """One real API call: model, tokens, cost; masked key."""
    from src.llm.client import LLMError

    settings = _require_cli_key()
    setup_logging(settings.log_level)
    console.print(f"api_key (masked): {settings.masked_key()}")
    usage = UsageTracker(run_id=f"smoke_{uuid4().hex[:8]}")
    client = LLMClient(settings, usage)
    try:
        result = client.chat(
            stage="analyser",
            system="You are a smoke-test assistant. Reply with exactly: PONG",
            user="ping",
            temperature=0,
        )
    except LLMError as e:
        console.print(f"[red]smoke failed:[/red] {e}")
        raise typer.Exit(code=1) from e
    console.print(f"model: {result['model']}")
    console.print(f"content: {result['content']!r}")
    console.print(f"tokens: {result['usage'].total_tokens}")
    console.print(f"cost_usd: {result['usage'].cost_usd:.6f}")


@app.command()
def research(
    request: str = typer.Argument(..., help="Natural-language research request"),
    auto_assume: bool = typer.Option(
        False,
        "--auto-assume",
        help="Continue past clarification using recorded assumptions",
    ),
) -> None:
    """Full pipeline ending in human approval gate."""
    settings = _require_cli_key()
    setup_logging(settings.log_level)
    if len(request) > settings.max_request_chars:
        raise typer.BadParameter(f"Request too long (>{settings.max_request_chars})")
    pipe = Pipeline(settings)
    state = pipe.run(request, auto_assume=auto_assume)
    console.print(f"\nRun complete: {state.run_id}")
    if state.draft_report and state.draft_report.approval:
        console.print(f"Decision: {state.draft_report.approval.decision}")
    console.print(f"Artefacts under runs/{state.run_id}/")


@app.command("demo-tools")
def demo_tools() -> None:
    """Adversarial + happy-path tool dispatcher demo (no LLM required for errors)."""
    settings = get_settings()
    setup_logging(settings.log_level)
    state = ResearchState(run_id="tool_demo", max_tool_calls=100)
    dispatcher = ToolDispatcher(build_default_registry(), state)

    # Happy path search
    ok = dispatcher.dispatch(
        "search_information",
        {"query": "Zendesk pricing", "source_type": "pricing", "max_results": 5},
    )
    console.print("search ok:", ok.get("ok"), "count:", ok.get("count"))

    # Calculate
    calc = dispatcher.dispatch(
        "calculate_metric",
        {"operation": "growth_rate", "values": [5.1, 8.2]},
    )
    console.print("calc:", calc.get("result"), calc.get("formula"))

    # Adversarial: unknown tool
    e1 = dispatcher.dispatch("fly_to_moon", {"x": 1})
    console.print("unknown_tool:", e1.get("error"))

    # Malformed JSON
    e2 = dispatcher.dispatch("search_information", "{not json")
    console.print("malformed_json:", e2.get("error"))

    # Out of bounds
    e3 = dispatcher.dispatch(
        "search_information",
        {"query": "pricing", "source_type": "pricing", "max_results": 500},
    )
    console.print("schema_validation:", e3.get("error"), e3.get("message"))

    # Unresolvable save
    e4 = dispatcher.dispatch(
        "save_research",
        {
            "question_id": "q1",
            "claim": "Invented fact with fake citation",
            "claim_type": "fact",
            "source_ref": "tr_does_not_exist",
            "confidence": "high",
        },
    )
    console.print("unresolvable_source:", e4.get("error"))
    console.print("rejections logged:", len(state.rejections))


@app.command()
def show_messages() -> None:
    """Demonstrate context assembly: print exact message list for one call."""
    settings = _require_cli_key()
    setup_logging(settings.log_level)
    usage = UsageTracker(run_id="msg_demo")
    client = LLMClient(settings, usage)
    result = client.chat(
        stage="planner",
        system="You are a planner. Reply briefly.",
        user="List one research question about AI support software pricing.",
        temperature=0.2,
    )
    console.print(json.dumps(result["messages_sent"], indent=2))
    console.print("response:", result["content"])


if __name__ == "__main__":
    # Allow `python -m src.main`
    app()
