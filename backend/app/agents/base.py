"""Base class every agent extends. An agent = folder with agent.py, config.yaml and prompt.md."""
import json
import logging
import re
import time
from typing import Any, Callable, ClassVar

from app.agents.config import AgentConfig
from app.agents.llm import LLM, LLMError, make_llm
from app.agents.state import ResearchState

# emit(agent, message, level="info", kind="log", **fields)
Emit = Callable[..., None]
log = logging.getLogger(__name__)

JSON_SPEC = """

Respond with ONE JSON object and nothing else (no markdown fences), exactly in this shape:
{
  "rating": "<one of: %(ratings)s>",
  "score": <integer -100 (very negative) .. 100 (very positive)>,
  "confidence": <number 0..1>,
  "headline": "<one sentence verdict>",
  "summary": "<2-5 sentence analysis in plain text>",
  "key_points": ["<3-7 short evidence-backed bullets>"],
  "risks": ["<2-5 short bullets>"],
  "extra": {"<Section title>": ["<bullets>"]}
}
Use only the data provided. Never invent numbers. If evidence is thin, lower the confidence."""


class NoData(ValueError):
    """The agent's input does not exist (not an error): the agent is reported as skipped."""


_UNQUOTED = re.compile(r'^(\s*"(?:headline|summary|rating)"\s*:\s*)([^"\s\[{\d-][^\n]*?)\s*(,?)$', re.MULTILINE)


def _repair(text: str) -> str:
    """Fix the common model slip of dropping the opening quote (and sometimes the closing one) of a string value."""
    def fix(m: re.Match) -> str:
        body = m.group(2).rstrip('"').replace('"', "'")
        return f'{m.group(1)}"{body}"{m.group(3) or ","}'
    return _UNQUOTED.sub(fix, text)


def parse_json(text: str) -> dict:
    """Extract the first JSON object from model output (tolerates code fences / chatter / small slips)."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in model output")
    body = text[start: end + 1]
    try:
        return json.loads(body, strict=False)  # strict=False allows raw newlines in strings
    except json.JSONDecodeError:
        return json.loads(_repair(body), strict=False)


def _strs(v: Any, limit: int = 12) -> list[str]:
    return [str(x).strip() for x in (v if isinstance(v, list) else []) if str(x).strip()][:limit]


def rating_from_score(score: int) -> str:
    return "bullish" if score >= 25 else "bearish" if score <= -25 else "neutral"


def compact_reports(reports: dict, names: list[str] | None = None, max_chars: int = 1800) -> str:
    """Render analyst reports as compact text for downstream agents (debaters, portfolio manager)."""
    parts = []
    for name, r in reports.items():
        if names is not None and name not in names:
            continue
        if r.get("status") != "done":
            parts.append(f"## {r['title']}: {r['status'].upper()} ({r.get('error') or 'no data'})")
            continue
        body = "\n".join([f"Rating: {r['rating']} | score {r['score']} | confidence {r['confidence']}",
                          f"Headline: {r['headline']}", f"Summary: {r['summary']}",
                          "Key points: " + "; ".join(r["key_points"]), "Risks: " + "; ".join(r["risks"])])
        parts.append(f"## {r['title']}\n{body[:max_chars]}")
    return "\n\n".join(parts)


class BaseAgent:
    name: ClassVar[str]
    stage: ClassVar[str] = "analyst"  # analyst | debate | decision
    ratings: ClassVar[tuple[str, ...]] = ("bullish", "neutral", "bearish")
    fixed_rating: ClassVar[str | None] = None
    needs: ClassVar[str] = ""  # human-readable input requirement, shown in the UI

    def __init__(self, config: AgentConfig, llm: LLM | None = None) -> None:
        self.config = config
        self._llm = llm

    @property
    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = make_llm(self.config.llm)
        return self._llm

    # ---- hooks agents override --------------------------------------------------------------
    def skip_reason(self, state: ResearchState) -> str | None:
        return None

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        """Collect/compute inputs. Return {"data": <UI payload>, ...private context}."""
        return {"data": {}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        raise NotImplementedError

    def fallback(self, ctx: dict, state: ResearchState) -> dict | None:
        """Rule-based result used when the LLM is unavailable. Return None to fail instead."""
        return None

    # ---- orchestration ----------------------------------------------------------------------
    def _normalize(self, raw: dict) -> dict:
        rating = self.fixed_rating or str(raw.get("rating", "")).lower().strip().replace(" ", "_")
        if rating not in self.ratings:
            rating = self.ratings[len(self.ratings) // 2]
        try:
            score = max(-100, min(100, int(round(float(raw.get("score", 0))))))
        except (TypeError, ValueError):
            score = 0
        try:
            conf = max(0.0, min(1.0, float(raw.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        extra = raw.get("extra") if isinstance(raw.get("extra"), dict) else {}
        return {
            "rating": rating, "score": score, "confidence": round(conf, 2),
            "headline": str(raw.get("headline", "")).strip(),
            "summary": str(raw.get("summary", "")).strip(),
            "key_points": _strs(raw.get("key_points")),
            "risks": _strs(raw.get("risks")),
            "extra": {str(k): _strs(v) for k, v in list(extra.items())[:6] if _strs(v)},
        }

    def _report(self, status: str, **fields: Any) -> dict:
        base = {"agent": self.name, "title": self.config.title, "stage": self.stage, "status": status,
                "rating": "n/a", "score": 0, "confidence": 0.0, "headline": "", "summary": "",
                "key_points": [], "risks": [], "extra": {}, "data": {}, "model": self.config.llm.model,
                "degraded": False, "error": None, "duration_s": 0.0}
        base.update(fields)
        return base

    def run(self, state: ResearchState, emit: Emit) -> dict:
        t0 = time.time()
        reason = self.skip_reason(state)
        if reason:
            emit(self.name, f"Skipped: {reason}", level="warn", kind="agent_skipped")
            return self._report("skipped", error=reason)

        emit(self.name, f"Started ({self.config.llm.model})", kind="agent_start")
        ctx: dict = {"data": {}}
        try:
            ctx = self.gather(state, emit)
            prompt = self.user_prompt(ctx, state, emit)
            system = (self.config.system_prompt + JSON_SPEC % {"ratings": ", ".join(self.ratings)})
            emit(self.name, "Reasoning with the LLM", kind="log")
            raw_text = self.llm.complete(system, prompt)
            try:
                raw = parse_json(raw_text)
            except ValueError as bad:  # malformed JSON: ask once more, strictly
                log.warning("agent %s returned bad JSON (%s): %r", self.name, bad, raw_text[:300])
                raw = parse_json(self.llm.complete(system, prompt + "\n\nReturn ONLY one valid JSON object."))
            out = self._normalize(raw)
            report = self._report("done", data=ctx.get("data", {}), **out)
        except NoData as exc:
            emit(self.name, f"Skipped: {exc}", level="warn", kind="agent_skipped")
            return self._report("skipped", error=str(exc), duration_s=round(time.time() - t0, 1))
        except (LLMError, ValueError) as exc:
            fb = None
            try:
                fb = self.fallback(ctx, state)
            except Exception:
                fb = None
            if fb is None:
                emit(self.name, f"Failed: {exc}", level="error", kind="agent_failed")
                return self._report("failed", error=str(exc), duration_s=round(time.time() - t0, 1))
            emit(self.name, f"LLM unavailable ({exc}); used rule-based result", level="warn")
            report = self._report("done", data=ctx.get("data", {}), degraded=True, **self._normalize(fb))
        except Exception as exc:
            emit(self.name, f"Failed: {type(exc).__name__}: {exc}", level="error", kind="agent_failed")
            return self._report("failed", error=f"{type(exc).__name__}: {exc}",
                                duration_s=round(time.time() - t0, 1))

        report["duration_s"] = round(time.time() - t0, 1)
        emit(self.name, report["headline"] or "Done", level="success", kind="agent_done",
             rating=report["rating"], score=report["score"], confidence=report["confidence"])
        return report
