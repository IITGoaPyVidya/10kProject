import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { AnalysisResult, Job, RedFlags, Sentiment } from "../types";
import { useNarrow } from "../useNarrow";

function SentimentView({ s }: { s: Sentiment }) {
  return (
    <>
      <div className="metrics">
        <div><small>Sentences</small><b>{s.summary.sentences}</b></div>
        <div><small>Avg net sentiment</small><b>{s.summary.avg_score.toFixed(3)}</b></div>
        <div><small>Extreme sentences</small><b>{s.summary.extreme_count}</b></div>
      </div>

      <h2>Sentiment Drift</h2>
      <div className="chart">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={s.drift}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="segment" label={{ value: "Call progression", position: "insideBottom", offset: -4 }} />
            <YAxis domain={[-1, 1]} />
            <Tooltip formatter={(v: number) => v.toFixed(3)} />
            <ReferenceLine y={0} strokeDasharray="4 4" />
            <Line type="monotone" dataKey="score" name="Net sentiment" stroke="#2563eb" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <h2>Aggressive Analyst Questions &amp; Management Responses</h2>
      {s.questions.length === 0 ? <p className="muted">No question sentences detected.</p> : (
        <div className="table-scroll">
          <table>
            <thead><tr><th>Question</th><th>Neg.</th><th>Response snippet</th></tr></thead>
            <tbody>
              {s.questions.map((q, i) => (
                <tr key={i}><td>{q.question}</td><td>{q.negative}</td><td>{q.response}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Extreme Shift Sentences</h2>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Label</th><th>Strength</th><th>Sentence</th></tr></thead>
          <tbody>
            {s.extremes.map((e, i) => (
              <tr key={i}><td>{e.label}</td><td>{e.strength}</td><td>{e.sentence}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function RedFlagView({ r }: { r: RedFlags }) {
  const narrow = useNarrow();
  const data = [...r.flags].sort((a, b) => b.mentions - a.mentions);
  return (
    <>
      <h2>Corporate Integrity Scorecard</h2>
      <div className="metrics">
        <div><small>Integrity score (0-100)</small><b>{r.score}</b></div>
      </div>
      <div className="chart">
        <ResponsiveContainer width="100%" height={Math.max(260, data.length * 32)}>
          <BarChart data={data} layout="vertical" margin={{ left: narrow ? 0 : 120 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" allowDecimals={false} />
            <YAxis type="category" dataKey="flag" width={narrow ? 110 : 200} tick={{ fontSize: narrow ? 10 : 12 }} />
            <Tooltip />
            <Bar dataKey="mentions" fill="#dc2626" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

export function TranscriptBox({ text }: { text: string }) {
  return (
    <details open>
      <summary><b>Transcript</b></summary>
      <pre className="transcript">{text}</pre>
    </details>
  );
}

export function Results({ job, result }: { job: Job; result: AnalysisResult }) {
  return (
    <section className="results">
      <p className="muted">
        {job.filename} - {result.stats.pages !== undefined
          ? `${result.stats.pages} pages`
          : `${Math.round((result.stats.duration_s ?? 0) / 60)} min video`}, {result.stats.chars.toLocaleString()} characters
      </p>
      {result.transcript && <TranscriptBox text={result.transcript} />}
      {result.sentiment && <SentimentView s={result.sentiment} />}
      {result.red_flags && <RedFlagView r={result.red_flags} />}
      {result.llm && (
        <>
          <h2>{job.doc_type === "transcript" ? "Adversarial Analyst Report" : "Structural Risk Summary"}
            <small className="muted"> ({result.llm.model})</small></h2>
          <article className="markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.llm.report_markdown}</ReactMarkdown>
          </article>
        </>
      )}
    </section>
  );
}
