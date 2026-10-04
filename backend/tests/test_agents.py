import json
import time

import numpy as np
import pandas as pd
import pytest

from app.agents import llm as llm_mod
from app.agents.config import load_agent_config
from app.agents.registry import build_graph, load_agents
from app.agents.tools import indicators, market_data


def fake_prices(n: int = 400) -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-01-01", periods=n)
    close = pd.Series(100 + np.cumsum(np.random.default_rng(1).normal(0.3, 1.0, n)), index=idx)
    return pd.DataFrame({"Open": close, "High": close + 1, "Low": close - 1, "Close": close,
                         "Volume": np.full(n, 1_000_000.0)}, index=idx)


FUND = {"info": {"longName": "Test Co", "revenueGrowth": 0.2, "earningsGrowth": 0.18, "operatingMargins": 0.25,
                 "returnOnEquity": 0.3, "debtToEquity": 20.0, "trailingPE": 22.0, "currentRatio": 2.0},
        "series": [{"year": "2024", "revenue": 100.0, "net_income": 20.0}], "free_cash_flow": 15.0}

NEWS = [{"title": "Test Co wins big deal", "source": "Wire", "url": "", "date": "", "summary": ""}]


class FakeLLM:
    def __init__(self, cfg):
        self.model = cfg.model

    def complete(self, system: str, user: str) -> str:
        return json.dumps({"rating": "bullish", "score": 40, "confidence": 0.7, "headline": "Looks good",
                           "summary": "Fine.", "key_points": ["a"], "risks": ["b"], "extra": {"Catalysts": ["c"]}})


@pytest.fixture()
def fake_world(monkeypatch):
    monkeypatch.setattr(market_data, "get_history", lambda t, p="2y": fake_prices())
    monkeypatch.setattr(market_data, "get_fundamentals", lambda t: FUND)
    monkeypatch.setattr(market_data, "get_news", lambda t, c="", n=10: NEWS)
    llm_mod.set_llm_factory(FakeLLM)
    yield
    llm_mod.set_llm_factory(None)


def test_indicators_shape():
    out = indicators.compute(fake_prices())
    assert -100 <= out["quant_score"] <= 100
    assert out["metrics"]["rsi14"] is not None and len(out["chart"]) == 252


def test_config_layering_and_env_override(monkeypatch):
    base = load_agent_config("technicals")
    assert base.llm.model and base.params["history_period"] == "2y" and base.system_prompt
    monkeypatch.setenv("AGENT_TECHNICALS_MODEL", "meta/other-model")
    monkeypatch.setenv("AGENT_NEWS_ENABLED", "false")
    assert load_agent_config("technicals").llm.model == "meta/other-model"
    assert load_agent_config("news").enabled is False
    assert load_agent_config("fundamentals").llm.model != "meta/other-model"


def test_graph_runs_and_skips_missing_inputs(fake_world, monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "x")
    events = []
    agents = [a for a in load_agents().values() if a.config.enabled]
    graph = build_graph(agents, lambda agent, msg, level="info", kind="log", **f: events.append((agent, kind)))
    state = {"ticker": "TEST.NS", "company": "", "horizon": "medium", "concall_text": "", "annual_text": "", "reports": {}}
    reports = graph.invoke(state)["reports"]
    assert reports["concall"]["status"] == "skipped"
    assert reports["annual_report"]["status"] == "skipped"
    for n in ("fundamentals", "technicals", "news", "bull_case", "bear_case", "portfolio_manager"):
        assert reports[n]["status"] == "done", n
    assert reports["portfolio_manager"]["rating"] == "hold"  # fake "bullish" is invalid for the PM scale -> default
    assert reports["technicals"]["data"]["chart"]


def test_llm_failure_degrades_to_rule_based(monkeypatch):
    monkeypatch.setattr(market_data, "get_history", lambda t, p="2y": fake_prices())
    monkeypatch.setattr(market_data, "get_fundamentals", lambda t: FUND)

    class Boom:
        model = "x"

        def complete(self, s, u):
            raise llm_mod.LLMError("down")

    llm_mod.set_llm_factory(lambda cfg: Boom())
    try:
        agents = [a for a in load_agents().values() if a.name in ("fundamentals", "technicals", "portfolio_manager")]
        graph = build_graph(agents, lambda *a, **k: None)
        reports = graph.invoke({"ticker": "T", "company": "", "horizon": "long", "concall_text": "",
                                "annual_text": "", "reports": {}})["reports"]
    finally:
        llm_mod.set_llm_factory(None)
    assert reports["fundamentals"]["degraded"] and reports["technicals"]["degraded"]
    assert reports["portfolio_manager"]["status"] == "done" and reports["portfolio_manager"]["degraded"]


def test_research_api_end_to_end(fake_world, client):
    r = client.get("/api/v1/research/agents")
    assert r.status_code == 200 and {a["name"] for a in r.json()} >= {"concall", "portfolio_manager"}

    r = client.post("/api/v1/research", data={"ticker": "TEST", "exchange": "NSE"})
    assert r.status_code == 202
    jid = r.json()["id"]
    for _ in range(100):
        job = client.get(f"/api/v1/research/{jid}").json()
        if job["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "completed", job
    assert job["ticker"] == "TEST.NS" and job["final"]["agent"] == "portfolio_manager"
    assert job["agents"]["concall"]["status"] == "skipped"
    later = client.get(f"/api/v1/research/{jid}?since={job['next_index']}").json()
    assert later["events"] == []


def test_research_rejects_bad_input(client):
    assert client.post("/api/v1/research", data={"ticker": "bad ticker!"}).status_code == 400
    assert client.post("/api/v1/research", data={"ticker": "TCS", "agents": "nope"}).status_code == 400
    assert client.post("/api/v1/research", data={"ticker": "TCS", "agents": "bull_case"}).status_code == 400
    assert client.post("/api/v1/research", data={"ticker": "TCS", "concall_youtube": "https://evil.com/x"}).status_code == 400


def test_parse_json_repairs_unquoted_strings():
    from app.agents.base import parse_json

    bad = ('{"rating": "bullish", "score": 55,\n'
           '  "headline": TCS is solid, with "quotes" inside.",\n'
           '  "summary": TCS delivers growth\n'
           '  "key_points": ["a"]}')
    out = parse_json(bad)
    assert out["score"] == 55 and out["headline"].startswith("TCS is solid") and out["key_points"] == ["a"]

