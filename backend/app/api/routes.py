"""HTTP routes: health, config, and the analysis job API."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.services.jobs import JobStore
from app.services.pipeline import run_job

router = APIRouter()

DocType = Literal["transcript", "filing"]
Mode = Literal["llm", "local", "both"]


class ConfigResponse(BaseModel):
    llm_configured: bool
    llm_model: str
    local_model_available: bool
    max_upload_mb: int


class JobCreated(BaseModel):
    id: str
    status: str


class JobResponse(BaseModel):
    id: str
    status: str
    progress: float
    message: str
    doc_type: str
    mode: str
    filename: str
    error: str | None = None
    result: dict[str, Any] | None = None


def get_store(request: Request) -> JobStore:
    return request.app.state.store


def get_executor(request: Request) -> ThreadPoolExecutor:
    return request.app.state.executor


@router.get("/health/live", tags=["health"])
def live() -> dict:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
def ready() -> dict:
    return {"status": "ok"}


@router.get("/api/v1/config", response_model=ConfigResponse, tags=["meta"])
def config(settings: Annotated[Settings, Depends(get_settings)]) -> ConfigResponse:
    return ConfigResponse(
        llm_configured=settings.llm_configured,
        llm_model=settings.nvidia_model,
        local_model_available=settings.local_model_available,
        max_upload_mb=settings.max_upload_mb,
    )


async def _read_pdf(file: UploadFile, max_bytes: int) -> bytes:
    """Read the upload in chunks, enforcing the size limit and a PDF magic-number check."""
    buf = bytearray()
    while chunk := await file.read(1 << 20):
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise HTTPException(413, f"File exceeds the {max_bytes // (1 << 20)} MB limit.")
    if not buf.startswith(b"%PDF-"):
        raise HTTPException(415, "Only PDF files are accepted.")
    return bytes(buf)


@router.post("/api/v1/analyses", response_model=JobCreated, status_code=202, tags=["analyses"])
async def create_analysis(
    file: Annotated[UploadFile, File()],
    doc_type: Annotated[DocType, Form()],
    mode: Annotated[Mode, Form()] = "llm",
    settings: Settings = Depends(get_settings),
    store: JobStore = Depends(get_store),
    executor: ThreadPoolExecutor = Depends(get_executor),
) -> JobCreated:
    if mode in ("llm", "both") and not settings.llm_configured:
        raise HTTPException(400, "NVIDIA_API_KEY is not configured on the server.")
    if mode in ("local", "both") and doc_type == "transcript" and not settings.local_model_available:
        raise HTTPException(400, "Local FinBERT is not installed in this deployment "
                                 "(build the backend with INSTALL_LOCAL=true).")

    data = await _read_pdf(file, settings.max_upload_mb * (1 << 20))

    cache_key = hashlib.sha256(data).hexdigest() + f":{doc_type}:{mode}:{settings.nvidia_model}"
    cached = store.find_cached(cache_key)
    if cached:
        return JobCreated(id=cached.id, status=cached.status)

    if store.pending_count() >= settings.max_queued_jobs:
        raise HTTPException(429, "Server is busy; try again shortly.", headers={"Retry-After": "30"})

    job = store.create(doc_type, mode, (file.filename or "document.pdf")[:200], cache_key)
    executor.submit(run_job, store, job.id, data, settings)
    return JobCreated(id=job.id, status=job.status)


@router.get("/api/v1/analyses/{job_id}", response_model=JobResponse, tags=["analyses"])
def get_analysis(job_id: str, store: JobStore = Depends(get_store)) -> JobResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(404, "Analysis not found or expired.")
    return JobResponse(id=job.id, status=job.status, progress=job.progress, message=job.message,
                       doc_type=job.doc_type, mode=job.mode, filename=job.filename,
                       error=job.error, result=job.result)
