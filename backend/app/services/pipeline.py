"""Analysis pipelines executed in a worker thread for each job (PDF upload or YouTube link)."""
import logging

from app.core.config import Settings
from app.services.finbert import LocalModelUnavailable, run_local_finbert
from app.services.jobs import JobStore
from app.services.llm import LlmError, run_llm_analysis
from app.services.pdf import extract_document, has_content
from app.services.red_flags import scan_red_flags
from app.services.youtube import extract_video_id, fetch_transcript

log = logging.getLogger(__name__)

MODES = ("llm", "local", "both")


def _analyze(store: JobStore, job_id: str, text: str, result: dict, settings: Settings) -> None:
    """Shared analysis stage: local engine and/or LLM over already-extracted text."""
    job = store.get(job_id)
    if job is None:
        return
    use_llm, use_local = job.mode in ("llm", "both"), job.mode in ("local", "both")

    def progress(p: float, msg: str) -> None:
        store.update(job_id, progress=round(min(p, 0.99), 3), message=msg)

    if use_local:
        progress(0.1, "Running local analysis")
        if job.doc_type == "transcript":
            result["sentiment"] = run_local_finbert(text, settings)
        else:
            result["red_flags"] = scan_red_flags(text)

    if use_llm:
        result["llm"] = {
            "model": settings.nvidia_model,
            "report_markdown": run_llm_analysis(text, job.doc_type, settings, progress),
        }
    store.update(job_id, status="completed", progress=1.0, message="Done", result=result)


def _guarded(store: JobStore, job_id: str, work) -> None:
    try:
        store.update(job_id, status="processing", message="Starting")
        work()
        log.info("job %s completed", job_id)
    except (LlmError, LocalModelUnavailable, ValueError) as exc:
        log.warning("job %s failed: %s", job_id, exc)
        store.update(job_id, status="failed", error=str(exc), message="Failed")
    except Exception:
        log.exception("job %s crashed", job_id)
        store.update(job_id, status="failed", error="Internal error while processing the document.",
                     message="Failed")


def run_job(store: JobStore, job_id: str, pdf_bytes: bytes, settings: Settings) -> None:
    def work() -> None:
        def on_page(n: int, t: int) -> None:
            store.update(job_id, progress=round(0.1 * n / t, 3), message=f"Reading PDF page {n}/{t}")

        doc = extract_document(pdf_bytes, on_progress=on_page)
        if not has_content(doc.text):
            raise ValueError("No extractable text found (scanned PDF? OCR is not supported).")
        result = {"stats": {"pages": doc.pages, "chars": len(doc.text)}}
        _analyze(store, job_id, doc.text, result, settings)

    _guarded(store, job_id, work)


def run_youtube_job(store: JobStore, job_id: str, url: str, settings: Settings) -> None:
    def work() -> None:
        store.update(job_id, message="Fetching transcript", progress=0.05)
        video_id = extract_video_id(url)
        t = fetch_transcript(video_id)
        if not has_content(t["text"]):
            raise ValueError("The transcript is empty.")
        result = {
            "stats": {"source": "youtube", "video_id": video_id, "segments": t["segments"],
                      "duration_s": t["duration_s"], "chars": len(t["text"])},
            "transcript": t["display"],
        }
        # Publish the transcript right away so the UI can show it while analysis runs.
        store.update(job_id, result=dict(result), progress=0.1, message="Transcript ready, analyzing")
        _analyze(store, job_id, t["text"], result, settings)

    _guarded(store, job_id, work)
