from app.agents.base import BaseAgent, Emit
from app.agents.longdoc import condense
from app.agents.state import ResearchState
from app.services.red_flags import scan_red_flags


class AnnualReportAgent(BaseAgent):
    name = "annual_report"
    stage = "analyst"
    needs = "Annual report / 10-K PDF"

    def skip_reason(self, state: ResearchState) -> str | None:
        return None if state.get("annual_text") else "No annual report provided"

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        text = state["annual_text"]
        emit(self.name, "Scanning for accounting and governance red flags", kind="log")
        scan = scan_red_flags(text)
        p = self.config.params
        notes = condense(text, self.llm, agent=self.name, kind="annual report", emit=emit,
                         focus="risk factors, legal/related-party/going-concern language, accounting quality, "
                               "financial-table anomalies, capital allocation, forward commitments",
                         single_pass_chars=p.get("single_pass_chars", 100_000),
                         chunk_chars=p.get("chunk_chars", 60_000), workers=p.get("workers", 4))
        return {"text": notes, "scan": scan,
                "data": {"integrity_score": scan["score"], "flags": scan["flags"], "chars": len(text)}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        hits = "; ".join(f"{f['flag']}: {f['mentions']}" for f in ctx["scan"]["flags"] if f["mentions"])
        return (f"Company: {state.get('company') or state['ticker']} ({state['ticker']})\n"
                f"Investment horizon: {state['horizon']}\n"
                f"Keyword integrity scan (0-100, higher is cleaner): {ctx['scan']['score']}. Hits: {hits or 'none'}\n\n"
                f"ANNUAL REPORT (or notes from it):\n{ctx['text']}")

    def fallback(self, ctx: dict, state: ResearchState) -> dict:
        s = ctx["scan"]["score"]
        score = int((s - 50) * 1.2)
        return {"rating": "bullish" if s >= 75 else "bearish" if s < 40 else "neutral", "score": score,
                "confidence": 0.3, "headline": f"Keyword integrity score {s}/100 (LLM unavailable)",
                "summary": "Rule-based keyword scan only; no LLM reading of the report.",
                "key_points": [f"{f['flag']}: {f['mentions']} mentions" for f in ctx["scan"]["flags"] if f["mentions"]][:6]}
