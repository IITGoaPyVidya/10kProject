import type { AgentReport } from "../../types";
import { Gauge, RATING, ScoreBar, Section } from "./ui";

function Side({ r, tone }: { r?: AgentReport; tone: "bull" | "bear" }) {
  if (!r || r.status !== "done") return null;
  return (
    <div className={`side ${tone}`}>
      <h4>{tone === "bull" ? "Bull case" : "Bear case"} <small>conviction {Math.abs(r.score)}</small></h4>
      <p>{r.headline}</p>
      <Section title="Arguments" items={r.key_points} />
      {Object.entries(r.extra).map(([k, v]) => <Section key={k} title={k} items={v} />)}
    </div>
  );
}

export function Verdict({ ticker, final, reports }: {
  ticker: string; final: AgentReport; reports: Record<string, AgentReport>;
}) {
  const meta = RATING[final.rating] ?? { label: final.rating, color: "#6b7280" };
  const scores = (final.data?.agent_scores ?? {}) as Record<string, { score: number; rating: string }>;
  return (
    <section className="verdict" style={{ borderColor: meta.color }}>
      <div className="verdict-top">
        <div className="verdict-gauge">
          <Gauge score={final.score} color={meta.color} />
          <div className="verdict-rating" style={{ color: meta.color }}>{meta.label}</div>
          <small className="muted">confidence {Math.round(final.confidence * 100)}%</small>
        </div>
        <div className="verdict-body">
          <small className="muted">PORTFOLIO MANAGER VERDICT · {ticker}</small>
          <h2>{final.headline}</h2>
          <p>{final.summary}</p>
          {final.degraded && <span className="chip warn">rule-based consensus (LLM unavailable)</span>}
        </div>
      </div>

      <div className="agree">
        <h4>Where each agent stands</h4>
        {Object.entries(scores).filter(([n]) => reports[n]?.stage === "analyst").map(([n, s]) => (
          <div className="agree-row" key={n}>
            <span>{reports[n]?.title ?? n}</span>
            <ScoreBar score={s.score} />
            <b style={{ color: RATING[s.rating]?.color }}>{s.score > 0 ? "+" : ""}{s.score}</b>
          </div>
        ))}
      </div>

      <div className="cols">
        <Section title="Key points" items={final.key_points} />
        <Section title="Risks" items={final.risks} />
      </div>
      <div className="cols">
        {Object.entries(final.extra).map(([k, v]) => <Section key={k} title={k} items={v} />)}
      </div>

      {(reports.bull_case || reports.bear_case) && (
        <div className="debate">
          <Side r={reports.bull_case} tone="bull" />
          <Side r={reports.bear_case} tone="bear" />
        </div>
      )}
      <p className="muted disclaimer">AI-generated research support, not financial advice. Verify the data and do your own diligence.</p>
    </section>
  );
}
