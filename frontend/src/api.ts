import type { AgentInfo, AppConfig, DocType, Job, Mode, ResearchJob, SymbolMatch } from "./types";

/** API error that may carry 'did you mean' symbol suggestions. */
export class ApiError extends Error {
  constructor(message: string, public suggestions: SymbolMatch[] = []) { super(message); }
}

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    let suggestions: SymbolMatch[] = [];
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail?.message) { detail = body.detail.message; suggestions = body.detail.suggestions ?? []; }
    } catch { /* non-JSON error body */ }
    throw new ApiError(detail, suggestions);
  }
  return res.json() as Promise<T>;
}

export const getConfig = (): Promise<AppConfig> => fetch("/api/v1/config").then(parse<AppConfig>);

export async function createAnalysis(file: File, docType: DocType, mode: Mode): Promise<{ id: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", docType);
  form.append("mode", mode);
  return parse(await fetch("/api/v1/analyses", { method: "POST", body: form }));
}

export const getAnalysis = (id: string): Promise<Job> => fetch(`/api/v1/analyses/${id}`).then(parse<Job>);

export const getAgents = (): Promise<AgentInfo[]> => fetch("/api/v1/research/agents").then(parse<AgentInfo[]>);

export const searchSymbols = (q: string, prefer: string, signal: AbortSignal): Promise<SymbolMatch[]> =>
  fetch(`/api/v1/research/search?q=${encodeURIComponent(q)}&prefer=${prefer}`, { signal }).then(parse<SymbolMatch[]>);

export async function startResearch(form: FormData): Promise<{ id: string }> {
  return parse(await fetch("/api/v1/research", { method: "POST", body: form }));
}

export const getResearch = (id: string, since: number): Promise<ResearchJob> =>
  fetch(`/api/v1/research/${id}?since=${since}`).then(parse<ResearchJob>);

export async function createYoutubeAnalysis(url: string, mode: Mode): Promise<{ id: string }> {
  return parse(await fetch("/api/v1/analyses/youtube", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, mode }),
  }));
}
