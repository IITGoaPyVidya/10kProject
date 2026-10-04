import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

import type { AgentReport } from "../../types";
import { fmtBig, fmtNum, fmtPct, RatingChip, Section } from "./ui";

function Metrics({ rows }: { rows: [string, string][] }) {
  return (
    <div className="metric-grid">
      {rows.map(([k, v]) => <div key={k}><small>{k}</small><b>{v}</b></div>)}
    </div>
  );
}

function Technicals({ d }: { d: AgentReport["data"] }) {
  const m = d.metrics ?? {};
  return (
    <>
      <div className="chart">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={d.chart ?? []}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="d" minTickGap={50} tick={{ fontSize: 11 }} />
            <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
            <Tooltip /><Legend />
            <Line dataKey="close" name="Close" stroke="#2563eb" dot={false} strokeWidth={2} />
            <Line dataKey="sma50" name="50-day" stroke="#f59e0b" dot={false} />
            <Line dataKey="sma200" name="200-day" stroke="#dc2626" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <Metrics rows={[
        ["Price", fmtNum(m.price)], ["RSI (14)", fmtNum(m.rsi14, 0)], ["MACD", fmtNum(m.macd, 2)],
        ["1M return", `${fmtNum(m.return_1m_pct, 1)}%`], ["3M return", `${fmtNum(m.return_3m_pct, 1)}%`],
        ["1Y return", `${fmtNum(m.return_1y_pct, 1)}%`], ["Support (60d)", fmtNum(m.support_60d)],
        ["Resistance (60d)", fmtNum(m.resistance_60d)], ["From 52w high", `${fmtNum(m.pct_from_52w_high, 1)}%`],
        ["ATR (14)", fmtNum(m.atr14)], ["Volatility (ann.)", `${fmtNum(m.volatility_ann_pct, 1)}%`],
        ["Rule score", String(d.quant_score ?? "-")],
      ]} />
    </>
  );
}

function Fundamentals({ d }: { d: AgentReport["data"] }) {
  const i = d.info ?? {};
  return (
    <>
      {d.series?.length > 0 && (
        <div className="chart">
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={d.series}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="year" /><YAxis tickFormatter={fmtBig} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: number) => fmtBig(v)} /><Legend />
              <Bar dataKey="revenue" name="Revenue" fill="#2563eb" />
              <Bar dataKey="net_income" name="Net income" fill="#16a34a" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <Metrics rows={[
        ["Market cap", fmtBig(i.marketCap)], ["P/E (TTM)", fmtNum(i.trailingPE, 1)], ["Forward P/E", fmtNum(i.forwardPE, 1)],
        ["P/B", fmtNum(i.priceToBook, 1)], ["EV/EBITDA", fmtNum(i.enterpriseToEbitda, 1)], ["ROE", fmtPct(i.returnOnEquity)],
        ["Op. margin", fmtPct(i.operatingMargins)], ["Net margin", fmtPct(i.profitMargins)],
        ["Revenue growth", fmtPct(i.revenueGrowth)], ["Earnings growth", fmtPct(i.earningsGrowth)],
        ["Debt/Equity", fmtNum(i.debtToEquity, 0)], ["Free cash flow", fmtBig(d.free_cash_flow)],
      ]} />
    </>
  );
}

function News({ d }: { d: AgentReport["data"] }) {
  return (
    <ul className="headlines">
      {(d.headlines ?? []).map((h: { title: string; source: string; url: string }, i: number) => (
        <li key={i}>
          {h.url ? <a href={h.url} target="_blank" rel="noreferrer noopener">{h.title}</a> : h.title}
          <small> {h.source}</small>
        </li>
      ))}
    </ul>
  );
}

function AnnualReport({ d }: { d: AgentReport["data"] }) {
  const flags = [...(d.flags ?? [])].filter((f: { mentions: number }) => f.mentions > 0)
    .sort((a: { mentions: number }, b: { mentions: number }) => b.mentions - a.mentions);
  return (
    <>
      <Metrics rows={[["Keyword integrity score", `${d.integrity_score ?? "-"}/100`]]} />
      {flags.length > 0 && (
        <div className="chart">
          <ResponsiveContainer width="100%" height={Math.max(160, flags.length * 32)}>
            <BarChart data={flags} layout="vertical" margin={{ left: 110 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" allowDecimals={false} /><YAxis type="category" dataKey="flag" width={190} />
              <Tooltip /><Bar dataKey="mentions" fill="#dc2626" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  );
}

export function AgentReportPanel({ report }: { report: AgentReport }) {
  if (report.status !== "done") {
    return (
      <div className="card report">
        <h3>{report.title}</h3>
        <p className="muted">{report.status === "skipped" ? "Skipped" : "Failed"}: {report.error}</p>
      </div>
    );
  }
  return (
    <div className="card report">
      <div className="report-head">
        <h3>{report.title}</h3>
        <RatingChip rating={report.rating} />
        <span className="muted">score {report.score > 0 ? "+" : ""}{report.score} · confidence {Math.round(report.confidence * 100)}%</span>
        <span className="muted">{report.model.split("/").pop()} · {report.duration_s}s</span>
        {report.degraded && <span className="chip warn">rule-based fallback</span>}
      </div>
      {report.headline && <p className="headline">{report.headline}</p>}
      {report.summary && <p>{report.summary}</p>}
      {report.agent === "technicals" && <Technicals d={report.data} />}
      {report.agent === "fundamentals" && <Fundamentals d={report.data} />}
      {report.agent === "news" && <News d={report.data} />}
      {report.agent === "annual_report" && <AnnualReport d={report.data} />}
      <div className="cols">
        <Section title="Key points" items={report.key_points} />
        <Section title="Risks" items={report.risks} />
      </div>
      <div className="cols">
        {Object.entries(report.extra).map(([k, v]) => <Section key={k} title={k} items={v} />)}
      </div>
    </div>
  );
}
