import json

from app.agents.base import BaseAgent, Emit, NoData
from app.agents.state import ResearchState
from app.agents.tools import market_data


class NewsAgent(BaseAgent):
    name = "news"
    stage = "analyst"
    needs = "Ticker (recent headlines)"

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        emit(self.name, "Searching recent headlines", kind="log")
        items = market_data.get_news(state["ticker"], state.get("company", ""),
                                     self.config.params.get("max_headlines", 10))
        if not items:
            raise NoData("No recent headlines found for this symbol")
        emit(self.name, f"Found {len(items)} headlines", kind="log")
        return {"items": items, "data": {"headlines": items}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        return (f"Company: {state.get('company') or state['ticker']} ({state['ticker']})\n"
                f"Investment horizon: {state['horizon']}\nHeadlines:\n{json.dumps(ctx['items'], indent=1)}")
