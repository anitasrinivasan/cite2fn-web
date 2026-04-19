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

    claude_model: str
    """Anthropic model id used when the user supplies their own key."""

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
        self.claude_model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

        origins = os.environ.get("CORS_ORIGINS", "*")
        self.cors_origins = [o.strip() for o in origins.split(",") if o.strip()]

        self.max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "25"))
        self.job_ttl_hours = int(os.environ.get("JOB_TTL_HOURS", "24"))


settings = Settings()
