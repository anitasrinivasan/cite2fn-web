"""Tests for the seven body-text defects surfaced during E2E testing.

Each test builds a minimal lxml `<w:p>` element by hand and asserts the
expected post-condition after running the relevant fix.
"""

from __future__ import annotations

from lxml import etree

from cite2fn.cleanup import (
    _collapse_stray_whitespace,
    _remove_orphan_brackets,
    _remove_text_from_paragraph,
    _remove_wrapping_brackets,
    _remove_year_from_runs,
)
from cite2fn.footnotes import (
    _make_tag,
    merge_adjacent_footnote_refs,
    normalize_footnote_placement,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NSMAP = {"w": W}


# ---------------------------------------------------------------------------
# Helpers for building paragraph XML
# ---------------------------------------------------------------------------


def _p(*runs: etree._Element) -> etree._Element:
    p = etree.Element(_make_tag("p"), nsmap=NSMAP)
    for r in runs:
        p.append(r)
    return p


def _text_run(text: str) -> etree._Element:
    r = etree.Element(_make_tag("r"), nsmap=NSMAP)
    t = etree.SubElement(r, _make_tag("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return r


def _ref_run(note_id: int = 1) -> etree._Element:
    r = etree.Element(_make_tag("r"), nsmap=NSMAP)
    ref = etree.SubElement(r, _make_tag("footnoteReference"))
    ref.set(_make_tag("id"), str(note_id))
    return r


def _hyperlink(text: str) -> etree._Element:
    hl = etree.Element(_make_tag("hyperlink"), nsmap=NSMAP)
    hl.append(_text_run(text))
    return hl


def _paragraph_text(p: etree._Element) -> str:
    return "".join(t.text or "" for t in p.findall(f".//{{{W}}}t"))


def _has_ref_at(p: etree._Element, after_text: str) -> bool:
    """Return True iff the run immediately after a run whose text ends with
    `after_text` is a footnoteReference run."""
    runs = list(p)
    for i, r in enumerate(runs):
        if r.tag != _make_tag("r"):
            continue
        t_elems = r.findall(_make_tag("t"))
        text = "".join(t.text or "" for t in t_elems)
        if text.endswith(after_text) and i + 1 < len(runs):
            nxt = runs[i + 1]
            if nxt.tag == _make_tag("r") and nxt.findall(_make_tag("footnoteReference")):
                return True
    return False


# ---------------------------------------------------------------------------
# Bug E — _remove_year_from_runs tries all patterns
# ---------------------------------------------------------------------------


def test_remove_year_tries_all_patterns():
    # Text is "Author (2025) found" with NO leading space pattern matching
    # the first entry in _remove_year_from_runs. Before the fix, this left
    # "(2025)" in place because the function returned after the first failed
    # pattern.
    p = _p(_text_run("Author(2025) found"))
    _remove_year_from_runs(p, "2025", "Author (2025)")
    assert _paragraph_text(p) == "Author found"


def test_remove_text_from_paragraph_returns_bool():
    p = _p(_text_run("hello world"))
    assert _remove_text_from_paragraph(p, "world") is True
    assert _remove_text_from_paragraph(p, "world") is False  # already gone


# ---------------------------------------------------------------------------
# Bug G — orphan bracket sweep after rule-3 hyperlink removal
# ---------------------------------------------------------------------------


def test_orphan_close_paren_removed():
    # Hyperlink contained "(2025" (no closing paren), ")" was in a following
    # run. After rule-3 removes the hyperlink, ")" must be stripped.
    p = _p(_text_run("See "), _text_run("remainder"))
    # Simulate the state *after* removing a hyperlink whose text was "Author (2025"
    # by inserting our "close paren" into the remainder run.
    p[1].findall(_make_tag("t"))[0].text = ") remainder"
    _remove_orphan_brackets(p, removed_idx=1, removed_text="Author (2025")
    assert _paragraph_text(p) == "See  remainder"


def test_orphan_open_paren_removed():
    # Reverse case: hyperlink text was "2025)" (no open paren), "(" in prev run.
    p = _p(_text_run("See ("), _text_run(" remainder"))
    _remove_orphan_brackets(p, removed_idx=1, removed_text="2025)")
    assert _paragraph_text(p) == "See  remainder"


def test_balanced_brackets_left_alone():
    # If the removed text had matched brackets, don't touch anything.
    p = _p(_text_run("See ("), _text_run(") remainder"))
    _remove_orphan_brackets(p, removed_idx=1, removed_text="(Author 2025)")
    assert _paragraph_text(p) == "See () remainder"  # nothing stripped


# ---------------------------------------------------------------------------
# Bugs B, C, D — normalize_footnote_placement
# ---------------------------------------------------------------------------


def test_strips_trailing_space_before_ref():
    p = _p(_text_run("et al. "), _ref_run(9))
    normalize_footnote_placement(p)
    # Preceding text should have no trailing space
    assert p[0].findall(_make_tag("t"))[0].text == "et al."


def test_removes_empty_preceding_run_if_only_whitespace():
    p = _p(_text_run("et al."), _text_run("   "), _ref_run(9))
    normalize_footnote_placement(p)
    # Middle whitespace-only run is gone; ref is immediately after "et al."
    assert len(p) == 2
    assert p[0].findall(_make_tag("t"))[0].text == "et al."
    assert p[1].findall(_make_tag("footnoteReference"))


def test_inserts_space_after_letter():
    p = _p(_ref_run(21), _text_run("reports"))
    normalize_footnote_placement(p)
    assert p[1].findall(_make_tag("t"))[0].text == " reports"


def test_no_space_before_possessive_apostrophe():
    p = _p(_ref_run(31), _text_run("'s study"))
    normalize_footnote_placement(p)
    # Possessives stay as-is
    assert p[1].findall(_make_tag("t"))[0].text == "'s study"


def test_no_space_before_punctuation_after_move():
    # FN placed before period — should move ref past period.
    p = _p(_text_run("et al"), _ref_run(4), _text_run(". Next"))
    normalize_footnote_placement(p)
    text = _paragraph_text(p)
    assert text == "et al. Next"
    # Verify the ref is after the period
    assert _has_ref_at(p, ".")


def test_moves_ref_past_comma():
    p = _p(_text_run("et al"), _ref_run(5), _text_run(", and also"))
    normalize_footnote_placement(p)
    assert _paragraph_text(p) == "et al, and also"
    assert _has_ref_at(p, ",")


def test_idempotent():
    p = _p(_text_run("et al. "), _ref_run(9), _text_run("reports"))
    normalize_footnote_placement(p)
    snapshot = etree.tostring(p)
    normalize_footnote_placement(p)
    assert etree.tostring(p) == snapshot


def test_no_op_on_paragraph_without_refs():
    p = _p(_text_run("Just regular text, no citations."))
    snapshot = etree.tostring(p)
    normalize_footnote_placement(p)
    assert etree.tostring(p) == snapshot


def test_multiple_refs_in_paragraph():
    # Two FN refs in the same paragraph with different defects — each fixed independently.
    p = _p(
        _text_run("First "),
        _ref_run(1),
        _text_run("reports while "),
        _text_run("second "),
        _ref_run(2),
        _text_run("'s methodology"),
    )
    normalize_footnote_placement(p)
    # Ref 1: space added after → " reports"
    # Ref 2: possessive preserved → "'s methodology"
    full = _paragraph_text(p)
    assert "First" in full and " reports" in full
    assert "second" in full and "'s methodology" in full


# ---------------------------------------------------------------------------
# Fix 1 — _collapse_stray_whitespace (new in this round)
# ---------------------------------------------------------------------------


def test_collapse_space_before_period():
    p = _p(_text_run("survey data . Automatic"))
    _collapse_stray_whitespace(p)
    assert _paragraph_text(p) == "survey data. Automatic"


def test_collapse_space_before_comma():
    p = _p(_text_run("authors , then more"))
    _collapse_stray_whitespace(p)
    assert _paragraph_text(p) == "authors, then more"


def test_collapse_double_space():
    p = _p(_text_run("text  with  doubles"))
    _collapse_stray_whitespace(p)
    assert _paragraph_text(p) == "text with doubles"


def test_collapse_space_after_open_paren():
    p = _p(_text_run("see ( remainder"))
    _collapse_stray_whitespace(p)
    assert _paragraph_text(p) == "see (remainder"


def test_collapse_across_run_boundary():
    # "text " in one run, ". More" in the next — the space before the period
    # crosses runs so the within-text regex won't catch it.
    p = _p(_text_run("text "), _text_run(". More"))
    _collapse_stray_whitespace(p)
    assert _paragraph_text(p) == "text. More"


# ---------------------------------------------------------------------------
# Fix 2 — _remove_wrapping_brackets (new in this round)
# ---------------------------------------------------------------------------


def test_wrap_parens_removed_around_removal_position():
    # State after removing a hyperlink whose parens were in surrounding runs.
    # `(` at end of run 0, `)` at start of run 1 (after the removal site).
    p = _p(_text_run("fatigue. ("), _text_run(") They can"))
    _remove_wrapping_brackets(p, removed_idx=1)
    assert _paragraph_text(p) == "fatigue.  They can"


def test_wrap_square_brackets():
    p = _p(_text_run("see ["), _text_run("] next"))
    _remove_wrapping_brackets(p, removed_idx=1)
    assert _paragraph_text(p) == "see  next"


def test_no_action_when_not_wrapped():
    # No wrap pair around the position — left alone.
    p = _p(_text_run("fatigue. "), _text_run("They can"))
    _remove_wrapping_brackets(p, removed_idx=1)
    assert _paragraph_text(p) == "fatigue. They can"


# ---------------------------------------------------------------------------
# Fix 3 — merge_adjacent_footnote_refs
# ---------------------------------------------------------------------------


class _FakeFnManager:
    """Minimal stand-in for FootnoteManager.get_note_text + replace_footnote_content
    used by the merger tests without needing a full Document."""

    def __init__(self, texts: dict[int, str]):
        self._note_texts = dict(texts)
        self.replacements: dict[int, str] = {}

    def get_note_text(self, note_id: int):
        return self._note_texts.get(note_id)

    def replace_footnote_content(self, note_id: int, new_text: str) -> None:
        self._note_texts[note_id] = new_text
        self.replacements[note_id] = new_text


def test_merge_two_adjacent_refs():
    p = _p(_text_run("text"), _ref_run(1), _ref_run(2), _text_run(" more"))
    fm = _FakeFnManager({1: "Source A.", 2: "Source B."})
    removed = merge_adjacent_footnote_refs(p, fm)
    assert removed == 1
    assert fm.replacements[1] == "Source A; Source B."
    # Only one ref should remain in the paragraph
    refs = [r for r in p if r.findall(_make_tag("footnoteReference"))]
    assert len(refs) == 1


def test_merge_four_adjacent_refs():
    p = _p(
        _text_run("text ("),
        _ref_run(11),
        _ref_run(12),
        _ref_run(13),
        _ref_run(14),
        _text_run(")"),
    )
    fm = _FakeFnManager({
        11: "Zhou 2025.",
        12: "Kim 2024.",
        13: "Lee 2023.",
        14: "Wang 2025.",
    })
    removed = merge_adjacent_footnote_refs(p, fm)
    assert removed == 3
    assert fm.replacements[11] == "Zhou 2025; Kim 2024; Lee 2023; Wang 2025."


def test_refs_separated_by_text_not_merged():
    p = _p(_ref_run(1), _text_run(" between "), _ref_run(2))
    fm = _FakeFnManager({1: "A.", 2: "B."})
    removed = merge_adjacent_footnote_refs(p, fm)
    assert removed == 0
    assert fm.replacements == {}


def test_refs_separated_by_whitespace_still_merged():
    p = _p(_ref_run(1), _text_run(" "), _ref_run(2))
    fm = _FakeFnManager({1: "A.", 2: "B."})
    removed = merge_adjacent_footnote_refs(p, fm)
    assert removed == 1
    assert fm.replacements[1] == "A; B."


def test_missing_cached_text_skips_merge():
    p = _p(_ref_run(1), _ref_run(99))  # 99 not in cache (e.g. pre-existing footnote)
    fm = _FakeFnManager({1: "A."})
    removed = merge_adjacent_footnote_refs(p, fm)
    assert removed == 0  # refuse to merge if we'd lose content
