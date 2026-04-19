"use client";

import { useMemo, useState } from "react";
import type { Citation } from "@/lib/types";

export function ReviewTable({
  citations,
  onAccept,
  submitting,
}: {
  citations: Citation[];
  onAccept: (edited: Pick<Citation, "id" | "bluebook_text" | "confidence">[]) => void;
  submitting: boolean;
}) {
  const [edits, setEdits] = useState<Record<string, string>>({});

  const flaggedCount = useMemo(
    () => citations.filter((c) => c.confidence === "needs_review").length,
    [citations],
  );

  const handleAccept = () => {
    const payload = citations.map((c) => ({
      id: c.id,
      bluebook_text: edits[c.id] ?? c.bluebook_text ?? "",
      confidence: c.confidence,
    }));
    onAccept(payload);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">
            Review your citations
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            {citations.length} detected
            {flaggedCount > 0 && (
              <>
                {" "}
                &middot;{" "}
                <span className="font-medium text-amber-700">
                  {flaggedCount} flagged for review
                </span>
              </>
            )}
            . Edit anything that needs fixing, then accept to generate the document.
          </p>
        </div>
      </div>

      <ul className="space-y-4">
        {citations.map((c) => {
          const flagged = c.confidence === "needs_review";
          const value = edits[c.id] ?? c.bluebook_text ?? "";
          return (
            <li
              key={c.id}
              className={`rounded-md border p-4 ${
                flagged
                  ? "border-amber-300 bg-amber-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="mb-2 flex items-start justify-between gap-4">
                <div className="min-w-0 space-y-0.5">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                    Original:{" "}
                    <span className="font-mono normal-case text-slate-700">
                      {c.display_text}
                    </span>
                  </p>
                  {c.url && (
                    <p className="text-xs text-slate-500">
                      Source:{" "}
                      <a
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-slate-700 underline-offset-2 hover:text-slate-900 hover:underline break-all"
                      >
                        {c.url}
                      </a>
                    </p>
                  )}
                </div>
                {flagged && (
                  <span className="shrink-0 rounded-full bg-amber-200 px-2 py-0.5 text-xs font-medium text-amber-900">
                    Needs review
                  </span>
                )}
              </div>
              <textarea
                value={value}
                onChange={(e) =>
                  setEdits((prev) => ({ ...prev, [c.id]: e.target.value }))
                }
                rows={Math.max(2, Math.ceil(value.length / 80))}
                className="w-full resize-y rounded-md border border-slate-300 bg-white p-2 font-mono text-sm text-slate-900 focus:border-slate-900 focus:outline-none"
              />
            </li>
          );
        })}
      </ul>

      <div className="flex justify-end gap-3">
        <button
          onClick={handleAccept}
          disabled={submitting}
          className="rounded-md bg-slate-900 px-6 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {submitting ? "Submitting…" : "Accept and generate document"}
        </button>
      </div>
    </div>
  );
}
