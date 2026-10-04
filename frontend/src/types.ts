export type DocType = "transcript" | "filing";
export type Mode = "llm" | "local" | "both";
export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface AppConfig {
  llm_configured: boolean;
  llm_model: string;
  local_model_available: boolean;
  max_upload_mb: number;
}

export interface DriftPoint { segment: number; score: number; positive: number; negative: number }
export interface Question { question: string; negative: number; response: string }
export interface Extreme { label: string; strength: number; sentence: string }
export interface Sentiment {
  summary: { sentences: number; avg_score: number; extreme_count: number };
  drift: DriftPoint[];
  questions: Question[];
  extremes: Extreme[];
}
export interface RedFlags { score: number; flags: { flag: string; weight: number; mentions: number }[] }

export interface AnalysisResult {
  stats: { pages: number; chars: number };
  sentiment?: Sentiment;
  red_flags?: RedFlags;
  llm?: { model: string; report_markdown: string };
}

export interface Job {
  id: string;
  status: JobStatus;
  progress: number;
  message: string;
  doc_type: DocType;
  mode: Mode;
  filename: string;
  error: string | null;
  result: AnalysisResult | null;
}
