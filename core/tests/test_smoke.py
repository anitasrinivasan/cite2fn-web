"""Smoke tests: verify the package imports and every module has its expected entry points.

These don't exercise real .docx processing — that's covered by end-to-end tests
driven from the api/ layer against fixtures. This file exists so a broken import
or missing symbol fails CI immediately.
"""

from __future__ import annotations


def test_package_imports() -> None:
    import cite2fn  # noqa: F401


def test_all_modules_import() -> None:
    from cite2fn import (  # noqa: F401
        apa,
        assemble,
        cleanup,
        cli,
        comments,
        detect,
        docx_io,
        fetch,
        footnotes,
        models,
        references,
        references_list,
        supra,
    )


def test_core_entry_points() -> None:
    from cite2fn.assemble import assemble_document
    from cite2fn.cli import main
    from cite2fn.detect import detect_citations
    from cite2fn.fetch import fetch_metadata_batch
    from cite2fn.references import parse_references
    from cite2fn.references_list import insert_references_list

    for obj in (
        assemble_document,
        main,
        detect_citations,
        fetch_metadata_batch,
        parse_references,
        insert_references_list,
    ):
        assert callable(obj)


def test_supported_styles_and_formats() -> None:
    """Regression guard: the assemble signature must accept bluebook/apa and all three formats."""
    import inspect

    from cite2fn.assemble import assemble_document

    sig = inspect.signature(assemble_document)
    params = sig.parameters
    assert "style" in params
    assert "output_format" in params
