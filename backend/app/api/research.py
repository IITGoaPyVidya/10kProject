"""HTTP routes for the multi-agent stock research desk."""
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from app.agents.registry import load_agents
from app.agents.tools import market_data
from app.agents.tools.market_data import normalize_ticker
from app.api.routes import _read_pdf
from app.core.config import Settings, get_settings
from app.services.research_jobs import ResearchStore
from app.services.research_pipeline import run_research
from app.services.youtube import extract_video_id

router = APIRouter(prefix="/api/v1/research", tags=["research"])

_TICKER_RE = re.compile(r"^[A-Za-z0-9.^=&-]{1,20}$")


class AgentInfo(BaseModel):
    name: str
    title: str
    description: str
    stage: str
    enabled: bool
    model: str
    needs: str
    llm_ready: bool


class SymbolMatch(BaseModel):
    symbol: str
    name: str
    exchange: str
    type: str | None = None


class ResearchCreated(BaseModel):
    id: str


class ResearchResponse(BaseModel):
    id: str
    ticker: str
    company: str
    horizon: str
    status: str
    progress: float
    agents: dict[str, dict[str, Any]]
    events: list[dict[str, Any]]
    next_index: int
    reports: dict[str, dict[str, Any]]
    final: dict[str, Any] | None = None
    error: str | None = None
    started_at: float
    elapsed_s: float


def get_store(request: Request) -> ResearchStore:
    return request.app.state.research


def get_executor(request: Request) -> ThreadPoolExecutor:
    return request.app.state.executor


@router.get("/agents", response_model=list[AgentInfo])
def list_agents() -> list[AgentInfo]:
    """Agent roster with each agent's configured model (never any keys)."""
    return [AgentInfo(name=a.name, title=a.config.title, description=a.config.description, stage=a.stage,
                      enabled=a.config.enabled, model=a.config.llm.model, needs=a.needs,
                      llm_ready=bool(a.config.llm.api_key))
            for a in load_agents().values()]


@router.get("/search", response_model=list[SymbolMatch])
async def search_symbols(q: Annotated[str, Query(min_length=1, max_length=60)],
                         prefer: Annotated[Literal["NSE", "BSE", ""], Query()] = "") -> list[SymbolMatch]:
    """Closest stock matches for what the user has typed so far (powers the ticker autocomplete)."""
    return [SymbolMatch(**m) for m in await run_in_threadpool(market_data.search_symbols, q, prefer)]


@router.post("", response_model=ResearchCreated, status_code=202)
async def start_research(
    ticker: Annotated[str, Form()],
    exchange: Annotated[Literal["NSE", "BSE", "US", "AS_TYPED"], Form()] = "NSE",
    company: Annotated[str, Form(max_length=100)] = "",
    horizon: Annotated[Literal["short", "medium", "long"], Form()] = "medium",
    agents: Annotated[str, Form(description="comma-separated agent names; empty = all enabled")] = "",
    concall_youtube: Annotated[str, Form(max_length=300)] = "",
    concall_pdf: Annotated[UploadFile | None, File()] = None,
    annual_report_pdf: Annotated[UploadFile | None, File()] = None,
    settings: Settings = Depends(get_settings),
    store: ResearchStore = Depends(get_store),
    executor: ThreadPoolExecutor = Depends(get_executor),
) -> ResearchCreated:
    ticker = ticker.strip()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(400, "Enter a valid ticker symbol (letters, digits, '.', '-').")
    ticker = normalize_ticker(ticker, exchange)

    available = load_agents()
    requested = [n.strip() for n in agents.split(",") if n.strip()]
    unknown = [n for n in requested if n not in available]
    if unknown:
        raise HTTPException(400, f"Unknown agents: {', '.join(unknown)}")
    chosen = requested or [n for n, a in available.items() if a.config.enabled]
    if not any(available[n].stage == "analyst" for n in chosen):
        raise HTTPException(400, "Select at least one analyst agent.")
    if not any(available[n].config.llm.api_key for n in chosen):
        raise HTTPException(400, "No LLM API key configured for the selected agents (set NVIDIA_API_KEY).")

    yt = concall_youtube.strip()
    if yt:
        try:
            extract_video_id(yt)
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    if not await run_in_threadpool(market_data.symbol_exists, ticker):
        typed = ticker.split(".")[0]
        close = await run_in_threadpool(market_data.search_symbols, typed, exchange if exchange in ("NSE", "BSE") else "")
        raise HTTPException(404, {"message": f"No market data found for '{ticker}'.", "suggestions": close})

    limit = settings.max_upload_mb * (1 << 20)
    concall_bytes = await _read_pdf(concall_pdf, limit) if concall_pdf and concall_pdf.filename else None
    annual_bytes = await _read_pdf(annual_report_pdf, limit) if annual_report_pdf and annual_report_pdf.filename else None

    if store.pending_count() >= settings.max_queued_jobs:
        raise HTTPException(429, "Server is busy; try again shortly.", headers={"Retry-After": "30"})

    meta = {n: {"title": available[n].config.title, "stage": available[n].stage,
                "model": available[n].config.llm.model} for n in chosen}
    job = store.create(ticker, company.strip(), horizon, meta)
    executor.submit(run_research, store, job.id, agent_names=chosen, concall_pdf=concall_bytes,
                    annual_pdf=annual_bytes, youtube_url=yt or None, settings=settings)
    return ResearchCreated(id=job.id)


@router.get("/{job_id}", response_model=ResearchResponse)
def get_research(job_id: str, since: Annotated[int, Query(ge=0)] = 0,
                 store: ResearchStore = Depends(get_store)) -> ResearchResponse:
    snap = store.snapshot(job_id, since)
    if snap is None:
        raise HTTPException(404, "Research run not found or expired.")
    return ResearchResponse(**snap)
