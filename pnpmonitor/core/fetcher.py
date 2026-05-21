"""Fetch recent publication listings from pnp.ligo.org."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

PNP_ROOT = "https://pnp.ligo.org"

# Ordered list of URLs to try for the publications listing
_PUB_URLS = [
    f"{PNP_ROOT}/publications",
    f"{PNP_ROOT}/publication",
    f"{PNP_ROOT}/node?type=publication",
]

# Drupal document-number pattern: P-, G-, T-, D-, E-, etc. followed by digits
_DOCNUM_RE = re.compile(r"\b[PGTDECL]-?\d{6,7}(?:-v\d+)?\b", re.I)
_AUTHOR_CLASS_RE = re.compile(r"author", re.I)


@dataclass
class Publication:
    title: str
    url: str
    doc_number: str = ""
    date: str = ""
    authors: list[str] = field(default_factory=list)


def _format_authors(authors: list[str]) -> str:
    if not authors:
        return ""
    if len(authors) <= 4:
        return ", ".join(authors)
    return f"{authors[0]}, {authors[1]}, et al."


def _split_author_string(text: str) -> list[str]:
    """Split a comma-or-semicolon-delimited author string.

    Handles both 'Firstname Lastname' (split on comma) and
    'Lastname, Firstname' formats (commas are both separators and
    name-internal).  Semicolons are always treated as separators.
    """
    if ";" in text:
        return [n.strip() for n in text.split(";") if n.strip()]

    # Detect 'Lastname, Firstname' by checking whether tokens after commas
    # look like initials or first names (≤ 15 chars, no comma of their own).
    # If ALL post-comma tokens fit that pattern we treat pairs as one name.
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) <= 1:
        return parts

    # Heuristic: 'Last, First' format has single-word tokens after each comma
    # (e.g. "Adams, E." or "Adams, Emma"), while 'Firstname Lastname' format
    # has multi-word tokens (e.g. "Emma Adams") as separators.
    even_tokens = parts[0::2]  # positions 0, 2, 4 … (last names)
    odd_tokens  = parts[1::2]  # positions 1, 3, 5 … (first names / initials)
    if odd_tokens and all(len(t.split()) == 1 for t in odd_tokens):
        authors = []
        for i, last in enumerate(even_tokens):
            first = odd_tokens[i] if i < len(odd_tokens) else ""
            authors.append(f"{last}, {first}" if first else last)
        return authors

    return parts


def _extract_authors(container: Tag) -> list[str]:
    """Pull author names from a Drupal view row, handling common field layouts."""
    author_el = container.find(class_=_AUTHOR_CLASS_RE)
    if not author_el or not isinstance(author_el, Tag):
        return []

    def _clean(s: str) -> str:
        return " ".join(s.split())  # collapse all internal whitespace

    # Pattern 1: individual field-item divs/spans (multi-value Drupal field)
    items = author_el.find_all(class_=re.compile(r"field-item", re.I))
    if items:
        return [_clean(el.get_text()) for el in items if el.get_text(strip=True)]

    # Pattern 2: delimited text in a single element
    text = _clean(author_el.get_text())
    if re.search(r"[,;]", text):
        return [_clean(n) for n in _split_author_string(text) if n.strip()]

    # Pattern 3: single author as plain text
    return [_clean(text)] if text.strip() else []


def _abs_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return PNP_ROOT + ("" if href.startswith("/") else "/") + href


def _parse_publications(html: str, base_url: str, n: int) -> list[Publication]:
    """Try several selector strategies to extract publication entries."""
    soup = BeautifulSoup(html, "lxml")
    results: list[Publication] = []

    # Strategy 1: Drupal view rows (div-based)
    view_content = soup.find("div", class_=re.compile(r"view-content"))
    if view_content and isinstance(view_content, Tag):
        rows = view_content.find_all(
            "div", class_=re.compile(r"views-row|view-row"), recursive=False
        )
        for row in rows[:n]:
            link = row.find("a", href=True)
            if link:
                title = link.get_text(strip=True)
                url = _abs_url(str(link["href"]))
                date_el = row.find(class_=re.compile(r"date|created|field-date"))
                date = date_el.get_text(strip=True) if date_el else ""
                doc_m = _DOCNUM_RE.search(row.get_text())
                results.append(Publication(
                    title=title, url=url,
                    doc_number=doc_m.group(0) if doc_m else "",
                    date=date,
                    authors=_extract_authors(row),
                ))
        if results:
            return results

    # Strategy 2: Drupal view table rows
    table = soup.find("table", class_=re.compile(r"views-table|view-table"))
    if table and isinstance(table, Tag):
        for tr in table.find_all("tr")[1:n + 1]:  # skip header row
            link = tr.find("a", href=True)
            if link:
                title = link.get_text(strip=True)
                url = _abs_url(str(link["href"]))
                date_td = tr.find("td", class_=re.compile(r"date|created"))
                date = date_td.get_text(strip=True) if date_td else ""
                doc_m = _DOCNUM_RE.search(tr.get_text())
                results.append(Publication(
                    title=title, url=url,
                    doc_number=doc_m.group(0) if doc_m else "",
                    date=date,
                    authors=_extract_authors(tr),
                ))
        if results:
            return results

    # Strategy 3: Any list of links to /node/ paths (broad fallback)
    seen: set[str] = set()
    for link in soup.find_all("a", href=re.compile(r"/node/\d+")):
        title = link.get_text(strip=True)
        url = _abs_url(str(link["href"]))
        if not title or url in seen:
            continue
        seen.add(url)
        # Search doc number in the link text itself first, then narrow siblings
        link_text = link.get_text(" ", strip=True)
        doc_m = _DOCNUM_RE.search(link_text)
        if not doc_m:
            # Try immediate next/prev sibling text only (avoid spanning rows)
            for sib in [link.next_sibling, link.previous_sibling]:
                if sib and hasattr(sib, "get_text"):
                    doc_m = _DOCNUM_RE.search(sib.get_text())
                elif sib and isinstance(sib, str):
                    doc_m = _DOCNUM_RE.search(sib)
                if doc_m:
                    break
        results.append(Publication(
            title=title, url=url,
            doc_number=doc_m.group(0) if doc_m else "",
        ))
        if len(results) >= n:
            break
    return results


def fetch_recent_publications(
    session: requests.Session, n: int = 20, page: int = 0
) -> list[Publication]:
    """Return up to *n* publications from pnp.ligo.org starting at *page* (0-indexed).

    Drupal paginates via ``?page=N``.  page=0 is the first/newest batch,
    page=1 the next 20, and so on.  Raises RuntimeError if all URLs fail.
    """
    last_error: Optional[Exception] = None
    for base_url in _PUB_URLS:
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}items_per_page={n}&page={page}"
        try:
            resp = session.get(url, timeout=20, allow_redirects=True)
            if PNP_ROOT not in resp.url:
                raise RuntimeError("Session expired — please log in again.")
            if resp.status_code != 200:
                continue
            pubs = _parse_publications(resp.text, url, n)
            if pubs:
                return pubs
        except RuntimeError:
            raise
        except Exception as exc:
            last_error = exc

    if last_error:
        raise RuntimeError(f"Could not fetch publications: {last_error}")
    raise RuntimeError(
        "No publication listings found. The page structure may have changed."
    )
