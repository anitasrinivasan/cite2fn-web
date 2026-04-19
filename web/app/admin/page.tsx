import type { Metadata } from "next";
import { ContentLayout } from "@/components/ContentLayout";

export const metadata: Metadata = {
  title: "Admin — cite2fn",
  robots: "noindex, nofollow",
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Stats = {
  now: number;
  jobs_total: number;
  jobs_last_7d: number;
  jobs_last_30d: number;
  funnel: {
    created: number;
    reached_review: number;
    done: number;
    downloaded: number;
    errored: number;
  };
  style_breakdown: Record<string, number>;
  output_format_breakdown: Record<string, number>;
  llm_backend_breakdown: Record<string, number>;
  claude_tier_breakdown: Record<
    string,
    { total: number; fell_back_to_haiku: number }
  >;
  citation_averages: {
    avg_total: number | null;
    avg_confident: number | null;
    avg_needs_review: number | null;
  };
  top_errors: { error_type: string; count: number }[];
  daily_jobs: { date: string; count: number }[];
  recent_feedback: {
    id: number;
    title: string;
    description: string;
    email: string | null;
    job_id: string | null;
    user_agent: string | null;
    created_at: number;
  }[];
};

async function fetchStats(token: string): Promise<Stats | { error: string; status: number }> {
  try {
    const res = await fetch(
      `${API_BASE}/api/admin/stats?token=${encodeURIComponent(token)}`,
      { cache: "no-store" },
    );
    if (!res.ok) {
      return { error: await safeText(res), status: res.status };
    }
    return (await res.json()) as Stats;
  } catch (e) {
    return { error: e instanceof Error ? e.message : String(e), status: 0 };
  }
}

async function safeText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body);
  } catch {
    return `${res.status} ${res.statusText}`;
  }
}

export default async function AdminPage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;

  if (!token) {
    return (
      <ContentLayout title="Admin">
        <p className="text-slate-600">
          Access token required. Append{" "}
          <code className="font-mono">?token=…</code> to the URL.
        </p>
      </ContentLayout>
    );
  }

  const result = await fetchStats(token);
  if ("error" in result) {
    return (
      <ContentLayout title="Admin">
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {result.status === 401
            ? "Invalid token."
            : result.status === 404
            ? "Admin area not configured on this server."
            : `Error: ${result.error}`}
        </div>
      </ContentLayout>
    );
  }

  const stats = result;
  const maxDaily = Math.max(1, ...stats.daily_jobs.map((d) => d.count));

  return (
    <ContentLayout title="Admin · Stats">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Jobs (all time)" value={stats.jobs_total} />
        <StatCard label="Jobs (last 7d)" value={stats.jobs_last_7d} />
        <StatCard label="Jobs (last 30d)" value={stats.jobs_last_30d} />
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">Funnel</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Funnel label="Created" value={stats.funnel.created} />
          <Funnel label="Reached review" value={stats.funnel.reached_review} />
          <Funnel label="Done" value={stats.funnel.done} />
          <Funnel label="Downloaded" value={stats.funnel.downloaded} />
          <Funnel label="Errored" value={stats.funnel.errored} />
        </dl>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">
          Daily jobs (last 30 days)
        </h2>
        <svg
          viewBox={`0 0 ${stats.daily_jobs.length * 10} 60`}
          className="h-20 w-full"
          preserveAspectRatio="none"
          aria-label="Daily job counts bar chart"
        >
          {stats.daily_jobs.map((d, i) => {
            const h = (d.count / maxDaily) * 55;
            return (
              <rect
                key={d.date}
                x={i * 10 + 1}
                y={60 - h}
                width={8}
                height={h}
                fill="#0f172a"
              >
                <title>{`${d.date}: ${d.count}`}</title>
              </rect>
            );
          })}
        </svg>
      </section>

      <section className="mt-10 grid grid-cols-1 gap-6 sm:grid-cols-2">
        <Breakdown label="Style" data={stats.style_breakdown} />
        <Breakdown label="Output format" data={stats.output_format_breakdown} />
        <Breakdown label="LLM backend" data={stats.llm_backend_breakdown} />
        <ClaudeTier data={stats.claude_tier_breakdown} />
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">
          Citation averages (per doc)
        </h2>
        <dl className="grid grid-cols-3 gap-3">
          <Funnel
            label="Detected"
            value={fmt(stats.citation_averages.avg_total)}
          />
          <Funnel
            label="High confidence"
            value={fmt(stats.citation_averages.avg_confident)}
          />
          <Funnel
            label="Needs review"
            value={fmt(stats.citation_averages.avg_needs_review)}
          />
        </dl>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">
          Top errors (last 30d)
        </h2>
        {stats.top_errors.length === 0 ? (
          <p className="text-sm text-slate-500">No errors recorded.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="py-2">Error type</th>
                <th className="py-2 text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_errors.map((e) => (
                <tr key={e.error_type} className="border-b border-slate-100">
                  <td className="py-2 font-mono">{e.error_type}</td>
                  <td className="py-2 text-right">{e.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900">
          Recent bug reports
        </h2>
        {stats.recent_feedback.length === 0 ? (
          <p className="text-sm text-slate-500">No feedback yet.</p>
        ) : (
          <ul className="space-y-4">
            {stats.recent_feedback.map((f) => (
              <li
                key={f.id}
                className="rounded-md border border-slate-200 bg-white p-4 text-sm"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <strong className="text-slate-900">{f.title}</strong>
                  <span className="text-xs text-slate-500">
                    {new Date(f.created_at * 1000).toLocaleString()}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-slate-700">
                  {f.description}
                </p>
                {(f.email || f.job_id) && (
                  <p className="mt-2 text-xs text-slate-500">
                    {f.email && (
                      <span>
                        reply: <code className="font-mono">{f.email}</code>
                      </span>
                    )}
                    {f.email && f.job_id && " · "}
                    {f.job_id && (
                      <span>
                        job: <code className="font-mono">{f.job_id.slice(0, 10)}…</code>
                      </span>
                    )}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mt-12 text-xs text-slate-500">
        Last fetched {new Date(stats.now * 1000).toLocaleString()}.
      </p>
    </ContentLayout>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 font-mono text-2xl text-slate-900">{value}</p>
    </div>
  );
}

function Funnel({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <dt className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-lg text-slate-900">{value}</dd>
    </div>
  );
}

function Breakdown({
  label,
  data,
}: {
  label: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data);
  const total = entries.reduce((acc, [, v]) => acc + v, 0) || 1;
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-medium text-slate-700">{label}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">No data yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {entries.map(([k, v]) => (
            <li key={k} className="flex items-center justify-between">
              <span className="font-mono text-slate-700">{k}</span>
              <span>
                <span className="mr-2 font-mono text-slate-900">{v}</span>
                <span className="text-xs text-slate-500">
                  ({Math.round((v / total) * 100)}%)
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ClaudeTier({
  data,
}: {
  data: Record<string, { total: number; fell_back_to_haiku: number }>;
}) {
  const entries = Object.entries(data);
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-medium text-slate-700">
        Claude model tier
      </h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">No Claude jobs yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {entries.map(([tier, info]) => (
            <li key={tier}>
              <div className="flex items-center justify-between">
                <span className="font-mono text-slate-700">{tier}</span>
                <span className="font-mono text-slate-900">{info.total}</span>
              </div>
              {info.fell_back_to_haiku > 0 && (
                <p className="text-xs text-amber-700">
                  {info.fell_back_to_haiku} fell back to Haiku
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function fmt(value: number | null): string {
  if (value === null) return "—";
  return value.toString();
}
