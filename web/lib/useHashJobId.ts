"use client";

import { useEffect, useState } from "react";

/**
 * Read and write the current job id in the URL hash (`#abc123`).
 *
 * Reading the hash preserves state across refresh. Writing the hash when a
 * job is created means refreshing during processing returns to the same job
 * instead of starting over.
 */
export function useHashJobId(): [string | null, (id: string | null) => void] {
  const [jobId, setJobIdState] = useState<string | null>(null);

  useEffect(() => {
    const read = () => {
      const raw = window.location.hash.replace(/^#/, "");
      setJobIdState(raw.length > 0 ? raw : null);
    };
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);

  const setJobId = (id: string | null) => {
    if (id === null) {
      history.replaceState(null, "", window.location.pathname + window.location.search);
    } else {
      history.replaceState(null, "", `#${id}`);
    }
    setJobIdState(id);
  };

  return [jobId, setJobId];
}
