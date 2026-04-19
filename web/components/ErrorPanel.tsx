export function ErrorPanel({
  message,
  onReset,
}: {
  message: string;
  onReset: () => void;
}) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6 dark:border-red-900 dark:bg-red-950">
      <h2 className="text-lg font-semibold text-red-900 dark:text-red-100">Something went wrong</h2>
      <p className="mt-1 text-sm text-red-800 dark:text-red-300">{message}</p>
      <button
        onClick={onReset}
        className="mt-4 inline-flex items-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300"
      >
        Start over
      </button>
    </div>
  );
}
