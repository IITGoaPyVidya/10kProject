"""Shared logic for the bull / bear debaters: argue one side using the analysts' evidence."""
from app.agents.base import BaseAgent, Emit, compact_reports
from app.agents.state import ResearchState


class DebaterAgent(BaseAgent):
    stage = "debate"
    side = ""

    def skip_reason(self, state: ResearchState) -> str | None:
        done = [r for r in state["reports"].values() if r.get("status") == "done" and r["stage"] == "analyst"]
        return None if done else "No analyst reports to argue from"

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        analysts = [n for n, r in state["reports"].items() if r["stage"] == "analyst"]
        return (f"Company: {state.get('company') or state['ticker']} ({state['ticker']})\n"
                f"Investment horizon: {state['horizon']}\n"
                f"Make the strongest honest {self.side} case using ONLY this analyst evidence.\n\n"
                f"{compact_reports(state['reports'], analysts)}")
