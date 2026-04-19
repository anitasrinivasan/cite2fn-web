"""Tests for the feedback form (multipart w/ optional image attachments),
event recording, and admin dashboard."""

from __future__ import annotations

import importlib
import io
import sqlite3
import tempfile

import pytest


@pytest.fixture
def client(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp)
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin-token")

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


# Minimum valid 1x1 PNG bytes (for attachment tests)
_PNG_1x1 = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01\x7f\xf6\xe9\xaa"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _form(**fields):
    """Build a multipart form with string fields. Matches the new
    multipart-based feedback endpoint."""
    data = {k: str(v) for k, v in fields.items()}
    return data


def test_feedback_post_persists_row(client):
    res = client.post(
        "/api/feedback",
        data=_form(
            title="Footnote in wrong place",
            description="FN 3 ended up inside a paren.",
            email="user@example.com",
        ),
    )
    assert res.status_code == 201
    rows = _query(client, "SELECT * FROM feedback")
    assert len(rows) == 1
    assert rows[0]["title"] == "Footnote in wrong place"
    assert rows[0]["email"] == "user@example.com"


def test_feedback_rejects_empty_title(client):
    res = client.post(
        "/api/feedback",
        data=_form(title="", description="something"),
    )
    assert res.status_code == 422


def test_feedback_allows_omitted_email(client):
    res = client.post(
        "/api/feedback",
        data=_form(title="bug", description="desc"),
    )
    assert res.status_code == 201
    rows = _query(client, "SELECT email FROM feedback")
    assert rows[0]["email"] is None


def test_feedback_records_event(client):
    client.post("/api/feedback", data=_form(title="t", description="d"))
    rows = _query(
        client,
        "SELECT event_type FROM events WHERE event_type = 'feedback_submitted'",
    )
    assert len(rows) == 1


def test_feedback_accepts_image_attachment(client):
    res = client.post(
        "/api/feedback",
        data=_form(title="with screenshot", description="here's what I saw"),
        files=[("attachments", ("shot.png", io.BytesIO(_PNG_1x1), "image/png"))],
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["attachment_count"] == 1

    attachments = _query(client, "SELECT * FROM feedback_attachments")
    assert len(attachments) == 1
    assert attachments[0]["mime_type"] == "image/png"
    assert attachments[0]["size_bytes"] == len(_PNG_1x1)

    # File should exist on disk
    from api.config import settings
    fid = attachments[0]["feedback_id"]
    name = attachments[0]["filename"]
    disk_path = settings.storage_dir / "feedback" / str(fid) / name
    assert disk_path.exists()
    assert disk_path.read_bytes() == _PNG_1x1


def test_feedback_rejects_non_image_attachment(client):
    res = client.post(
        "/api/feedback",
        data=_form(title="t", description="d"),
        files=[("attachments", ("notes.txt", io.BytesIO(b"text data"), "text/plain"))],
    )
    assert res.status_code == 400
    assert "unsupported" in res.json()["detail"].lower()


def test_admin_attachment_route_requires_token(client):
    # Submit one with an attachment
    res = client.post(
        "/api/feedback",
        data=_form(title="with screenshot", description="d"),
        files=[("attachments", ("a.png", io.BytesIO(_PNG_1x1), "image/png"))],
    )
    fb_id = res.json()["id"]
    rows = _query(client, "SELECT filename FROM feedback_attachments")
    fname = rows[0]["filename"]

    # No token
    res_noauth = client.get(f"/api/admin/feedback/{fb_id}/attachments/{fname}")
    assert res_noauth.status_code == 401

    # Correct token returns the file
    res_auth = client.get(
        f"/api/admin/feedback/{fb_id}/attachments/{fname}?token=test-admin-token"
    )
    assert res_auth.status_code == 200
    assert res_auth.content == _PNG_1x1


def test_admin_without_token_returns_401(client):
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
        data=_form(title="t", description="d", email="a@b.c"),
    )
    res = client.get("/api/admin/stats?token=test-admin-token")
    assert res.status_code == 200
    fb = res.json()["recent_feedback"]
    assert len(fb) == 1
    assert fb[0]["title"] == "t"
    # New field: attachments array (empty here)
    assert fb[0]["attachments"] == []


def test_admin_feedback_includes_attachment_metadata(client):
    client.post(
        "/api/feedback",
        data=_form(title="t", description="d"),
        files=[("attachments", ("a.png", io.BytesIO(_PNG_1x1), "image/png"))],
    )
    res = client.get("/api/admin/stats?token=test-admin-token")
    fb = res.json()["recent_feedback"][0]
    assert len(fb["attachments"]) == 1
    att = fb["attachments"][0]
    assert att["mime_type"] == "image/png"
    assert att["size_bytes"] == len(_PNG_1x1)
    assert att["filename"].endswith(".png")


def test_feedback_marked_test_when_header_set(client):
    client.post(
        "/api/feedback",
        data=_form(title="real", description="real bug"),
    )
    client.post(
        "/api/feedback",
        data=_form(title="devtest", description="my own click"),
        headers={"X-Cite2fn-Test": "1"},
    )

    res = client.get("/api/admin/stats?token=test-admin-token")
    body = res.json()
    assert len(body["recent_feedback"]) == 1
    assert body["recent_feedback"][0]["title"] == "real"
    assert body["test_counts"]["feedback"] == 1

    res2 = client.get("/api/admin/stats?token=test-admin-token&include_test=1")
    body2 = res2.json()
    assert len(body2["recent_feedback"]) == 2
    assert body2["include_test"] is True


def test_test_mode_env_marks_everything(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("ADMIN_TOKEN", "t")
    monkeypatch.setenv("CITE2FN_TEST_MODE", "1")

    from api import config

    importlib.reload(config)
    from api import jobs, main

    importlib.reload(jobs)
    importlib.reload(main)

    from fastapi.testclient import TestClient

    with TestClient(main.app) as c:
        c.post("/api/feedback", data={"title": "x", "description": "y"})
        res = c.get("/api/admin/stats?token=t")
        body = res.json()
        assert len(body["recent_feedback"]) == 0
        assert body["test_counts"]["feedback"] == 1


def test_admin_hidden_when_no_token_configured(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("STORAGE_DIR", tmp)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("CITE2FN_TEST_MODE", raising=False)

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
