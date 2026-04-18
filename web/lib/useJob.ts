"use client";

import { useEffect, useRef, useState } from "react";
import { getJob } from "./api";
import { isActive, type Job } from "./types";

const POLL_MS = 2000;

export function useJob(jobId: string | null): {
  job: Job | null;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  refresh: () => Promise<void>;
} {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState<boolean>(jobId !== null);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const cancelledRef = useRef(false);

  const fetchJob = async (id: string) => {
    try {
      const next = await getJob(id);
      if (cancelledRef.current) return;
      if (next === null) {
        setNotFound(true);
        setJob(null);
      } else {
        setJob(next);
        setNotFound(false);
      }
      setError(null);
    } catch (e) {
      if (cancelledRef.current) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (!cancelledRef.current) setLoading(false);
    }
  };

  useEffect(() => {
    cancelledRef.current = false;
    setNotFound(false);

    if (!jobId) {
      setJob(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    void fetchJob(jobId);

    const interval = setInterval(() => {
      setJob((current) => {
        if (current && !isActive(current.status)) return current;
        void fetchJob(jobId);
        return current;
      });
    }, POLL_MS);

    return () => {
      cancelledRef.current = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const refresh = async () => {
    if (jobId) await fetchJob(jobId);
  };

  return { job, loading, notFound, error, refresh };
}
