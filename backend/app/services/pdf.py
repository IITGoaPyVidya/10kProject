"""PDF extraction (text + tables as Markdown) and text chunking."""
import io
import re
from dataclasses import dataclass
from typing import Callable

import pdfplumber
from pypdf import PdfReader


@dataclass
class ParsedDocument:
    text: str
    pages: int


def _table_to_markdown(table: list[list]) -> str:
    """Render a pdfplumber table as Markdown so the LLM keeps row/column structure."""
    rows = [[(c or "").replace("\n", " ").strip() for c in row] for row in table if row]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def extract_document(
    pdf_bytes: bytes,
    include_tables: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> ParsedDocument:
    """Extract text per page with [PAGE n] markers; tables are appended as Markdown."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total = len(reader.pages)
    plumber = pdfplumber.open(io.BytesIO(pdf_bytes)) if include_tables else None
    out: list[str] = []
    try:
        for n, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:  # one malformed page must not abort the document
                text = ""
            block = f"\n[PAGE {n}]\n{text}"
            if plumber is not None:
                try:
                    ppage = plumber.pages[n - 1]
                    tables = [t for t in (_table_to_markdown(t) for t in ppage.extract_tables()) if t]
                    ppage.flush_cache()  # keep memory flat on 300+ page files
                    if tables:
                        block += "\n[TABLES ON THIS PAGE]\n" + "\n\n".join(tables)
                except Exception:
                    pass
            out.append(block)
            if on_progress:
                on_progress(n, total)
    finally:
        if plumber is not None:
            plumber.close()
    text = "\n".join(out)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text).strip()
    return ParsedDocument(text=text, pages=total)


def has_content(text: str) -> bool:
    """True if the document has any text beyond page/time markers."""
    return bool(re.sub(r"\[PAGE \d+\]|\[TIME [\d:]+\]", "", text).strip())


def split_sentences(text: str, min_chars: int = 25) -> list[str]:
    """Split into sentences; short fragments, page markers and table rows are dropped."""
    text = re.sub(r"\[PAGE \d+\]|\[TIME [\d:]+\]|\[TABLES ON THIS PAGE\]", " ", text)
    text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("|"))
    flat = re.sub(r"\s*\n\s*", " ", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])", flat)
    return [p.strip() for p in parts if len(p.strip()) >= min_chars]


def chunk_text(text: str, max_chars: int) -> list[str]:
    """Greedily pack lines into chunks <= max_chars so pages/tables are rarely split mid-line."""
    chunks: list[str] = []
    cur: list[str] = []
    size = 0
    for line in text.splitlines():
        while len(line) > max_chars:  # pathological single line
            if cur:
                chunks.append("\n".join(cur))
                cur, size = [], 0
            chunks.append(line[:max_chars])
            line = line[max_chars:]
        if size + len(line) + 1 > max_chars and cur:
            chunks.append("\n".join(cur))
            cur, size = [], 0
        cur.append(line)
        size += len(line) + 1
    if cur:
        chunks.append("\n".join(cur))
    return chunks
