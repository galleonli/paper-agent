"""
Scholar Inbox: Google Scholar Alerts via email (mbox / eml_dir / imap).

No RSS. No crawling. Scholar Inbox never consumes max_papers_per_day and never uses
bandit/exploration/diversity constraints. Ordering: arrival (email received time) only.

Implemented: mbox, eml_dir, imap.
"""

from __future__ import annotations

import hashlib
import html
import imaplib
import os
import re
from dataclasses import dataclass

import requests
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from paper_agent.core.config import Config
from paper_agent.core.models import Paper
from paper_agent.core.state import filter_unseen, load_seen, save_seen
from paper_agent.sources import arxiv as arxiv_source


SCHOLAR_NS = "scholar:"
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _extract_arxiv_id(url: str) -> str | None:
    m = re.search(r"arxiv\.org/(abs|pdf)/([^/?]+)", url, re.I)
    return m.group(2) if m else None


def _extract_doi(url: str) -> str | None:
    if "doi.org" in url:
        from urllib.parse import urlparse
        p = urlparse(url)
        doi = (p.path or "").lstrip("/").strip()
        if doi:
            return doi
    m = re.search(r"10\.\d{4,9}/\S+", url)
    if m:
        return m.group(0).rstrip(").,;")
    return None


def _normalize_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = (parsed.netloc or "").lower()
    path = parsed.path or ""
    return f"{scheme}://{netloc}{path}"


def _stable_paper_id(link: str) -> str:
    """
    Derive stable paper ID: arxiv:<id> | doi:<doi> | urlhash:<sha1(normalized)>.
    Caller will namespace as scholar:<paper_id> for Paper.id and seen.
    """
    arxiv_id = _extract_arxiv_id(link)
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    doi = _extract_doi(link)
    if doi:
        return f"doi:{doi.lower()}"
    norm = _normalize_url(link)
    h = hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]
    return f"urlhash:{h}"


def _namespaced_id(derived_id: str) -> str:
    """Namespace for seen: scholar:<paper_id>."""
    return f"{SCHOLAR_NS}{derived_id}"


def _get_received_timestamp(msg, fallback_mtime: float | None = None) -> datetime | None:
    """Email received time: Date header, else fallback (e.g. file mtime for eml_dir)."""
    date_header = msg.get("Date")
    if date_header:
        try:
            dt = parsedate_to_datetime(date_header)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError):
            pass
    if fallback_mtime is not None:
        return datetime.fromtimestamp(fallback_mtime, tz=timezone.utc)
    return None


def _get_text_body(msg) -> str:
    """Best-effort decoded body preferring text/plain, then text/html."""
    if msg.is_multipart():
        html_fallback = ""
        for part in msg.walk():
            ctype = (part.get_content_type() or "").lower()
            if ctype == "text/plain":
                raw = part.get_payload(decode=True)
                if raw:
                    return raw.decode("utf-8", errors="replace")
                return ""
            if ctype == "text/html" and not html_fallback:
                raw = part.get_payload(decode=True)
                if raw:
                    html_fallback = raw.decode("utf-8", errors="replace")
        if html_fallback:
            return html_fallback
    raw = msg.get_payload(decode=True)
    if raw:
        return raw.decode("utf-8", errors="replace")
    return ""


def _extract_items_from_body(text: str) -> list[tuple[str, str, str]]:
    """
    Extract (title, link, snippet) from body. One item per URL line.
    Title = text before URL on same line (strip " - "); snippet = rest of line or next line.
    """
    items: list[tuple[str, str, str]] = []
    # Google Scholar alerts are often HTML-only and may be one giant line.
    # Avoid treating raw HTML as plain text URL lines.
    if "<html" in text.lower() or "gse_alrt_title" in text:
        return items
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for m in _URL_RE.finditer(line):
            url = m.group(0).rstrip(".,;:)")
            before = line[: m.start()].strip().strip("-–—:")
            title = before if before and len(before) > 1 else ""
            snippet = line[m.end() :].strip() or ""
            items.append((title, url, snippet))
    return items


def _looks_like_html(text: str) -> bool:
    t = text.lower()
    return "<html" in t or "<body" in t or "gse_alrt_title" in t


def _strip_tags(value: str) -> str:
    return _HTML_TAG_RE.sub("", value or "").strip()


def _unwrap_scholar_url(link: str) -> str:
    """Prefer destination URL from scholar.google.com/scholar_url?url=... links."""
    from urllib.parse import parse_qs, urlparse, unquote

    try:
        parsed = urlparse(link)
        if "scholar.google.com" in (parsed.netloc or "") and parsed.path.startswith("/scholar_url"):
            qs = parse_qs(parsed.query)
            target = (qs.get("url") or [""])[0]
            if target:
                return unquote(target)
    except Exception:
        pass
    return link


def _extract_items_from_html(html_text: str) -> list[tuple[str, str, str]]:
    """
    Extract (title, link, snippet) from Scholar alert HTML.
    Uses title anchors with class gse_alrt_title; snippet is best-effort.
    """
    items: list[tuple[str, str, str]] = []
    if not html_text:
        return items

    # Anchor blocks in Scholar template may place href/class in any attribute order.
    anchor_re = re.compile(r"<a\b([^>]*)>(.*?)</a>", re.IGNORECASE | re.DOTALL)
    href_re = re.compile(r"""href\s*=\s*(['"])(.*?)\1""", re.IGNORECASE | re.DOTALL)
    class_re = re.compile(r"""class\s*=\s*(['"])(.*?)\1""", re.IGNORECASE | re.DOTALL)
    # Optional snippet block appears after the title block.
    snippet_re = re.compile(
        r'<div[^>]*class="gse_alrt_sni"[^>]*>(.*?)</div>',
        re.IGNORECASE | re.DOTALL,
    )

    snippet_iter = iter(snippet_re.finditer(html_text))
    next_snippet = next(snippet_iter, None)

    for m in anchor_re.finditer(html_text):
        attrs = m.group(1) or ""
        class_m = class_re.search(attrs)
        classes = (class_m.group(2) if class_m else "").lower()
        if "gse_alrt_title" not in classes:
            continue

        href_m = href_re.search(attrs)
        if not href_m:
            continue

        href_raw = html.unescape(href_m.group(2).strip())
        title_html = html.unescape(m.group(2))
        title = _strip_tags(title_html) or "Scholar Alert"
        link = _unwrap_scholar_url(href_raw)

        snippet = ""
        while next_snippet is not None and next_snippet.start() < m.end():
            next_snippet = next(snippet_iter, None)
        if next_snippet is not None:
            snippet_html = html.unescape(next_snippet.group(1))
            snippet = _strip_tags(snippet_html).replace("\xa0", " ").strip()

        if link.startswith("http"):
            items.append((title, link, snippet))
    return items


@dataclass
class _RawItem:
    """One paper-like item from an email (before stable ID and filter)."""
    title: str
    link: str
    snippet: str
    received_ts: datetime | None
    authors: list[str]  # best-effort; often empty


def _parse_message(msg, fallback_mtime: float | None = None) -> list[_RawItem]:
    """Parse one email into raw items (title, link, snippet, received_ts)."""
    received = _get_received_timestamp(msg, fallback_mtime)
    subject = (msg.get("Subject") or "").strip() or "Scholar Alert"
    body = _get_text_body(msg)
    if _looks_like_html(body):
        triples = _extract_items_from_html(body)
    else:
        triples = _extract_items_from_body(body)
    out: list[_RawItem] = []
    for title_frag, link, snippet in triples:
        title = title_frag or subject
        out.append(
            _RawItem(
                title=title,
                link=link,
                snippet=snippet,
                received_ts=received,
                authors=[],
            )
        )
    return out


def _apply_light_filter(
    items: list[_RawItem],
    light_filter,
) -> list[_RawItem]:
    """Case-insensitive: include_keywords, exclude_keywords."""
    inc = [k.lower() for k in (light_filter.include_keywords or [])]
    exc = [k.lower() for k in (light_filter.exclude_keywords or [])]

    def matches_any(text: str, patterns: list[str]) -> bool:
        t = (text or "").lower()
        return any(p in t for p in patterns)

    filtered: list[_RawItem] = []
    for it in items:
        combined = f"{it.title}\n{it.snippet}".strip()
        if inc and not matches_any(combined, inc):
            continue
        if exc and matches_any(combined, exc):
            continue
        filtered.append(it)
    return filtered


def _load_mbox(mbox_path: str) -> list[tuple[bytes, float | None]]:
    """Load messages from mbox; return list of (raw_bytes, mtime_or_None)."""
    path = Path(mbox_path)
    if not path.is_file():
        return []
    import mailbox
    out: list[tuple[bytes, float | None]] = []
    try:
        mbox = mailbox.mbox(str(path))
        for msg in mbox:
            out.append((msg.as_bytes(), None))
        mbox.close()
    except (OSError, AttributeError):
        pass
    return out


def _load_eml_dir(eml_dir: str) -> list[tuple[bytes, float | None]]:
    """Load .eml files from directory; return list of (raw_bytes, file_mtime)."""
    path = Path(eml_dir)
    if not path.is_dir():
        return []
    out: list[tuple[bytes, float | None]] = []
    for f in path.glob("*.eml"):
        try:
            raw = f.read_bytes()
            mtime = f.stat().st_mtime
            out.append((raw, mtime))
        except OSError:
            continue
    # Sort by mtime descending (newest first) so ordering is consistent
    out.sort(key=lambda x: x[1] or 0, reverse=True)
    return out


def _parse_internaldate_to_ts(meta: bytes) -> float | None:
    """
    Parse IMAP INTERNALDATE from fetch metadata bytes.
    Example: b'1 (RFC822 {1234} INTERNALDATE "06-Mar-2026 10:00:00 +0000")'
    """
    try:
        text = meta.decode("utf-8", errors="replace")
        m = re.search(r'INTERNALDATE\s+"([^"]+)"', text)
        if not m:
            return None
        dt = datetime.strptime(m.group(1), "%d-%b-%Y %H:%M:%S %z")
        return dt.timestamp()
    except (ValueError, OSError):
        return None


def _imap_select_mailbox(conn: imaplib.IMAP4_SSL, provider: str, gmail_label: str) -> bool:
    """
    Select mailbox/label.
    For Gmail/IMAP we prefer configured label when provided; otherwise INBOX.
    """
    mailbox = "INBOX"
    if provider in ("imap", "gmail") and gmail_label:
        mailbox = gmail_label
    status, _ = conn.select(mailbox)
    if status == "OK":
        return True
    if mailbox != "INBOX":
        status, _ = conn.select("INBOX")
        if status == "OK":
            return True
    return False


def _fetch_imap_gmail(config: Config) -> list[tuple[bytes, float | None]]:
    """
    Fetch emails via IMAP using credentials from config + env var.
    Returns list of (raw_bytes, internaldate_ts_or_none).
    """
    sa = config.sources.scholar_alerts
    email_cfg = sa.email
    provider = (email_cfg.provider or "").lower()

    host = (email_cfg.imap_host or "").strip()
    user = (email_cfg.imap_user or "").strip()
    pw_env = (email_cfg.imap_password_env or "").strip()
    password = os.getenv(pw_env) if pw_env else None
    if not host or not user or not password:
        return []

    messages: list[tuple[bytes, float | None]] = []
    conn: imaplib.IMAP4_SSL | None = None
    try:
        conn = imaplib.IMAP4_SSL(host)
        conn.login(user, password)
        if not _imap_select_mailbox(conn, provider, email_cfg.gmail_label):
            return []

        status, search_data = conn.search(None, "ALL")
        if status != "OK" or not search_data or not search_data[0]:
            return []
        msg_ids = [x for x in search_data[0].split() if x]

        # Fetch newest first from server order to reduce work before max_items_per_run.
        limit = max(1, int(sa.max_items_per_run))
        for msg_id in reversed(msg_ids):
            status, fetch_data = conn.fetch(msg_id, "(RFC822 INTERNALDATE)")
            if status != "OK" or not fetch_data:
                continue
            for part in fetch_data:
                if (
                    isinstance(part, tuple)
                    and len(part) == 2
                    and isinstance(part[0], (bytes, bytearray))
                    and isinstance(part[1], (bytes, bytearray))
                ):
                    ts = _parse_internaldate_to_ts(bytes(part[0]))
                    messages.append((bytes(part[1]), ts))
                    break
            if len(messages) >= limit:
                break
    except (imaplib.IMAP4.error, OSError):
        return []
    finally:
        if conn is not None:
            try:
                conn.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
    return messages


def _raw_items_from_source(config: Config) -> list[_RawItem]:
    """Load emails from configured provider and return flat list of raw items."""
    sa = config.sources.scholar_alerts
    email_cfg = sa.email
    provider = (email_cfg.provider or "").lower()
    messages: list[tuple[bytes, float | None]] = []

    if provider == "mbox":
        if email_cfg.mbox_path:
            messages = _load_mbox(email_cfg.mbox_path)
    elif provider == "eml_dir":
        if email_cfg.eml_dir:
            messages = _load_eml_dir(email_cfg.eml_dir)
    elif provider in ("imap", "gmail"):
        messages = _fetch_imap_gmail(config)

    parser = BytesParser(policy=policy.default)
    all_items: list[_RawItem] = []
    for raw, mtime in messages:
        try:
            msg = parser.parsebytes(raw)
        except Exception:
            continue
        if email_cfg.from_addresses:
            from_addr = (msg.get("From") or "").lower()
            if not any(addr.lower() in from_addr for addr in email_cfg.from_addresses):
                continue
        all_items.extend(_parse_message(msg, mtime))
    return all_items


def _fetch_title_abstract_from_url(
    url: str,
    timeout_seconds: int = 5,
) -> tuple[str | None, str | None]:
    """
    Best-effort fetch of page title and abstract (meta description or og:description).
    Returns (title, abstract) or (None, None) on any failure; never raises.
    """
    if not (url or "").strip().startswith("http"):
        return (None, None)
    try:
        resp = requests.get(
            url.strip(),
            timeout=timeout_seconds,
            headers={"User-Agent": "PaperAgent/1.0 (paper inbox)"},
        )
        resp.raise_for_status()
        text = resp.text or ""
    except Exception:
        return (None, None)
    title: str | None = None
    abstract: str | None = None
    title_m = re.search(r"<title[^>]*>([^<]+)</title>", text, re.I | re.DOTALL)
    if title_m:
        title = html.unescape(title_m.group(1)).strip()
        if title:
            title = title[:2000]
    desc_m = re.search(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]+content=["\']([^"\']+)["\']',
        text,
        re.I,
    )
    if not desc_m:
        desc_m = re.search(
            r'content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\'](?:description|og:description)["\']',
            text,
            re.I,
        )
    if desc_m:
        abstract = html.unescape(desc_m.group(1)).strip()
        if abstract:
            abstract = abstract[:5000]
    return (title, abstract)


def fetch(now: datetime, lookback_days: int, config: Config) -> list[Paper]:
    """
    Fetch papers from Scholar Alerts email (mbox or eml_dir).
    Returns only unseen papers; updates shared state/seen.json with scholar:<paper_id>.
    """
    if not getattr(config.sources.scholar_alerts, "enabled", False):
        return []
    if getattr(config.sources.scholar_alerts, "mode", "").lower() != "email":
        return []

    sa = config.sources.scholar_alerts
    email_cfg = sa.email
    provider = (email_cfg.provider or "").lower()
    if provider not in ("mbox", "eml_dir", "imap", "gmail"):
        return []

    raw_items = _raw_items_from_source(config)
    if not raw_items:
        return []

    cutoff = now.astimezone(timezone.utc) - timedelta(days=lookback_days)
    raw_items = [it for it in raw_items if (it.received_ts or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]
    raw_items = _apply_light_filter(raw_items, sa.light_filter)
    # Order by received desc (newest first); within same ts preserve list order
    raw_items.sort(key=lambda it: it.received_ts or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    raw_items = raw_items[: sa.max_items_per_run]

    # Build Papers with namespaced IDs; enrich from arXiv or generic fetch when possible; never crash
    papers: list[Paper] = []
    for it in raw_items:
        derived = _stable_paper_id(it.link)
        paper_id = _namespaced_id(derived)
        updated_iso = (
            it.received_ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if it.received_ts
            else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        title = it.title or "Scholar Alert"
        summary = it.snippet
        authors = it.authors
        categories: list[str] = []
        link_pdf = None

        arxiv_id = _extract_arxiv_id(it.link)
        if arxiv_id:
            try:
                full = arxiv_source.fetch_arxiv_by_id(arxiv_id)
                if full is not None:
                    title = full.title
                    summary = full.summary or it.snippet
                    authors = full.authors or authors
                    categories = full.categories or []
                    updated_iso = full.updated or updated_iso
                    link_pdf = full.link_pdf
            except Exception:
                pass  # keep snippet; do not block

        if not summary or summary == it.snippet:
            try:
                fetched_title, fetched_abstract = _fetch_title_abstract_from_url(it.link)
                if fetched_abstract:
                    summary = fetched_abstract
                if fetched_title and (not title or title == "Scholar Alert"):
                    title = fetched_title
            except Exception:
                pass

        papers.append(
            Paper(
                id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                updated=updated_iso,
                link_abs=it.link,
                link_pdf=link_pdf,
            )
        )

    state_dir = config.delivery.state_dir
    paper_ids = [p.id for p in papers]
    unseen_ids, seen_cache = filter_unseen(state_dir, paper_ids)
    if not unseen_ids:
        return []
    unseen_set = set(unseen_ids)
    result = [p for p in papers if p.id in unseen_set]
    save_seen(state_dir, seen_cache)
    return result


# Export for tests
def parse_eml_extract_items(eml_bytes: bytes, fallback_mtime: float | None = None) -> list[tuple[str, datetime | None, str, str]]:
    """
    Parse one .eml message; return list of (paper_id, received_ts, title, link).
    paper_id is namespaced (scholar:arxiv:... etc.).
    """
    parser = BytesParser(policy=policy.default)
    msg = parser.parsebytes(eml_bytes)
    items = _parse_message(msg, fallback_mtime)
    out: list[tuple[str, datetime | None, str, str]] = []
    for it in items:
        derived = _stable_paper_id(it.link)
        pid = _namespaced_id(derived)
        out.append((pid, it.received_ts, it.title or "Scholar Alert", it.link))
    return out


def parse_mbox_extract_items(mbox_path: str) -> list[tuple[str, datetime | None, str, str]]:
    """
    Parse mbox file; return list of (paper_id, received_ts, title, link) for all items.
    """
    all_out: list[tuple[str, datetime | None, str, str]] = []
    for raw, _ in _load_mbox(mbox_path):
        all_out.extend(parse_eml_extract_items(raw, None))
    return all_out


__all__ = ["fetch", "parse_eml_extract_items", "parse_mbox_extract_items", "SCHOLAR_NS", "_stable_paper_id", "_namespaced_id"]
