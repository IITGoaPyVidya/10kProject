# AlphaInsight

Financial document analysis: earnings call transcripts and 10-K / annual reports.

- **backend/** FastAPI. Async job API, PDF + table extraction, NVIDIA LLM (map-reduce for long PDFs), optional local FinBERT.
- **frontend/** React + TypeScript (Vite), served by nginx, which also proxies `/api` to the backend.

Modes (UI sidebar): LLM only (default), Local only, Both.

## Run with Docker

```bash
cp .env.example .env        # set NVIDIA_API_KEY
docker compose up --build   # http://localhost:8080
```

To include FinBERT: set `INSTALL_LOCAL=true` in `.env` and rebuild.

## Local development

```bash
# backend
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements-dev.txt        # + requirements-local.txt for FinBERT
uvicorn app.main:app --reload              # http://localhost:8000/docs
pytest

# frontend
cd frontend && npm install && npm run dev  # http://localhost:5173
```

## Research Desk (multi-agent stock research)

Built on [LangGraph](https://github.com/langchain-ai/langgraph). Enter a ticker (optionally a concall PDF/YouTube link and an annual report PDF) and a team of agents runs:

```
concall | annual_report | fundamentals | technicals | news   (parallel)
                    -> bull_case | bear_case                  (debate)
                    -> portfolio_manager                      (final verdict)
```

Market data comes from Yahoo Finance via `yfinance` (use NSE symbols like `TCS` with exchange NSE, or `AAPL`). Agents with no input (e.g. no concall provided) are skipped, and the portfolio manager decides with what it has. Fundamentals, technicals and the manager fall back to rule-based scores if their LLM is unavailable.

### One folder per agent, each configured separately

```
backend/app/agents/
  defaults.yaml            shared defaults (provider, model, extra_body ...)
  concall/ annual_report/ fundamentals/ technicals/ news/ bull_case/ bear_case/ portfolio_manager/
    agent.py   logic (what data to gather, how to prompt)
    config.yaml  title, enabled, llm (base_url, model, api_key_env, temperature ...), params
    prompt.md  the agent's system prompt - edit it freely
```

Give an agent its own LLM by editing its `config.yaml`, e.g. a different provider:

```yaml
llm:
  base_url: https://api.openai.com/v1
  model: gpt-4.1-mini
  api_key_env: OPENAI_API_KEY   # set this in .env
  extra_body: null              # drop NVIDIA-specific request fields
```

Or override without touching files: `AGENT_TECHNICALS_MODEL=...`, `AGENT_NEWS_ENABLED=false` (also `_BASE_URL`, `_API_KEY_ENV`, `_TEMPERATURE`, `_MAX_TOKENS`).

To add an agent: create a folder with `agent.py` (subclass `BaseAgent`), `config.yaml`, `prompt.md`, then register the class in `app/agents/registry.py`.

Live smoke test without the UI: `python backend/scripts/smoke_research.py TCS.NS --concall samples/concall_july2026_tcs.pdf`.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/research/agents` | agent roster with each agent's model |
| POST | `/api/v1/research` | multipart: `ticker`, `exchange`, `horizon`, `agents`, `concall_pdf`, `concall_youtube`, `annual_report_pdf` -> 202 `{id}` |
| GET | `/api/v1/research/{id}?since=N` | agent states, new log events, reports, final verdict |

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/analyses` | multipart: `file`, `doc_type` (transcript/filing), `mode` (llm/local/both) -> 202 `{id}` |
| GET | `/api/v1/analyses/{id}` | status, progress, result |
| GET | `/api/v1/config` | which engines are available |
| GET | `/health/live`, `/health/ready` | probes |

The job store is in memory, so run a single backend worker (see `backend/app/services/jobs.py`).
