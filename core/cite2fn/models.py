"""Data models for cite2fn."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Literal


CitationType = Literal[
    "hyperlink_external",
    "hyperlink_internal",
    "parenthetical",
    "inline_author_date",
    "existing_footnote",
]

Confidence = Literal["confident", "needs_review"]


@dataclass
class Citation:
    """A detected citation in the document."""

    id: str
    type: CitationType
    display_text: str
    paragraph_index: int
    surrounding_sentence: str

    # Source information (at least one should be populated)
    url: str | None = None
    internal_anchor: str | None = None
    matched_reference: str | None = None

    # Parsed components
    author_name: str | None = None
    year: str | None = None

    # Position in paragraph (for cleanup/footnote insertion)
    run_indices: list[int] = field(default_factory=list)
    # For hyperlinks: the hyperlink element index within the paragraph
    hyperlink_index: int | None = None

    # Enrichment (filled later)
    fetched_metadata: dict | None = None
    bluebook_text: str | None = None
    confidence: Confidence | None = None
    cleanup_rule: int | None = None

    # For existing footnotes
    existing_footnote_id: int | None = None

    # Signal word preceding the citation (e.g. "See", "Cf.")
    signal_word: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Citation:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Reference:
    """A parsed entry from the References/Bibliography section."""

    full_text: str
    paragraph_index: int
    authors: list[str] = field(default_factory=list)
    year: str | None = None
    title: str | None = None
    # Bookmark anchors that point to this reference
    anchors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Reference:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class CitationLedger:
    """Tracks which sources have been cited and in which footnote,
    for supra/id. short-form handling."""

    # normalized_source_key -> first footnote number
    first_occurrence: dict[str, int] = field(default_factory=dict)
    # ordered list of (footnote_number, [source_keys]) for id. detection
    footnote_sources: list[tuple[int, list[str]]] = field(default_factory=list)


def citations_to_json(citations: list[Citation]) -> str:
    return json.dumps([c.to_dict() for c in citations], indent=2, ensure_ascii=False)


def citations_from_json(s: str) -> list[Citation]:
    return [Citation.from_dict(d) for d in json.loads(s)]


def references_to_json(refs: list[Reference]) -> str:
    return json.dumps([r.to_dict() for r in refs], indent=2, ensure_ascii=False)
