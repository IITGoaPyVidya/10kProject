"""Prompt templates for the LLM engine (map-reduce for long documents)."""

SYSTEM_PROMPT = """You are an adversarial hedge fund analyst. You are skeptical, precise, \
and you distrust management spin. Use ONLY the supplied text; never invent facts or numbers. \
Cite page numbers as (p.N) using the [PAGE N] markers. Tables appear as Markdown; read the \
numbers carefully and compute year-over-year changes where useful. If there is no evidence \
for a point, omit it."""

REPORT_FORMATS = {
    "transcript": """Output Markdown with exactly these sections:

## Hidden Management Commitments
Forward-guidance promises (targets, timelines, margins, capex, buybacks): promise, quote, how verifiable.

## The Analyst Hard-Talk
The 5 toughest analyst questions that management dodged or answered vaguely: the question, what management \
actually said, and what was avoided.

## Hidden Risk Vectors
Risks implied by tone, hedging language, or omissions.

## Key Numbers
Important financial figures and changes from any tables.""",
    "filing": """Output Markdown with exactly these sections:

## Executive Summary
3-5 bullets summarizing the structural risks.

## Hidden Risk Vectors
Structural risks buried in legal, risk-factor, going-concern, litigation, accounting-policy and related-party \
language: risk, quote, severity (High/Med/Low).

## Financial Table Red Flags
Anomalies in tabular data (margin erosion, receivables/inventory growth vs revenue, debt maturities, \
off-balance-sheet items, large non-GAAP adjustments).

## Hidden Management Commitments
Forward-looking commitments or obligations.""",
}

DOC_KIND = {"transcript": "earnings call transcript", "filing": "exchange filing / annual report"}

SINGLE_PASS = "Analyze the document below.\n\n{fmt}\n\nDOCUMENT:\n{doc}"

MAP = """You are reading part {i} of {n} of a {kind}. Extract concise bullet-point NOTES (max ~400 words) \
relevant to a hostile analyst: forward-looking promises, evasive or tough Q&A, legal/risk language, \
accounting oddities, and key table figures (with values and periods). Include (p.N) citations and short \
verbatim quotes. If nothing relevant, reply 'NONE'.

TEXT:
{doc}"""

REDUCE = """Below are analyst notes extracted sequentially from a full {kind}. Merge duplicates and write the \
final report from them only.

{fmt}

NOTES:
{notes}"""

MERGE = """Condense the following analyst notes into one deduplicated set of bullet-point notes, keeping \
page citations, quotes and numbers.

NOTES:
{notes}"""
