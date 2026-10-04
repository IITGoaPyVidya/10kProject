import { useEffect, useRef } from "react";

import type { ResearchEvent } from "../../types";

const PALETTE = ["#60a5fa", "#34d399", "#fbbf24", "#f472b6", "#a78bfa", "#fb923c", "#22d3ee", "#a3e635", "#f87171"];
const colorFor = (name: string) => {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return PALETTE[h % PALETTE.length];
};
const LEVEL_COLOR: Record<string, string> = { success: "#4ade80", warn: "#fbbf24", error: "#f87171", info: "#cbd5e1" };

export function ActivityFeed({ events, live }: { events: ResearchEvent[]; live: boolean }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  return (
    <div className="terminal" ref={box} aria-live="polite">
      {events.map((e) => (
        <div key={e.i} className="line">
          <span className="ts">+{e.ts.toFixed(1)}s</span>
          <span className="tag" style={{ color: colorFor(e.agent) }}>{e.agent}</span>
          <span style={{ color: LEVEL_COLOR[e.level] }}>{e.message}</span>
        </div>
      ))}
      {live && <div className="line"><span className="cursor" /></div>}
    </div>
  );
}
