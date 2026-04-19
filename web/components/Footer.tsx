import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-4xl space-y-3 px-6 py-6 text-xs text-slate-500">
        <p>
          Uploaded documents and outputs auto-delete after 24 hours. No account
          required. We don&apos;t store your Claude API key or share your
          documents.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <a
            href="https://www.anitasrinivasan.com"
            target="_blank"
            rel="noopener noreferrer"
            className="underline-offset-4 hover:text-slate-900 hover:underline"
          >
            © 2026 Anita Srinivasan
          </a>
          <div className="flex items-center gap-4">
            <Link
              href="/terms"
              className="underline-offset-4 hover:text-slate-900 hover:underline"
            >
              Terms
            </Link>
            <Link
              href="/privacy"
              className="underline-offset-4 hover:text-slate-900 hover:underline"
            >
              Privacy
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
