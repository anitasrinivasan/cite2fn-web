"""APA 7th edition citation formatter.

Formats citation metadata into APA-style reference strings using the same
*italic* marker convention as the Bluebook formatter, so that the same
Word-rendering pipeline (add_formatted_runs) can handle both styles.
"""

from __future__ import annotations


def format_apa(citation: dict) -> str:
    """Format a citation dict into an APA 7th edition reference string.

    Args:
        citation: Dict with keys like authors, title, journal, year,
                  volume, issue, first_page, last_page, doi, url, publisher.

    Returns:
        APA-formatted string with *italic* markers for Word rendering.
    """
    authors = citation.get("authors") or []
    year = citation.get("year", "n.d.")
    title = citation.get("title", "")
    journal = citation.get("journal", "")
    volume = citation.get("volume", "")
    issue = citation.get("issue", "")
    first_page = citation.get("first_page", "")
    last_page = citation.get("last_page", "")
    doi = citation.get("doi", "")
    url = citation.get("canonical_url") or citation.get("url", "")
    publisher = citation.get("publisher", "")

    parts: list[str] = []

    # --- Authors ---
    author_str = _format_apa_authors(authors)
    if author_str:
        parts.append(author_str)

    # --- Year ---
    parts.append(f"({year}).")

    # --- Title & source ---
    if journal:
        # Journal article: Title not italicized, journal italicized
        if title:
            t = _ensure_sentence_case(title)
            parts.append(f"{t}.")
        journal_part = f"*{journal}*"
        if volume:
            journal_part += f", *{volume}*"
            if issue:
                journal_part += f"({issue})"
        if first_page:
            pages = first_page
            if last_page:
                pages += f"\u2013{last_page}"
            journal_part += f", {pages}"
        journal_part += "."
        parts.append(journal_part)
    elif publisher:
        # Book: Title italicized
        if title:
            t = _ensure_sentence_case(title)
            parts.append(f"*{t}*.")
        parts.append(f"{publisher}.")
    else:
        # Web source / other: Title italicized
        if title:
            t = _ensure_sentence_case(title)
            parts.append(f"*{t}*.")

    # --- DOI or URL ---
    if doi:
        doi_url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
        parts.append(doi_url)
    elif url:
        parts.append(url)

    return " ".join(parts)


def _format_apa_authors(authors: list[str]) -> str:
    """Format author list in APA style: Last, F. M., & Last, F. M."""
    if not authors:
        return ""

    formatted = []
    for author in authors[:20]:  # APA 7th: list up to 20 authors
        formatted.append(_invert_author(author))

    if len(formatted) == 1:
        return formatted[0]
    elif len(formatted) == 2:
        return f"{formatted[0]}, & {formatted[1]}"
    else:
        return ", ".join(formatted[:-1]) + ", & " + formatted[-1]


def _invert_author(name: str) -> str:
    """Convert 'First M. Last' to 'Last, F. M.' for APA.

    If the name is already inverted (contains comma), return as-is.
    """
    name = name.strip()
    if "," in name:
        return name  # already inverted

    parts = name.split()
    if len(parts) == 1:
        return parts[0]

    last = parts[-1]
    initials = " ".join(
        f"{p[0]}." if not p.endswith(".") else p
        for p in parts[:-1]
    )
    return f"{last}, {initials}"


def _ensure_sentence_case(title: str) -> str:
    """Convert title to APA sentence case (capitalize first word only).

    Preserves: proper nouns that are already capitalized in the middle
    of the title, acronyms, and words after colons.
    """
    if not title:
        return title

    # Don't modify if it's already mostly lowercase (likely already sentence case)
    words = title.split()
    upper_count = sum(1 for w in words[1:] if w[0].isupper()) if len(words) > 1 else 0

    # If fewer than half the non-first words are capitalized, leave as-is
    if len(words) > 1 and upper_count < len(words[1:]) / 2:
        return title

    # Convert to sentence case
    result = []
    capitalize_next = True
    for word in words:
        if capitalize_next:
            result.append(word)  # keep original capitalization for first word / after colon
            capitalize_next = False
        elif word.isupper() and len(word) > 1:
            result.append(word)  # preserve acronyms (AI, LLM, etc.)
        else:
            result.append(word.lower())

        if word.endswith(":"):
            capitalize_next = True

    return " ".join(result)
