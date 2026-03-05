"""
arXiv fetcher via Atom API.
Queries by category; parses entries to common Paper model.
Respects rate limits (see Safety in README); use max_results and delay as configured.
"""

import re
import time
from urllib.parse import urlencode

import requests
from xml.etree import ElementTree as ET

from paper_agent.core.models import Paper


ARXiv_API_BASE = "https://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"
ARXIV_NS = "http://arxiv.org/schemas/atom"


def _extract_text(el: ET.Element | None, default: str = "") -> str:
    if el is not None and el.text:
        return (el.text or "").strip()
    if el is not None and len(el):
        return (el[0].text or "").strip()
    return default


def _extract_id_from_abs_url(url: str) -> str:
    """Extract arXiv ID from abstract URL (e.g. http://arxiv.org/abs/2301.12345)."""
    m = re.search(r"arxiv\.org/abs/([^/?]+)", url, re.I)
    return m.group(1) if m else url


def _parse_entry(entry: ET.Element) -> Paper | None:
    """Parse one Atom <entry> into Paper. Returns None if required fields missing."""
    ns = {"atom": ATOM_NS, "arxiv": ARXIV_NS}
    id_el = entry.find("atom:id", ns)
    if id_el is None or not id_el.text:
        return None
    link_abs = id_el.text.strip()
    paper_id = _extract_id_from_abs_url(link_abs)

    title_el = entry.find("atom:title", ns)
    title = _extract_text(title_el, "").replace("\n", " ").strip()
    if not title:
        return None

    summary_el = entry.find("atom:summary", ns)
    summary = _extract_text(summary_el, "").replace("\n", " ").strip()

    authors = []
    for author in entry.findall("atom:author", ns):
        name_el = author.find("atom:name", ns)
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    categories = []
    for cat in entry.findall("atom:category", ns):
        term = cat.get("term")
        if term and "arxiv.org" in (cat.get("scheme") or ""):
            categories.append(term)

    updated_el = entry.find("atom:updated", ns)
    updated = _extract_text(updated_el, "")

    link_pdf = None
    for link in entry.findall("atom:link", ns):
        if link.get("title") == "pdf" or (
            link.get("type") == "application/pdf" and link.get("href")
        ):
            link_pdf = link.get("href", "").strip()
            break

    return Paper(
        id=paper_id,
        title=title,
        summary=summary,
        authors=authors,
        categories=categories,
        updated=updated,
        link_abs=link_abs,
        link_pdf=link_pdf,
    )


def _build_search_query(allow_categories: list[str], deny_categories: list[str]) -> str:
    """Build arXiv search_query from allow/deny categories. cat:cs.LG OR cat:cs.CL etc."""
    if not allow_categories:
        return "all:all"  # No category filter
    cat_terms = [f"cat:{c.strip()}" for c in allow_categories if c.strip()]
    if not cat_terms:
        return "all:all"
    query = " OR ".join(cat_terms)
    if deny_categories:
        deny_terms = [f"ANDNOT cat:{c.strip()}" for c in deny_categories if c.strip()]
        query = query + " " + " ".join(deny_terms)
    return query


def _fetch_one_query(
    search_query: str,
    max_results: int,
    page_size: int,
    timeout_seconds: int,
) -> list[Paper]:
    """Fetch papers for a single search_query; returns up to max_results."""
    papers: list[Paper] = []
    start = 0
    while start < max_results:
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXiv_API_BASE}?{urlencode(params)}"
        try:
            resp = requests.get(url, timeout=timeout_seconds)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"arXiv API request failed: {e}") from e

        root = ET.fromstring(resp.content)
        ns = {"atom": ATOM_NS}
        entries = root.findall("atom:entry", ns)
        if not entries:
            break

        for entry in entries:
            paper = _parse_entry(entry)
            if paper and len(papers) < max_results:
                papers.append(paper)
        if len(entries) < page_size:
            break
        start += page_size

    return papers[:max_results]


def fetch_arxiv(
    allow_categories: list[str],
    deny_categories: list[str] | None = None,
    queries: list[str] | None = None,
    max_results: int = 100,
    timeout_seconds: int = 30,
    delay_between_requests_seconds: float = 3.0,
) -> list[Paper]:
    """
    Fetch papers from arXiv Atom API.
    If queries is non-empty, runs one search per query (combined with categories), merges and
    dedupes by paper id, then returns up to max_results. Otherwise uses category-only search.
    """
    deny_categories = deny_categories or []
    category_part = _build_search_query(allow_categories, deny_categories)
    page_size = min(max_results, 500)

    if queries:
        # Semantic queries: (user_query) AND (categories); merge results and dedupe by id
        seen_ids: set[str] = set()
        papers: list[Paper] = []
        per_query = max(10, max_results // len(queries))
        for i, q in enumerate(queries):
            q = (q or "").strip()
            if not q:
                continue
            combined = f"({q}) AND ({category_part})" if category_part != "all:all" else q
            batch = _fetch_one_query(
                combined, per_query, page_size, timeout_seconds
            )
            for p in batch:
                if p.id not in seen_ids:
                    seen_ids.add(p.id)
                    papers.append(p)
                    if len(papers) >= max_results:
                        break
            if len(papers) >= max_results:
                break
            if i < len(queries) - 1:
                time.sleep(delay_between_requests_seconds)
        return papers[:max_results]

    # Category-only (legacy): single search
    search_query = category_part
    papers = []
    start = 0
    while start < max_results:
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"{ARXiv_API_BASE}?{urlencode(params)}"
        try:
            resp = requests.get(url, timeout=timeout_seconds)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"arXiv API request failed: {e}") from e

        root = ET.fromstring(resp.content)
        ns = {"atom": ATOM_NS}
        entries = root.findall("atom:entry", ns)
        if not entries:
            break

        for entry in entries:
            paper = _parse_entry(entry)
            if paper and len(papers) < max_results:
                papers.append(paper)
        if len(entries) < page_size:
            break
        start += page_size
        if start < max_results:
            time.sleep(delay_between_requests_seconds)

    return papers[:max_results]
