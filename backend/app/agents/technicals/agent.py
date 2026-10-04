import json

from app.agents.base import BaseAgent, Emit, rating_from_score
from app.agents.state import ResearchState
from app.agents.tools import indicators, market_data


class TechnicalsAgent(BaseAgent):
    name = "technicals"
    stage = "analyst"
    needs = "Ticker (price history)"

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        period = self.config.params.get("history_period", "2y")
        emit(self.name, f"Downloading {period} of daily prices for {state['ticker']}", kind="log")
        df = market_data.get_history(state["ticker"], period)
        if df is None or len(df) < 60:
            raise ValueError(f"Not enough price history for {state['ticker']} (check the symbol).")
        emit(self.name, "Computing SMA, RSI, MACD, Bollinger, ATR and key levels", kind="log")
        ind = indicators.compute(df)
        return {"ind": ind, "data": {"metrics": ind["metrics"], "signals": ind["signals"],
                                      "quant_score": ind["quant_score"], "chart": ind["chart"]}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        ind = ctx["ind"]
        return (f"Ticker: {state['ticker']}\nInvestment horizon: {state['horizon']}\n"
                f"Indicators: {json.dumps(ind['metrics'])}\n"
                f"Rule-based score {ind['quant_score']:+d}: {json.dumps(ind['signals'])}")

    def fallback(self, ctx: dict, state: ResearchState) -> dict:
        ind = ctx["ind"]
        s = ind["quant_score"]
        return {"rating": rating_from_score(s), "score": s, "confidence": 0.4,
                "headline": f"Rule-based technical score {s:+d} (LLM unavailable)",
                "summary": "Computed from trend, momentum and volume rules only.",
                "key_points": [f"{x['signal']} ({x['points']:+d})" for x in ind["signals"]][:7]}
