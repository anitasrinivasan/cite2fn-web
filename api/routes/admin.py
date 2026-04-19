"""GET /api/admin/stats — operational dashboard feed.

Protected by a shared `ADMIN_TOKEN` env var. If the token env var is not set,
the route returns 404 to hide its existence from unauthenticated clients.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api import config, jobs

router = APIRouter()


def _require_token(token: str | None) -> None:
    # Reference `config.settings` via the module (not a captured `settings`
    # binding) so tests that reload `api.config` pick up the new values.
    admin_token = config.settings.admin_token
    if not admin_token:
        # If no server-side token is configured, pretend the admin area
        # doesn't exist.
        raise HTTPException(404, "Not Found")
    if not token or token != admin_token:
        raise HTTPException(401, "Unauthorized")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/admin/stats")
def admin_stats(token: str | None = Query(default=None)) -> dict:
    _require_token(token)

    now = int(time.time())
    one_day = 86400
    day_7 = now - 7 * one_day
    day_30 = now - 30 * one_day

    with _connect() as conn:
        # Overall job counts
        jobs_total = conn.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
        jobs_7d = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE created_at >= ?", (day_7,)
        ).fetchone()["n"]
        jobs_30d = conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE created_at >= ?", (day_30,)
        ).fetchone()["n"]

        # Funnel counts based on status + review event presence.
        status_rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM jobs GROUP BY status"
        ).fetchall()
        status_counts = {r["status"]: r["n"] for r in status_rows}
        reached_review = conn.execute(
            "SELECT COUNT(DISTINCT job_id) AS n FROM events WHERE event_type = 'review_submitted'"
        ).fetchone()["n"]
        downloaded = conn.execute(
            "SELECT COUNT(DISTINCT job_id) AS n FROM events WHERE event_type = 'download_fetched'"
        ).fetchone()["n"]

        funnel = {
            "created": jobs_total,
            "reached_review": reached_review,
            "done": status_counts.get("done", 0),
            "downloaded": downloaded,
            "errored": status_counts.get("error", 0),
        }

        # Preference breakdowns
        def _breakdown(column: str) -> dict[str, int]:
            rows = conn.execute(
                f"SELECT {column} AS v, COUNT(*) AS n FROM jobs GROUP BY {column}"
            ).fetchall()
            return {r["v"]: r["n"] for r in rows}

        style_breakdown = _breakdown("style")
        output_format_breakdown = _breakdown("output_format")
        llm_backend_breakdown = _breakdown("llm_backend")

        # Claude model tier: count haiku vs. sonnet-requested, and also how
        # many sonnet jobs fell back to haiku.
        claude_rows = conn.execute(
            """
            SELECT claude_model_tier AS tier,
                   SUM(sonnet_fell_back) AS fell_back,
                   COUNT(*) AS n
            FROM jobs
            WHERE llm_backend = 'claude'
            GROUP BY claude_model_tier
            """
        ).fetchall()
        claude_tier_breakdown = {
            r["tier"]: {
                "total": r["n"],
                "fell_back_to_haiku": r["fell_back"] or 0,
            }
            for r in claude_rows
        }

        # Citation averages (from citations_converted events).
        avg_row = conn.execute(
            """
            SELECT
                AVG(CAST(json_extract(metadata, '$.count_total') AS REAL)) AS avg_total,
                AVG(CAST(json_extract(metadata, '$.count_confident') AS REAL)) AS avg_confident,
                AVG(CAST(json_extract(metadata, '$.count_needs_review') AS REAL)) AS avg_needs_review
            FROM events
            WHERE event_type = 'citations_converted'
            """
        ).fetchone()
        citation_averages = {
            "avg_total": _round(avg_row["avg_total"]),
            "avg_confident": _round(avg_row["avg_confident"]),
            "avg_needs_review": _round(avg_row["avg_needs_review"]),
        }

        # Top error types in the last 30 days.
        error_rows = conn.execute(
            """
            SELECT json_extract(metadata, '$.error_type') AS error_type, COUNT(*) AS n
            FROM events
            WHERE event_type = 'job_errored' AND created_at >= ?
            GROUP BY error_type
            ORDER BY n DESC
            LIMIT 5
            """,
            (day_30,),
        ).fetchall()
        top_errors = [
            {"error_type": r["error_type"] or "unknown", "count": r["n"]}
            for r in error_rows
        ]

        # Daily job counts, last 30 days, filled with zeros for missing days.
        daily_rows = conn.execute(
            """
            SELECT date(created_at, 'unixepoch') AS d, COUNT(*) AS n
            FROM jobs
            WHERE created_at >= ?
            GROUP BY d
            ORDER BY d ASC
            """,
            (day_30,),
        ).fetchall()
        daily_map = {r["d"]: r["n"] for r in daily_rows}
        daily_jobs: list[dict[str, Any]] = []
        for i in range(30):
            ts = now - (29 - i) * one_day
            day_str = time.strftime("%Y-%m-%d", time.gmtime(ts))
            daily_jobs.append({"date": day_str, "count": daily_map.get(day_str, 0)})

        # Recent feedback (most recent 20)
        feedback_rows = conn.execute(
            """
            SELECT id, title, description, email, job_id, user_agent, created_at
            FROM feedback
            ORDER BY created_at DESC
            LIMIT 20
            """
        ).fetchall()
        recent_feedback = [
            {
                "id": r["id"],
                "title": r["title"],
                "description": r["description"],
                "email": r["email"],
                "job_id": r["job_id"],
                "user_agent": r["user_agent"],
                "created_at": r["created_at"],
            }
            for r in feedback_rows
        ]

    return {
        "now": now,
        "jobs_total": jobs_total,
        "jobs_last_7d": jobs_7d,
        "jobs_last_30d": jobs_30d,
        "funnel": funnel,
        "style_breakdown": style_breakdown,
        "output_format_breakdown": output_format_breakdown,
        "llm_backend_breakdown": llm_backend_breakdown,
        "claude_tier_breakdown": claude_tier_breakdown,
        "citation_averages": citation_averages,
        "top_errors": top_errors,
        "daily_jobs": daily_jobs,
        "recent_feedback": recent_feedback,
    }


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 1)
