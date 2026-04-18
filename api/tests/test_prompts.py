"""Prompt content tests — guard against accidental regressions in the rules both drivers share."""

from __future__ import annotations

from api.drivers._prompts import SYSTEM_PROMPT_FULL, SYSTEM_PROMPT_LEAN, user_message


def test_both_prompts_cover_both_styles():
    for prompt in (SYSTEM_PROMPT_FULL, SYSTEM_PROMPT_LEAN):
        assert "Bluebook" in prompt
        assert "APA" in prompt


def test_both_prompts_describe_markers():
    for prompt in (SYSTEM_PROMPT_FULL, SYSTEM_PROMPT_LEAN):
        assert "*asterisks*" in prompt
        assert "~tildes~" in prompt


def test_both_prompts_carve_out_acronyms():
    """The SEC/NIST/CFTC carve-out is load-bearing — regressing it breaks small-caps rendering."""
    for prompt in (SYSTEM_PROMPT_FULL, SYSTEM_PROMPT_LEAN):
        assert "acronym" in prompt.lower() or "initialism" in prompt.lower()
        # Examples the tooling relies on
        for acr in ("SEC", "NIST"):
            assert acr in prompt


def test_full_is_longer_than_lean():
    assert len(SYSTEM_PROMPT_FULL) > len(SYSTEM_PROMPT_LEAN)


def test_user_message_is_valid_json():
    import json

    out = user_message([{"citation_id": "x", "display_text": "y"}], "bluebook")
    parsed = json.loads(out)
    assert parsed["style"] == "bluebook"
    assert parsed["citations"][0]["citation_id"] == "x"
