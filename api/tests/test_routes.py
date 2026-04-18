"""Route-level smoke tests. Uses a temp STORAGE_DIR so no real state bleeds between tests.

End-to-end tests that exercise the full pipeline live elsewhere — they need real
.docx fixtures and a mocked LLM driver. These tests verify:
- /health responds
- /api/jobs rejects malformed inputs
- /api/jobs/:id returns 404 for unknown jobs
"""

from __future__ import annotations

import io
import os
import tempfile

import pytest


@pytest.fixture
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp)
    monkeypatch.setenv("GROQ_API_KEY", "test-key-so-validation-passes")

    # Reload modules that captured settings at import time.
    import importlib
    from api import config

    importlib.reload(config)
    from api import jobs, main

    importlib.reload(jobs)
    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["groq_configured"] is True


def test_get_unknown_job(client):
    r = client.get("/api/jobs/does-not-exist")
    assert r.status_code == 404


def test_upload_rejects_non_docx(client):
    r = client.post(
        "/api/jobs",
        files={"file": ("paper.pdf", io.BytesIO(b"not a docx"), "application/pdf")},
        data={
            "style": "bluebook",
            "output_format": "footnotes",
            "llm_backend": "groq",
        },
    )
    assert r.status_code == 400
    assert "docx" in r.json()["detail"].lower()


def test_upload_rejects_bad_style(client):
    r = client.post(
        "/api/jobs",
        files={"file": ("paper.docx", io.BytesIO(b"dummy"), "application/octet-stream")},
        data={
            "style": "chicago",
            "output_format": "footnotes",
            "llm_backend": "groq",
        },
    )
    assert r.status_code == 400
    assert "style" in r.json()["detail"].lower()


def test_upload_rejects_claude_without_key(client):
    r = client.post(
        "/api/jobs",
        files={"file": ("paper.docx", io.BytesIO(b"dummy"), "application/octet-stream")},
        data={
            "style": "bluebook",
            "output_format": "footnotes",
            "llm_backend": "claude",
        },
    )
    assert r.status_code == 400
    assert "claude_api_key" in r.json()["detail"].lower() or "key" in r.json()["detail"].lower()


def test_review_on_unknown_job(client):
    r = client.post("/api/jobs/missing/review", json={"citations": []})
    assert r.status_code == 404


def test_download_on_unknown_job(client):
    r = client.get("/api/jobs/missing/download")
    assert r.status_code == 404
