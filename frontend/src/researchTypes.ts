export type AgentStage = "analyst" | "debate" | "decision";
export type AgentStatus = "pending" | "working" | "done" | "skipped" | "failed";

export interface SymbolMatch {
  symbol: string;
  name: string;
  exchange: string;
  type?: string | null;
}

export interface AgentInfo {
  name: string;
  title: string;
  description: string;
  stage: AgentStage;
  enabled: boolean;
  model: string;
  needs: string;
  llm_ready: boolean;
}

export interface AgentLive {
  title: string;
  stage: AgentStage;
  model: string;
  status: AgentStatus;
  rating?: string;
  score?: number;
  confidence?: number;
  message?: string;
}

export interface ResearchEvent {
  i: number;
  ts: number;
  agent: string;
  level: "info" | "success" | "warn" | "error";
  kind: string;
  message: string;
}

export interface AgentReport {
  agent: string;
  title: string;
  stage: AgentStage;
  status: "done" | "skipped" | "failed";
  rating: string;
  score: number;
  confidence: number;
  headline: string;
  summary: string;
  key_points: string[];
  risks: string[];
  extra: Record<string, string[]>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  data: Record<string, any>;
  model: string;
  degraded: boolean;
  error: string | null;
  duration_s: number;
}

export interface ResearchJob {
  id: string;
  ticker: string;
  company: string;
  horizon: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  agents: Record<string, AgentLive>;
  events: ResearchEvent[];
  next_index: number;
  reports: Record<string, AgentReport>;
  final: AgentReport | null;
  error: string | null;
  started_at: number;
  elapsed_s: number;
}
