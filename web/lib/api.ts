import type {
  Citation,
  ClaudeModelTier,
  Job,
  LLMBackend,
  OutputFormat,
  Style,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type UploadOptions = {
  file: File;
  style: Style;
  output_format: OutputFormat;
  llm_backend: LLMBackend;
  claude_api_key?: string;
  claude_model_tier?: ClaudeModelTier;
  keep_references?: boolean;
};

export async function uploadJob(opts: UploadOptions): Promise<Job> {
  const form = new FormData();
  form.set("file", opts.file);
  form.set("style", opts.style);
  form.set("output_format", opts.output_format);
  form.set("llm_backend", opts.llm_backend);
  if (opts.claude_api_key) form.set("claude_api_key", opts.claude_api_key);
  if (opts.claude_model_tier) form.set("claude_model_tier", opts.claude_model_tier);
  if (opts.keep_references) form.set("keep_references", "true");

  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const detail = await extractError(res);
    throw new Error(detail);
  }
  return (await res.json()) as Job;
}

export type FeedbackPayload = {
  title: string;
  description: string;
  email?: string;
  job_id?: string;
  attachments?: File[];
};

export async function submitFeedback(payload: FeedbackPayload): Promise<void> {
  const form = new FormData();
  form.set("title", payload.title);
  form.set("description", payload.description);
  if (payload.email) form.set("email", payload.email);
  if (payload.job_id) form.set("job_id", payload.job_id);
  for (const file of payload.attachments ?? []) {
    form.append("attachments", file);
  }

  const res = await fetch(`${API_BASE}/api/feedback`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(await extractError(res));
}

export async function getJob(jobId: string): Promise<Job | null> {
  const res = await fetch(`${API_BASE}/api/jobs/${encodeURIComponent(jobId)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await extractError(res));
  return (await res.json()) as Job;
}

export async function submitReview(
  jobId: string,
  citations: Pick<Citation, "id" | "bluebook_text" | "confidence">[],
): Promise<Job> {
  const res = await fetch(
    `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/review`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ citations }),
    },
  );
  if (!res.ok) throw new Error(await extractError(res));
  return (await res.json()) as Job;
}

export function downloadUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/download`;
}

async function extractError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}
