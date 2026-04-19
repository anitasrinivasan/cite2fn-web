"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Estimate remaining time for a phase based on items processed since the phase started.
 *
 * Returns a humanized string like "~30s remaining" or "~2m 15s remaining",
 * or null if there isn't enough data yet (no items done, or phase just started).
 */
export function useEta(phase: string | undefined, done: number, total: number): string | null {
  const [eta, setEta] = useState<string | null>(null);
  const phaseStartRef = useRef<{ phase: string; at: number } | null>(null);
  const lastDoneRef = useRef<number>(0);

  useEffect(() => {
    if (!phase) {
      setEta(null);
      return;
    }

    // New phase -> reset the timer.
    if (!phaseStartRef.current || phaseStartRef.current.phase !== phase) {
      phaseStartRef.current = { phase, at: Date.now() };
      lastDoneRef.current = 0;
      setEta(null);
      return;
    }

    if (total <= 0 || done <= 0 || done >= total) {
      setEta(null);
      return;
    }

    // Need a tiny bit of elapsed time to avoid wild estimates from first update.
    const elapsedMs = Date.now() - phaseStartRef.current.at;
    if (elapsedMs < 1500) return;

    const rate = done / (elapsedMs / 1000); // items per second
    if (rate <= 0) return;

    const remainingSec = Math.max(1, Math.round((total - done) / rate));
    setEta(humanize(remainingSec));
    lastDoneRef.current = done;
  }, [phase, done, total]);

  return eta;
}

function humanize(seconds: number): string {
  if (seconds < 60) return `~${seconds}s remaining`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (s === 0) return `~${m}m remaining`;
  return `~${m}m ${s}s remaining`;
}
