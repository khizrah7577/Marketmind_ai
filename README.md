# MarketMind AI

Autonomous market intelligence platform: plan → tool-calling research loop → evidence provenance → QC → human approval.

Built with the **official OpenAI SDK** (no CrewAI / LangChain agent frameworks), a curated local corpus, SQLite history, and a multi-page Streamlit dashboard.

## Quick start

```powershell
cd D:\langchain\Marketmind_ai
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH="D:\langchain\Marketmind_ai"
streamlit run app.py
```

1. Open the app (Dashboard works without a key).
2. Go to **Settings** → enter your OpenAI API key → **Connect OpenAI**.
3. Use **Research Studio** to launch a real research run.
4. Review **Quality Control**, **Reports** (approve/reject/expand/rescope), **Evidence Explorer**, etc.

Optional CLI: copy `.env.example` → `.env` for `python -m src.main smoke`.

## Pages

| Page | Purpose |
|------|---------|
| Dashboard | KPIs + charts from SQLite (demo seed if empty) |
| Research Studio | Scope form + live stage progress + real pipeline |
| Research Plan | Objectives / sub-questions |
| Competitor Intelligence | Matrix + coverage charts |
| Market Analytics | Claim mix + deterministic calculator |
| Evidence Explorer | Filterable provenance |
| Quality Control | Defect list / repair rounds |
| Reports | Preview, Markdown/PDF export, human gate |
| Research History | Open / compare runs |
| Evaluation Center | 18-case catalog + automated dispatcher suite |
| Settings | Runtime key + model/limit display |

## Architecture

- Agents: `src/agents/*` (manual plan–act–observe in `researcher.py`)
- Tools + dispatcher: `src/tools/*`
- Services: `src/services/*`
- Persistence: `runs/<id>/` + `database/marketmind.db` (gitignored)
- UI: `ui/pages/*`, theme `ui/styles/theme.css`

## Streamlit Cloud

**Repo:** https://github.com/khizrah7577/Marketmind_ai  
**Entry point:** `app.py` · **Branch:** `master` · **Working directory:** repository root

### Deploy steps

1. Sign in at [share.streamlit.io](https://share.streamlit.io/) with the GitHub account that owns `khizrah7577/Marketmind_ai`.
2. **Create app** → select repository `Marketmind_ai` → branch `master` → main file `app.py`.
3. (Optional) **Advanced settings → Secrets** — add only if you want a server-side key:
   ```toml
   OPENAI_API_KEY = "sk-..."
   ```
   Prefer leaving secrets empty and connecting the key in **Settings** at runtime (session-only).
4. Click **Deploy**. Wait for the build to finish and open the live URL.
5. Smoke-test: connect API key → Dashboard KPIs → Research Studio (demo or live) → Report Studio approval gate.

### Persistence note

Streamlit Community Cloud uses ephemeral containers. Local SQLite under `database/` and `runs/` may reset on redeploy. For durable history, use an external store or re-seed demo data after redeploy. Runtime API keys are never written to disk.

### Security

Do **not** commit `.env`, API keys, or `database/marketmind.db`. Keys belong in Streamlit Secrets or the in-app Settings session only.

## Tests

```powershell
pytest tests -q
python evaluation/run_eval.py
```
