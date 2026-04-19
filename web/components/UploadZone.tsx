"use client";

import { useRef, useState } from "react";
import type {
  ClaudeModelTier,
  LLMBackend,
  OutputFormat,
  Style,
} from "@/lib/types";

export type UploadSubmission = {
  file: File;
  style: Style;
  output_format: OutputFormat;
  llm_backend: LLMBackend;
  claude_api_key?: string;
  claude_model_tier?: ClaudeModelTier;
  keep_references: boolean;
};

export function UploadZone({
  onSubmit,
  disabled,
  error,
}: {
  onSubmit: (submission: UploadSubmission) => void;
  disabled?: boolean;
  error?: string | null;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [style, setStyle] = useState<Style>("bluebook");
  const [outputFormat, setOutputFormat] = useState<OutputFormat>("footnotes");
  const [llmBackend, setLlmBackend] = useState<LLMBackend>("groq");
  const [claudeKey, setClaudeKey] = useState("");
  const [claudeModelTier, setClaudeModelTier] = useState<ClaudeModelTier>("haiku");
  const [keepRefs, setKeepRefs] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (f: File | null) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".docx")) {
      alert("Please upload a .docx file.");
      return;
    }
    setFile(f);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    onSubmit({
      file,
      style,
      output_format: outputFormat,
      llm_backend: llmBackend,
      claude_api_key: llmBackend === "claude" ? claudeKey : undefined,
      claude_model_tier: llmBackend === "claude" ? claudeModelTier : undefined,
      keep_references: keepRefs,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      <div
        className={`rounded-lg border-2 border-dashed p-10 text-center transition ${
          dragOver
            ? "border-slate-900 bg-slate-50"
            : "border-slate-300 bg-white"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFile(e.dataTransfer.files?.[0] ?? null);
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".docx"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <div className="space-y-2">
            <p className="font-mono text-sm text-slate-700">{file.name}</p>
            <button
              type="button"
              className="text-xs text-slate-500 underline hover:text-slate-800"
              onClick={() => {
                setFile(null);
                if (fileInputRef.current) fileInputRef.current.value = "";
              }}
            >
              Choose a different file
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-slate-700">
              Drop a <code className="font-mono">.docx</code> here
            </p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="text-sm font-medium text-slate-900 underline"
            >
              or browse
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <RadioGroup
          label="Citation style"
          name="style"
          value={style}
          onChange={(v) => setStyle(v as Style)}
          options={[
            { value: "bluebook", label: "Bluebook (21st ed.)" },
            { value: "apa", label: "APA (7th ed.)" },
          ]}
        />
        <RadioGroup
          label="Output format"
          name="output_format"
          value={outputFormat}
          onChange={(v) => setOutputFormat(v as OutputFormat)}
          options={[
            { value: "footnotes", label: "Footnotes" },
            { value: "endnotes", label: "Endnotes" },
            { value: "references", label: "List of References" },
          ]}
        />
      </div>

      <div className="space-y-4">
        <RadioGroup
          label="Formatting engine"
          name="llm_backend"
          value={llmBackend}
          onChange={(v) => setLlmBackend(v as LLMBackend)}
          options={[
            {
              value: "groq",
              label: "Free (Llama 4 Scout on Groq) — slower, may be lower quality on edge cases",
            },
            {
              value: "claude",
              label: "Your Claude API key — best quality",
            },
          ]}
        />
        {llmBackend === "claude" && (
          <div className="space-y-4">
            <div>
              <label
                htmlFor="claude-key"
                className="block text-sm font-medium text-slate-700"
              >
                Claude API key
              </label>
              <input
                id="claude-key"
                type="password"
                autoComplete="off"
                required
                value={claudeKey}
                onChange={(e) => setClaudeKey(e.target.value)}
                placeholder="sk-ant-..."
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm focus:border-slate-900 focus:outline-none"
              />
              <div className="mt-1 flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-xs text-slate-500">
                  Held in memory on our server for this job only. Never logged, never stored.
                </p>
                <a
                  href="https://console.anthropic.com/settings/keys"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-slate-600 underline-offset-4 hover:text-slate-900 hover:underline"
                >
                  Don&apos;t have one? Get a Claude API key →
                </a>
              </div>
            </div>

            <RadioGroup
              label="Claude model"
              name="claude_model_tier"
              value={claudeModelTier}
              onChange={(v) => setClaudeModelTier(v as ClaudeModelTier)}
              options={[
                {
                  value: "haiku",
                  label: "Haiku 4.5 — works on all Claude plans, including free",
                },
                {
                  value: "sonnet",
                  label: "Sonnet 4.6 — higher quality, requires a paid Claude account",
                },
              ]}
            />
            {claudeModelTier === "sonnet" && (
              <p className="text-xs text-slate-500">
                If your account doesn&apos;t support Sonnet 4.6 we&apos;ll automatically
                retry with Haiku 4.5 and flag any affected citations for review.
              </p>
            )}
          </div>
        )}
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="text-sm text-slate-600 underline-offset-4 hover:underline"
        >
          {showAdvanced ? "Hide" : "Show"} advanced options
        </button>
        {showAdvanced && (
          <div className="mt-3">
            <label className="inline-flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={keepRefs}
                onChange={(e) => setKeepRefs(e.target.checked)}
                className="h-4 w-4"
              />
              Keep the original References section in the output document
            </label>
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <button
        type="submit"
        disabled={disabled || !file}
        className="w-full rounded-md bg-slate-900 py-3 text-sm font-medium text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        Convert citations
      </button>
    </form>
  );
}

function RadioGroup({
  label,
  name,
  value,
  onChange,
  options,
}: {
  label: string;
  name: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <fieldset>
      <legend className="mb-2 block text-sm font-medium text-slate-700">
        {label}
      </legend>
      <div className="space-y-2">
        {options.map((opt) => (
          <label
            key={opt.value}
            className="flex cursor-pointer items-start gap-3 rounded-md border border-slate-200 px-3 py-2 text-sm hover:border-slate-400"
          >
            <input
              type="radio"
              name={name}
              value={opt.value}
              checked={value === opt.value}
              onChange={() => onChange(opt.value)}
              className="mt-0.5"
            />
            <span className="text-slate-800">{opt.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
