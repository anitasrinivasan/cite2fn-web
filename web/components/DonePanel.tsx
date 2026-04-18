import type { Job } from "@/lib/types";
import { downloadUrl } from "@/lib/api";

export function DonePanel({ job, onReset }: { job: Job; onReset: () => void }) {
  const report = job.progress?.report ?? {};
  const issues = report.issues ?? [];

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-6">
        <h2 className="text-lg font-semibold text-emerald-900">
          Your document is ready
        </h2>
        <p className="mt-1 text-sm text-emerald-800">
          Every citation has been reviewed and inserted as{" "}
          {job.output_format === "references" ? "a reference list" : job.output_format}.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <a
            href={downloadUrl(job.id)}
            className="inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700"
          >
            Download .docx
          </a>
          <button
            onClick={onReset}
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100"
          >
            Convert another document
          </button>
        </div>
      </div>

      <details className="rounded-md border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-sm font-medium text-slate-800">
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
            <p className="mb-2 text-sm font-medium text-slate-800">Issues</p>
            <ul className="list-disc space-y-1 pl-5 text-xs text-slate-700">
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
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-mono text-slate-900">{value}</dd>
    </div>
  );
}
