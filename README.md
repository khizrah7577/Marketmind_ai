# MarketMind AI

Autonomous business research agent for Verity Strategy Partners–style market intelligence briefs.

Built against the OpenAI API with **tool calling**, **structured outputs**, a bounded plan–act–observe loop (no agent framework), evidence provenance, quality control, and a mandatory human approval gate.

## Scenario

Primary deliverable: **S1 — AI customer support software**, backed by a curated local corpus under `data/corpus/` (26 documents: vendors, pricing, planted market-size contradiction, planted enterprise seat gap, planted prompt-injection page).

## Open the app in your browser (Streamlit)

No `.env` API key is required to start the app. You connect your own OpenAI key in the UI.

```powershell
cd D:\langchain\Marketmind_ai
.\.venv\Scripts\activate
$env:PYTHONPATH="D:\langchain\Marketmind_ai"
streamlit run app.py
```

1. Open `http://localhost:8501`
2. Paste your OpenAI API key (password field) → **Connect OpenAI**
3. Get a key at https://platform.openai.com/api-keys
4. Start research, review the draft, then **approve / reject / expand / rescope**
5. Use **Disconnect API key** in the sidebar to clear the key from the session

The key is kept only in `st.session_state` for the active browser session. It is never written to disk, GitHub, or source code.

## Optional CLI setup

CLI commands still accept `OPENAI_API_KEY` from the environment or a local `.env` (git-ignored):

```powershell
copy .env.example .env
# edit .env with your key — local only
python -m src.main smoke
python -m src.main demo-tools
python -m src.main research "Research the market for AI-powered customer support software..." --auto-assume
```

## Tests

```powershell
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
| Runtime API auth | `src/auth/`, `app.py` connect screen |

## Hard constraints observed

- No agent framework — custom loop in `src/agents/researcher.py`
- Every tool call schema-validated before execution
- Never publishes without explicit human approval (no auto-approve flag)
- User API keys only in session (Streamlit) or local env (CLI); never committed
- All loops bounded (iterations, tool calls, cost, repair rounds)

## Documentation

- `docs/api_verification.md` — API docs version/date verified against
- `docs/architecture.md` — component flow
- `docs/technical_notes.md` — temperatures, schema vs truth, tool abuse exercise
