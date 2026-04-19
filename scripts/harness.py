"""Local integration harness: exercise the real pipeline on a real .docx with
a mocked LLM so body-placement bugs surface without any API calls.

Usage:
    python scripts/harness.py <input.docx> <output.docx>
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

from cite2fn.assemble import assemble_document
from cite2fn.detect import detect_citations
from cite2fn.references import match_citations_to_references, parse_references


def main() -> None:
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    citations = detect_citations(str(in_path))
    refs = parse_references(str(in_path))
    if refs:
        citations = match_citations_to_references(citations, refs)

    for i, c in enumerate(citations, start=1):
        if not c.bluebook_text:
            author = c.author_name or "Author"
            year = c.year or "2025"
            c.bluebook_text = (
                f"{author}, *Source {i}*, 1 ~Mock. J.~ 100 ({year})."
            )
            c.confidence = "confident"

    print("=== CITATIONS DETECTED ===")
    for c in citations:
        print(f"  id={c.id} type={c.type} para={c.paragraph_index} "
              f"author={c.author_name!r} year={c.year!r} "
              f"display={c.display_text[:60]!r}")

    citations_data = [c.to_dict() for c in citations]

    report = assemble_document(
        input_path=str(in_path),
        output_path=str(out_path),
        citations_data=citations_data,
        output_format="footnotes",
        style="bluebook",
    )

    print("\n=== REPORT ===")
    print(f"  citations detected: {len(citations)}")
    print(f"  footnotes_inserted: {report.get('footnotes_inserted')}")
    print(f"  existing_footnotes_converted: {report.get('existing_footnotes_converted')}")
    print(f"  footnotes_merged: {report.get('footnotes_merged', 0)}")
    print(f"  comments_added: {report.get('comments_added')}")
    if report.get("issues"):
        print(f"  issues ({len(report['issues'])}):")
        for issue in report["issues"][:30]:
            print(f"    - {issue}")

    audit(out_path, citations)


def audit(path: Path, citations: list) -> None:
    NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as z:
        root = etree.fromstring(z.read("word/document.xml"))

    paragraphs = []
    for p in root.findall(".//w:p", NS):
        pieces = []
        fns_here = []
        for child in p.iter():
            tag = etree.QName(child).localname
            if tag == "t":
                pieces.append(child.text or "")
            elif tag in ("footnoteReference", "endnoteReference"):
                fid = child.get(f"{{{NS['w']}}}id")
                pieces.append(f"[FN{fid}]")
                fns_here.append(fid)
        line = "".join(pieces)
        paragraphs.append((line, fns_here))

    print("\n=== AUDIT ===")
    total_defects = 0
    seen_fns: set[str] = set()
    for pi, (line, fns) in enumerate(paragraphs):
        defects = []
        if re.search(r" \[FN\d+\]", line):
            defects.append("space-before-FN")
        if re.search(r"\[FN\d+\][.,;:]", line):
            defects.append("FN-before-punct")
        if re.search(r"\[FN\d+\][A-Za-z]", line):
            defects.append("no-space-after-FN")
        if re.search(r"\(\s*[A-Za-z][^()]*\)\[FN\d+\]", line):
            defects.append("parens-around-author")
        if re.search(r"\[FN\d+\]\s*\[FN\d+\]", line):
            defects.append("clumped-FNs")
        if re.search(r"\(\d{4}\)", line):
            defects.append("year-in-parens-still-present")
        if " ." in line or " ," in line:
            defects.append("space-before-punct")
        if "  " in line:
            defects.append("double-space")
        # Adjacent punct in body. Skip the legitimate Latin abbreviation
        # "et al." followed by a comma — `.,` is expected there.
        adj = [
            m for m in re.finditer(r"[.,;:]{2,}", line)
            if not line[max(0, m.start() - 6):m.end()].lower().startswith("et al")
            and not re.search(r"\bet al\.,", line[max(0, m.start() - 10):m.end()])
        ]
        if adj:
            defects.append(f"adjacent-punct@{adj[0].group()}")
        for fn in fns:
            seen_fns.add(fn)

        if defects:
            total_defects += len(defects)
            print(f"\nP{pi}  defects: {defects}")
            # Show the offending segment
            print(f"   {line[:400]}")

    # Missing FNs: count expected vs seen
    expected_fns = [c for c in citations if c.bluebook_text and c.type != "existing_footnote"]
    print(f"\n=== FN COVERAGE ===")
    print(f"  expected (citations with bluebook_text): {len(expected_fns)}")
    print(f"  seen in body: {len(seen_fns)}")
    if len(seen_fns) < len(expected_fns):
        print(f"  **{len(expected_fns) - len(seen_fns)} FN markers missing from body**")

    print(f"\n=== TOTAL DEFECTS: {total_defects} ===")


if __name__ == "__main__":
    main()
