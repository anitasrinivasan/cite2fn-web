"""URL fetching and metadata extraction for academic sources.

Fetches URLs and extracts bibliographic metadata from HTML meta tags,
OpenGraph tags, and structured data.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx
from bs4 import BeautifulSoup


# Domains that should be skipped (internal document links, not real URLs)
SKIP_DOMAINS = {"docs.google.com"}

# Known academic repositories with special handling
ARXIV_DOMAINS = {"arxiv.org"}
DOI_DOMAINS = {"doi.org", "dx.doi.org"}
SSRN_DOMAINS = {"ssrn.com", "papers.ssrn.com"}

# User agents: custom first, browser-like fallback for 403s
USER_AGENT = "cite2footnote/0.1 (academic citation tool; +https://github.com/anitasrinivasan/cite2fn)"
BROWSER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def fetch_metadata_batch(
    urls: list[str],
    timeout: float = 10.0,
    delay: float = 0.5,
) -> dict[str, dict]:
    """Fetch metadata for a batch of URLs.

    Returns {url: metadata_dict} where metadata_dict contains:
    - title, authors, journal, year, volume, pages, doi, abstract
    - fetch_error: str if fetch failed

    Deduplicates URLs before fetching. Adds delay between requests.
    """
    # Deduplicate
    unique_urls = list(dict.fromkeys(urls))
    results: dict[str, dict] = {}

    for i, url in enumerate(unique_urls):
        if _should_skip(url):
            results[url] = {"fetch_error": "Skipped (invalid or internal link)"}
            continue

        normalized = _normalize_url(url)

        try:
            metadata = _fetch_single(normalized, timeout)
            # Record the normalization chain
            if normalized != url:
                metadata["normalized_from"] = url
        except Exception as e:
            metadata = {"fetch_error": str(e)}

        results[url] = metadata

        # Rate limiting
        if i < len(unique_urls) - 1:
            time.sleep(delay)

    return results


def _should_skip(url: str) -> bool:
    """Check if a URL should be skipped."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # No TLD = not a real URL (e.g. "http://bhatnagar")
    if "." not in domain:
        return True

    return any(skip in domain for skip in SKIP_DOMAINS)


# Regex for EZproxy-style library proxy URLs
# Pattern: real-host-with-hyphens.libproxy.INSTITUTION.edu
_PROXY_RE = re.compile(
    r"^(https?)://([\w-]+(?:-[\w-]+)+)\."  # mangled hostname
    r"libproxy\.[\w.-]+/"                   # proxy domain
    r"(.*)",                                # path
)

# Query parameters that are session-specific and should be stripped
_EPHEMERAL_PARAMS = frozenset({
    "casa_token", "token", "needAccess",
    "fr", "rr", "ref", "pdf_download",
})


def _normalize_url(url: str) -> str:
    """Normalize a URL to its canonical, permanent form.

    Applied *before* fetching. Handles:
    - Library proxy rewrites (EZproxy)
    - Ephemeral query parameters
    - arXiv html/pdf → abs conversion
    """
    url = _strip_proxy(url)
    url = _strip_ephemeral_params(url)
    url = _normalize_arxiv(url)
    return url


def _strip_proxy(url: str) -> str:
    """Remove EZproxy library-proxy wrappers.

    journals-sagepub-com.libproxy.berkeley.edu/doi/X
    → journals.sagepub.com/doi/X

    www-tandfonline-com.libproxy.berkeley.edu/doi/pdf/X
    → www.tandfonline.com/doi/pdf/X
    """
    m = _PROXY_RE.match(url)
    if not m:
        return url
    scheme, mangled_host, path = m.groups()
    real_host = mangled_host.replace("-", ".")
    return f"{scheme}://{real_host}/{path}"


def _strip_ephemeral_params(url: str) -> str:
    """Remove session tokens, access flags, and referrer params."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    params = parse_qs(parsed.query, keep_blank_values=True)
    cleaned = {k: v for k, v in params.items()
               if k not in _EPHEMERAL_PARAMS}
    if len(cleaned) == len(params):
        return url  # nothing removed
    new_query = urlencode(cleaned, doseq=True)
    return urlunparse(parsed._replace(query=new_query, fragment=""))


def _normalize_arxiv(url: str) -> str:
    """Convert arXiv html/pdf URLs to abs URLs for richer metadata."""
    m = re.search(r"arxiv\.org/(?:html|pdf)/(\d+\.\d+(?:v\d+)?)", url)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    return url


def _fetch_single(url: str, timeout: float) -> dict:
    """Fetch a single URL and extract metadata.

    Tries the custom user-agent first. On 403, retries with a browser-like
    user-agent. For PDF responses, attempts basic metadata extraction.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        resp = client.get(url, headers=headers)

        # Retry with browser UA on 403
        if resp.status_code == 403:
            headers["User-Agent"] = BROWSER_USER_AGENT
            resp = client.get(url, headers=headers)

        resp.raise_for_status()

    content_type = resp.headers.get("content-type", "")

    # Handle PDF responses
    if "pdf" in content_type:
        meta = _extract_pdf_metadata(resp.content, url)
        # Use redirect target as canonical if available
        if resp.url != url:
            meta["canonical_url"] = str(resp.url)
        return meta

    if "html" not in content_type and "xml" not in content_type:
        return {"fetch_error": f"Non-HTML content type: {content_type}", "url": url}

    soup = BeautifulSoup(resp.text, "html.parser")
    metadata: dict = {"url": url}

    # 1. Try Highwire Press citation meta tags (used by most academic sites)
    _extract_highwire(soup, metadata)

    # 2. Try Dublin Core meta tags
    _extract_dublin_core(soup, metadata)

    # 3. Try OpenGraph tags
    _extract_opengraph(soup, metadata)

    # 4. Resolve canonical URL
    metadata["canonical_url"] = _extract_canonical_url(
        soup, str(resp.url), url
    )

    # 5. Fallback to <title>
    if "title" not in metadata or not metadata["title"]:
        title_tag = soup.find("title")
        if title_tag:
            metadata["title"] = title_tag.get_text(strip=True)

    return metadata


def _extract_canonical_url(
    soup: BeautifulSoup,
    resp_url: str,
    original_url: str,
) -> str:
    """Determine the stable, canonical URL for a fetched page.

    Checks three signals in priority order:
    1. <link rel="canonical"> — set by the publisher, most reliable.
    2. DOI from citation_doi meta tag — reconstructed as https://doi.org/...
    3. Final URL after redirects (resp.url) — if different from input.

    Falls back to the (already-normalized) original_url.
    """
    # 1. <link rel="canonical">
    canon_tag = soup.find("link", rel="canonical")
    if canon_tag and canon_tag.get("href"):
        href = canon_tag["href"]
        if href.startswith("http"):
            return href

    # 2. DOI → doi.org
    doi_tag = soup.find("meta", attrs={"name": "citation_doi"})
    if doi_tag and doi_tag.get("content"):
        doi = doi_tag["content"]
        if not doi.startswith("http"):
            return f"https://doi.org/{doi}"
        return doi

    # 3. Redirect target
    if resp_url and resp_url != original_url:
        return resp_url

    return original_url


def _extract_pdf_metadata(content: bytes, url: str) -> dict:
    """Extract metadata from a PDF document.

    Uses pymupdf (PyMuPDF) if available, otherwise returns a minimal
    result with the URL and a note that PDF parsing is not installed.
    """
    metadata: dict = {"url": url}
    try:
        import pymupdf  # noqa: F811

        doc = pymupdf.open(stream=content, filetype="pdf")
        pdf_meta = doc.metadata
        if pdf_meta.get("title"):
            metadata["title"] = pdf_meta["title"]
        if pdf_meta.get("author"):
            metadata["authors"] = [a.strip() for a in pdf_meta["author"].split(",") if a.strip()]
        if pdf_meta.get("creationDate"):
            year_match = re.search(r"(\d{4})", pdf_meta["creationDate"])
            if year_match:
                metadata["year"] = year_match.group(1)
        if pdf_meta.get("subject"):
            metadata["abstract"] = pdf_meta["subject"]
        doc.close()

        if len(metadata) == 1:  # only url
            metadata["fetch_warning"] = "PDF fetched but contained no embedded metadata"
    except ImportError:
        metadata["fetch_warning"] = "PDF source detected but pymupdf is not installed (pip install pymupdf)"

    return metadata


def _extract_highwire(soup: BeautifulSoup, metadata: dict) -> None:
    """Extract Highwire Press citation meta tags."""
    tag_map = {
        "citation_title": "title",
        "citation_journal_title": "journal",
        "citation_date": "date",
        "citation_year": "year",
        "citation_volume": "volume",
        "citation_issue": "issue",
        "citation_firstpage": "first_page",
        "citation_lastpage": "last_page",
        "citation_doi": "doi",
        "citation_pdf_url": "pdf_url",
        "citation_abstract": "abstract",
        "citation_publisher": "publisher",
    }

    for meta_name, field in tag_map.items():
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            metadata[field] = tag["content"]

    # Authors (can be multiple tags)
    authors = []
    for tag in soup.find_all("meta", attrs={"name": "citation_author"}):
        if tag.get("content"):
            authors.append(tag["content"])
    if authors:
        metadata["authors"] = authors

    # Extract year from date if not directly available
    if "year" not in metadata and "date" in metadata:
        year_match = re.search(r"(\d{4})", metadata["date"])
        if year_match:
            metadata["year"] = year_match.group(1)


def _extract_dublin_core(soup: BeautifulSoup, metadata: dict) -> None:
    """Extract Dublin Core meta tags."""
    dc_map = {
        "DC.title": "title",
        "DC.creator": "authors",
        "DC.date": "date",
        "DC.publisher": "publisher",
        "DC.identifier": "doi",
    }

    for meta_name, field in dc_map.items():
        if field in metadata:
            continue
        tag = soup.find("meta", attrs={"name": meta_name})
        if tag and tag.get("content"):
            value = tag["content"]
            if field == "authors":
                metadata[field] = [value]
            else:
                metadata[field] = value


def _extract_opengraph(soup: BeautifulSoup, metadata: dict) -> None:
    """Extract OpenGraph meta tags as fallback."""
    og_map = {
        "og:title": "title",
        "og:description": "abstract",
        "og:site_name": "journal",
    }

    for og_prop, field in og_map.items():
        if field in metadata:
            continue
        tag = soup.find("meta", attrs={"property": og_prop})
        if tag and tag.get("content"):
            metadata[field] = tag["content"]
