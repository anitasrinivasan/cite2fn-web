"""POST /api/feedback — in-site bug report / feedback form (multipart)."""

from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from api import jobs
from api.config import settings
from api.routes._testmode import request_is_test

router = APIRouter()


# Hard limits for attachments so users can't flood us via the open form.
_ALLOWED_MIME = ("image/png", "image/jpeg", "image/gif", "image/webp")
_MAX_FILES = 4
_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB per image


@router.post("/feedback", status_code=201)
async def submit_feedback(
    request: Request,
    title: str = Form(..., min_length=1, max_length=200),
    description: str = Form(..., min_length=1, max_length=5000),
    email: str | None = Form(default=None, max_length=200),
    job_id: str | None = Form(default=None, max_length=64),
    attachments: list[UploadFile] | None = File(default=None),
) -> dict:
    title_s = title.strip()
    description_s = description.strip()
    if not title_s or not description_s:
        raise HTTPException(400, "Title and description cannot be empty.")

    email_s = email.strip() if email else None
    if email_s == "":
        email_s = None

    files = [f for f in (attachments or []) if f and f.filename]
    if len(files) > _MAX_FILES:
        raise HTTPException(400, f"Max {_MAX_FILES} attachments per report.")

    is_test = request_is_test(request)
    user_agent = request.headers.get("user-agent")

    feedback_id = jobs.insert_feedback(
        title=title_s,
        description=description_s,
        email=email_s,
        job_id=job_id,
        user_agent=user_agent,
        is_test=is_test,
    )

    stored_attachments: list[dict] = []
    if files:
        target_dir = jobs.feedback_attachments_dir() / str(feedback_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        for uf in files:
            mime = (uf.content_type or "").lower()
            if mime not in _ALLOWED_MIME:
                raise HTTPException(400, f"Unsupported file type: {mime or 'unknown'}.")
            data = await uf.read()
            if len(data) > _MAX_FILE_BYTES:
                raise HTTPException(413, f"Attachment exceeds {_MAX_FILE_BYTES // (1024 * 1024)} MB.")

            safe_name = _sanitize_filename(uf.filename or "screenshot", mime)
            dest = target_dir / safe_name
            dest.write_bytes(data)

            stored_attachments.append(
                {
                    "filename": safe_name,
                    "mime": mime,
                    "size": len(data),
                }
            )
            jobs.insert_feedback_attachment(
                feedback_id=feedback_id,
                filename=safe_name,
                mime_type=mime,
                size_bytes=len(data),
            )

    jobs.record_event(
        "feedback_submitted",
        job_id=job_id,
        is_test=is_test,
        has_email=bool(email_s),
        attachment_count=len(stored_attachments),
    )

    return {
        "ok": True,
        "id": feedback_id,
        "attachment_count": len(stored_attachments),
    }


def _sanitize_filename(raw: str, mime: str) -> str:
    """Produce a safe storage filename — strips path components and dangerous
    chars, ensures an extension consistent with the declared MIME type, and
    guarantees uniqueness within the attachment dir via a short random suffix.
    """
    base = Path(raw).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or "attachment"
    stem = stem[:60]
    ext = Path(stem).suffix.lower()
    expected_ext = mimetypes.guess_extension(mime) or ""
    if not ext or (expected_ext and ext != expected_ext):
        stem = (Path(stem).stem or "attachment") + expected_ext
    return f"{uuid.uuid4().hex[:8]}_{stem}"
