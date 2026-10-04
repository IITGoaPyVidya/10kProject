"""Market data access (yfinance). Kept in one module so tests can monkeypatch the three fetchers."""
import math
from typing import Any

import pandas as pd
import yfinance as yf


def _clean(v: Any) -> Any:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return v


def normalize_ticker(ticker: str, exchange: str) -> str:
    """Append a Yahoo suffix when the user typed a bare symbol (NSE -> .NS, BSE -> .BO)."""
    t = ticker.strip().upper()
    if "." in t or t.startswith("^") or exchange == "AS_TYPED" or exchange == "US":
        return t
    return t + {"NSE": ".NS", "BSE": ".BO"}.get(exchange, "")


def get_history(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Daily OHLCV; empty frame if the symbol is unknown."""
    return yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)


def get_fundamentals(ticker: str) -> dict:
    """Snapshot ratios plus annual revenue/net income series."""
    t = yf.Ticker(ticker)
    info = t.info or {}
    series: list[dict] = []
    try:
        fin = t.financials
        if fin is not None and not fin.empty:
            for col in sorted(fin.columns):
                rev = fin[col].get("Total Revenue")
                ni = fin[col].get("Net Income")
                series.append({"year": str(col)[:4], "revenue": _clean(rev), "net_income": _clean(ni)})
    except Exception:
        pass
    fcf = None
    try:
        cf = t.cashflow
        if cf is not None and not cf.empty and "Free Cash Flow" in cf.index:
            fcf = _clean(cf.loc["Free Cash Flow"].iloc[0])
    except Exception:
        pass
    keys = ["longName", "sector", "industry", "currency", "marketCap", "currentPrice", "trailingPE", "forwardPE",
            "priceToBook", "enterpriseToEbitda", "returnOnEquity", "returnOnAssets", "profitMargins",
            "operatingMargins", "revenueGrowth", "earningsGrowth", "debtToEquity", "currentRatio",
            "dividendYield", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow"]
    return {"info": {k: _clean(info.get(k)) for k in keys}, "series": series[-5:], "free_cash_flow": fcf}


def get_news(ticker: str, company: str = "", limit: int = 10) -> list[dict]:
    """Recent headlines: ticker news first, then a name search (Indian tickers often have none)."""
    items: list[dict] = []

    def parse(n: dict) -> dict | None:
        c = n.get("content") if isinstance(n.get("content"), dict) else n
        title = c.get("title")
        if not title:
            return None
        url = (c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else c.get("link")
        src = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher")
        return {"title": title, "source": src or "", "url": url or "",
                "date": str(c.get("pubDate") or c.get("providerPublishTime") or ""),
                "summary": (c.get("summary") or "")[:300]}

    try:
        items = [p for p in (parse(n) for n in (yf.Ticker(ticker).news or [])) if p]
    except Exception:
        items = []
    if not items:
        try:
            q = company or ticker.split(".")[0]
            items = [p for p in (parse(n) for n in (yf.Search(q, news_count=limit).news or [])) if p]
        except Exception:
            items = []
    return items[:limit]
