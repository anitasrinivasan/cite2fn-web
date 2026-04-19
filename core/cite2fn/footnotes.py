"""Footnote and endnote insertion via direct XML manipulation.

python-docx has no footnote creation API, so we work directly with
the XML using lxml. This module handles:
- Creating a footnotes/endnotes part from scratch (for docs that have none)
- Inserting new footnotes/endnotes with formatted text
- Inserting footnote references in the body at the correct position
- Replacing existing footnote content
"""

from __future__ import annotations

import copy
from lxml import etree
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.packuri import PackURI
from docx.opc.part import Part

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
NSMAP = {"w": W, "r": R, "w14": W14}

# Relationship type URIs
FOOTNOTES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes"
ENDNOTES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes"

# Content types
FOOTNOTES_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"
ENDNOTES_CT = "application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"


def _make_tag(localname: str) -> str:
    """Create a fully qualified tag name in the Word namespace."""
    return f"{{{W}}}{localname}"


def _make_r_tag(localname: str) -> str:
    """Create a fully qualified tag name in the relationships namespace."""
    return f"{{{R}}}{localname}"


class FootnoteManager:
    """Manages footnote/endnote insertion for a document."""

    def __init__(self, doc: Document, use_endnotes: bool = False):
        self.doc = doc
        self.use_endnotes = use_endnotes
        self._notes_part = None
        # Cache the original bluebook-style text for each inserted note so the
        # adjacent-ref merger can combine formatted text without having to
        # reverse-engineer italic/smallcaps markers from the XML.
        self._note_texts: dict[int, str] = {}
        self._notes_xml = None
        self._next_id = None
        self._rel_type = ENDNOTES_REL if use_endnotes else FOOTNOTES_REL
        self._content_type = ENDNOTES_CT if use_endnotes else FOOTNOTES_CT
        self._part_name = "endnotes.xml" if use_endnotes else "footnotes.xml"
        self._note_tag = "endnote" if use_endnotes else "footnote"
        self._ref_tag = "endnoteReference" if use_endnotes else "footnoteReference"
        self._note_ref_tag = "endnoteRef" if use_endnotes else "footnoteRef"
        self._root_tag = "endnotes" if use_endnotes else "footnotes"

        self._init_notes_part()

    def _init_notes_part(self) -> None:
        """Find or create the footnotes/endnotes XML part."""
        # Look for existing part
        for rel in self.doc.part.rels.values():
            if self._rel_type in str(rel.reltype):
                self._notes_part = rel.target_part
                self._notes_xml = etree.fromstring(self._notes_part.blob)
                self._compute_next_id()
                self._ensure_arabic_numbering()
                return

        # No existing part — create one from scratch
        self._create_notes_part()

        # Ensure arabic numbering (1, 2, 3) in all cases
        self._ensure_arabic_numbering()

    def _compute_next_id(self) -> None:
        """Compute the next available footnote/endnote ID."""
        max_id = -1
        for note in self._notes_xml:
            note_id = note.get(_make_tag("id"))
            if note_id is not None:
                try:
                    max_id = max(max_id, int(note_id))
                except ValueError:
                    pass
        self._next_id = max_id + 1

    def _ensure_arabic_numbering(self) -> None:
        """Set footnote/endnote numbering to arabic (1, 2, 3).

        Word defaults to arabic for footnotes but roman numerals (i, ii, iii)
        for endnotes. This explicitly sets decimal numbering in the section
        properties to guarantee arabic numerals in both cases.
        """
        body = self.doc.element.body
        pr_tag = "endnotePr" if self.use_endnotes else "footnotePr"

        # Ensure sectPr exists
        sect_pr = body.find(_make_tag("sectPr"))
        if sect_pr is None:
            sect_pr = etree.SubElement(body, _make_tag("sectPr"))

        # Find or create the footnotePr/endnotePr element
        note_pr = sect_pr.find(_make_tag(pr_tag))
        if note_pr is None:
            note_pr = etree.SubElement(sect_pr, _make_tag(pr_tag))

        # Set numFmt to decimal (arabic numerals)
        num_fmt = note_pr.find(_make_tag("numFmt"))
        if num_fmt is None:
            num_fmt = etree.SubElement(note_pr, _make_tag("numFmt"))
        num_fmt.set(_make_tag("val"), "decimal")

    def _create_notes_part(self) -> None:
        """Create a new footnotes/endnotes XML part from scratch."""
        # Create the root XML element
        root = etree.Element(
            _make_tag(self._root_tag),
            nsmap={"w": W, "r": R, "w14": W14},
        )

        # Word expects separator notes (these are auto-generated separators)
        # For Google Docs exports, these may not exist, but Word needs them
        # for proper rendering. We'll create them.
        sep_note = self._make_separator_note("-1", "separator")
        root.append(sep_note)
        cont_note = self._make_separator_note("0", "continuationSeparator")
        root.append(cont_note)

        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)

        # Create the OPC part
        part = Part(
            partname=PackURI(f"/word/{self._part_name}"),
            content_type=self._content_type,
            blob=xml_bytes,
            package=self.doc.part.package,
        )

        # Add the relationship
        self.doc.part.relate_to(part, self._rel_type)

        self._notes_part = part
        self._notes_xml = root
        self._next_id = 1  # Start after the separator notes

    def _make_separator_note(self, note_id: str, sep_type: str) -> etree._Element:
        """Create a separator footnote/endnote element."""
        note = etree.SubElement(
            etree.Element("dummy"),  # temporary parent
            _make_tag(self._note_tag),
        )
        note.set(_make_tag("type"), sep_type)
        note.set(_make_tag("id"), note_id)

        p = etree.SubElement(note, _make_tag("p"))
        r = etree.SubElement(p, _make_tag("r"))
        if sep_type == "separator":
            etree.SubElement(r, _make_tag("separator"))
        else:
            etree.SubElement(r, _make_tag("continuationSeparator"))

        # Detach from dummy parent
        note.getparent().remove(note)
        return note

    def insert_footnote(
        self,
        text: str,
        paragraph_element: etree._Element,
        insert_after_element: etree._Element | None = None,
    ) -> int:
        """Insert a new footnote/endnote and return its ID.

        Args:
            text: The footnote text content.
            paragraph_element: The body paragraph to insert the reference into.
            insert_after_element: The element (w:r or w:hyperlink) after which
                to insert the footnote reference. If None, appends to end of paragraph.

        Returns:
            The footnote/endnote ID number.
        """
        note_id = self._next_id
        self._next_id += 1

        # 1. Create the footnote/endnote element in the notes part
        note_elem = self._make_note_element(note_id, text)
        self._notes_xml.append(note_elem)
        self._note_texts[note_id] = text

        # 2. Insert the reference in the body paragraph
        ref_run = self._make_reference_run(note_id)
        if insert_after_element is not None:
            parent = insert_after_element.getparent()
            idx = list(parent).index(insert_after_element)

            # Advance past any immediately following punctuation run
            # so the footnote ref appears after punctuation (Bluebook Rule 1.1)
            next_idx = idx + 1
            siblings = list(parent)
            if next_idx < len(siblings):
                next_elem = siblings[next_idx]
                if next_elem.tag == _make_tag("r"):
                    t_elems = next_elem.findall(_make_tag("t"))
                    if t_elems and t_elems[0].text and t_elems[0].text[0] in ".,;:":
                        if t_elems[0].text.strip() in (".", ",", ";", ":", ".,", ",.", ". "):
                            idx = next_idx  # insert after the punctuation-only run
                        else:
                            # Split: extract leading punctuation into its own run
                            punct = t_elems[0].text[0]
                            t_elems[0].text = t_elems[0].text[1:]
                            punct_run = copy.deepcopy(next_elem)
                            for t in punct_run.findall(_make_tag("t")):
                                t.text = punct
                            parent.insert(next_idx, punct_run)
                            idx = next_idx  # insert after the new punctuation-only run

            parent.insert(idx + 1, ref_run)
        else:
            paragraph_element.append(ref_run)

        # 3. Update the part blob
        self._flush()

        return note_id

    def replace_footnote_content(self, footnote_id: int, new_text: str) -> None:
        """Replace the text content of an existing footnote."""
        for note in self._notes_xml:
            if note.get(_make_tag("id")) == str(footnote_id):
                # Remove all existing content
                for child in list(note):
                    note.remove(child)

                # Create new content paragraph
                p = self._make_note_paragraph(new_text)
                note.append(p)

                self._note_texts[footnote_id] = new_text
                self._flush()
                return

    def get_note_text(self, footnote_id: int) -> str | None:
        """Return the bluebook-style source text originally passed to
        `insert_footnote` or `replace_footnote_content`. Returns None if
        unknown (e.g. existing footnotes parsed from the source document)."""
        return self._note_texts.get(footnote_id)

    def get_all_note_ids(self) -> list[int]:
        """Get all non-separator footnote/endnote IDs in order."""
        ids = []
        for note in self._notes_xml:
            note_type = note.get(_make_tag("type"))
            if note_type in ("separator", "continuationSeparator"):
                continue
            note_id = note.get(_make_tag("id"))
            if note_id is not None:
                ids.append(int(note_id))
        return sorted(ids)

    def _make_note_element(self, note_id: int, text: str) -> etree._Element:
        """Create a complete footnote/endnote XML element."""
        note = etree.Element(_make_tag(self._note_tag))
        note.set(_make_tag("id"), str(note_id))

        p = self._make_note_paragraph(text)
        note.append(p)
        return note

    def _make_note_paragraph(self, text: str) -> etree._Element:
        """Create the paragraph content for a footnote/endnote."""
        p = etree.SubElement(etree.Element("dummy"), _make_tag("p"))
        p.getparent().remove(p)

        # Paragraph properties: 10pt Times New Roman
        ppr = etree.SubElement(p, _make_tag("pPr"))
        spacing = etree.SubElement(ppr, _make_tag("spacing"))
        spacing.set(_make_tag("line"), "240")
        spacing.set(_make_tag("lineRule"), "auto")
        rpr_p = etree.SubElement(ppr, _make_tag("rPr"))
        fonts = etree.SubElement(rpr_p, _make_tag("rFonts"))
        fonts.set(_make_tag("ascii"), "Times New Roman")
        fonts.set(_make_tag("hAnsi"), "Times New Roman")
        fonts.set(_make_tag("cs"), "Times New Roman")
        sz = etree.SubElement(rpr_p, _make_tag("sz"))
        sz.set(_make_tag("val"), "20")  # 10pt = 20 half-points

        # Footnote reference run (the superscript number)
        ref_run = etree.SubElement(p, _make_tag("r"))
        ref_rpr = etree.SubElement(ref_run, _make_tag("rPr"))
        rstyle = etree.SubElement(ref_rpr, _make_tag("rStyle"))
        rstyle.set(_make_tag("val"), "FootnoteReference")
        valign = etree.SubElement(ref_rpr, _make_tag("vertAlign"))
        valign.set(_make_tag("val"), "superscript")
        etree.SubElement(ref_run, _make_tag(self._note_ref_tag))

        # Space after the reference number
        space_run = etree.SubElement(p, _make_tag("r"))
        space_rpr = etree.SubElement(space_run, _make_tag("rPr"))
        fonts2 = etree.SubElement(space_rpr, _make_tag("rFonts"))
        fonts2.set(_make_tag("ascii"), "Times New Roman")
        fonts2.set(_make_tag("hAnsi"), "Times New Roman")
        fonts2.set(_make_tag("cs"), "Times New Roman")
        sz2 = etree.SubElement(space_rpr, _make_tag("sz"))
        sz2.set(_make_tag("val"), "20")
        space_t = etree.SubElement(space_run, _make_tag("t"))
        space_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        space_t.text = " "

        # Content runs — handle italic markers for Bluebook formatting
        # Simple approach: split on *..* for italic spans
        self._add_formatted_runs(p, text)

        return p

    def _add_formatted_runs(self, paragraph: etree._Element, text: str) -> None:
        """Add text runs to a paragraph, handling *italic* and ~small caps~ markers."""
        add_formatted_runs(paragraph, text)

    def _make_reference_run(self, note_id: int) -> etree._Element:
        """Create the footnote/endnote reference run for the body text."""
        run = etree.Element(_make_tag("r"))
        rpr = etree.SubElement(run, _make_tag("rPr"))
        rstyle = etree.SubElement(rpr, _make_tag("rStyle"))
        rstyle.set(_make_tag("val"), "FootnoteReference")
        valign = etree.SubElement(rpr, _make_tag("vertAlign"))
        valign.set(_make_tag("val"), "superscript")

        ref = etree.SubElement(run, _make_tag(self._ref_tag))
        ref.set(_make_tag("id"), str(note_id))

        return run

    def _flush(self) -> None:
        """Write the modified XML back to the part blob."""
        self._notes_part._blob = etree.tostring(
            self._notes_xml,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        )


def add_formatted_runs(
    paragraph: etree._Element,
    text: str,
    font: str = "Times New Roman",
    size_half_pts: int = 20,
) -> None:
    """Add text runs to a paragraph, handling *italic* and ~small caps~ markers.

    Marker conventions:
    - *text* for italic (titles, case names, Id., supra)
    - ~TEXT~ for small caps (journal names, institutional authors)

    Args:
        paragraph: The lxml paragraph element to append runs to.
        text: Text with optional *italic* and ~small caps~ markers.
        font: Font name (default Times New Roman).
        size_half_pts: Font size in half-points (20 = 10pt, 24 = 12pt).
    """
    import re
    # Split on *...* for italic and ~...~ for small caps
    parts = re.split(r"(\*[^*]+\*|~[^~]+~)", text)

    for part in parts:
        if not part:
            continue

        is_italic = part.startswith("*") and part.endswith("*")
        is_smallcaps = part.startswith("~") and part.endswith("~")
        if is_italic:
            part = part[1:-1]
        elif is_smallcaps:
            part = part[1:-1]

        run = etree.SubElement(paragraph, _make_tag("r"))
        rpr = etree.SubElement(run, _make_tag("rPr"))

        # 1. Fonts
        fonts = etree.SubElement(rpr, _make_tag("rFonts"))
        fonts.set(_make_tag("ascii"), font)
        fonts.set(_make_tag("hAnsi"), font)
        fonts.set(_make_tag("cs"), font)

        # 2. Formatting toggles (must come before sz per OOXML spec)
        if is_italic:
            etree.SubElement(rpr, _make_tag("i"))
        elif is_smallcaps:
            sc = etree.SubElement(rpr, _make_tag("smallCaps"))
            sc.set(_make_tag("val"), "true")

        # 3. Size
        sz = etree.SubElement(rpr, _make_tag("sz"))
        sz.set(_make_tag("val"), str(size_half_pts))

        t = etree.SubElement(run, _make_tag("t"))
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t.text = part


# --- Post-processing: footnote-placement normalization --------------------
#
# After every FN ref has been inserted and every cleanup rule has run, sweep
# each paragraph to enforce three rules that are hard to guarantee during
# insertion alone (stray whitespace from cleanup, adjacent runs that start with
# punctuation, or runs that start with a letter and need a space inserted).
#
# Order matters: move-past-punctuation runs FIRST (may change which run is
# "next"), then strip-space-before, then ensure-space-after.

_REF_TAGS = {_make_tag("footnoteReference"), _make_tag("endnoteReference")}
_PUNCT_CHARS = ".,;:!?"


def merge_adjacent_footnote_refs(
    paragraph: etree._Element,
    fn_manager: "FootnoteManager",
) -> int:
    """Find groups of footnote refs that sit adjacent in the body and merge them.

    Two refs are "adjacent" if only whitespace runs (or nothing) separate them
    in the paragraph. For each group of 2+ refs, the first ref's footnote
    content is replaced with a semicolon-joined concatenation of every source
    in the group (trailing period ensured). The subsequent ref runs are
    removed from the body so Word renders a single superscript number.

    Returns the number of refs that were merged away (0 means no-op).
    """
    children = list(paragraph)
    groups: list[list[etree._Element]] = []
    current: list[etree._Element] = []

    for child in children:
        if _is_ref_run(child):
            current.append(child)
            continue
        if child.tag == _make_tag("r"):
            # Non-ref text run — only keep grouping if it's whitespace-only.
            text = "".join(t.text or "" for t in child.findall(_make_tag("t")))
            if text.strip() == "":
                continue  # whitespace between refs is fine — stay in the group
            if current:
                groups.append(current)
                current = []
            continue
        # hyperlink / ins / del / bookmark etc. — breaks the group
        if current:
            groups.append(current)
            current = []

    if current:
        groups.append(current)

    removed = 0
    for group in groups:
        if len(group) < 2:
            continue
        ids = [_get_ref_id(r) for r in group]
        texts = [fn_manager.get_note_text(i) for i in ids]
        # If we don't have cached text for any note, we can't merge that group
        # without losing content — skip.
        if any(t is None for t in texts):
            continue
        merged = "; ".join(t.rstrip(". ").rstrip() for t in texts if t)
        if not merged.endswith("."):
            merged += "."
        fn_manager.replace_footnote_content(ids[0], merged)
        for r in group[1:]:
            parent = r.getparent()
            if parent is not None:
                parent.remove(r)
        removed += len(group) - 1

    return removed


def _get_ref_id(ref_run: etree._Element) -> int | None:
    for child in ref_run:
        if child.tag in _REF_TAGS:
            raw = child.get(_make_tag("id"))
            if raw is not None:
                try:
                    return int(raw)
                except ValueError:
                    return None
    return None


def normalize_footnote_placement(paragraph: etree._Element) -> None:
    """Apply placement rules to every footnote/endnote ref run in `paragraph`.

    1. FN must not precede `.,;:!?` — if next run starts with punctuation,
       move the ref after it.
    2. No whitespace immediately before the FN — strip trailing whitespace
       from the preceding run's last `w:t`.
    3. FN followed by a letter needs a space — prepend one. Skips `'"),.;:`
       and existing whitespace.
    """
    # Collect first; mutating the tree while iterating is error-prone.
    ref_runs = [r for r in list(paragraph) if _is_ref_run(r)]
    for ref_run in ref_runs:
        _move_past_punctuation(ref_run)
    for ref_run in ref_runs:
        _strip_whitespace_before(ref_run)
    for ref_run in ref_runs:
        _ensure_space_after(ref_run)


def _is_ref_run(elem: etree._Element) -> bool:
    if elem.tag != _make_tag("r"):
        return False
    return any(child.tag in _REF_TAGS for child in elem)


def _move_past_punctuation(ref_run: etree._Element) -> None:
    parent = ref_run.getparent()
    if parent is None:
        return
    idx = list(parent).index(ref_run)
    if idx + 1 >= len(parent):
        return
    next_run = parent[idx + 1]
    if next_run.tag != _make_tag("r"):
        return
    t_elems = next_run.findall(_make_tag("t"))
    if not t_elems or not t_elems[0].text:
        return
    text = t_elems[0].text
    if text[0] not in _PUNCT_CHARS:
        return

    # How many leading punct chars?
    end = 0
    while end < len(text) and text[end] in _PUNCT_CHARS:
        end += 1
    leading = text[:end]
    remainder = text[end:]

    # Leave remainder in place; insert a copy with only the leading punct before the ref_run.
    t_elems[0].text = remainder
    t_elems[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    punct_run = copy.deepcopy(next_run)
    for pt in punct_run.findall(_make_tag("t")):
        pt.text = leading
        pt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    parent.insert(idx, punct_run)


def _strip_whitespace_before(ref_run: etree._Element) -> None:
    parent = ref_run.getparent()
    if parent is None:
        return
    idx = list(parent).index(ref_run)
    # Walk backward through any immediately-preceding whitespace-only runs,
    # trimming or removing as needed.
    while idx > 0:
        prev = parent[idx - 1]
        if prev.tag != _make_tag("r"):
            return
        t_elems = prev.findall(_make_tag("t"))
        if not t_elems:
            return
        last = t_elems[-1]
        if last.text is None:
            return
        stripped = last.text.rstrip()
        if stripped == last.text:
            return  # no trailing whitespace → done
        if stripped == "":
            # entire text was whitespace
            parent_t = last.getparent()
            parent_t.remove(last)
            # If this run has no more text elements, remove the whole run and
            # keep walking back to check the next preceding run.
            if not prev.findall(_make_tag("t")):
                parent.remove(prev)
                idx -= 1
                continue
            return
        last.text = stripped
        return


def _ensure_space_after(ref_run: etree._Element) -> None:
    parent = ref_run.getparent()
    if parent is None:
        return
    idx = list(parent).index(ref_run)
    if idx + 1 >= len(parent):
        return
    next_run = parent[idx + 1]
    if next_run.tag != _make_tag("r"):
        return
    t_elems = next_run.findall(_make_tag("t"))
    if not t_elems or not t_elems[0].text:
        return
    first = t_elems[0].text[0]
    # Only prepend a space if the next char is a letter or digit. Preserve
    # possessives (`'s`), punctuation, parens, quotes, and existing spaces.
    if not first.isalnum():
        return
    t_elems[0].text = " " + t_elems[0].text
    t_elems[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
