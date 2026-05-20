import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .auth import AuthManager
from .storage import StorageManager

_STRIP_TAGS = ["script", "style", "noscript", "meta", "link", "iframe"]
_HIDDEN_INPUT_RE = re.compile(r'<input[^>]+type=["\']hidden["\'][^>]*/?>',  re.I)


def _extract_content_hash(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in _STRIP_TAGS:
        for el in soup.find_all(tag):
            el.decompose()
    for el in soup.find_all("input", attrs={"type": "hidden"}):
        el.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_change_summary(old_html: str, new_html: str) -> str:
    def get_items(html: str) -> set[str]:
        soup = BeautifulSoup(html, "lxml")
        items: set[str] = set()
        for el in soup.find_all(["tr", "li"]):
            text = el.get_text(" ", strip=True)
            if len(text) > 5:
                items.add(text[:200])
        return items

    old_items = get_items(old_html)
    new_items = get_items(new_html)
    added = new_items - old_items
    removed = old_items - new_items
    parts: list[str] = []
    if added:
        parts.append(f"+{len(added)} new item(s)")
    if removed:
        parts.append(f"−{len(removed)} removed")
    return "; ".join(parts) if parts else "Content changed"


@dataclass
class CheckResult:
    url: str
    label: str
    changed: bool = False
    summary: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error


class PageMonitor:
    def __init__(self, auth: AuthManager, storage: StorageManager) -> None:
        self._auth = auth
        self._storage = storage
        self._session: Optional[requests.Session] = None

    def refresh_session(self) -> bool:
        self._session = self._auth.build_session()
        if self._session is None:
            return False
        return self._auth.is_session_valid(self._session)

    def check_all_pages(self) -> list[CheckResult]:
        if self._session is None:
            self._session = self._auth.build_session()

        if self._session is None or not self._auth.is_session_valid(self._session):
            return []

        pages = self._storage.get_monitored_pages()
        results: list[CheckResult] = []
        for page in pages:
            if not page["enabled"]:
                continue
            results.append(self._check_one(self._session, page["url"], page["label"]))
        return results

    def _check_one(self, session: requests.Session, url: str, label: str) -> CheckResult:
        try:
            resp = session.get(url, timeout=20, allow_redirects=True)
            resp.raise_for_status()
            new_hash = _extract_content_hash(resp.text)
            old_hash, old_html = self._storage.get_last_state(url)

            if old_hash is None:
                # First check — store baseline, not a change
                self._storage.update_state(url, new_hash, resp.text)
                return CheckResult(url=url, label=label)

            if new_hash != old_hash:
                summary = _extract_change_summary(old_html or "", resp.text)
                self._storage.update_state(url, new_hash, resp.text)
                return CheckResult(url=url, label=label, changed=True, summary=summary)

            self._storage.update_state(url, new_hash, resp.text)
            return CheckResult(url=url, label=label)

        except requests.RequestException as exc:
            return CheckResult(url=url, label=label, error=str(exc))
