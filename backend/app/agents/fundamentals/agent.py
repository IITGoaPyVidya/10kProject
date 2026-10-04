import json

from app.agents.base import BaseAgent, Emit, rating_from_score
from app.agents.state import ResearchState
from app.agents.tools import market_data


def quant_score(info: dict, fcf: float | None) -> tuple[int, list[dict]]:
    """Transparent rule-based quality/valuation score in [-100, 100] with the reasons behind it."""
    score, why = 0, []

    def add(points: int, text: str) -> None:
        nonlocal score
        score += points
        why.append({"signal": text, "points": points})

    g, eg, om, roe = info.get("revenueGrowth"), info.get("earningsGrowth"), info.get("operatingMargins"), info.get("returnOnEquity")
    de, pe, cr = info.get("debtToEquity"), info.get("trailingPE"), info.get("currentRatio")
    if g is not None:
        add(15 if g > 0.15 else 8 if g > 0.08 else -15 if g < 0 else 0, f"Revenue growth {g:.1%}")
    if eg is not None:
        add(10 if eg > 0.15 else -10 if eg < 0 else 0, f"Earnings growth {eg:.1%}")
    if om is not None:
        add(10 if om > 0.20 else -8 if om < 0.08 else 0, f"Operating margin {om:.1%}")
    if roe is not None:
        add(12 if roe > 0.18 else -10 if roe < 0.08 else 0, f"Return on equity {roe:.1%}")
    if de is not None:
        add(8 if de < 50 else -12 if de > 150 else 0, f"Debt/equity {de:.0f}%")
    if pe is not None and pe > 0:
        add(8 if pe < 15 else -10 if pe > 40 else 0, f"Trailing P/E {pe:.1f}")
    if fcf is not None:
        add(8 if fcf > 0 else -10, "Positive free cash flow" if fcf > 0 else "Negative free cash flow")
    if cr is not None:
        add(5 if cr > 1.5 else -8 if cr < 1 else 0, f"Current ratio {cr:.2f}")
    return max(-100, min(100, score * 100 // 75)), why


class FundamentalsAgent(BaseAgent):
    name = "fundamentals"
    stage = "analyst"
    needs = "Ticker (market data)"

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        emit(self.name, f"Fetching financial statements for {state['ticker']}", kind="log")
        f = market_data.get_fundamentals(state["ticker"])
        if not any(v is not None for v in f["info"].values()):
            raise ValueError(f"No fundamentals found for {state['ticker']} (check the symbol).")
        score, why = quant_score(f["info"], f["free_cash_flow"])
        emit(self.name, f"Computed quality/valuation score {score:+d}", kind="log")
        return {"fund": f, "quant": score, "why": why,
                "data": {"info": f["info"], "series": f["series"], "free_cash_flow": f["free_cash_flow"],
                         "quant_score": score, "signals": why}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        return (f"Company: {ctx['fund']['info'].get('longName') or state['ticker']} ({state['ticker']})\n"
                f"Investment horizon: {state['horizon']}\n"
                f"Metrics: {json.dumps(ctx['fund']['info'])}\n"
                f"Annual revenue / net income (oldest to newest): {json.dumps(ctx['fund']['series'])}\n"
                f"Free cash flow (latest year): {ctx['fund']['free_cash_flow']}\n"
                f"Rule-based score {ctx['quant']:+d}: {json.dumps(ctx['why'])}")

    def fallback(self, ctx: dict, state: ResearchState) -> dict:
        s = ctx["quant"]
        return {"rating": rating_from_score(s), "score": s, "confidence": 0.4,
                "headline": f"Rule-based fundamentals score {s:+d} (LLM unavailable)",
                "summary": "Computed from growth, margin, return, leverage, valuation and cash-flow rules only.",
                "key_points": [f"{w['signal']} ({w['points']:+d})" for w in ctx["why"]][:7]}
