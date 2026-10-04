"""Map step for long documents: condense a big text into focused notes using the agent's own LLM."""
from concurrent.futures import ThreadPoolExecutor

from app.agents.base import Emit
from app.agents.llm import LLM
from app.services.pdf import chunk_text

MAP_SYSTEM = "You are a meticulous equity research assistant. Use ONLY the supplied text. Be concise and factual."

MAP_USER = """You are reading part {i} of {n} of a {kind}. Extract concise bullet-point NOTES (max ~400 words) \
relevant to this focus: {focus}
Include (p.N) page citations or [mm:ss] timestamps when markers are present, short verbatim quotes, and key \
table figures with values and periods. If nothing is relevant, reply 'NONE'.

TEXT:
{doc}"""


def condense(text: str, llm: LLM, *, agent: str, kind: str, focus: str, emit: Emit,
             single_pass_chars: int = 100_000, chunk_chars: int = 60_000, workers: int = 4,
             max_notes_chars: int = 100_000) -> str:
    """Return the text itself if short, otherwise merged per-chunk notes."""
    if len(text) <= single_pass_chars:
        return text
    chunks = chunk_text(text, chunk_chars)
    n = len(chunks)
    emit(agent, f"Long document ({len(text):,} chars): reading in {n} sections", kind="log")
    done = 0

    def one(arg: tuple[int, str]) -> str:
        nonlocal done
        i, chunk = arg
        out = llm.complete(MAP_SYSTEM, MAP_USER.format(i=i + 1, n=n, kind=kind, focus=focus, doc=chunk))
        done += 1
        emit(agent, f"Read section {done}/{n}", kind="log")
        return out

    with ThreadPoolExecutor(max_workers=workers) as pool:
        notes = [x for x in pool.map(one, enumerate(chunks)) if x.strip().upper() != "NONE"]
    return "\n\n".join(notes)[:max_notes_chars]
