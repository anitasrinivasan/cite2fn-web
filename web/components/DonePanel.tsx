import type { Job } from "@/lib/types";
import { downloadUrl } from "@/lib/api";

export function DonePanel({ job, onReset }: { job: Job; onReset: () => void }) {
  const report = job.progress?.report ?? {};
  const issues = report.issues ?? [];

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-6 dark:border-emerald-800 dark:bg-emerald-950">
        <h2 className="text-lg font-semibold text-emerald-900 dark:text-emerald-100">
          Your document is ready
        </h2>
        <p className="mt-1 text-sm text-emerald-800 dark:text-emerald-300">
          Every citation has been reviewed and inserted as{" "}
          {job.output_format === "references" ? "a reference list" : job.output_format}.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <a
            href={downloadUrl(job.id)}
            className="inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300"
          >
            Download .docx
          </a>
          <button
            onClick={onReset}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Convert another document
          </button>
        </div>
      </div>

      <details className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
        <summary className="cursor-pointer text-sm font-medium text-slate-800 dark:text-slate-200">
          View report
        </summary>
        <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
          <Stat label="Total citations" value={report.total_citations ?? "—"} />
          <Stat
            label="Footnotes inserted"
            value={report.footnotes_inserted ?? "—"}
          />
          <Stat
            label="Existing footnotes converted"
            value={report.existing_footnotes_converted ?? "—"}
          />
          <Stat
            label="Comments added"
            value={report.comments_added ?? "—"}
          />
          <Stat
            label="References listed"
            value={report.references_listed ?? "—"}
          />
          <Stat
            label="References section removed"
            value={report.references_removed ? "yes" : "no"}
          />
        </dl>
        {issues.length > 0 && (
          <div className="mt-4">
            <p className="mb-2 text-sm font-medium text-slate-800 dark:text-slate-200">Issues</p>
            <ul className="list-disc space-y-1 pl-5 text-xs text-slate-700 dark:text-slate-400">
              {issues.map((i, idx) => (
                <li key={idx}>{i}</li>
              ))}
            </ul>
          </div>
        )}
      </details>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className="mt-0.5 font-mono text-slate-900 dark:text-slate-100">{value}</dd>
    </div>
  );
}
