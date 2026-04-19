"""POST /api/feedback — in-site bug report / feedback form."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api import jobs
from api.routes._testmode import request_is_test

router = APIRouter()


class FeedbackPayload(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)
    email: str | None = Field(default=None, max_length=200)
    job_id: str | None = Field(default=None, max_length=64)


@router.post("/feedback", status_code=201)
def submit_feedback(payload: FeedbackPayload, request: Request) -> dict:
    title = payload.title.strip()
    description = payload.description.strip()
    if not title or not description:
        raise HTTPException(400, "Title and description cannot be empty.")

    email = payload.email.strip() if payload.email else None
    if email is not None and email == "":
        email = None

    user_agent = request.headers.get("user-agent")
    is_test = request_is_test(request)

    feedback_id = jobs.insert_feedback(
        title=title,
        description=description,
        email=email,
        job_id=payload.job_id,
        user_agent=user_agent,
        is_test=is_test,
    )

    jobs.record_event(
        "feedback_submitted",
        job_id=payload.job_id,
        is_test=is_test,
        has_email=bool(email),
    )

    return {"ok": True, "id": feedback_id}
