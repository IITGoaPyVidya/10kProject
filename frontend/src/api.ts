import type { AppConfig, DocType, Job, Mode } from "./types";

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch { /* non-JSON error body */ }
    throw new Error(detail);
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
