"""GET /api/jobs/:id — status + progress + (when awaiting_review) the citations payload.
POST /api/jobs/:id/review — accept user edits and trigger assembly.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api import jobs as jobs_module
from api import pipeline

router = APIRouter()


class ReviewedCitation(BaseModel):
    id: str
    bluebook_text: str
    confidence: str | None = None


class ReviewPayload(BaseModel):
    citations: list[ReviewedCitation]


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = jobs_module.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")

    payload = job.to_public_dict()

    if job.status == "awaiting_review" and job.citations_path.exists():
        payload["citations"] = json.loads(job.citations_path.read_text(encoding="utf-8"))

    return payload


@router.post("/jobs/{job_id}/review")
async def submit_review(job_id: str, review: ReviewPayload) -> dict:
    job = jobs_module.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    if job.status != "awaiting_review":
        raise HTTPException(
            409,
            f"Job is in state '{job.status}', not awaiting_review.",
        )
    if not job.citations_path.exists():
        raise HTTPException(500, "Citations payload missing on disk.")

    # Merge user edits onto the stored citations (preserves fields the user didn't touch).
    stored = json.loads(job.citations_path.read_text(encoding="utf-8"))
    edits = {c.id: c for c in review.citations}
    citations_edited = 0
    for cite in stored:
        edit = edits.get(cite["id"])
        if edit is not None:
            if (cite.get("bluebook_text") or "") != edit.bluebook_text:
                citations_edited += 1
            cite["bluebook_text"] = edit.bluebook_text
            if edit.confidence:
                cite["confidence"] = edit.confidence

    job.citations_path.write_text(
        json.dumps(stored, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    jobs_module.record_event(
        "review_submitted",
        job_id=job_id,
        citations_total=len(stored),
        citations_edited=citations_edited,
    )

    asyncio.create_task(pipeline.run_assemble(job, stored))

    return jobs_module.get_job(job_id).to_public_dict()  # type: ignore[union-attr]
