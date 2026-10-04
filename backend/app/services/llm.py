"""LLM engine: NVIDIA-hosted model via the OpenAI-compatible API, map-reduce for long documents."""
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from openai import OpenAI

from app.core.config import Settings
from app.services import prompts
from app.services.pdf import chunk_text

ProgressFn = Callable[[float, str], None]


class LlmError(RuntimeError):
    """Raised when the LLM backend fails after retries."""


def _chat(client: OpenAI, settings: Settings, user: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=settings.nvidia_model,
            messages=[{"role": "system", "content": prompts.SYSTEM_PROMPT},
                      {"role": "user", "content": user}],
            temperature=0.2,
            top_p=1,
            max_tokens=settings.llm_max_output_tokens,
            stream=False,
            extra_body={"chat_template_kwargs": {"enable_thinking": settings.llm_enable_thinking}},
        )
    except Exception as exc:  # SDK already retried 429/5xx with backoff
        raise LlmError(f"LLM request failed: {type(exc).__name__}: {exc}") from exc
    choice = resp.choices[0]
    if not (choice.message.content or "").strip():
        raise LlmError(f"LLM returned no content (finish_reason={choice.finish_reason}); "
                       "the model may have used its whole token budget on reasoning.")
    return choice.message.content


def run_llm_analysis(text: str, doc_type: str, settings: Settings,
                     on_progress: ProgressFn | None = None) -> str:
    """Short docs: one call. Long docs: parallel map over chunks -> (hierarchical merge) -> reduce."""
    progress = on_progress or (lambda *_: None)
    client = OpenAI(
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key.get_secret_value(),
        timeout=settings.llm_timeout_s,
        max_retries=settings.llm_max_retries,
    )
    kind, fmt = prompts.DOC_KIND[doc_type], prompts.REPORT_FORMATS[doc_type]

    if len(text) <= settings.single_pass_chars:
        progress(0.5, "Analyzing with LLM")
        return _chat(client, settings, prompts.SINGLE_PASS.format(fmt=fmt, doc=text))

    chunks = chunk_text(text, settings.chunk_chars)
    n = len(chunks)
    done = 0

    def map_one(arg: tuple[int, str]) -> str:
        nonlocal done
        i, chunk = arg
        out = _chat(client, settings, prompts.MAP.format(i=i + 1, n=n, kind=kind, doc=chunk))
        done += 1
        progress(0.1 + 0.75 * done / n, f"Analyzed section {done}/{n}")
        return out

    with ThreadPoolExecutor(max_workers=settings.llm_workers) as pool:
        notes = [x for x in pool.map(map_one, enumerate(chunks)) if x.strip().upper() not in ("", "NONE")]
    if not notes:
        return "No relevant content found by the model."

    combined = "\n\n".join(notes)
    while len(combined) > settings.reduce_max_chars:  # hierarchical merge for very long notes
        progress(0.88, "Condensing notes")
        groups = chunk_text(combined, settings.reduce_max_chars // 2)
        with ThreadPoolExecutor(max_workers=settings.llm_workers) as pool:
            merged = list(pool.map(lambda g: _chat(client, settings, prompts.MERGE.format(notes=g)), groups))
        new = "\n\n".join(merged)
        if len(new) >= len(combined):  # no progress; avoid an endless loop
            combined = new[: settings.reduce_max_chars]
            break
        combined = new

    progress(0.92, "Writing final report")
    return _chat(client, settings, prompts.REDUCE.format(kind=kind, fmt=fmt, notes=combined))
