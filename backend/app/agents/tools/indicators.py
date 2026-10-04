"""Technical indicators computed with pandas (no TA library needed)."""
import numpy as np
import pandas as pd


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    line = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    return line, line.ewm(span=9, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _f(v, nd: int = 2):
    return None if v is None or pd.isna(v) else round(float(v), nd)


def compute(df: pd.DataFrame) -> dict:
    """Return {metrics, signals, quant_score, chart} from daily OHLCV."""
    close = df["Close"].dropna()
    price = float(close.iloc[-1])
    sma20, sma50, sma200 = (close.rolling(n).mean() for n in (20, 50, 200))
    r = rsi(close)
    m, ms = macd(close)
    bb_mid, bb_std = close.rolling(20).mean(), close.rolling(20).std()
    vol = df["Volume"]

    def ret(days: int):
        return _f((price / close.iloc[-days - 1] - 1) * 100) if len(close) > days else None

    hi52, lo52 = close.tail(252).max(), close.tail(252).min()
    recent = close.tail(60)
    metrics = {
        "price": _f(price), "rsi14": _f(r.iloc[-1]), "macd": _f(m.iloc[-1], 3), "macd_signal": _f(ms.iloc[-1], 3),
        "sma20": _f(sma20.iloc[-1]), "sma50": _f(sma50.iloc[-1]), "sma200": _f(sma200.iloc[-1]),
        "bollinger_upper": _f((bb_mid + 2 * bb_std).iloc[-1]), "bollinger_lower": _f((bb_mid - 2 * bb_std).iloc[-1]),
        "atr14": _f(atr(df).iloc[-1]), "high_52w": _f(hi52), "low_52w": _f(lo52),
        "pct_from_52w_high": _f((price / hi52 - 1) * 100), "support_60d": _f(recent.min()),
        "resistance_60d": _f(recent.max()),
        "volume_ratio_20d": _f(vol.tail(5).mean() / vol.tail(20).mean()) if vol.tail(20).mean() else None,
        "return_1m_pct": ret(21), "return_3m_pct": ret(63), "return_6m_pct": ret(126), "return_1y_pct": ret(252),
        "volatility_ann_pct": _f(close.pct_change().tail(252).std() * np.sqrt(252) * 100),
    }

    score, signals = 0, []

    def add(points: int, text: str) -> None:
        nonlocal score
        score += points
        signals.append({"signal": text, "points": points})

    if not pd.isna(sma50.iloc[-1]):
        add(10 if price > sma50.iloc[-1] else -10, "Price above 50-day average" if price > sma50.iloc[-1] else "Price below 50-day average")
    if not pd.isna(sma200.iloc[-1]):
        add(15 if price > sma200.iloc[-1] else -15, "Price above 200-day average" if price > sma200.iloc[-1] else "Price below 200-day average")
        if not pd.isna(sma50.iloc[-1]):
            add(10 if sma50.iloc[-1] > sma200.iloc[-1] else -10,
                "50-day above 200-day (golden-cross regime)" if sma50.iloc[-1] > sma200.iloc[-1] else "50-day below 200-day (death-cross regime)")
    rv = r.iloc[-1]
    if not pd.isna(rv):
        if rv > 70:
            add(-8, f"RSI {rv:.0f}: overbought")
        elif rv < 30:
            add(8, f"RSI {rv:.0f}: oversold (rebound potential)")
        elif rv > 50:
            add(5, f"RSI {rv:.0f}: positive momentum")
        else:
            add(-5, f"RSI {rv:.0f}: weak momentum")
    add(8 if m.iloc[-1] > ms.iloc[-1] else -8, "MACD above signal line" if m.iloc[-1] > ms.iloc[-1] else "MACD below signal line")
    r3 = metrics["return_3m_pct"]
    if r3 is not None:
        add(10 if r3 > 5 else -10 if r3 < -5 else 0, f"3-month return {r3:+.1f}%")
    if metrics["volume_ratio_20d"] and metrics["volume_ratio_20d"] > 1.3:
        add(5 if (metrics["return_1m_pct"] or 0) > 0 else -5, "Volume surge confirming the recent move")

    tail = df.tail(252)
    s50, s200 = sma50.reindex(tail.index), sma200.reindex(tail.index)
    chart = [{"d": str(i.date()), "close": _f(c), "sma50": _f(a), "sma200": _f(b)}
             for i, c, a, b in zip(tail.index, tail["Close"], s50, s200)]
    return {"metrics": metrics, "signals": signals, "quant_score": max(-100, min(100, score * 100 // 66)),
            "chart": chart}
