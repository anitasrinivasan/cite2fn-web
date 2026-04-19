"use client";

import Link from "next/link";
import { useState } from "react";
import { BugReportModal } from "@/components/BugReportModal";

export function Header({ jobId }: { jobId?: string | null }) {
  const [bugOpen, setBugOpen] = useState(false);

  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link
            href="/"
            className="text-lg font-semibold tracking-tight text-slate-900 hover:text-slate-700"
          >
            cite2fn
          </Link>
          <nav className="flex items-center gap-6 text-sm">
            <Link
              href="/how-it-works"
              className="text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline"
            >
              How it works
            </Link>
            <button
              type="button"
              onClick={() => setBugOpen(true)}
              className="text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline"
            >
              Report a bug
            </button>
          </nav>
        </div>
      </header>
      <BugReportModal
        open={bugOpen}
        onClose={() => setBugOpen(false)}
        jobId={jobId}
      />
    </>
  );
}
