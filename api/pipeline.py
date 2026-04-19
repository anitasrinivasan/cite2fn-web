"""End-to-end pipeline: detect -> fetch -> format -> (review) -> assemble.

Two entry points:

- `run_prepare(job)`: runs detect, fetch, and format, leaving the job in
  `awaiting_review` state with a citations.json payload on disk. Fire-and-forget
  (called via `asyncio.create_task` from the upload route).

- `run_assemble(job, edited)`: called after the user submits their review;
  takes the final list of edited citations and writes the output .docx.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from typing import Any

from cite2fn.assemble import assemble_document
from cite2fn.detect import detect_citations
from cite2fn.fetch import fetch_metadata_batch
from cite2fn.models import Citation
from cite2fn.references import match_citations_to_references, parse_references

from api import formatter, jobs

log = logging.getLogger("cite2fn.api.pipeline")


async def run_prepare(job: jobs.Job) -> None:
    """Detect, fetch, and format. Leaves the job in awaiting_review."""
    try:
        # --- Phase 1: detect ---
        jobs.update_job(job.id, status="detecting", progress={"phase": "detecting"})
        phase_start = time.time()
        jobs.record_event("phase_entered", job_id=job.id, phase="detecting")
        citations = await asyncio.to_thread(detect_citations, str(job.input_path))
        jobs.record_event(
            "phase_completed",
            job_id=job.id,
            phase="detecting",
            duration_ms=int((time.time() - phase_start) * 1000),
        )
        jobs.record_event(
            "citations_detected",
            job_id=job.id,
            count=len(citations),
        )

        if not citations:
            jobs.update_job(
                job.id,
                status="error",
                error="No citations detected in the document.",
            )
            jobs.record_event(
                "job_errored",
                job_id=job.id,
                phase="detecting",
                error_type="no_citations_detected",
            )
            jobs.pop_api_key(job.id)
            return

        # --- Phase 2: fetch metadata ---
        phase_start = time.time()
        jobs.record_event("phase_entered", job_id=job.id, phase="fetching")
        urls = _unique_urls(citations)
        metadata = await _fetch_with_progress(job.id, urls)
        for cite in citations:
            if cite.url and cite.url in metadata:
                cite.fetched_metadata = metadata[cite.url]
        fetch_failures = sum(1 for m in metadata.values() if m.get("fetch_error"))
        jobs.record_event(
            "phase_completed",
            job_id=job.id,
            phase="fetching",
            duration_ms=int((time.time() - phase_start) * 1000),
            urls_attempted=len(urls),
            fetch_failures=fetch_failures,
        )

        # Match references section entries
        refs = await asyncio.to_thread(parse_references, str(job.input_path))
        if refs:
            citations = await asyncio.to_thread(
                match_citations_to_references, citations, refs
            )

        # --- Phase 3: format via LLM ---
        phase_start = time.time()
        jobs.update_job(job.id, status="formatting")
        jobs.record_event("phase_entered", job_id=job.id, phase="formatting")
        llm_inputs = [_to_llm_input(c) for c in citations]
        formatted = await formatter.format_all(job, llm_inputs)

        by_id = {f.citation_id: f for f in formatted}
        confident = 0
        needs_review = 0
        for cite in citations:
            fmt = by_id.get(cite.id)
            if fmt is not None:
                cite.bluebook_text = fmt.formatted_text
                cite.confidence = fmt.confidence  # type: ignore[assignment]
                if fmt.confidence == "needs_review":
                    needs_review += 1
                else:
                    confident += 1
            else:
                # LLM skipped this citation in its response — don't let it
                # silently drop out of the pipeline. Fill in a visible
                # placeholder so the user can fix it during review.
                cite.bluebook_text = f"[NEEDS MANUAL FORMATTING] {cite.display_text}"
                cite.confidence = "needs_review"  # type: ignore[assignment]
                needs_review += 1

        jobs.record_event(
            "phase_completed",
            job_id=job.id,
            phase="formatting",
            duration_ms=int((time.time() - phase_start) * 1000),
        )
        jobs.record_event(
            "citations_converted",
            job_id=job.id,
            count_total=len(citations),
            count_confident=confident,
            count_needs_review=needs_review,
        )

        # --- Persist & transition to awaiting_review ---
        job.citations_path.write_text(
            json.dumps([c.to_dict() for c in citations], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        jobs.update_job(
            job.id,
            status="awaiting_review",
            progress={"phase": "awaiting_review", "total_citations": len(citations)},
        )

    except Exception as exc:
        log.exception("pipeline failed for job %s", job.id)
        jobs.update_job(
            job.id,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
        jobs.record_event(
            "job_errored",
            job_id=job.id,
            phase="prepare",
            error_type=type(exc).__name__,
            # Truncate message aggressively — no need for stack traces or PII.
            error_message=str(exc)[:200],
        )
        jobs.pop_api_key(job.id)


async def run_assemble(job: jobs.Job, edited_citations: list[dict[str, Any]]) -> None:
    """Write the output .docx from the reviewed citations."""
    try:
        phase_start = time.time()
        jobs.update_job(job.id, status="assembling", progress={"phase": "assembling"})
        jobs.record_event("phase_entered", job_id=job.id, phase="assembling")
        report = await asyncio.to_thread(
            assemble_document,
            str(job.input_path),
            str(job.output_path),
            edited_citations,
            use_endnotes=False,
            keep_references=job.keep_references,
            output_format=job.output_format,
            style=job.style,
        )
        jobs.record_event(
            "phase_completed",
            job_id=job.id,
            phase="assembling",
            duration_ms=int((time.time() - phase_start) * 1000),
        )
        jobs.update_job(job.id, status="done", progress={"phase": "done", "report": report})
        jobs.record_event("job_done", job_id=job.id)
    except Exception as exc:
        log.exception("assemble failed for job %s", job.id)
        jobs.update_job(
            job.id,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
        )
        jobs.record_event(
            "job_errored",
            job_id=job.id,
            phase="assembling",
            error_type=type(exc).__name__,
            error_message=str(exc)[:200],
        )
    finally:
        # Claude key is only needed during the format phase; scrub regardless.
        jobs.pop_api_key(job.id)


def _unique_urls(citations: list[Citation]) -> list[str]:
    seen: dict[str, None] = {}
    for c in citations:
        if c.url:
            seen[c.url] = None
    return list(seen.keys())


async def _fetch_with_progress(
    job_id: str,
    urls: list[str],
) -> dict[str, dict]:
    """Fetch metadata one URL at a time so the frontend can render X/Y progress."""
    results: dict[str, dict] = {}
    total = len(urls)
    jobs.update_job(job_id, status="fetching", progress={"phase": "fetching", "done": 0, "total": total})

    for i, url in enumerate(urls, start=1):
        try:
            single = await asyncio.to_thread(fetch_metadata_batch, [url], 10.0, 0.0)
            results.update(single)
        except Exception as exc:  # defensive — fetch is already best-effort
            results[url] = {"fetch_error": f"{type(exc).__name__}: {exc}"}
        jobs.update_job(
            job_id,
            progress={"phase": "fetching", "done": i, "total": total},
        )

    return results


def _to_llm_input(cite: Citation) -> dict[str, Any]:
    """Shape a Citation for the LLM formatter prompt — only fields the model needs."""
    meta = cite.fetched_metadata or {}
    return {
        "citation_id": cite.id,
        "type": cite.type,
        "display_text": cite.display_text,
        "surrounding_sentence": cite.surrounding_sentence,
        "url": cite.url,
        "canonical_url": meta.get("canonical_url"),
        "metadata": meta,
        "reference_entry": cite.matched_reference,
        "author_name": cite.author_name,
        "year": cite.year,
        "signal_word": cite.signal_word,
    }
