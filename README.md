# MarketMind AI

Autonomous business research agent for Verity Strategy Partners–style market intelligence briefs.

Built against the OpenAI API with **tool calling**, **structured outputs**, a bounded plan–act–observe loop (no agent framework), evidence provenance, quality control, and a mandatory human approval gate.

## Scenario

Primary deliverable: **S1 — AI customer support software**, backed by a curated local corpus under `data/corpus/` (26 documents: vendors, pricing, planted market-size contradiction, planted enterprise seat gap, planted prompt-injection page).

## Quick start

```bash
cd D:\langchain\Marketmind_ai
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env and set a valid OPENAI_API_KEY
```

### Open the app in your browser (Streamlit)

```powershell
cd D:\langchain\Marketmind_ai
.\.venv\Scripts\activate
$env:PYTHONPATH="D:\langchain\Marketmind_ai"
streamlit run app.py
```

Your browser should open at `http://localhost:8501`. Use **Start research**, review the draft, then **approve / reject / expand / rescope**.

Smoke test (CLI, one real API call):

```bash
set PYTHONPATH=D:\langchain\Marketmind_ai
python -m src.main smoke
```

Tool dispatcher demo (no successful LLM call required for adversarial cases):

```bash
python -m src.main demo-tools
```

Full research run (ends at human approval gate — approve / reject / expand / rescope):

```bash
python -m src.main research "Research the market for AI-powered customer support software and prepare a business intelligence report." --auto-assume
```

Unit tests + dispatcher eval:

```bash
python -m pytest tests -q
python evaluation\run_eval.py
```

## What was built (assignment map)

| Task | Location |
|------|----------|
| T01 Config, client, usage, logging | `src/config.py`, `src/llm/`, `src/logging_setup.py` |
| T02 Parameter discipline | `docs/technical_notes.md`, `show-messages` CLI |
| T03 Schemas + structured outputs | `src/schemas/` |
| T04 Analyser + planner | `src/agents/request_analyser.py`, `planner.py` |
| T05 Tools + dispatcher | `src/tools/` |
| T06 Agent loop + state | `src/agents/researcher.py`, `src/state/`, `src/pipeline.py` |
| T07 Evidence typing | `src/schemas/evidence.py`, `evidence_analyst.py`, `save_research` |
| T08 QC + repair | `src/agents/quality_control.py` |
| T09 Approval gate | `src/approval/cli_gate.py` |
| T10 Report | `src/agents/report_generator.py`, markdown under `runs/` |

## Hard constraints observed

- No agent framework — custom loop in `src/agents/researcher.py`
- Every tool call schema-validated before execution
- Never publishes without explicit human approval (no auto-approve flag)
- Secrets only from environment; `.env` git-ignored
- All loops bounded (iterations, tool calls, cost, repair rounds)

## Documentation

- `docs/api_verification.md` — API docs version/date verified against
- `docs/architecture.md` — component flow
- `docs/technical_notes.md` — temperatures, schema vs truth, tool abuse exercise
