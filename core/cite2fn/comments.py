"""Word comment insertion for flagging issues.

Uses python-docx's comment API to add margin annotations to the document.
"""

from __future__ import annotations

from docx import Document
from docx.text.paragraph import Paragraph
from docx.text.run import Run


AUTHOR = "cite2footnote"
INITIALS = "C2F"


def add_no_source_comment(doc: Document, paragraph: Paragraph, run: Run | None = None) -> None:
    """Flag a citation with no source URL."""
    text = (
        "\u26a0 Citation detected but no source URL. "
        "Please add a hyperlink to the source document so Bluebook formatting can be verified."
    )
    _add_comment(doc, paragraph, run, text)


def add_fetch_failed_comment(doc: Document, paragraph: Paragraph, url: str, run: Run | None = None) -> None:
    """Flag a citation whose URL could not be fetched."""
    text = f"\u26a0 Could not access {url} \u2014 citation formatted from display text only. Please verify."
    _add_comment(doc, paragraph, run, text)


def add_ambiguous_cleanup_comment(doc: Document, paragraph: Paragraph, run: Run | None = None) -> None:
    """Flag ambiguous text cleanup."""
    text = "\u26a0 Review: should the author name be kept in the body text here, or removed entirely?"
    _add_comment(doc, paragraph, run, text)


def add_low_confidence_comment(doc: Document, paragraph: Paragraph, run: Run | None = None) -> None:
    """Flag a citation where LLM formatting confidence is low."""
    text = "\u26a0 Bluebook formatting may be incorrect \u2014 please verify against the source."
    _add_comment(doc, paragraph, run, text)


def add_possible_supra_comment(
    doc: Document, paragraph: Paragraph, source_note: int, run: Run | None = None,
) -> None:
    """Flag a possible repeated citation that might use supra."""
    text = (
        f"\u26a0 This may be a repeated citation of the source in note {source_note} "
        "\u2014 consider using supra."
    )
    _add_comment(doc, paragraph, run, text)


def _add_comment(doc: Document, paragraph: Paragraph, run: Run | None, text: str) -> None:
    """Add a comment to the document, anchored to a run or paragraph."""
    try:
        if run is not None:
            paragraph.add_comment(text, author=AUTHOR, initials=INITIALS, comment_range=run)
        else:
            # Anchor to the first run if no specific run given
            if paragraph.runs:
                paragraph.add_comment(
                    text, author=AUTHOR, initials=INITIALS, comment_range=paragraph.runs[0]
                )
            else:
                paragraph.add_comment(text, author=AUTHOR, initials=INITIALS)
    except (AttributeError, TypeError):
        # Fallback: python-docx version may not support comment_range
        # Just add the comment without anchoring
        try:
            paragraph.add_comment(text, author=AUTHOR, initials=INITIALS)
        except Exception:
            pass  # Skip if comments not supported at all
