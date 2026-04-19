"use client";

import { useEta } from "@/lib/useEta";
import type { Job } from "@/lib/types";

const PHASE_COPY: Record<string, { title: string; subtitle: string }> = {
  pending: {
    title: "Starting…",
    subtitle: "Queued for processing.",
  },
  detecting: {
    title: "Detecting citations",
    subtitle: "Scanning the document for hyperlinks, parentheticals, and inline references.",
  },
  fetching: {
    title: "Fetching source metadata",
    subtitle: "Pulling title, authors, and publication info from each linked source.",
  },
  formatting: {
    title: "Formatting citations",
    subtitle: "Turning metadata into properly styled citation text.",
  },
  assembling: {
    title: "Assembling your document",
    subtitle: "Inserting footnotes and cleaning up the body text.",
  },
};

export function ProgressPanel({ job }: { job: Job }) {
  const phase = job.progress?.phase ?? job.status;
  const copy = PHASE_COPY[phase] ?? PHASE_COPY.pending;

  const done = job.progress?.done ?? 0;
  const total = job.progress?.total ?? 0;
  const showBar = total > 0 && (phase === "fetching" || phase === "formatting");
  const eta = useEta(showBar ? phase : undefined, done, total);

  return (
    <div className="space-y-6 rounded-lg border border-slate-200 bg-white p-8">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-slate-900">{copy.title}</h2>
        <p className="text-sm text-slate-600">{copy.subtitle}</p>
      </div>

      {showBar ? (
        <div className="space-y-2">
          <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full bg-slate-900 transition-all"
              style={{ width: `${Math.min(100, (done / total) * 100)}%` }}
            />
          </div>
          <div className="flex items-baseline justify-between">
            <p className="font-mono text-xs text-slate-600">
              {done} / {total}
            </p>
            {eta && <p className="text-xs text-slate-500">{eta}</p>}
          </div>
        </div>
      ) : (
        <Spinner />
      )}
    </div>
  );
}

function Spinner() {
  return (
    <div className="flex items-center gap-3">
      <svg
        className="h-5 w-5 animate-spin text-slate-900"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
        <path
          d="M22 12a10 10 0 0 1-10 10"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <span className="text-sm text-slate-600">Working…</span>
    </div>
  );
}
