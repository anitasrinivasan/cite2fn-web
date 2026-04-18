"""POST /api/jobs — multipart upload + options, returns job_id."""

from __future__ import annotations

import asyncio
import shutil

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api import jobs, pipeline
from api.config import settings

router = APIRouter()


@router.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    style: str = Form(...),
    output_format: str = Form(...),
    keep_references: bool = Form(False),
    llm_backend: str = Form(...),
    claude_api_key: str | None = Form(None),
) -> dict:
    # --- Validate inputs ---
    if not (file.filename or "").lower().endswith(".docx"):
        raise HTTPException(400, "Only .docx files are supported.")
    if style not in ("bluebook", "apa"):
        raise HTTPException(400, "style must be 'bluebook' or 'apa'.")
    if output_format not in ("footnotes", "endnotes", "references"):
        raise HTTPException(400, "output_format must be 'footnotes', 'endnotes', or 'references'.")
    if llm_backend not in ("claude", "groq"):
        raise HTTPException(400, "llm_backend must be 'claude' or 'groq'.")

    if llm_backend == "claude" and not claude_api_key:
        raise HTTPException(
            400,
            "llm_backend='claude' requires claude_api_key. Omit the key to use the free 'groq' fallback.",
        )
    if llm_backend == "groq" and not settings.groq_api_key:
        raise HTTPException(
            503,
            "Free Groq fallback is not configured on this server. Provide a Claude API key instead.",
        )

    # --- Persist the upload ---
    job = jobs.create_job(
        style=style,  # type: ignore[arg-type]
        output_format=output_format,  # type: ignore[arg-type]
        keep_references=keep_references,
        llm_backend=llm_backend,  # type: ignore[arg-type]
    )
    try:
        with job.input_path.open("wb") as dst:
            shutil.copyfileobj(file.file, dst, length=1024 * 1024)
    finally:
        await file.close()

    # Upload size enforcement after write (size not always known up-front).
    if job.input_path.stat().st_size > settings.max_upload_mb * 1024 * 1024:
        job.input_path.unlink(missing_ok=True)
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit.")

    if claude_api_key:
        jobs.store_api_key(job.id, claude_api_key)

    # Fire-and-forget processing. If the server restarts, the job is lost — v1
    # intentionally accepts this; production would move to a real worker queue.
    asyncio.create_task(pipeline.run_prepare(job))

    return job.to_public_dict()
