"""Formatter adapter: turns detected citations + fetched metadata into formatted citation text.

This is the step the plugin delegates to Claude inside the user's Code session.
For the web service, the same work happens server-side through one of two drivers:

- `claude`: used when the user provides their own Anthropic API key. Best quality,
  leverages Anthropic prompt caching on the long style-rules system prompt.
- `groq`: free fallback using Llama 3.3 70B Versatile. OpenAI-compatible API,
  leaner system prompt (Groq has no prompt caching so every token costs per call).

Both drivers implement `format_chunk(...)` and the adapter batches citations into
chunks of 10 so the frontend can show incremental progress.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from api import jobs
from api.drivers import claude as claude_driver
from api.drivers import groq as groq_driver

CHUNK_SIZE = 10

Style = Literal["bluebook", "apa"]


@dataclass
class FormattedCitation:
    citation_id: str
    formatted_text: str
    confidence: str  # "high" | "needs_review"
    note: str | None = None


class Driver(Protocol):
    async def format_chunk(
        self,
        chunk: list[dict[str, Any]],
        style: Style,
    ) -> list[FormattedCitation]: ...


def _driver_for_job(job: jobs.Job) -> Driver:
    if job.llm_backend == "claude":
        key = jobs.get_api_key(job.id)
        if not key:
            raise RuntimeError("Claude backend selected but no API key in memory")
        return claude_driver.ClaudeDriver(api_key=key)
    return groq_driver.GroqDriver()


async def format_all(
    job: jobs.Job,
    citations: list[dict[str, Any]],
) -> list[FormattedCitation]:
    """Format every citation in the document, emitting progress as chunks complete."""
    driver = _driver_for_job(job)

    chunks = [
        citations[i : i + CHUNK_SIZE] for i in range(0, len(citations), CHUNK_SIZE)
    ]

    results: list[FormattedCitation] = []
    with jobs.progress_tracker(job.id, phase="formatting", total=len(citations)) as tick:
        tasks = [driver.format_chunk(chunk, job.style) for chunk in chunks]
        for future in asyncio.as_completed(tasks):
            chunk_results = await future
            results.extend(chunk_results)
            tick(len(chunk_results))

    # Restore input order (as_completed loses it).
    by_id = {r.citation_id: r for r in results}
    return [by_id[c["citation_id"]] for c in citations if c["citation_id"] in by_id]
