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
ClaudeModelTier = Literal["haiku", "sonnet"]


@dataclass
class Job:
    id: str
    status: Status
    style: Style
    output_format: OutputFormat
    keep_references: bool
    llm_backend: LLMBackend
    claude_model_tier: ClaudeModelTier = "haiku"
    phase_progress: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    created_at: int = 0
    updated_at: int = 0
    # Set to True if we attempted Sonnet but had to fall back to Haiku for
    # this job (free-tier Claude accounts don't serve Sonnet). Surfaced in
    # the review UI so users know what they got.
    sonnet_fell_back: bool = False
    # When true, this job was created by a developer/operator (either via
    # server-wide CITE2FN_TEST_MODE or the X-Cite2fn-Test request header)
    # and is excluded from the default admin dashboard metrics.
    is_test: bool = False

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
            "claude_model_tier": self.claude_model_tier,
            "sonnet_fell_back": self.sonnet_fell_back,
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
                claude_model_tier TEXT NOT NULL DEFAULT 'haiku',
                sonnet_fell_back INTEGER NOT NULL DEFAULT 0,
                phase_progress TEXT NOT NULL DEFAULT '{}',
                error TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        # Additive migration for databases created before the new columns
        # existed. SQLite ignores errors on duplicate add — we swallow them.
        for col, ddl in (
            ("claude_model_tier", "TEXT NOT NULL DEFAULT 'haiku'"),
            ("sonnet_fell_back", "INTEGER NOT NULL DEFAULT 0"),
            ("is_test", "INTEGER NOT NULL DEFAULT 0"),
        ):
            try:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                job_id TEXT,
                metadata TEXT NOT NULL DEFAULT '{}',
                is_test INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        for col, ddl in (("is_test", "INTEGER NOT NULL DEFAULT 0"),):
            try:
                conn.execute(f"ALTER TABLE events ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                email TEXT,
                job_id TEXT,
                user_agent TEXT,
                is_test INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
            """
        )
        for col, ddl in (("is_test", "INTEGER NOT NULL DEFAULT 0"),):
            try:
                conn.execute(f"ALTER TABLE feedback ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass


def create_job(
    style: Style,
    output_format: OutputFormat,
    keep_references: bool,
    llm_backend: LLMBackend,
    claude_model_tier: ClaudeModelTier = "haiku",
    is_test: bool = False,
) -> Job:
    now = int(time.time())
    job = Job(
        id=uuid.uuid4().hex,
        status="pending",
        style=style,
        output_format=output_format,
        keep_references=keep_references,
        llm_backend=llm_backend,
        claude_model_tier=claude_model_tier,
        is_test=is_test,
        created_at=now,
        updated_at=now,
    )
    job.dir.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, status, style, output_format, keep_references,
                              llm_backend, claude_model_tier, is_test,
                              phase_progress, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.status,
                job.style,
                job.output_format,
                int(job.keep_references),
                job.llm_backend,
                job.claude_model_tier,
                int(job.is_test),
                json.dumps(job.phase_progress),
                job.error,
                job.created_at,
                job.updated_at,
            ),
        )
    return job


def mark_sonnet_fell_back(job_id: str) -> None:
    """Set the sonnet_fell_back flag on a job — the Claude driver calls this
    when an attempted Sonnet request returned a tier-not-supported error and
    we retried with Haiku."""
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET sonnet_fell_back = 1, updated_at = ? WHERE id = ?",
            (int(time.time()), job_id),
        )


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
    # These columns were added by ALTER TABLE in init_db for pre-existing
    # databases; default safely if the row predates them.
    def _get(col, default):
        try:
            return row[col]
        except (IndexError, KeyError):
            return default

    return Job(
        id=row["id"],
        status=row["status"],
        style=row["style"],
        output_format=row["output_format"],
        keep_references=bool(row["keep_references"]),
        llm_backend=row["llm_backend"],
        claude_model_tier=_get("claude_model_tier", None) or "haiku",
        sonnet_fell_back=bool(_get("sonnet_fell_back", 0)),
        is_test=bool(_get("is_test", 0)),
        phase_progress=json.loads(row["phase_progress"] or "{}"),
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def record_event(
    event_type: str,
    job_id: str | None = None,
    is_test: bool | None = None,
    **metadata: Any,
) -> None:
    """Insert a row into the `events` table.

    No PII — pass only aggregate / operational fields. Events persist
    indefinitely for trend analysis; individual job data is still deleted on
    the job TTL schedule (the events just reference job_id as a string).

    `is_test` controls whether this event is marked as test data. If left
    None, we look it up from the associated job (if job_id is given and the
    job exists) so callers don't have to thread the flag through every
    event emission site.
    """
    now = int(time.time())
    payload = json.dumps(metadata, ensure_ascii=False) if metadata else "{}"
    if is_test is None and job_id is not None:
        job = get_job(job_id)
        is_test = bool(job.is_test) if job is not None else False
    is_test_int = 1 if is_test else 0
    with _connect() as conn:
        conn.execute(
            "INSERT INTO events (event_type, job_id, metadata, is_test, created_at) VALUES (?, ?, ?, ?, ?)",
            (event_type, job_id, payload, is_test_int, now),
        )


def insert_feedback(
    title: str,
    description: str,
    email: str | None = None,
    job_id: str | None = None,
    user_agent: str | None = None,
    is_test: bool = False,
) -> int:
    """Insert a bug-report / feedback row. Returns the new row id."""
    now = int(time.time())
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO feedback (title, description, email, job_id, user_agent, is_test, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, description, email, job_id, user_agent, int(is_test), now),
        )
        return cursor.lastrowid or 0


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
