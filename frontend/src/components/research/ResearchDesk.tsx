import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, getAgents, getResearch, startResearch } from "../../api";
import type { AgentInfo, ResearchEvent, ResearchJob, SymbolMatch } from "../../types";
import { ActivityFeed } from "./ActivityFeed";
import { AgentReportPanel } from "./AgentReportPanel";
import { MissionControl } from "./MissionControl";
import { SymbolPicker } from "./SymbolPicker";
import { Verdict } from "./Verdict";

const POLL_MS = 1000;
const HORIZONS = [["short", "Short (weeks)"], ["medium", "Medium (months)"], ["long", "Long (years)"]] as const;
const STAGE_ORDER: Record<string, number> = { analyst: 0, debate: 1, decision: 2 };

function FilePick({ label, file, onPick, disabled }: {
  label: string; file: File | null; onPick: (f: File | null) => void; disabled: boolean;
}) {
  return (
    <label className={`drop ${file ? "has" : ""}`}>
      <input type="file" accept="application/pdf" hidden disabled={disabled}
             onChange={(e) => { onPick(e.target.files?.[0] ?? null); e.target.value = ""; }} />
      <span>{file ? file.name : label}</span>
      {file && <button type="button" className="x" onClick={(e) => { e.preventDefault(); onPick(null); }}>remove</button>}
    </label>
  );
}

export function ResearchDesk() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [ticker, setTicker] = useState("");
  const [exchange, setExchange] = useState("NSE");
  const [company, setCompany] = useState("");
  const [horizon, setHorizon] = useState("medium");
  const [concall, setConcall] = useState<File | null>(null);
  const [annual, setAnnual] = useState<File | null>(null);
  const [yt, setYt] = useState("");
  const [picked1, setPicked1] = useState<SymbolMatch | null>(null);
  const [didYouMean, setDidYouMean] = useState<SymbolMatch[]>([]);

  const [job, setJob] = useState<ResearchJob | null>(null);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const since = useRef(0);
  const timer = useRef<number>();

  useEffect(() => {
    getAgents().then((a) => {
      setAgents(a);
      setPicked(new Set(a.filter((x) => x.enabled).map((x) => x.name)));
    }).catch((e) => setError(e.message));
    return () => window.clearTimeout(timer.current);
  }, []);

  const poll = useCallback(async (id: string) => {
    try {
      const j = await getResearch(id, since.current);
      since.current = j.next_index;
      if (j.events.length) setEvents((prev) => [...prev, ...j.events]);
      setJob(j);
      if (j.status === "queued" || j.status === "running") {
        timer.current = window.setTimeout(() => void poll(id), POLL_MS);
      } else {
        setBusy(false);
        if (j.status === "failed") setError(j.error ?? "Research failed.");
      }
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }, []);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    window.clearTimeout(timer.current);
    setError(null); setDidYouMean([]); setJob(null); setEvents([]); setSelected(null); since.current = 0;
    setBusy(true);
    const exactPick = picked1 && picked1.symbol === ticker.trim();
    const fd = new FormData();
    fd.append("ticker", ticker.trim());
    fd.append("exchange", exactPick ? "AS_TYPED" : exchange);
    fd.append("company", company.trim());
    fd.append("horizon", horizon);
    fd.append("agents", [...picked].join(","));
    if (yt.trim()) fd.append("concall_youtube", yt.trim());
    if (concall) fd.append("concall_pdf", concall);
    if (annual) fd.append("annual_report_pdf", annual);
    try {
      const { id } = await startResearch(fd);
      void poll(id);
    } catch (err) {
      setError((err as Error).message);
      if (err instanceof ApiError) setDidYouMean(err.suggestions);
      setBusy(false);
    }
  };

  const pickSymbol = (m: SymbolMatch) => {
    setPicked1(m);
    setTicker(m.symbol);
    setCompany(m.name);
    setError(null);
    setDidYouMean([]);
  };

  const toggle = (name: string) =>
    setPicked((s) => { const n = new Set(s); n.has(name) ? n.delete(name) : n.add(name); return n; });

  const hasConcall = !!concall || !!yt.trim();
  const missingInput = (a: AgentInfo) =>
    (a.name === "concall" && !hasConcall) || (a.name === "annual_report" && !annual);
  const sortedAgents = [...agents].sort((a, b) => STAGE_ORDER[a.stage] - STAGE_ORDER[b.stage]);
  const active = busy || job?.status === "running" || job?.status === "queued";
  const selReport = selected && job ? job.reports[selected] : undefined;

  return (
    <div className="desk">
      <form className="card desk-form" onSubmit={run}>
        <div className="row-fields">
          <SymbolPicker value={ticker} onChange={setTicker} onPick={pickSymbol} prefer={exchange === "BSE" ? "BSE" : "NSE"}
                        disabled={active} />
          <label>Exchange
            <select value={exchange} onChange={(e) => setExchange(e.target.value)} disabled={active}>
              <option value="NSE">India - NSE (.NS)</option>
              <option value="BSE">India - BSE (.BO)</option>
              <option value="US">US / as typed</option>
              <option value="AS_TYPED">Exact Yahoo symbol</option>
            </select>
          </label>
          <label>Company (optional)
            <input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Tata Consultancy Services"
                   disabled={active} />
          </label>
          <div className="seg" role="radiogroup" aria-label="Investment horizon">
            <small>Horizon</small>
            <div>
              {HORIZONS.map(([v, l]) => (
                <button type="button" key={v} className={horizon === v ? "on" : ""} disabled={active}
                        onClick={() => setHorizon(v)}>{l}</button>
              ))}
            </div>
          </div>
        </div>

        <div className="row-fields docs">
          <FilePick label="Earnings call PDF (optional)" file={concall} onPick={setConcall} disabled={active} />
          <input className="yt" type="url" placeholder="...or a YouTube link of the concall" value={yt}
                 onChange={(e) => setYt(e.target.value)} disabled={active || !!concall} />
          <FilePick label="Annual report PDF (optional)" file={annual} onPick={setAnnual} disabled={active} />
        </div>

        <div className="roster">
          {sortedAgents.map((a) => (
            <label key={a.name} className={`roster-card ${picked.has(a.name) ? "on" : ""}`} title={a.description}>
              <input type="checkbox" checked={picked.has(a.name)} onChange={() => toggle(a.name)} disabled={active} />
              <div>
                <b>{a.title}</b>
                <small>{a.model.split("/").pop()}</small>
                {picked.has(a.name) && missingInput(a) && <em>needs {a.needs.toLowerCase()}</em>}
                {!a.llm_ready && <em className="warn">no API key</em>}
              </div>
            </label>
          ))}
        </div>

        <div className="desk-actions">
          <button className="primary" type="submit" disabled={active || !ticker.trim() || picked.size === 0}>
            {active ? "Research team is working..." : "Run research team"}
          </button>
          <small className="muted">Analysts run in parallel, then a bull/bear debate, then the portfolio manager decides.</small>
        </div>
      </form>

      {error && (
        <div className="banner err">
          {error}
          {didYouMean.length > 0 && (
            <div className="dym">
              <span>Did you mean:</span>
              {didYouMean.map((m) => (
                <button type="button" key={m.symbol} onClick={() => pickSymbol(m)}>
                  <b>{m.symbol}</b> {m.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {job && (
        <>
          <div className="card run-head">
            <div>
              <b className="ticker">{job.ticker}</b>
              <span className={`pill ${job.status === "completed" ? "done" : job.status === "failed" ? "failed" : "working"}`}>
                {job.status}
              </span>
            </div>
            <div className="run-progress">
              <div className="bar"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
              <small>{Math.round(job.progress * 100)}% · {job.elapsed_s.toFixed(0)}s elapsed</small>
            </div>
          </div>

          <MissionControl agents={job.agents} selected={selected} onSelect={setSelected} />

          {job.final && <Verdict ticker={job.ticker} final={job.final} reports={job.reports} />}

          <div className="desk-grid">
            <div>
              <h4 className="muted">Live activity</h4>
              <ActivityFeed events={events} live={active} />
            </div>
            <div>
              <h4 className="muted">{selReport ? "Agent report" : "Agent report (click an agent card)"}</h4>
              {selReport && <AgentReportPanel report={selReport} />}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
