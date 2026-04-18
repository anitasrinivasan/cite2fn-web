"""CLI entry points for cite2fn.

Provides JSON I/O commands that the Claude Code skill invokes via Bash.

Usage:
    python -m cite2fn.cli detect <input.docx>
    python -m cite2fn.cli parse-references <input.docx>
    python -m cite2fn.cli fetch-urls <urls.json>
    python -m cite2fn.cli assemble <input.docx> <citations.json> [-o output.docx] [--style bluebook|apa] [--format footnotes|endnotes|references]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def cmd_detect(args: list[str]) -> None:
    """Detect all citations in a document. Outputs JSON to stdout."""
    if not args:
        print("Usage: python -m cite2fn.cli detect <input.docx>", file=sys.stderr)
        sys.exit(1)

    from cite2fn.detect import detect_citations
    from cite2fn.models import citations_to_json

    doc_path = args[0]
    citations = detect_citations(doc_path)
    print(citations_to_json(citations))


def cmd_parse_references(args: list[str]) -> None:
    """Parse references section and match to citations. Outputs JSON to stdout."""
    if not args:
        print("Usage: python -m cite2fn.cli parse-references <input.docx>", file=sys.stderr)
        sys.exit(1)

    from cite2fn.references import parse_references
    from cite2fn.models import references_to_json

    doc_path = args[0]
    refs = parse_references(doc_path)
    print(references_to_json(refs))


def cmd_fetch_urls(args: list[str]) -> None:
    """Fetch metadata for a list of URLs. Input: JSON file with list of URLs.
    Outputs JSON to stdout: {url: metadata_dict}."""
    if not args:
        print("Usage: python -m cite2fn.cli fetch-urls <urls.json>", file=sys.stderr)
        sys.exit(1)

    from cite2fn.fetch import fetch_metadata_batch

    urls_path = args[0]
    with open(urls_path) as f:
        urls = json.load(f)

    results = fetch_metadata_batch(urls)
    print(json.dumps(results, indent=2, ensure_ascii=False))


def cmd_assemble(args: list[str]) -> None:
    """Assemble the final document with citations in the chosen style and format.

    Input: original .docx + citations JSON (with bluebook_text filled in).
    Output: converted .docx + report.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="cite2fn assemble")
    parser.add_argument("input_docx", help="Input .docx file")
    parser.add_argument("citations_json", help="JSON file with formatted citations")
    parser.add_argument("-o", "--output", help="Output .docx path")
    parser.add_argument("--style", default="bluebook", choices=["bluebook", "apa"],
                        help="Citation style (default: bluebook)")
    parser.add_argument("--format", default="footnotes",
                        choices=["footnotes", "endnotes", "references"],
                        dest="output_format",
                        help="Output format (default: footnotes)")
    parser.add_argument("--endnotes", action="store_true",
                        help="Use endnotes (shorthand for --format endnotes)")
    parser.add_argument("--keep-references", action="store_true",
                        help="Don't remove References section (footnotes/endnotes mode)")
    parsed = parser.parse_args(args)

    from cite2fn.assemble import assemble_document

    input_path = Path(parsed.input_docx)
    output_path = parsed.output or str(input_path.stem) + "_converted.docx"

    with open(parsed.citations_json) as f:
        citations_data = json.load(f)

    report = assemble_document(
        input_path=str(input_path),
        output_path=output_path,
        citations_data=citations_data,
        use_endnotes=parsed.endnotes,
        keep_references=parsed.keep_references,
        output_format=parsed.output_format,
        style=parsed.style,
    )

    print(json.dumps(report, indent=2, ensure_ascii=False))


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python -m cite2fn.cli <command> [args]\n"
            "Commands: detect, parse-references, fetch-urls, assemble",
            file=sys.stderr,
        )
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "detect": cmd_detect,
        "parse-references": cmd_parse_references,
        "fetch-urls": cmd_fetch_urls,
        "assemble": cmd_assemble,
    }

    if command not in commands:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)

    commands[command](args)


if __name__ == "__main__":
    main()
