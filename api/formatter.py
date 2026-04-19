"""Formatter adapter: turns detected citations + fetched metadata into formatted citation text.

This is the step the plugin delegates to Claude inside the user's Code session.
For the web service, the same work happens server-side through one of two drivers:

- `claude`: used when the user provides their own Anthropic API key. Best quality,
  leverages Anthropic prompt caching on the long style-rules system prompt.
- `groq`: free fallback using a Groq-hosted OSS model (default Llama 4 Scout).
  OpenAI-compatible API, leaner system prompt (Groq has no prompt caching so
  every token costs per call).

Both drivers implement `format_chunk(...)` and the adapter batches citations into
chunks of 10 so the frontend can show incremental progress.
"""

from __future__ import annotations

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

        def _mark_fallback() -> None:
            jobs.mark_sonnet_fell_back(job.id)
            jobs.record_event(
                "sonnet_fell_back_to_haiku",
                job_id=job.id,
            )

        return claude_driver.ClaudeDriver(
            api_key=key,
            model_tier=job.claude_model_tier,
            on_fallback=_mark_fallback,
        )
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

    # Chunks run serially on purpose. Concurrent chunks on Groq's free tier
    # collide and 429 each other out on tight TPM budgets. Claude has much
    # higher limits but serialized is still fine for v1.
    results: list[FormattedCitation] = []
    with jobs.progress_tracker(job.id, phase="formatting", total=len(citations)) as tick:
        for chunk in chunks:
            chunk_results = await driver.format_chunk(chunk, job.style)
            results.extend(chunk_results)
            tick(len(chunk_results))

    # Preserve input order.
    by_id = {r.citation_id: r for r in results}
    return [by_id[c["citation_id"]] for c in citations if c["citation_id"] in by_id]
