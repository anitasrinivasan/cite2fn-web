"""Inline text cleanup after footnote insertion.

Implements Rules 1-5 from the spec:
1. Author name is grammatical → keep name, drop year
2. Standalone parenthetical → remove entirely
3. Entire hyperlinked phrase is citation (no grammatical role) → remove
4. Hyperlink on non-citation text → remove hyperlink formatting, keep text
5. Remove hyperlink formatting after adding footnote
"""

from __future__ import annotations

import re
from lxml import etree
from docx import Document

from cite2fn.models import Citation

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def classify_cleanup_rule(citation: Citation, para_text: str) -> int:
    """Determine which cleanup rule applies to a citation.

    Returns the rule number (1-5).
    """
    display = citation.display_text

    if citation.type == "parenthetical":
        # Check if the author name appears before the parenthetical
        # e.g., "Bisbee et al. (2023) found" → Rule 1 (inline author + year in parens)
        # vs "(Spann et al., 2025)" → Rule 2 (standalone)

        # Find the citation in the text
        idx = para_text.find(display)
        if idx >= 0:
            before = para_text[:idx].rstrip()
            # If the parenthetical is at the start or preceded by a period/sentence boundary
            if not before or before[-1] in ".!?:;":
                return 2  # Standalone at start
            # If preceded by author name text that's part of the sentence
            return 2  # Default for parenthetical: remove entirely

    if citation.type == "inline_author_date":
        return 1  # Keep author name, drop year

    if citation.type in ("hyperlink_external", "hyperlink_internal"):
        # Check if the hyperlinked text has a grammatical role
        idx = para_text.find(display)
        if idx >= 0:
            before = para_text[:idx].rstrip()
            after = para_text[idx + len(display):].lstrip()

            # If preceded by "As", "by", or other prepositions → grammatical role
            if before and re.search(r"\b(?:As|by|from|see|following|per)\s*$", before, re.IGNORECASE):
                return 1  # Keep name, drop year

            # If followed by a verb → author is subject → Rule 1
            if after and re.match(r"\s*(?:describes?|found|show|demonstrate|argue|note|report|compar)", after, re.IGNORECASE):
                return 1

            # If the display text doesn't look like a citation (no year, no "et al.")
            if not citation.year and "et al" not in display.lower():
                # Could be a non-citation hyperlink (like "Automatic Persona Generation")
                if not re.search(r"\d{4}", display):
                    return 4  # Keep text, remove hyperlink

            # If at end of sentence or after punctuation → standalone → Rule 3
            if before and before[-1] in ".!?;,":
                return 3

            # Default for hyperlinks: check if parenthetical
            if display.startswith("("):
                return 2

            return 1  # Default: keep author, drop year

    if citation.type == "existing_footnote":
        return 0  # No cleanup needed for existing footnotes

    return 5  # Default: just remove hyperlink formatting


def apply_cleanup(
    doc: Document,
    citation: Citation,
    rule: int,
) -> None:
    """Apply the cleanup rule to the document for a given citation.

    Modifies the document XML in-place.
    """
    if rule == 0:
        return  # No cleanup needed

    if citation.type in ("parenthetical", "inline_author_date"):
        _cleanup_text_citation(doc, citation, rule)
    elif citation.type in ("hyperlink_external", "hyperlink_internal"):
        _cleanup_hyperlink_citation(doc, citation, rule)


def _cleanup_text_citation(doc: Document, citation: Citation, rule: int) -> None:
    """Clean up parenthetical or inline author-date citations in body text."""
    para = doc.paragraphs[citation.paragraph_index]
    para_elem = para._element

    if rule == 2:
        # Remove the entire parenthetical text
        _remove_text_from_paragraph(para_elem, citation.display_text)
    elif rule == 1:
        # Keep author name, remove year (and surrounding parens if inline)
        if citation.year:
            # For inline: "Author et al. (2023)" → "Author et al."
            # Remove " (YYYY)" or "(YYYY)" or ", YYYY" or " YYYY"
            patterns = [
                f" ({citation.year})",
                f"({citation.year})",
                f", {citation.year}",
                f" {citation.year}",
            ]
            for pat in patterns:
                if pat in citation.display_text:
                    _remove_text_from_paragraph(para_elem, pat)
                    break


def _cleanup_hyperlink_citation(doc: Document, citation: Citation, rule: int) -> None:
    """Clean up hyperlinked citations by removing hyperlink formatting."""
    para = doc.paragraphs[citation.paragraph_index]
    para_elem = para._element

    # Find the hyperlink element(s) for this citation
    hyperlinks = para_elem.findall(f".//{{{W}}}hyperlink")

    for hl in hyperlinks:
        texts = [t.text for t in hl.findall(f".//{{{W}}}t") if t.text]
        hl_text = "".join(texts)

        if not _text_matches(hl_text, citation.display_text):
            continue

        if rule == 3:
            # Remove entirely — remove the hyperlink and all its content
            parent = hl.getparent()
            parent.remove(hl)
            # Clean up trailing/leading whitespace and punctuation
        elif rule in (1, 4, 5):
            # Keep text, remove hyperlink wrapper
            _unwrap_hyperlink(hl)

            if rule == 1 and citation.year:
                # Also remove the year from the text
                _remove_year_from_runs(para_elem, citation.year, citation.display_text)
        elif rule == 2:
            # Remove entirely (standalone parenthetical that was hyperlinked)
            parent = hl.getparent()
            parent.remove(hl)


def _unwrap_hyperlink(hyperlink: etree._Element) -> None:
    """Remove hyperlink wrapper, keeping the child runs in place."""
    parent = hyperlink.getparent()
    idx = list(parent).index(hyperlink)

    # Move all children out of the hyperlink
    children = list(hyperlink)
    for i, child in enumerate(children):
        hyperlink.remove(child)
        parent.insert(idx + i, child)

        # Remove hyperlink-style formatting from the runs
        rpr = child.find(f"{{{W}}}rPr")
        if rpr is not None:
            # Remove color
            for color in rpr.findall(f"{{{W}}}color"):
                rpr.remove(color)
            # Remove underline
            for u in rpr.findall(f"{{{W}}}u"):
                rpr.remove(u)
            # Remove hyperlink style
            for rstyle in rpr.findall(f"{{{W}}}rStyle"):
                if rstyle.get(f"{{{W}}}val") in ("Hyperlink", "InternetLink"):
                    rpr.remove(rstyle)

    parent.remove(hyperlink)


def _text_matches(hl_text: str, citation_text: str) -> bool:
    """Check if hyperlink text matches a citation's display text (fuzzy)."""
    # Normalize whitespace and strip
    hl_norm = " ".join(hl_text.split()).strip("()[].,; ")
    cite_norm = " ".join(citation_text.split()).strip("()[].,; ")
    # Check containment in either direction
    return hl_norm in cite_norm or cite_norm in hl_norm or hl_norm == cite_norm


def _remove_text_from_paragraph(para_elem: etree._Element, text_to_remove: str) -> None:
    """Remove a specific text string from paragraph runs."""
    for run in para_elem.findall(f".//{{{W}}}r"):
        for t_elem in run.findall(f"{{{W}}}t"):
            if t_elem.text and text_to_remove in t_elem.text:
                t_elem.text = t_elem.text.replace(text_to_remove, "", 1)
                # Clean up double spaces
                t_elem.text = re.sub(r"  +", " ", t_elem.text)
                return

    # If not found in a single run, try across consecutive runs
    # (the text may span multiple runs)
    runs = para_elem.findall(f".//{{{W}}}r")
    full_text = ""
    run_map: list[tuple[etree._Element, int, int]] = []  # (t_elem, start, end)
    for run in runs:
        for t_elem in run.findall(f"{{{W}}}t"):
            if t_elem.text:
                start = len(full_text)
                full_text += t_elem.text
                run_map.append((t_elem, start, len(full_text)))

    idx = full_text.find(text_to_remove)
    if idx >= 0:
        remove_end = idx + len(text_to_remove)
        for t_elem, start, end in run_map:
            if end <= idx or start >= remove_end:
                continue
            # This run overlaps with the text to remove
            text = t_elem.text
            local_start = max(0, idx - start)
            local_end = min(len(text), remove_end - start)
            t_elem.text = text[:local_start] + text[local_end:]


def _remove_year_from_runs(
    para_elem: etree._Element, year: str, context: str
) -> None:
    """Remove year text (and surrounding parens) from runs near a citation."""
    patterns = [f" ({year})", f"({year})", f", {year}", f" {year}"]
    for pat in patterns:
        _remove_text_from_paragraph(para_elem, pat)
        return  # Only remove once
