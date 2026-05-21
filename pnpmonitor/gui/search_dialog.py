"""Dialog that fetches and displays pnp.ligo.org publications with pagination."""
from __future__ import annotations

import json
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame,
)

from ..core.auth import AuthManager
from ..core.fetcher import Publication, fetch_recent_publications, _format_authors, _format_author_surnames
from ..core.storage import StorageManager

PAGE_SIZE = 20
_STALE_MINUTES = 60  # auto-refresh if cache is older than this


def _cache_age_str(fetched_at_iso: str) -> str:
    """Human-readable age string for a fetched_at ISO timestamp."""
    try:
        then = datetime.fromisoformat(fetched_at_iso)
        delta = datetime.now() - then
        minutes = int(delta.total_seconds() // 60)
        if minutes < 1:
            return "just now"
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        return f"on {then.strftime('%Y-%m-%d')}"
    except (ValueError, TypeError):
        return "unknown"


def _pub_to_dict(pub: Publication) -> dict:
    return {
        "url": pub.url,
        "title": pub.title,
        "doc_number": pub.doc_number,
        "date": pub.date,
        "authors_json": json.dumps(pub.authors),
    }


def _dict_to_pub(row: dict) -> Publication:
    try:
        authors = json.loads(row.get("authors_json", "[]"))
    except (json.JSONDecodeError, TypeError):
        authors = []
    return Publication(
        url=row["url"],
        title=row.get("title", ""),
        doc_number=row.get("doc_number", ""),
        date=row.get("date", ""),
        authors=authors,
    )

_STYLE = """
QDialog {
    background-color: #111111;
}
QLabel#heading {
    color: #ececec;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: -0.3px;
}
QLabel#sub {
    color: #555555;
    font-size: 11px;
}
QLabel#status {
    color: #666666;
    font-size: 11px;
    font-style: italic;
}
QListWidget {
    background-color: #161616;
    color: #e8e8e8;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    font-size: 13px;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 11px 14px;
    border-radius: 8px;
    margin: 1px 0;
}
QListWidget::item:selected {
    background-color: #4f86e018;
    color: #f2f2f2;
}
QListWidget::item:hover {
    background-color: #1f1f1f;
}
QPushButton {
    background-color: #1a1a1a;
    color: #aaaaaa;
    border: 1px solid #2e2e2e;
    border-radius: 16px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: 500;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #222222;
    border-color: #444444;
    color: #ececec;
}
QPushButton:disabled {
    color: #333333;
    border-color: #222222;
}
QPushButton#open_btn {
    background-color: #4f86e018;
    border-color: #4f86e050;
    color: #7aa8f0;
    font-weight: 600;
}
QPushButton#open_btn:hover {
    background-color: #4f86e030;
    border-color: #4f86e0;
    color: #a0c0f8;
}
QPushButton#monitor_btn {
    background-color: #4f86e010;
    border-color: #4f86e040;
    color: #7aa8f0;
}
QPushButton#monitor_btn:hover {
    background-color: #4f86e025;
    border-color: #4f86e0;
    color: #a0c0f8;
}
QPushButton#more_btn {
    color: #666666;
    border-color: #2a2a2a;
}
QPushButton#more_btn:hover {
    background-color: #1f1f1f;
    border-color: #3a3a3a;
    color: #aaaaaa;
}
QFrame#divider {
    background-color: #2a2a2a;
    max-height: 1px;
}
"""


class _FetchThread(QThread):
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, auth: AuthManager, page: int) -> None:
        super().__init__()
        self._auth = auth
        self._page = page

    def run(self) -> None:
        try:
            session = self._auth.build_session()
            if session is None:
                self.error_occurred.emit("Not logged in. Please log in first.")
                return
            pubs = fetch_recent_publications(session, n=PAGE_SIZE, page=self._page)
            self.results_ready.emit(pubs)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class SearchDialog(QDialog):
    add_to_monitor = pyqtSignal(str, str)  # (url, label)

    def __init__(
        self,
        auth: AuthManager,
        storage: StorageManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._auth = auth
        self._storage = storage
        self._pubs: list[Publication] = []
        self._current_page = 0
        self._thread: _FetchThread | None = None

        self.setWindowTitle("Recent Publications — pnp.ligo.org")
        self.setMinimumSize(640, 540)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._load_or_fetch()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 18, 18, 18)

        heading = QLabel("Recent Publications")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        self._sub = QLabel(f"Showing the {PAGE_SIZE} most recent entries from pnp.ligo.org")
        self._sub.setObjectName("sub")
        layout.addWidget(self._sub)

        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        self._status = QLabel("Fetching publications…")
        self._status.setObjectName("status")
        layout.addWidget(self._status)

        self._list = QListWidget()
        self._list.setAlternatingRowColors(False)
        self._list.doubleClicked.connect(self._on_open)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, stretch=1)

        hint = QLabel("Double-click to open in browser  ·  Select then click Add to Monitor to track a page")
        hint.setObjectName("sub")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._refresh_btn = QPushButton("↻  Refresh")
        self._refresh_btn.clicked.connect(lambda: self._start_fetch(reset=True))
        btn_row.addWidget(self._refresh_btn)

        self._more_btn = QPushButton("Get More")
        self._more_btn.setObjectName("more_btn")
        self._more_btn.setEnabled(False)
        self._more_btn.clicked.connect(self._load_more)
        btn_row.addWidget(self._more_btn)

        btn_row.addStretch()

        self._monitor_btn = QPushButton("+ Add to Monitor")
        self._monitor_btn.setObjectName("monitor_btn")
        self._monitor_btn.setEnabled(False)
        self._monitor_btn.clicked.connect(self._on_add_to_monitor)
        btn_row.addWidget(self._monitor_btn)

        self._open_btn = QPushButton("Open in Browser")
        self._open_btn.setObjectName("open_btn")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open)
        btn_row.addWidget(self._open_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ── Cache + Fetch ─────────────────────────────────────────────────────────

    def _load_or_fetch(self) -> None:
        """On open: show cache instantly, then silently refresh if stale."""
        cached_rows, fetched_at = self._storage.load_pub_cache()
        if cached_rows:
            pubs = [_dict_to_pub(r) for r in cached_rows]
            self._pubs = pubs
            # Restore page counter so "Get More" fetches the next page
            self._current_page = max(0, (len(pubs) - 1) // PAGE_SIZE)
            for pub in pubs:
                self._list.addItem(self._make_item(pub))
            age = _cache_age_str(fetched_at)
            total = len(pubs)
            self._status.setText(f"{total} publication(s)  ·  cached {age}")
            self._sub.setText(
                f"Showing {total} entries from pnp.ligo.org"
                if total > PAGE_SIZE
                else f"Showing the {total} most recent entries from pnp.ligo.org"
            )
            self._more_btn.setEnabled(True)

            # Auto-refresh only if the cache is stale
            try:
                then = datetime.fromisoformat(fetched_at)
                stale = (datetime.now() - then).total_seconds() > _STALE_MINUTES * 60
            except (ValueError, TypeError):
                stale = True
            if stale:
                self._start_fetch(reset=True, silent=True)
        else:
            self._start_fetch(reset=True, silent=False)

    def _start_fetch(self, reset: bool, silent: bool = False) -> None:
        if reset:
            self._current_page = 0
            if not silent:
                self._pubs = []
                self._list.clear()

        if not silent:
            self._open_btn.setEnabled(False)
            self._monitor_btn.setEnabled(False)
            self._more_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)

        if not silent:
            self._status.setText(
                "Fetching publications…" if reset
                else f"Loading more…  (page {self._current_page + 1})"
            )

        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait()

        self._thread = _FetchThread(self._auth, page=self._current_page)
        self._thread.results_ready.connect(
            lambda pubs: self._on_results(pubs, reset, silent)
        )
        self._thread.error_occurred.connect(lambda msg: self._on_error(msg, silent))
        self._thread.start()

    def _load_more(self) -> None:
        self._current_page += 1
        self._start_fetch(reset=False, silent=False)

    def _on_results(self, pubs: list, was_reset: bool, was_silent: bool) -> None:
        self._refresh_btn.setEnabled(True)

        if was_reset and not was_silent:
            # Hard refresh: replace everything
            self._pubs = []
            self._list.clear()

        self._pubs.extend(pubs)

        # Persist to cache
        if was_reset:
            self._storage.save_pub_cache([_pub_to_dict(p) for p in pubs])
        else:
            self._storage.append_pub_cache([_pub_to_dict(p) for p in pubs])

        if not pubs and not self._pubs:
            self._status.setText("No publications found.")
            return

        for pub in pubs:
            self._list.addItem(self._make_item(pub))

        total = len(self._pubs)
        self._status.setText(f"{total} publication(s)  ·  just updated")
        self._sub.setText(
            f"Showing {total} entries from pnp.ligo.org"
            if total > PAGE_SIZE
            else f"Showing the {total} most recent entries from pnp.ligo.org"
        )
        self._more_btn.setEnabled(len(pubs) > 0)
        if len(pubs) == 0 and not was_reset:
            self._status.setText(f"{total} publication(s) — no more available")

    def _on_error(self, msg: str, was_silent: bool) -> None:
        self._refresh_btn.setEnabled(True)
        if self._current_page > 0:
            self._current_page -= 1
        if self._pubs:
            # We have cached data — show a gentle warning rather than wiping the list
            self._more_btn.setEnabled(True)
            self._status.setText(f"Could not refresh — showing cached data  ({msg})")
        else:
            self._status.setText(f"Error: {msg}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _make_item(pub: Publication) -> QListWidgetItem:
        top_line = pub.title or "(no title)"

        lines = [top_line]

        authors = _format_authors(pub.authors)
        meta_parts: list[str] = []
        if authors:
            meta_parts.append(authors)
        if pub.doc_number:
            meta_parts.append(pub.doc_number)
        if pub.date:
            meta_parts.append(pub.date)
        if meta_parts:
            lines.append("  ·  ".join(meta_parts))

        item = QListWidgetItem("\n".join(lines))
        item.setData(Qt.ItemDataRole.UserRole,     pub.url)
        item.setData(Qt.ItemDataRole.UserRole + 1, pub.title)
        item.setData(Qt.ItemDataRole.UserRole + 2, _format_author_surnames(pub.authors))
        return item

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_selection_changed(self) -> None:
        has_sel = bool(self._list.selectedItems())
        self._open_btn.setEnabled(has_sel)
        self._monitor_btn.setEnabled(has_sel)

    def _on_open(self) -> None:
        item = self._list.currentItem()
        if item:
            url = item.data(Qt.ItemDataRole.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def _on_add_to_monitor(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        url     = item.data(Qt.ItemDataRole.UserRole)
        title   = item.data(Qt.ItemDataRole.UserRole + 1) or url
        authors = item.data(Qt.ItemDataRole.UserRole + 2) or ""
        label   = f"{authors}: {title}" if authors else title
        label   = label[:80] + ("…" if len(label) > 80 else "")
        self._storage.add_page(url, label)
        self.add_to_monitor.emit(url, label)
        item.setText(item.text() + "  ✓ monitoring")
        item.setForeground(QColor("#3d8a5a"))
        self._monitor_btn.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait()
        super().closeEvent(event)
