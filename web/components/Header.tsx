const BUG_URL =
  process.env.NEXT_PUBLIC_BUG_REPORT_URL ??
  "https://github.com/anitasrinivasan/cite2fn-web/issues/new?title=Bug%20report&labels=bug";

export function Header({ onReset }: { onReset?: () => void }) {
  return (
    <header className="border-b border-slate-200">
      <div className="mx-auto flex max-w-4xl items-center justify-between px-6 py-4">
        <button
          className="text-lg font-semibold tracking-tight text-slate-900 hover:text-slate-700"
          onClick={onReset}
          aria-label="Start over"
        >
          cite2fn
        </button>
        <a
          href={BUG_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline"
        >
          Report a bug
        </a>
      </div>
    </header>
  );
}
