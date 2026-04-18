# cite2fn (core library)

The citation-conversion engine for the `cite2fn-web` project. Detects hyperlinked, parenthetical, and inline author-date citations in a `.docx`, fetches bibliographic metadata from URLs, and assembles a new document with the citations rendered as Bluebook or APA footnotes, endnotes, or a list of references.

This package is web-framework agnostic — the `api/` service imports it directly, and it can also be installed and run as a standalone CLI for local debugging.

## Install

```bash
pip install -e .
```

`pymupdf` is a required dependency (used to extract metadata from PDF sources) — it ships automatically.

## CLI (local debugging)

```bash
# Detect citations
python -m cite2fn.cli detect paper.docx

# Parse the References section
python -m cite2fn.cli parse-references paper.docx

# Fetch metadata for a list of URLs
python -m cite2fn.cli fetch-urls urls.json

# Assemble the final document
python -m cite2fn.cli assemble paper.docx citations.json \
    -o paper_converted.docx \
    --style bluebook \
    --format footnotes
```

The CLI is a thin wrapper around the library — see `cite2fn/cli.py`. The `api/` service calls the same functions directly without shelling out.

## Tests

```bash
pip install -e '.[dev]'
pytest
```

The smoke tests in `tests/test_smoke.py` verify imports and public entry points. Real-document tests live alongside the `api/` layer with committed `.docx` fixtures.

## Module layout

| File | Purpose |
| --- | --- |
| `detect.py` | Find all citations in a `.docx` (hyperlinks, parentheticals, inline author-date, existing footnotes) |
| `references.py` | Parse a References/Bibliography section and match entries to citations |
| `fetch.py` | HTTP fetch + HTML/PDF metadata extraction, URL canonicalization (strips EZproxy etc.) |
| `apa.py` | APA 7th edition rendering helpers |
| `footnotes.py` | Render runs with italic / small caps markers; insert footnotes and endnotes |
| `supra.py` | Apply Bluebook *supra* and *Id.* short forms |
| `cleanup.py` | Remove redundant inline citations after footnotes are inserted |
| `comments.py` | Attach Word comments for low-confidence citations |
| `assemble.py` | Orchestrate the full pipeline: detect → format → insert → clean up |
| `references_list.py` | Build an alphabetical reference list appended to the document |
| `docx_io.py`, `models.py` | Low-level `.docx` I/O and data classes |
| `cli.py` | JSON-I/O CLI entry points |
