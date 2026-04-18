"""Job state + SQLite persistence.

A Job tracks one end-to-end conversion: detect -> fetch -> format -> (review) -> assemble.
Progress is stored as a JSON blob (`phase_progress`) so the frontend can render
"Fetched 5/12 sources" with a single GET.

Claude API keys provided by the user are held in an in-memory dict keyed by
job_id — never persisted to SQLite — and scrubbed when the job terminates.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from api.config import settings

Status = Literal[
    "pending",
    "detecting",
    "fetching",
    "formatting",
    "awaiting_review",
    "assembling",
    "done",
    "error",
]

Style = Literal["bluebook", "apa"]
OutputFormat = Literal["footnotes", "endnotes", "references"]
LLMBackend = Literal["claude", "groq"]


@dataclass
class Job:
    id: str
    status: Status
    style: Style
    output_format: OutputFormat
    keep_references: bool
    llm_backend: LLMBackend
    phase_progress: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: int = 0
    updated_at: int = 0

    @property
    def dir(self) -> Path:
        return settings.storage_dir / self.id

    @property
    def input_path(self) -> Path:
        return self.dir / "input.docx"

    @property
    def output_path(self) -> Path:
        return self.dir / "output.docx"

    @property
    def citations_path(self) -> Path:
        return self.dir / "citations.json"

    def to_public_dict(self) -> dict[str, Any]:
        """Dict returned to API clients — excludes sensitive fields."""
        return {
            "id": self.id,
            "status": self.status,
            "style": self.style,
            "output_format": self.output_format,
            "llm_backend": self.llm_backend,
            "progress": self.phase_progress,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# In-memory secrets that must never hit disk.
_api_keys: dict[str, str] = {}


def store_api_key(job_id: str, key: str) -> None:
    _api_keys[job_id] = key


def pop_api_key(job_id: str) -> str | None:
    return _api_keys.pop(job_id, None)


def get_api_key(job_id: str) -> str | None:
    return _api_keys.get(job_id)


def _connect() -> sqlite3.Connection:
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                style TEXT NOT NULL,
                output_format TEXT NOT NULL,
                keep_references INTEGER NOT NULL DEFAULT 0,
                llm_backend TEXT NOT NULL,
                phase_progress TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )


def create_job(
    style: Style,
    output_format: OutputFormat,
    keep_references: bool,
    llm_backend: LLMBackend,
) -> Job:
    now = int(time.time())
    job = Job(
        id=uuid.uuid4().hex,
        status="pending",
        style=style,
        output_format=output_format,
        keep_references=keep_references,
        llm_backend=llm_backend,
        created_at=now,
        updated_at=now,
    )
    job.dir.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, status, style, output_format, keep_references,
                              llm_backend, phase_progress, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.status,
                job.style,
                job.output_format,
                int(job.keep_references),
                job.llm_backend,
                json.dumps(job.phase_progress),
                job.error,
                job.created_at,
                job.updated_at,
            ),
        )
    return job


def get_job(job_id: str) -> Job | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return _row_to_job(row)


def update_job(
    job_id: str,
    *,
    status: Status | None = None,
    progress: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    fields: list[str] = []
    values: list[Any] = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if progress is not None:
        fields.append("phase_progress = ?")
        values.append(json.dumps(progress))
    if error is not None:
        fields.append("error = ?")
        values.append(error)
    if not fields:
        return
    fields.append("updated_at = ?")
    values.append(int(time.time()))
    values.append(job_id)
    with _connect() as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", values)


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        status=row["status"],
        style=row["style"],
        output_format=row["output_format"],
        keep_references=bool(row["keep_references"]),
        llm_backend=row["llm_backend"],
        phase_progress=json.loads(row["phase_progress"] or "{}"),
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@contextmanager
def progress_tracker(job_id: str, phase: str, total: int):
    """Context manager that emits progress updates as work completes.

    Use as:
        with progress_tracker(job_id, "fetching", total=len(urls)) as tick:
            for url in urls:
                ...
                tick()
    """
    state = {"done": 0, "total": total, "phase": phase}
    update_job(job_id, progress=state)

    def tick(n: int = 1) -> None:
        state["done"] += n
        update_job(job_id, progress=dict(state))

    try:
        yield tick
    finally:
        pass
