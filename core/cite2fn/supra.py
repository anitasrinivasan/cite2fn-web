"""Supra/Id. short-form citation logic.

After all footnotes have been inserted, applies Bluebook short-form rules:
1. Id. — when the immediately preceding footnote cites the same source
2. Supra — when a source was cited in an earlier (non-adjacent) footnote
"""

from __future__ import annotations

import re
from cite2fn.models import CitationLedger


def normalize_source_key(
    author: str | None,
    title: str | None = None,
    doi: str | None = None,
    url: str | None = None,
) -> str:
    """Create a normalized key for identifying the same source across citations.

    Priority: DOI > URL > author+title
    """
    if doi:
        return f"doi:{doi.lower().strip()}"
    if url:
        # Normalize URL: strip fragments, query params for matching
        clean_url = re.sub(r"[#?].*$", "", url.lower().strip().rstrip("/"))
        return f"url:{clean_url}"
    if author and title:
        return f"auth:{author.lower().strip()}|{title.lower().strip()[:50]}"
    if author:
        return f"auth:{author.lower().strip()}"
    return ""


def apply_short_forms(
    footnotes: list[dict],
) -> list[dict]:
    """Apply supra/id. short forms to a list of footnotes.

    Each footnote dict should have:
        - note_id: int
        - bluebook_text: str
        - source_key: str (from normalize_source_key)
        - author_name: str | None
        - signal_word: str | None (e.g., "See", "Cf.")

    Returns the same list with bluebook_text modified for short forms.
    Also adds 'short_form_type' field: None, 'id', or 'supra'.
    """
    if not footnotes:
        return footnotes

    ledger = CitationLedger()

    for i, fn in enumerate(footnotes):
        key = fn.get("source_key", "")
        if not key:
            fn["short_form_type"] = None
            continue

        # Check if this is a repeat citation
        if key in ledger.first_occurrence:
            first_note = ledger.first_occurrence[key]

            # Check if immediately preceding footnote has the same source
            if i > 0 and _prev_cites_same(footnotes[i - 1], key):
                fn["short_form_type"] = "id"
                fn["bluebook_text"] = _format_id(fn)
            else:
                fn["short_form_type"] = "supra"
                first_fn = next((f for f in footnotes if f["note_id"] == first_note), None)
                fn["bluebook_text"] = _format_supra(fn, first_note, first_fn)
        else:
            # First occurrence — use full citation
            ledger.first_occurrence[key] = fn["note_id"]
            fn["short_form_type"] = None

        ledger.footnote_sources.append((fn["note_id"], [key]))

    return footnotes


def _prev_cites_same(prev_fn: dict, source_key: str) -> bool:
    """Check if the previous footnote cites the same single source."""
    prev_key = prev_fn.get("source_key", "")
    return prev_key == source_key


def _format_id(fn: dict) -> str:
    """Format an Id. citation."""
    signal = fn.get("signal_word", "")
    prefix = f"{signal} " if signal else ""

    # TODO: handle pin cites (page numbers) — for now, just Id.
    return f"{prefix}*Id.*"


def _format_supra(fn: dict, first_note_id: int, first_fn: dict | None = None) -> str:
    """Format a supra citation.

    Gets the author name from the first footnote (the one supra refers back to),
    falling back to the current citation, then to parsing the first footnote's
    bluebook_text.
    """
    signal = fn.get("signal_word", "")
    prefix = f"{signal} " if signal else ""

    # Get author from the FIRST footnote (the one supra refers back to)
    author = None
    if first_fn:
        author = first_fn.get("author_name")
    # Fall back to current citation's author
    if not author:
        author = fn.get("author_name")
    # Last resort: extract leading text before first comma from first footnote's bluebook_text
    if not author and first_fn:
        full_text = first_fn.get("bluebook_text", "")
        if full_text:
            author = full_text.split(",")[0].strip()
            author = author.replace("*", "").replace("~", "")

    if not author:
        author = "[Author]"

    # Clean up: use just last name, strip "et al."
    author = author.split(",")[0].strip()
    author = re.sub(r"\s+et\s+al\.?", "", author)

    return f"{prefix}{author}, *supra* note {first_note_id}"
