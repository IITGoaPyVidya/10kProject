"""Runs one research job: ingest documents, then execute the LangGraph agent workflow."""
import logging

from app.agents.registry import build_graph, load_agents
from app.core.config import Settings
from app.services.pdf import extract_document, has_content
from app.services.research_jobs import ResearchStore
from app.services.youtube import extract_video_id, fetch_transcript

log = logging.getLogger(__name__)
SYSTEM = "system"


def run_research(store: ResearchStore, job_id: str, *, agent_names: list[str], concall_pdf: bytes | None,
                 annual_pdf: bytes | None, youtube_url: str | None, settings: Settings) -> None:
    job = store.get(job_id)
    if job is None:
        return

    def emit(agent: str, message: str, level: str = "info", kind: str = "log", **fields) -> None:
        store.emit(job_id, agent, message, level, kind, **fields)

    try:
        store.set_status(job_id, "running")
        emit(SYSTEM, f"Research desk opened for {job.ticker}", kind="log")

        concall_text = ""
        if concall_pdf:
            emit(SYSTEM, "Reading earnings call PDF")
            doc = extract_document(concall_pdf, include_tables=False)
            concall_text = doc.text if has_content(doc.text) else ""
            emit(SYSTEM, f"Earnings call: {doc.pages} pages, {len(concall_text):,} characters", level="success")
        elif youtube_url:
            emit(SYSTEM, "Fetching YouTube transcript")
            t = fetch_transcript(extract_video_id(youtube_url))
            concall_text = t["text"]
            emit(SYSTEM, f"Transcript: {t['duration_s'] // 60} min, {len(concall_text):,} characters", level="success")

        annual_text = ""
        if annual_pdf:
            emit(SYSTEM, "Reading annual report PDF (extracting tables too)")
            last = {"n": 0}

            def on_page(n: int, total: int) -> None:
                if n - last["n"] >= 25 or n == total:
                    last["n"] = n
                    emit(SYSTEM, f"Annual report: page {n}/{total}")

            doc = extract_document(annual_pdf, on_progress=on_page)
            annual_text = doc.text if has_content(doc.text) else ""
            emit(SYSTEM, f"Annual report: {doc.pages} pages, {len(annual_text):,} characters", level="success")

        agents = load_agents()
        chosen = [agents[n] for n in agent_names if n in agents]
        graph = build_graph(chosen, emit, on_report=lambda n, r: store.set_report(job_id, n, r))
        emit(SYSTEM, f"Dispatching {len(chosen)} agents", kind="log")

        state = {"ticker": job.ticker, "company": job.company, "horizon": job.horizon,
                 "concall_text": concall_text, "annual_text": annual_text, "reports": {}}
        result = graph.invoke(state)

        reports = result["reports"]
        for name, rep in reports.items():
            store.set_report(job_id, name, rep)
        final = reports.get("portfolio_manager")
        emit(SYSTEM, "Research complete", level="success", kind="log")
        store.complete(job_id, final)
        log.info("research %s completed for %s", job_id, job.ticker)
    except Exception as exc:
        log.exception("research %s failed", job_id)
        msg = str(exc) if isinstance(exc, ValueError) else "Internal error while running the research."
        emit(SYSTEM, msg, level="error")
        store.set_status(job_id, "failed", msg)
