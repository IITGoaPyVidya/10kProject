"""FastAPI application factory."""
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.research import router as research_router
from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_var
from app.services.jobs import JobStore
from app.services.research_jobs import ResearchStore

log = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = JobStore(settings.job_ttl_seconds)
        app.state.research = ResearchStore(settings.job_ttl_seconds)
        app.state.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs,
                                                thread_name_prefix="job")
        if not settings.llm_configured:
            log.warning("NVIDIA_API_KEY is not set; LLM modes will be rejected.")
        yield
        app.state.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="AlphaInsight API", version="1.0.0", lifespan=lifespan)

    if settings.cors_origin_list:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                           allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    app.include_router(router)
    app.include_router(research_router)
    return app


app = create_app()
