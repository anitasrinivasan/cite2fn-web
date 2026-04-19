"use client";

import Link from "next/link";
import { useState } from "react";
import { BugReportModal } from "@/components/BugReportModal";
import { ThemeToggle } from "@/components/ThemeToggle";

export function Header({ jobId }: { jobId?: string | null }) {
  const [bugOpen, setBugOpen] = useState(false);

  return (
    <>
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
          <Link
            href="/"
            className="text-lg font-semibold tracking-tight text-slate-900 hover:text-slate-700 dark:text-slate-100 dark:hover:text-slate-300"
          >
            cite2fn
          </Link>
          <nav className="flex items-center gap-4 text-sm sm:gap-6">
            <Link
              href="/how-it-works"
              className="text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline dark:text-slate-400 dark:hover:text-slate-100"
            >
              How it works
            </Link>
            <button
              type="button"
              onClick={() => setBugOpen(true)}
              className="text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline dark:text-slate-400 dark:hover:text-slate-100"
            >
              Report a bug
            </button>
            <ThemeToggle />
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
