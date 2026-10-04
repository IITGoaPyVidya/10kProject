"""Agent registry and the LangGraph workflow that wires the agents together.

Graph:  START -> [analysts in parallel] -> [bull_case, bear_case in parallel] -> portfolio_manager -> END
Each stage is optional: disabled agents are simply left out and edges re-route around them.
"""
from typing import Callable, Iterable

from langgraph.graph import END, START, StateGraph

from app.agents.annual_report import AnnualReportAgent
from app.agents.base import BaseAgent, Emit
from app.agents.bear_case import BearCaseAgent
from app.agents.bull_case import BullCaseAgent
from app.agents.concall import ConcallAgent
from app.agents.config import load_agent_config
from app.agents.fundamentals import FundamentalsAgent
from app.agents.news import NewsAgent
from app.agents.portfolio_manager import PortfolioManagerAgent
from app.agents.state import ResearchState
from app.agents.technicals import TechnicalsAgent

# To add an agent: create a folder (agent.py, config.yaml, prompt.md), then register its class here.
AGENT_CLASSES: list[type[BaseAgent]] = [
    ConcallAgent, AnnualReportAgent, FundamentalsAgent, TechnicalsAgent, NewsAgent,
    BullCaseAgent, BearCaseAgent, PortfolioManagerAgent,
]


def load_agents() -> dict[str, BaseAgent]:
    """Instantiate every agent from its own config (including disabled ones, for the UI roster)."""
    return {cls.name: cls(load_agent_config(cls.name)) for cls in AGENT_CLASSES}


def build_graph(agents: Iterable[BaseAgent], emit: Emit, on_report: Callable[[str, dict], None] | None = None):
    """Compile the workflow for the given (enabled) agents; on_report fires as each agent finishes."""
    agents = list(agents)
    by_stage = {s: [a for a in agents if a.stage == s] for s in ("analyst", "debate", "decision")}
    if not by_stage["analyst"]:
        raise ValueError("Enable at least one analyst agent.")

    sg = StateGraph(ResearchState)

    def make_node(agent: BaseAgent):
        def node(state: ResearchState) -> dict:
            report = agent.run(state, emit)
            if on_report:
                on_report(agent.name, report)
            return {"reports": {agent.name: report}}
        return node

    for a in agents:
        sg.add_node(a.name, make_node(a))

    previous: list[str] = []
    for stage in ("analyst", "debate", "decision"):
        names = [a.name for a in by_stage[stage]]
        if not names:
            continue
        for n in names:
            sg.add_edge(previous if previous else START, n)  # list source = wait for all of the previous stage
        previous = names
    for n in previous:
        sg.add_edge(n, END)
    return sg.compile()
