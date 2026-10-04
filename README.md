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

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/analyses` | multipart: `file`, `doc_type` (transcript/filing), `mode` (llm/local/both) -> 202 `{id}` |
| GET | `/api/v1/analyses/{id}` | status, progress, result |
| GET | `/api/v1/config` | which engines are available |
| GET | `/health/live`, `/health/ready` | probes |

The job store is in memory, so run a single backend worker (see `backend/app/services/jobs.py`).
