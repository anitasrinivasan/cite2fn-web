"""List of References output mode.

Appends an alphabetically sorted reference list to the end of the document
instead of inserting footnotes/endnotes. Body text is left untouched.
"""

from __future__ import annotations

from lxml import etree
from docx import Document

from cite2fn.footnotes import add_formatted_runs, _make_tag, W


def insert_references_list(
    doc: Document,
    formatted_citations: list[str],
) -> int:
    """Append a "References" section with formatted citations to the document.

    Args:
        doc: The python-docx Document object.
        formatted_citations: Pre-sorted list of formatted citation strings
            (with *italic* and ~small caps~ markers).

    Returns:
        Number of references inserted.
    """
    body = doc.element.body

    # --- Add a "References" heading ---
    heading_p = _make_heading_paragraph("References")
    body.append(heading_p)

    # --- Add each reference as a paragraph with hanging indent ---
    for ref_text in formatted_citations:
        ref_p = _make_reference_paragraph(ref_text)
        body.append(ref_p)

    return len(formatted_citations)


def sort_references(citations_with_text: list[dict]) -> list[str]:
    """Sort formatted citations alphabetically by first author surname.

    Args:
        citations_with_text: List of dicts with at least 'bluebook_text'
            and optionally 'author_name' for sorting.

    Returns:
        Sorted list of formatted citation strings.
    """
    def sort_key(entry: dict) -> str:
        # Use author_name if available, otherwise extract from formatted text
        author = entry.get("author_name", "") or ""
        if not author and entry.get("bluebook_text"):
            # Take the first word(s) before a comma or parenthesis
            text = entry["bluebook_text"].lstrip("*~")
            for delim in (",", "(", "."):
                if delim in text:
                    author = text[:text.index(delim)]
                    break
            else:
                author = text[:30]
        return author.lower().strip()

    sorted_entries = sorted(citations_with_text, key=sort_key)
    return [e["bluebook_text"] for e in sorted_entries if e.get("bluebook_text")]


def _make_heading_paragraph(text: str) -> etree._Element:
    """Create a 'References' heading paragraph."""
    p = etree.Element(_make_tag("p"))

    # Paragraph properties: Heading 1 style, centered
    ppr = etree.SubElement(p, _make_tag("pPr"))
    pstyle = etree.SubElement(ppr, _make_tag("pStyle"))
    pstyle.set(_make_tag("val"), "Heading1")

    # Add spacing before
    spacing = etree.SubElement(ppr, _make_tag("spacing"))
    spacing.set(_make_tag("before"), "480")  # 24pt before
    spacing.set(_make_tag("after"), "240")  # 12pt after

    # Text run
    run = etree.SubElement(p, _make_tag("r"))
    rpr = etree.SubElement(run, _make_tag("rPr"))
    fonts = etree.SubElement(rpr, _make_tag("rFonts"))
    fonts.set(_make_tag("ascii"), "Times New Roman")
    fonts.set(_make_tag("hAnsi"), "Times New Roman")
    fonts.set(_make_tag("cs"), "Times New Roman")
    b = etree.SubElement(rpr, _make_tag("b"))
    sz = etree.SubElement(rpr, _make_tag("sz"))
    sz.set(_make_tag("val"), "28")  # 14pt

    t = etree.SubElement(run, _make_tag("t"))
    t.text = text

    return p


def _make_reference_paragraph(text: str) -> etree._Element:
    """Create a reference paragraph with hanging indent and formatted runs."""
    p = etree.Element(_make_tag("p"))

    # Paragraph properties: hanging indent (standard for reference lists)
    ppr = etree.SubElement(p, _make_tag("pPr"))
    spacing = etree.SubElement(ppr, _make_tag("spacing"))
    spacing.set(_make_tag("line"), "480")  # double-spaced (APA standard)
    spacing.set(_make_tag("lineRule"), "auto")
    spacing.set(_make_tag("after"), "0")

    # Hanging indent: 0.5 inch = 720 twips
    ind = etree.SubElement(ppr, _make_tag("ind"))
    ind.set(_make_tag("left"), "720")
    ind.set(_make_tag("hanging"), "720")

    # Default run properties
    rpr_p = etree.SubElement(ppr, _make_tag("rPr"))
    fonts = etree.SubElement(rpr_p, _make_tag("rFonts"))
    fonts.set(_make_tag("ascii"), "Times New Roman")
    fonts.set(_make_tag("hAnsi"), "Times New Roman")
    fonts.set(_make_tag("cs"), "Times New Roman")
    sz = etree.SubElement(rpr_p, _make_tag("sz"))
    sz.set(_make_tag("val"), "24")  # 12pt for reference list

    # Add formatted text runs (handles *italic* and ~small caps~ markers)
    add_formatted_runs(p, text, size_half_pts=24)

    return p
