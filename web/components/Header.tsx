import Link from "next/link";

const BUG_URL =
  process.env.NEXT_PUBLIC_BUG_REPORT_URL ??
  "https://github.com/anitasrinivasan/cite2fn-web/issues/new?title=Bug%20report&labels=bug";

export function Header() {
  return (
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
          <a
            href={BUG_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline"
          >
            Report a bug
          </a>
        </nav>
      </div>
    </header>
  );
}
