import type { ReactNode } from "react";

export const RATING: Record<string, { label: string; color: string }> = {
  strong_buy: { label: "Strong Buy", color: "#15803d" },
  buy: { label: "Buy", color: "#22c55e" },
  hold: { label: "Hold", color: "#d97706" },
  reduce: { label: "Reduce", color: "#ea580c" },
  avoid: { label: "Avoid", color: "#dc2626" },
  bullish: { label: "Bullish", color: "#16a34a" },
  neutral: { label: "Neutral", color: "#6b7280" },
  bearish: { label: "Bearish", color: "#dc2626" },
};

export const scoreColor = (s: number) => (s >= 25 ? "#16a34a" : s <= -25 ? "#dc2626" : "#d97706");

export function RatingChip({ rating }: { rating?: string }) {
  const r = RATING[rating ?? ""];
  if (!r) return null;
  return <span className="chip" style={{ background: r.color }}>{r.label}</span>;
}

/** Bar centred on zero: green to the right for positive scores, red to the left for negative. */
export function ScoreBar({ score }: { score: number }) {
  const pct = Math.min(Math.abs(score), 100) / 2;
  return (
    <div className="scorebar" title={`Score ${score > 0 ? "+" : ""}${score}`}>
      <div className="mid" />
      <div className="fill" style={{
        background: scoreColor(score), width: `${pct}%`,
        left: score >= 0 ? "50%" : `${50 - pct}%`,
      }} />
    </div>
  );
}

/** Semicircle gauge: -100 (left) to +100 (right). */
export function Gauge({ score, color }: { score: number; color: string }) {
  const angle = (Math.max(-100, Math.min(100, score)) / 100) * 90; // -90..90 degrees
  const rad = ((angle - 90) * Math.PI) / 180;
  const nx = 100 + 70 * Math.cos(rad);
  const ny = 100 + 70 * Math.sin(rad);
  return (
    <svg viewBox="0 0 200 120" className="gauge" role="img" aria-label={`Score ${score}`}>
      <defs>
        <linearGradient id="gg" x1="0" x2="1">
          <stop offset="0" stopColor="#dc2626" /><stop offset="0.5" stopColor="#f59e0b" />
          <stop offset="1" stopColor="#16a34a" />
        </linearGradient>
      </defs>
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="#e5e7eb" strokeWidth="14" strokeLinecap="round" />
      <path d="M 20 100 A 80 80 0 0 1 180 100" fill="none" stroke="url(#gg)" strokeWidth="14" strokeLinecap="round"
            opacity="0.9" />
      <line x1="100" y1="100" x2={nx} y2={ny} stroke={color} strokeWidth="4" strokeLinecap="round"
            className="needle" />
      <circle cx="100" cy="100" r="7" fill={color} />
      <text x="100" y="118" textAnchor="middle" fontSize="14" fontWeight="700" fill="#111827">
        {score > 0 ? "+" : ""}{score}
      </text>
    </svg>
  );
}

export function Section({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="section">
      <h4>{title}</h4>
      <ul>{items.map((t, i) => <li key={i}>{t}</li>)}</ul>
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}

export function fmtBig(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  const a = Math.abs(v);
  if (a >= 1e12) return `${(v / 1e12).toFixed(2)}T`;
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  return v.toFixed(2);
}

export function fmtNum(v: unknown, digits = 2): string {
  return typeof v === "number" ? v.toFixed(digits) : "-";
}

export function fmtPct(v: unknown): string {
  return typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "-";
}
