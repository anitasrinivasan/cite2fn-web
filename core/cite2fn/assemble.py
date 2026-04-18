"""Document assembly pipeline.

Takes a document and formatted citations, produces the final output with:
- Footnotes, endnotes, or a list of references
- Bluebook or APA citation style
- Inline text cleaned (footnote/endnote modes only)
- Word comments for flagged issues (footnote/endnote modes only)
- Supra/id. short forms applied (Bluebook footnote/endnote only)
- References section removed (footnote/endnote modes only)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from docx import Document

from cite2fn.models import Citation, citations_from_json
from cite2fn.footnotes import FootnoteManager
from cite2fn.cleanup import classify_cleanup_rule, apply_cleanup
from cite2fn.comments import (
    add_no_source_comment,
    add_fetch_failed_comment,
    add_low_confidence_comment,
)
from cite2fn.supra import normalize_source_key, apply_short_forms
from cite2fn.docx_io import save_document, remove_references_section
from cite2fn.references_list import insert_references_list, sort_references

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def assemble_document(
    input_path: str,
    output_path: str,
    citations_data: list[dict],
    use_endnotes: bool = False,
    keep_references: bool = False,
    output_format: str = "footnotes",
    style: str = "bluebook",
) -> dict:
    """Assemble the final document with all conversions applied.

    Args:
        input_path: Path to the original .docx
        output_path: Path for the output .docx
        citations_data: List of citation dicts with bluebook_text filled in
        use_endnotes: Use endnotes instead of footnotes (legacy flag)
        keep_references: Don't remove the References section
        output_format: "footnotes", "endnotes", or "references"
        style: "bluebook" or "apa"

    Returns:
        Report dict with stats and issues.
    """
    # Normalize legacy flag
    if use_endnotes and output_format == "footnotes":
        output_format = "endnotes"

    doc = Document(input_path)
    citations = [Citation.from_dict(d) for d in citations_data]

    report = {
        "input": input_path,
        "output": output_path,
        "style": style,
        "output_format": output_format,
        "total_citations": len(citations),
        "footnotes_inserted": 0,
        "existing_footnotes_converted": 0,
        "references_listed": 0,
        "comments_added": 0,
        "references_removed": False,
        "issues": [],
    }

    # --- List of References mode ---
    if output_format == "references":
        return _assemble_references_list(doc, citations, output_path, report)

    # --- Footnotes / Endnotes mode ---
    use_endnotes_flag = output_format == "endnotes"
    fn_manager = FootnoteManager(doc, use_endnotes=use_endnotes_flag)

    # Separate existing footnotes from new citations
    existing_fn_cites = [c for c in citations if c.type == "existing_footnote"]
    new_cites = [c for c in citations if c.type != "existing_footnote"]

    # Sort new citations by paragraph index (process in document order)
    new_cites.sort(key=lambda c: (c.paragraph_index, c.id))

    # --- Step 1: Convert existing footnotes ---
    for cite in existing_fn_cites:
        if cite.bluebook_text and cite.existing_footnote_id is not None:
            fn_manager.replace_footnote_content(cite.existing_footnote_id, cite.bluebook_text)
            report["existing_footnotes_converted"] += 1

    # --- Step 2: Prepare footnotes for new citations ---
    # Build the supra/id. data structure
    footnote_entries = []

    for cite in new_cites:
        if not cite.bluebook_text:
            continue

        source_key = normalize_source_key(
            author=cite.author_name,
            url=cite.url,
        )

        footnote_entries.append({
            "citation_id": cite.id,
            "note_id": None,  # Will be assigned during insertion
            "bluebook_text": cite.bluebook_text,
            "source_key": source_key,
            "author_name": cite.author_name,
            "signal_word": cite.signal_word,
            "short_form_type": None,
        })

    # Apply supra/id. (Bluebook only — APA doesn't use short forms)
    temp_note_id = fn_manager._next_id
    for entry in footnote_entries:
        entry["note_id"] = temp_note_id
        temp_note_id += 1

    if style == "bluebook":
        footnote_entries = apply_short_forms(footnote_entries)

    # Build lookup from citation_id to formatted text
    cite_to_text: dict[str, str] = {}
    for entry in footnote_entries:
        cite_to_text[entry["citation_id"]] = entry["bluebook_text"]

    # --- Step 2b: Validate formatting markers ---
    if style == "bluebook":
        for entry in footnote_entries:
            warnings = _validate_bluebook_markers(entry["bluebook_text"])
            for w in warnings:
                report["issues"].append(f"Citation {entry['citation_id']}: {w}")

    # --- Step 3: Insert footnotes and clean text ---
    # Process in reverse order within each paragraph to avoid index shifts
    paragraphs_cites: dict[int, list[Citation]] = {}
    for cite in new_cites:
        paragraphs_cites.setdefault(cite.paragraph_index, []).append(cite)

    for para_idx in sorted(paragraphs_cites.keys(), reverse=True):
        para_cites = paragraphs_cites[para_idx]
        # Process citations within this paragraph in reverse order
        for cite in reversed(para_cites):
            if cite.id not in cite_to_text:
                continue

            bluebook_text = cite_to_text[cite.id]
            para = doc.paragraphs[para_idx]
            para_elem = para._element
            para_text = para.text

            # Classify cleanup rule
            rule = classify_cleanup_rule(cite, para_text)
            cite.cleanup_rule = rule

            # Find the element to insert the footnote after
            insert_after = _find_insert_position(para_elem, cite)

            # Insert the footnote
            note_id = fn_manager.insert_footnote(
                bluebook_text, para_elem, insert_after
            )
            report["footnotes_inserted"] += 1

            # Apply text cleanup
            apply_cleanup(doc, cite, rule)

    # --- Step 4: Add comments for issues ---
    for cite in citations:
        if cite.type == "existing_footnote":
            continue

        para_idx = cite.paragraph_index
        if para_idx < 0 or para_idx >= len(doc.paragraphs):
            continue

        para = doc.paragraphs[para_idx]

        # No source URL
        if (cite.type in ("parenthetical", "inline_author_date")
                and not cite.url and not cite.matched_reference):
            add_no_source_comment(doc, para)
            report["comments_added"] += 1

        # Fetch failed
        if cite.fetched_metadata and cite.fetched_metadata.get("fetch_error"):
            add_fetch_failed_comment(doc, para, cite.url or "unknown")
            report["comments_added"] += 1

        # Low confidence
        if cite.confidence == "needs_review":
            add_low_confidence_comment(doc, para)
            report["comments_added"] += 1

    # --- Step 5: Remove references section ---
    if not keep_references:
        removed = remove_references_section(doc)
        if removed > 0:
            report["references_removed"] = True

    # --- Step 6: Save ---
    save_document(doc, output_path)

    return report


def _assemble_references_list(
    doc: Document,
    citations: list[Citation],
    output_path: str,
    report: dict,
) -> dict:
    """Assemble a document with a List of References at the end.

    Body text is left untouched. An alphabetically sorted reference list
    is appended at the end of the document.
    """
    # Remove old References section first (will be replaced)
    removed = remove_references_section(doc)
    if removed > 0:
        report["references_removed"] = True

    # Build entries for sorting
    entries = []
    for cite in citations:
        if not cite.bluebook_text:
            continue
        entries.append({
            "bluebook_text": cite.bluebook_text,
            "author_name": cite.author_name,
        })

    # Sort alphabetically and deduplicate
    sorted_refs = sort_references(entries)
    # Deduplicate (same formatted text)
    seen = set()
    unique_refs = []
    for ref in sorted_refs:
        if ref not in seen:
            seen.add(ref)
            unique_refs.append(ref)

    # Insert the reference list
    count = insert_references_list(doc, unique_refs)
    report["references_listed"] = count

    save_document(doc, output_path)
    return report


def _validate_bluebook_markers(bluebook_text: str) -> list[str]:
    """Flag potential formatting issues in bluebook_text."""
    warnings = []
    for match in re.finditer(r"~([^~]+)~", bluebook_text):
        inner = match.group(1).strip()
        # Strip punctuation and spaces to get the core text
        core = inner.replace("&", "").replace(" ", "").replace(".", "")
        # If the core is all-lowercase and short, it's likely an acronym
        # that shouldn't be in small caps at all
        if core.islower() and len(core) <= 5:
            warnings.append(
                f"Possible acronym in small caps: ~{inner}~ — "
                f"acronyms like {inner.upper()} should be plain uppercase, not in ~tildes~"
            )
    return warnings


def _find_insert_position(
    para_elem, cite: Citation
) -> None:
    """Find the XML element after which to insert the footnote reference.

    For hyperlinked citations: insert after the hyperlink element.
    For text citations: insert after the last run containing the citation text.
    Returns None to append to end of paragraph.
    """
    # For hyperlinks: find the matching hyperlink element
    if cite.type in ("hyperlink_external", "hyperlink_internal"):
        hyperlinks = para_elem.findall(f".//{{{W}}}hyperlink")
        for hl in hyperlinks:
            texts = [t.text for t in hl.findall(f".//{{{W}}}t") if t.text]
            hl_text = "".join(texts)
            if cite.display_text.strip("()[].,; ") in hl_text or hl_text in cite.display_text:
                return hl

    # For text citations: find the run containing the year or author
    search_text = cite.year or cite.author_name or cite.display_text
    if search_text:
        runs = para_elem.findall(f".//{{{W}}}r")
        for run in reversed(runs):
            for t in run.findall(f"{{{W}}}t"):
                if t.text and search_text in t.text:
                    return run

    return None
