"use client";

import { useEffect, useRef, useState } from "react";
import { submitFeedback } from "@/lib/api";

const MAX_FILES = 4;
const MAX_FILE_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set([
  "image/png",
  "image/jpeg",
  "image/gif",
  "image/webp",
]);

type Attached = {
  id: string;
  file: File;
  previewUrl: string;
};

export function BugReportModal({
  open,
  onClose,
  jobId,
}: {
  open: boolean;
  onClose: () => void;
  jobId?: string | null;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [attachments, setAttachments] = useState<Attached[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reset on open; revoke object URLs on close to avoid leaks.
  useEffect(() => {
    if (open) {
      setTitle("");
      setDescription("");
      setEmail("");
      setError(null);
      setDone(false);
      setSubmitting(false);
      setDragOver(false);
      setAttachments((prev) => {
        prev.forEach((a) => URL.revokeObjectURL(a.previewUrl));
        return [];
      });
    }
  }, [open]);

  useEffect(() => {
    return () => {
      attachments.forEach((a) => URL.revokeObjectURL(a.previewUrl));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const addFiles = (incoming: File[]) => {
    if (!incoming.length) return;
    setError(null);
    const current = attachments;
    const remainingSlots = MAX_FILES - current.length;
    if (remainingSlots <= 0) {
      setError(`Max ${MAX_FILES} attachments per report.`);
      return;
    }
    const next: Attached[] = [];
    for (const file of incoming.slice(0, remainingSlots)) {
      if (!ALLOWED_TYPES.has(file.type)) {
        setError(`"${file.name}" isn't a supported image type (PNG, JPEG, GIF, or WebP).`);
        continue;
      }
      if (file.size > MAX_FILE_BYTES) {
        setError(`"${file.name}" exceeds ${MAX_FILE_BYTES / (1024 * 1024)} MB.`);
        continue;
      }
      next.push({
        id: crypto.randomUUID(),
        file,
        previewUrl: URL.createObjectURL(file),
      });
    }
    if (next.length) setAttachments([...current, ...next]);
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => {
      const out: Attached[] = [];
      for (const a of prev) {
        if (a.id === id) {
          URL.revokeObjectURL(a.previewUrl);
          continue;
        }
        out.push(a);
      }
      return out;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await submitFeedback({
        title: title.trim(),
        description: description.trim(),
        email: email.trim() || undefined,
        job_id: jobId ?? undefined,
        attachments: attachments.map((a) => a.file),
      });
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4 dark:bg-black/60"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="bug-report-title"
    >
      <div
        className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl dark:bg-slate-900 dark:shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {done ? (
          <div className="space-y-4">
            <h2
              id="bug-report-title"
              className="text-lg font-semibold text-slate-900 dark:text-slate-100"
            >
              Thanks — we&apos;ll take a look.
            </h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Your report was submitted successfully.
            </p>
            <button
              onClick={onClose}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300"
            >
              Close
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-between">
              <h2
                id="bug-report-title"
                className="text-lg font-semibold text-slate-900 dark:text-slate-100"
              >
                Report a bug
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <div>
              <label
                htmlFor="bug-title"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Short summary
              </label>
              <input
                id="bug-title"
                type="text"
                required
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Footnote ended up in the wrong place"
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-slate-400"
              />
            </div>

            <div>
              <label
                htmlFor="bug-description"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                What happened
              </label>
              <div
                className={`mt-1 rounded-md border ${
                  dragOver
                    ? "border-slate-900 ring-2 ring-slate-200 dark:border-slate-300 dark:ring-slate-700"
                    : "border-slate-300 dark:border-slate-700"
                }`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragOver(false);
                  const files = Array.from(e.dataTransfer.files).filter((f) =>
                    f.type.startsWith("image/"),
                  );
                  addFiles(files);
                }}
              >
                <textarea
                  id="bug-description"
                  required
                  rows={5}
                  maxLength={5000}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  onPaste={(e) => {
                    const imgs: File[] = [];
                    for (const item of e.clipboardData.items) {
                      if (item.kind === "file" && item.type.startsWith("image/")) {
                        const f = item.getAsFile();
                        if (f) imgs.push(f);
                      }
                    }
                    if (imgs.length) {
                      e.preventDefault();
                      addFiles(imgs);
                    }
                  }}
                  placeholder="Steps to reproduce, what you expected, what you saw. Drag or paste screenshots here."
                  className="w-full resize-y rounded-md bg-transparent p-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none dark:text-slate-100 dark:placeholder:text-slate-500"
                />
                {attachments.length > 0 && (
                  <div className="flex flex-wrap gap-2 border-t border-slate-200 p-2 dark:border-slate-700">
                    {attachments.map((a) => (
                      <div
                        key={a.id}
                        className="group relative h-20 w-20 overflow-hidden rounded-md border border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={a.previewUrl}
                          alt={a.file.name}
                          className="h-full w-full object-cover"
                        />
                        <button
                          type="button"
                          onClick={() => removeAttachment(a.id)}
                          aria-label={`Remove ${a.file.name}`}
                          className="absolute right-0 top-0 flex h-5 w-5 items-center justify-center rounded-bl-md bg-slate-900/80 text-xs text-white hover:bg-slate-900"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-slate-400">
                <span>
                  Drag or paste screenshots, or{" "}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="underline underline-offset-2 hover:text-slate-800 dark:hover:text-slate-200"
                  >
                    browse
                  </button>
                  . PNG/JPEG/GIF/WebP, up to {MAX_FILES} files, 5 MB each.
                </span>
                {attachments.length > 0 && (
                  <span>{attachments.length}/{MAX_FILES} attached</span>
                )}
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                multiple
                className="hidden"
                onChange={(e) => {
                  addFiles(Array.from(e.target.files ?? []));
                  e.target.value = "";
                }}
              />
            </div>

            <div>
              <label
                htmlFor="bug-email"
                className="block text-sm font-medium text-slate-700 dark:text-slate-300"
              >
                Email{" "}
                <span className="text-slate-400 dark:text-slate-500">
                  (optional, if you want us to follow up)
                </span>
              </label>
              <input
                id="bug-email"
                type="email"
                maxLength={200}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-900 focus:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100 dark:placeholder:text-slate-500 dark:focus:border-slate-400"
              />
            </div>

            {jobId && (
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Attaching current job{" "}
                <code className="font-mono">{jobId.slice(0, 10)}…</code> so we can
                look up the logs.
              </p>
            )}

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">
                {error}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting || !title.trim() || !description.trim()}
                className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-slate-300 dark:disabled:bg-slate-700"
              >
                {submitting ? "Sending…" : "Send report"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
