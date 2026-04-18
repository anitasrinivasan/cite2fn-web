"""GET /api/jobs/:id/download — streams the output .docx."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from api import jobs as jobs_module

router = APIRouter()

DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.get("/jobs/{job_id}/download")
def download(job_id: str):
    job = jobs_module.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    if job.status != "done":
        raise HTTPException(409, f"Job is in state '{job.status}', not done.")
    if not job.output_path.exists():
        raise HTTPException(500, "Output file missing on disk.")

    return FileResponse(
        path=str(job.output_path),
        media_type=DOCX_CONTENT_TYPE,
        filename=f"cite2fn_{job_id}.docx",
    )
