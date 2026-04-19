"""Tests for the new feedback form, event recording, and admin dashboard."""

from __future__ import annotations

import importlib
import sqlite3
import tempfile

import pytest


@pytest.fixture
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")

    # Reload modules that captured settings at import time so the new env
    # vars take effect for this test.
    from api import config

    importlib.reload(config)
    from api import jobs, main

    importlib.reload(jobs)
    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        yield c


def _query(client, sql, params=()):
    from api.config import settings

    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def test_feedback_post_persists_row(client):
    res = client.post(
        "/api/feedback",
        json={
            "title": "Footnote in wrong place",
            "description": "After I uploaded my doc, FN 3 ended up inside a paren.",
            "email": "user@example.com",
        },
    )
    assert res.status_code == 201
    rows = _query(client, "SELECT * FROM feedback")
    assert len(rows) == 1
    assert rows[0]["title"] == "Footnote in wrong place"
    assert rows[0]["email"] == "user@example.com"


def test_feedback_rejects_empty_title(client):
    res = client.post(
        "/api/feedback",
        json={"title": "", "description": "something"},
    )
    assert res.status_code == 422


def test_feedback_allows_omitted_email(client):
    res = client.post(
        "/api/feedback",
        json={"title": "bug", "description": "desc"},
    )
    assert res.status_code == 201
    rows = _query(client, "SELECT email FROM feedback")
    assert rows[0]["email"] is None


def test_feedback_records_event(client):
    client.post("/api/feedback", json={"title": "t", "description": "d"})
    rows = _query(
        client,
        "SELECT event_type FROM events WHERE event_type = 'feedback_submitted'",
    )
    assert len(rows) == 1


def test_admin_without_token_returns_401(client):
    # Admin token IS configured in this test setup — so wrong/missing token
    # yields 401, not 404.
    res = client.get("/api/admin/stats")
    assert res.status_code == 401
    res = client.get("/api/admin/stats?token=wrong")
    assert res.status_code == 401


def test_admin_with_token_returns_stats(client):
    res = client.get("/api/admin/stats?token=test-admin-token")
    assert res.status_code == 200
    body = res.json()
    for key in (
        "jobs_total",
        "jobs_last_7d",
        "funnel",
        "style_breakdown",
        "output_format_breakdown",
        "llm_backend_breakdown",
        "claude_tier_breakdown",
        "citation_averages",
        "top_errors",
        "daily_jobs",
        "recent_feedback",
    ):
        assert key in body
    assert len(body["daily_jobs"]) == 30


def test_admin_stats_reflects_feedback(client):
    client.post(
        "/api/feedback",
        json={"title": "t", "description": "d", "email": "a@b.c"},
    )
    res = client.get("/api/admin/stats?token=test-admin-token")
    assert res.status_code == 200
    fb = res.json()["recent_feedback"]
    assert len(fb) == 1
    assert fb[0]["title"] == "t"


def test_admin_hidden_when_no_token_configured(monkeypatch):
    # With no ADMIN_TOKEN env var, the endpoint should return 404 to hide
    # its existence entirely.
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

    from api import config

    importlib.reload(config)
    from api import jobs, main

    importlib.reload(jobs)
    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        res = c.get("/api/admin/stats")
        assert res.status_code == 404
        res = c.get("/api/admin/stats?token=whatever")
        assert res.status_code == 404
