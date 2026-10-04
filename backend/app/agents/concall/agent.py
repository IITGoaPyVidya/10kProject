from app.agents.base import BaseAgent, Emit
from app.agents.longdoc import condense
from app.agents.state import ResearchState


class ConcallAgent(BaseAgent):
    name = "concall"
    stage = "analyst"
    needs = "Earnings call PDF or YouTube link"

    def skip_reason(self, state: ResearchState) -> str | None:
        return None if state.get("concall_text") else "No earnings call transcript provided"

    def gather(self, state: ResearchState, emit: Emit) -> dict:
        text = state["concall_text"]
        p = self.config.params
        notes = condense(text, self.llm, agent=self.name, kind="earnings call transcript", emit=emit,
                         focus="guidance and commitments, analyst questions dodged, tone shifts, demand/margin commentary",
                         single_pass_chars=p.get("single_pass_chars", 100_000),
                         chunk_chars=p.get("chunk_chars", 60_000), workers=p.get("workers", 4))
        return {"text": notes, "data": {"chars": len(text)}}

    def user_prompt(self, ctx: dict, state: ResearchState, emit: Emit) -> str:
        return (f"Company: {state.get('company') or state['ticker']} ({state['ticker']})\n"
                f"Investment horizon: {state['horizon']}\n\nEARNINGS CALL (or notes from it):\n{ctx['text']}")
