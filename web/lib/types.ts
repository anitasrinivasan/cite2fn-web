export type JobStatus =
  | "pending"
  | "detecting"
  | "fetching"
  | "formatting"
  | "awaiting_review"
  | "assembling"
  | "done"
  | "error";

export type Style = "bluebook" | "apa";
export type OutputFormat = "footnotes" | "endnotes" | "references";
export type LLMBackend = "claude" | "groq";

export type Progress = {
  phase?: string;
  done?: number;
  total?: number;
  total_citations?: number;
  report?: {
    total_citations?: number;
    footnotes_inserted?: number;
    existing_footnotes_converted?: number;
    comments_added?: number;
    references_listed?: number;
    references_removed?: boolean;
    issues?: string[];
  };
};

export type Citation = {
  id: string;
  type: string;
  display_text: string;
  surrounding_sentence: string;
  url: string | null;
  bluebook_text: string | null;
  confidence: string | null;
};

export type Job = {
  id: string;
  status: JobStatus;
  style: Style;
  output_format: OutputFormat;
  llm_backend: LLMBackend;
  progress: Progress;
  error: string | null;
  created_at: number;
  updated_at: number;
  citations?: Citation[];
};

export const ACTIVE_STATUSES: readonly JobStatus[] = [
  "pending",
  "detecting",
  "fetching",
  "formatting",
  "assembling",
];

export function isActive(status: JobStatus): boolean {
  return (ACTIVE_STATUSES as readonly string[]).includes(status);
}
