"""Helper: decide whether an incoming request should be treated as a test."""

from __future__ import annotations

from fastapi import Request

from api import config


def request_is_test(request: Request) -> bool:
    """True if either the server is globally in test mode (CITE2FN_TEST_MODE=1)
    or the request includes an X-Cite2fn-Test: 1 header."""
    if config.settings.test_mode:
        return True
    header = request.headers.get("x-cite2fn-test", "").strip().lower()
    return header in ("1", "true", "yes")
