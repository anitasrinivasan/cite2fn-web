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
        citations = await asyncio.to_thread(detect_citations, str(job.input_path))

        if not citations:
            jobs.update_job(
                job.id,
                status="error",
                error="No citations detected in the document.",
            )
            jobs.pop_api_key(job.id)
            return

        # --- Phase 2: fetch metadata ---
        urls = _unique_urls(citations)
        metadata = await _fetch_with_progress(job.id, urls)
        for cite in citations:
            if cite.url and cite.url in metadata:
                cite.fetched_metadata = metadata[cite.url]

        # Match references section entries
        refs = await asyncio.to_thread(parse_references, str(job.input_path))
        if refs:
            citations = await asyncio.to_thread(
                match_citations_to_references, citations, refs
            )

        # --- Phase 3: format via LLM ---
        jobs.update_job(job.id, status="formatting")
        llm_inputs = [_to_llm_input(c) for c in citations]
        formatted = await formatter.format_all(job, llm_inputs)

        by_id = {f.citation_id: f for f in formatted}
        for cite in citations:
            fmt = by_id.get(cite.id)
            if fmt is not None:
                cite.bluebook_text = fmt.formatted_text
                cite.confidence = fmt.confidence  # type: ignore[assignment]

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
        jobs.pop_api_key(job.id)


async def run_assemble(job: jobs.Job, edited_citations: list[dict[str, Any]]) -> None:
    """Write the output .docx from the reviewed citations."""
    try:
        jobs.update_job(job.id, status="assembling", progress={"phase": "assembling"})
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
        jobs.update_job(job.id, status="done", progress={"phase": "done", "report": report})
    except Exception as exc:
        log.exception("assemble failed for job %s", job.id)
        jobs.update_job(
            job.id,
            status="error",
            error=f"{type(exc).__name__}: {exc}",
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
