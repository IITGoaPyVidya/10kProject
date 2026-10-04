import json

from app.agents.base import BaseAgent, Emit, compact_reports
from app.agents.state import ResearchState


def consensus(reports: dict, weights: dict) -> dict:
    """Weighted average of analyst scores (weight x confidence), ignoring skipped/failed agents."""
    num = den = 0.0
    used = []
    for name, r in reports.items():
        if r["stage"] != "analyst" or r["status"] != "done":
            continue
        w = float(weights.get(name, 1.0)) * max(r["confidence"], 0.1)
        num += w * r["score"]
        den += w
        used.append({"agent": name, "score": r["score"], "confidence": r["confidence"], "weight": weights.get(name, 1.0)})
    return {"score": round(num / den) if den else 0, "inputs": used}


def rating_from_consensus(score: int) -> str:
    return ("strong_buy" if score >= 50 else "buy" if score >= 20 else "reduce" if score <= -20 and score > -50
            else "avoid" if score <= -50 else "hold")


class PortfolioManagerAgent(BaseAgent):
    name = "portfolio_manager"
    stage = "decision"
    ratings = ("strong_buy", "buy", "hold", "reduce", "avoid")

    def skip_reason(self, state: ResearchState) -> str | None:
        ok = [r for r in state["reports"].values() if r["stage"] == "analyst" and r["status"] == "done"]
        return None if ok else "No analyst produced a result, so there is nothing to decide on"

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        c = consensus(state["reports"], self.config.params.get("weights", {}))
        emit(self.name, f"Weighted consensus score {c['score']:+d} from {len(c['inputs'])} analysts", kind="log")
        return {"consensus": c, "data": {"consensus": c,
                                         "agent_scores": {n: {"score": r["score"], "rating": r["rating"]}
                                                          for n, r in state["reports"].items() if r["status"] == "done"}}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        return (f"Company: {state.get('company') or state['ticker']} ({state['ticker']})\n"
                f"Investment horizon: {state['horizon']}\n"
                f"Weighted consensus score: {ctx['consensus']['score']:+d} ({json.dumps(ctx['consensus']['inputs'])})\n\n"
                f"{compact_reports(state['reports'])}")

    def fallback(self, ctx: dict, state: ResearchState) -> dict:
        s = ctx["consensus"]["score"]
        return {"rating": rating_from_consensus(s), "score": s, "confidence": 0.4,
                "headline": f"Consensus score {s:+d} (LLM unavailable)",
                "summary": "Weighted average of the analysts' scores; no LLM synthesis was possible.",
                "key_points": [f"{i['agent']}: {i['score']:+d} (confidence {i['confidence']})" for i in ctx["consensus"]["inputs"]]}
