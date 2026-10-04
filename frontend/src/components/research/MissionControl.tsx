import type { AgentLive, AgentStage } from "../../types";
import { RatingChip, ScoreBar } from "./ui";

const STAGES: { id: AgentStage; label: string; sub: string }[] = [
  { id: "analyst", label: "1 / Analysts", sub: "working in parallel" },
  { id: "debate", label: "2 / Debate", sub: "bull vs bear" },
  { id: "decision", label: "3 / Decision", sub: "portfolio manager" },
];

const STATUS_LABEL: Record<string, string> = {
  pending: "Waiting", working: "Working", done: "Done", skipped: "Skipped", failed: "Failed",
};

function AgentCard({ name, a, selected, onSelect }: {
  name: string; a: AgentLive; selected: boolean; onSelect: (n: string) => void;
}) {
  const clickable = a.status === "done" || a.status === "failed" || a.status === "skipped";
  return (
    <button className={`agent ${a.status} ${selected ? "selected" : ""}`} disabled={!clickable}
            onClick={() => onSelect(name)}>
      <div className="agent-head">
        <span className="avatar">{a.status === "working" ? <i className="spinner" /> : a.title.charAt(0)}</span>
        <div>
          <b>{a.title}</b>
          <small>{a.model.split("/").pop()}</small>
        </div>
        <span className={`pill ${a.status}`}>{STATUS_LABEL[a.status]}</span>
      </div>
      {a.status === "working" && <div className="shimmer" />}
      {a.status === "done" && (
        <div className="agent-result">
          <RatingChip rating={a.rating} />
          <ScoreBar score={a.score ?? 0} />
        </div>
      )}
      {(a.status === "skipped" || a.status === "failed") && <small className="agent-msg">{a.message}</small>}
      {a.status === "done" && a.message && <small className="agent-msg">{a.message}</small>}
    </button>
  );
}

export function MissionControl({ agents, selected, onSelect }: {
  agents: Record<string, AgentLive>; selected: string | null; onSelect: (n: string) => void;
}) {
  return (
    <div className="mission">
      {STAGES.map((s, idx) => {
        const entries = Object.entries(agents).filter(([, a]) => a.stage === s.id);
        if (!entries.length) return null;
        return (
          <div className="stage" key={s.id}>
            <div className="stage-title"><b>{s.label}</b><small>{s.sub}</small></div>
            <div className="stage-cards">
              {entries.map(([n, a]) => (
                <AgentCard key={n} name={n} a={a} selected={selected === n} onSelect={onSelect} />
              ))}
            </div>
            {idx < STAGES.length - 1 && <div className="arrow" aria-hidden>&rsaquo;</div>}
          </div>
        );
      })}
    </div>
  );
}
