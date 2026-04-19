"use client";

import { useState } from "react";
import { DonePanel } from "@/components/DonePanel";
import { ErrorPanel } from "@/components/ErrorPanel";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { ProgressPanel } from "@/components/ProgressPanel";
import { ReviewTable } from "@/components/ReviewTable";
import { UploadZone, type UploadSubmission } from "@/components/UploadZone";
import { submitReview, uploadJob } from "@/lib/api";
import { useHashJobId } from "@/lib/useHashJobId";
import { useJob } from "@/lib/useJob";

export default function Home() {
  const [jobId, setJobId] = useHashJobId();
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const { job, loading, notFound, error: pollError, refresh } = useJob(jobId);

  const reset = () => {
    setJobId(null);
    setUploadError(null);
  };

  const handleUpload = async (sub: UploadSubmission) => {
    setUploadError(null);
    setSubmitting(true);
    try {
      const created = await uploadJob(sub);
      setJobId(created.id);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async (
    edited: { id: string; bluebook_text: string | null; confidence: string | null }[],
  ) => {
    if (!jobId) return;
    setSubmitting(true);
    try {
      await submitReview(jobId, edited);
      await refresh();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  let body: React.ReactNode;

  if (!jobId) {
    body = <Landing onUpload={handleUpload} disabled={submitting} error={uploadError} />;
  } else if (notFound) {
    body = (
      <ErrorPanel
        message="We couldn't find that job. It may have expired or been cleaned up."
        onReset={reset}
      />
    );
  } else if (pollError) {
    body = <ErrorPanel message={pollError} onReset={reset} />;
  } else if (loading || !job) {
    body = <LoadingShell />;
  } else if (job.status === "error") {
    body = <ErrorPanel message={job.error ?? "Unknown error"} onReset={reset} />;
  } else if (job.status === "done") {
    body = <DonePanel job={job} onReset={reset} />;
  } else if (job.status === "awaiting_review") {
    body = (
      <ReviewTable
        citations={job.citations ?? []}
        onAccept={handleReview}
        submitting={submitting}
        sonnetFellBack={job.sonnet_fell_back}
      />
    );
  } else {
    body = <ProgressPanel job={job} />;
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <Header jobId={jobId} />
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">{body}</main>
      <Footer />
    </div>
  );
}

function Landing({
  onUpload,
  disabled,
  error,
}: {
  onUpload: (sub: UploadSubmission) => void;
  disabled: boolean;
  error: string | null;
}) {
  return (
    <div className="space-y-10">
      <div className="space-y-3">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Convert citations in any <code className="font-mono">.docx</code> to
          Bluebook or APA
        </h1>
        <p className="max-w-2xl text-slate-600">
          Upload a Word document with linked sources — hyperlinks, parenthetical
          citations, inline author-date references. We&apos;ll pull metadata
          from each source, format every citation in your chosen style, and
          return a new document with footnotes, endnotes, or a reference list.
        </p>
      </div>
      <UploadZone onSubmit={onUpload} disabled={disabled} error={error} />
    </div>
  );
}

function LoadingShell() {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-8 text-sm text-slate-600">
      Loading…
    </div>
  );
}
