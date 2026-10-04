import { useCallback, useEffect, useRef, useState } from "react";

import { createAnalysis, getAnalysis, getConfig } from "./api";
import { Results } from "./components/Results";
import type { AppConfig, DocType, Job, Mode } from "./types";

const TABS: { id: DocType; label: string }[] = [
  { id: "transcript", label: "Earnings Transcripts" },
  { id: "filing", label: "10-K / Filings" },
];
const POLL_MS = 2000;

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("llm");
  const [docType, setDocType] = useState<DocType>("transcript");
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number>();

  useEffect(() => {
    getConfig().then(setConfig).catch((e) => setConfigError(e.message));
    return () => window.clearTimeout(timer.current);
  }, []);

  const poll = useCallback((id: string) => {
    getAnalysis(id)
      .then((j) => {
        setJob(j);
        if (j.status === "queued" || j.status === "processing") {
          timer.current = window.setTimeout(() => poll(id), POLL_MS);
        } else {
          setBusy(false);
        }
      })
      .catch((e) => { setError(e.message); setBusy(false); });
  }, []);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    window.clearTimeout(timer.current);
    setError(null);
    setJob(null);
    setBusy(true);
    try {
      const { id } = await createAnalysis(file, docType, mode);
      poll(id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const switchTab = (t: DocType) => {
    window.clearTimeout(timer.current);
    setDocType(t); setJob(null); setError(null); setBusy(false);
  };

  const llmOk = !!config?.llm_configured;
  const localOk = docType === "filing" || !!config?.local_model_available;
  const modeOptions: { id: Mode; label: string; enabled: boolean }[] = [
    { id: "llm", label: "LLM only", enabled: llmOk },
    { id: "local", label: "Local only", enabled: localOk },
    { id: "both", label: "Both", enabled: llmOk && localOk },
  ];

  return (
    <div className="layout">
      <aside className="sidebar">
        <h1>AlphaInsight</h1>
        <h3>Analysis mode</h3>
        {modeOptions.map((o) => (
          <label key={o.id} className={o.enabled ? "" : "disabled"}>
            <input type="radio" name="mode" checked={mode === o.id} disabled={!o.enabled}
                   onChange={() => setMode(o.id)} />
            {o.label}
          </label>
        ))}
        <h3>System status</h3>
        {configError && <p className="err">API unreachable: {configError}</p>}
        {config && (
          <ul className="status">
            <li><b>Mode:</b> {modeOptions.find((o) => o.id === mode)?.label}</li>
            <li><span className={`dot ${llmOk ? "ok" : "off"}`} />
              LLM API: {llmOk ? "Active" : "Inactive (no key)"}</li>
            <li className="muted">{config.llm_model}</li>
            <li><span className={`dot ${config.local_model_available ? "ok" : "off"}`} />
              Local FinBERT: {config.local_model_available ? "Installed" : "Not installed"}</li>
          </ul>
        )}
      </aside>

      <main>
        <nav className="tabs">
          {TABS.map((t) => (
            <button key={t.id} className={t.id === docType ? "active" : ""} onClick={() => switchTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>

        <label className="upload">
          <input type="file" accept="application/pdf" disabled={busy}
                 onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
          <span>{busy ? "Processing..." : "Choose a PDF to analyze"}</span>
          {config && <small>Max {config.max_upload_mb} MB. Long reports can take a few minutes.</small>}
        </label>

        {error && <div className="banner err">{error}</div>}
        {job && (job.status === "queued" || job.status === "processing") && (
          <div className="progress" role="status">
            <div className="bar"><div style={{ width: `${Math.round(job.progress * 100)}%` }} /></div>
            <span>{job.message}</span>
          </div>
        )}
        {job?.status === "failed" && <div className="banner err">{job.error ?? "Analysis failed."}</div>}
        {job?.status === "completed" && job.result && <Results job={job} result={job.result} />}
      </main>
    </div>
  );
}
