"""Environment-driven configuration for the cite2fn API service."""

from __future__ import annotations

import os
from pathlib import Path


class Settings:
    storage_dir: Path
    """Where job artifacts (uploads, outputs, citations JSON) live on disk."""

    db_path: Path
    """SQLite file tracking job state."""

    groq_api_key: str | None
    """Service-owned Groq key for the free-fallback LLM path."""

    groq_model: str
    """Groq-hosted OSS model id. Default: Llama 4 Scout."""

    # (claude_model / claude_sonnet_model / admin_token defined below)


    claude_model: str
    """Anthropic model id used as the default ("haiku") tier. Works on all
    Claude API plans including free tier."""

    claude_sonnet_model: str
    """Anthropic Sonnet model id — opt-in, higher quality, but requires a
    paid Claude API account."""

    admin_token: str | None
    """Bearer-style token for accessing the admin dashboard. If unset, the
    admin route returns 404 to hide its existence."""

    test_mode: bool
    """When true, every job and feedback record created through this server
    is marked is_test=1. Set via CITE2FN_TEST_MODE=1 on the dev server so
    local clicks don't pollute production metrics."""

    cors_origins: list[str]
    """Origins allowed to call the API. '*' in dev; the deployed web origin in prod."""

    max_upload_mb: int
    """Upload size cap."""

    job_ttl_hours: int
    """Hours to retain job artifacts before cleanup."""

    def __init__(self) -> None:
        self.storage_dir = Path(os.environ.get("STORAGE_DIR", "./data")).resolve()
        self.db_path = self.storage_dir / "jobs.db"

        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        self.groq_model = os.environ.get("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        # Haiku 4.5 is the safe default — it's the only Claude model that
        # works on free Anthropic API accounts.
        self.claude_model = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")
        self.claude_sonnet_model = os.environ.get("CLAUDE_SONNET_MODEL", "claude-sonnet-4-6")
        self.admin_token = os.environ.get("ADMIN_TOKEN")
        self.test_mode = os.environ.get("CITE2FN_TEST_MODE", "0").lower() in ("1", "true", "yes")

        origins = os.environ.get("CORS_ORIGINS", "*")
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]

        self.max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "25"))
        self.job_ttl_hours = int(os.environ.get("JOB_TTL_HOURS", "24"))


settings = Settings()
