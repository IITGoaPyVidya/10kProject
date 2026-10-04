"""Analysis pipeline executed in a worker thread for each job."""
import logging

from app.core.config import Settings
from app.services.finbert import LocalModelUnavailable, run_local_finbert
from app.services.jobs import JobStore
from app.services.llm import LlmError, run_llm_analysis
from app.services.pdf import extract_document, has_content
from app.services.red_flags import scan_red_flags

log = logging.getLogger(__name__)

MODES = ("llm", "local", "both")


def run_job(store: JobStore, job_id: str, pdf_bytes: bytes, settings: Settings) -> None:
    job = store.get(job_id)
    if job is None:
        return
    doc_type, mode = job.doc_type, job.mode
    use_llm, use_local = mode in ("llm", "both"), mode in ("local", "both")

    def progress(p: float, msg: str) -> None:
        store.update(job_id, progress=round(min(p, 0.99), 3), message=msg)

    try:
        store.update(job_id, status="processing", message="Reading PDF")
        doc = extract_document(
            pdf_bytes, on_progress=lambda n, t: progress(0.1 * n / t, f"Reading PDF page {n}/{t}"))
        if not has_content(doc.text):
            raise ValueError("No extractable text found (scanned PDF? OCR is not supported).")

        result: dict = {"stats": {"pages": doc.pages, "chars": len(doc.text)}}

        if use_local:
            progress(0.1, "Running local analysis")
            if doc_type == "transcript":
                result["sentiment"] = run_local_finbert(doc.text, settings)
            else:
                result["red_flags"] = scan_red_flags(doc.text)

        if use_llm:
            result["llm"] = {
                "model": settings.nvidia_model,
                "report_markdown": run_llm_analysis(doc.text, doc_type, settings, progress),
            }

        store.update(job_id, status="completed", progress=1.0, message="Done", result=result)
        log.info("job %s completed (%d pages, mode=%s)", job_id, doc.pages, mode)
    except (LlmError, LocalModelUnavailable, ValueError) as exc:
        log.warning("job %s failed: %s", job_id, exc)
        store.update(job_id, status="failed", error=str(exc), message="Failed")
    except Exception:
        log.exception("job %s crashed", job_id)
        store.update(job_id, status="failed", error="Internal error while processing the document.",
                     message="Failed")
