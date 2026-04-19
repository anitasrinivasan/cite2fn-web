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
  include_test: boolean;
  test_counts: { jobs: number; events: number; feedback: number };
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
    is_test: boolean;
    created_at: number;
    attachments: { filename: string; mime_type: string; size_bytes: number }[];
  }[];
};

async function fetchStats(
  token: string,
  includeTest: boolean,
): Promise<Stats | { error: string; status: number }> {
  try {
    const url = new URL(`${API_BASE}/api/admin/stats`);
    url.searchParams.set("token", token);
    if (includeTest) url.searchParams.set("include_test", "1");
    const res = await fetch(url, { cache: "no-store" });
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
  searchParams: Promise<{ token?: string; include_test?: string }>;
}) {
  const { token, include_test } = await searchParams;
  const includeTest = include_test === "1" || include_test === "true";

  if (!token) {
    return (
      <ContentLayout title="Admin">
        <p className="text-slate-600 dark:text-slate-400">
          Access token required. Append{" "}
          <code className="font-mono">?token=…</code> to the URL.
        </p>
      </ContentLayout>
    );
  }

  const result = await fetchStats(token, includeTest);
  if ("error" in result) {
    return (
      <ContentLayout title="Admin">
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
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
  const toggleHref = (() => {
    const p = new URLSearchParams();
    p.set("token", token);
    if (!stats.include_test) p.set("include_test", "1");
    return `/admin?${p.toString()}`;
  })();

  const totalTestRows =
    stats.test_counts.jobs + stats.test_counts.events + stats.test_counts.feedback;

  return (
    <ContentLayout title="Admin · Stats">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-slate-200 bg-white px-4 py-3 text-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="text-slate-700 dark:text-slate-300">
          {stats.include_test ? (
            <>
              <span className="font-medium text-amber-800 dark:text-amber-400">
                Showing real + test data.
              </span>{" "}
              Test-marked rows are included in every chart below.
            </>
          ) : (
            <>
              Showing <span className="font-medium">real user data only</span>.
              {totalTestRows > 0 && (
                <>
                  {" "}
                  <span className="text-slate-500 dark:text-slate-500">
                    ({stats.test_counts.jobs} test job
                    {stats.test_counts.jobs === 1 ? "" : "s"}
                    {stats.test_counts.feedback > 0 && (
                      <>, {stats.test_counts.feedback} test feedback</>
                    )}{" "}
                    hidden)
                  </span>
                </>
              )}
            </>
          )}
        </div>
        <a
          href={toggleHref}
          className="rounded-md border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          {stats.include_test ? "Hide test data" : "Include test data"}
        </a>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Jobs (all time)" value={stats.jobs_total} />
        <StatCard label="Jobs (last 7d)" value={stats.jobs_last_7d} />
        <StatCard label="Jobs (last 30d)" value={stats.jobs_last_30d} />
      </div>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900 dark:text-slate-100">Funnel</h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          <Funnel label="Created" value={stats.funnel.created} />
          <Funnel label="Reached review" value={stats.funnel.reached_review} />
          <Funnel label="Done" value={stats.funnel.done} />
          <Funnel label="Downloaded" value={stats.funnel.downloaded} />
          <Funnel label="Errored" value={stats.funnel.errored} />
        </dl>
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900 dark:text-slate-100">
          Daily jobs (last 30 days)
        </h2>
        <svg
          viewBox={`0 0 ${stats.daily_jobs.length * 10} 60`}
          className="h-20 w-full text-slate-900 dark:text-slate-200"
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
                fill="currentColor"
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
        <h2 className="mb-3 text-xl font-semibold text-slate-900 dark:text-slate-100">
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
        <h2 className="mb-3 text-xl font-semibold text-slate-900 dark:text-slate-100">
          Top errors (last 30d)
        </h2>
        {stats.top_errors.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No errors recorded.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-700 dark:text-slate-400">
              <tr>
                <th className="py-2">Error type</th>
                <th className="py-2 text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_errors.map((e) => (
                <tr key={e.error_type} className="border-b border-slate-100 dark:border-slate-800">
                  <td className="py-2 font-mono text-slate-800 dark:text-slate-200">{e.error_type}</td>
                  <td className="py-2 text-right text-slate-800 dark:text-slate-200">{e.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-xl font-semibold text-slate-900 dark:text-slate-100">
          Recent bug reports
        </h2>
        {stats.recent_feedback.length === 0 ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">No feedback yet.</p>
        ) : (
          <ul className="space-y-4">
            {stats.recent_feedback.map((f) => (
              <li
                key={f.id}
                className="rounded-md border border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="flex items-baseline justify-between gap-4">
                  <strong className="text-slate-900 dark:text-slate-100">{f.title}</strong>
                  <span className="text-xs text-slate-500 dark:text-slate-400">
                    {new Date(f.created_at * 1000).toLocaleString()}
                  </span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-slate-700 dark:text-slate-300">
                  {f.description}
                </p>
                {f.attachments.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {f.attachments.map((a) => {
                      const url = `${API_BASE}/api/admin/feedback/${f.id}/attachments/${a.filename}?token=${encodeURIComponent(token)}`;
                      return (
                        <a
                          key={a.filename}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={`${a.filename} (${Math.round(a.size_bytes / 1024)} KB)`}
                          className="block h-20 w-20 overflow-hidden rounded-md border border-slate-200 bg-slate-50 hover:border-slate-400 dark:border-slate-700 dark:bg-slate-800 dark:hover:border-slate-500"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={url}
                            alt={a.filename}
                            className="h-full w-full object-cover"
                          />
                        </a>
                      );
                    })}
                  </div>
                )}
                {(f.email || f.job_id) && (
                  <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
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

      <p className="mt-12 text-xs text-slate-500 dark:text-slate-400">
        Last fetched {new Date(stats.now * 1000).toLocaleString()}.
      </p>
    </ContentLayout>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <p className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
      <p className="mt-1 font-mono text-2xl text-slate-900 dark:text-slate-100">{value}</p>
    </div>
  );
}

function Funnel({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {label}
      </dt>
      <dd className="mt-1 font-mono text-lg text-slate-900 dark:text-slate-100">{value}</dd>
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
    <div className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-medium text-slate-700 dark:text-slate-300">{label}</h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">No data yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {entries.map(([k, v]) => (
            <li key={k} className="flex items-center justify-between">
              <span className="font-mono text-slate-700 dark:text-slate-300">{k}</span>
              <span>
                <span className="mr-2 font-mono text-slate-900 dark:text-slate-100">{v}</span>
                <span className="text-xs text-slate-500 dark:text-slate-500">
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
    <div className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <h3 className="mb-3 text-sm font-medium text-slate-700 dark:text-slate-300">
        Claude model tier
      </h3>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500 dark:text-slate-400">No Claude jobs yet.</p>
      ) : (
        <ul className="space-y-2 text-sm">
          {entries.map(([tier, info]) => (
            <li key={tier}>
              <div className="flex items-center justify-between">
                <span className="font-mono text-slate-700 dark:text-slate-300">{tier}</span>
                <span className="font-mono text-slate-900 dark:text-slate-100">{info.total}</span>
              </div>
              {info.fell_back_to_haiku > 0 && (
                <p className="text-xs text-amber-700 dark:text-amber-400">
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
