"""Dialog that fetches and displays pnp.ligo.org publications with pagination."""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame,
)

from ..core.auth import AuthManager
from ..core.fetcher import Publication, fetch_recent_publications
from ..core.storage import StorageManager

PAGE_SIZE = 20

_STYLE = """
QDialog {
    background-color: #0f0f1e;
}
QLabel#heading {
    color: #00d4aa;
    font-size: 14px;
    font-weight: bold;
}
QLabel#sub {
    color: #667799;
    font-size: 11px;
}
QLabel#status {
    color: #888888;
    font-size: 11px;
    font-style: italic;
}
QListWidget {
    background-color: #0c0c18;
    color: #cccccc;
    border: 1px solid #1a1a30;
    border-radius: 4px;
    font-size: 12px;
    outline: none;
}
QListWidget::item {
    padding: 10px 12px;
    border-bottom: 1px solid #1a1a30;
}
QListWidget::item:selected {
    background-color: #1a2040;
    color: #ffffff;
}
QListWidget::item:hover {
    background-color: #141428;
}
QPushButton {
    background-color: #1a1a30;
    color: #cccccc;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #202040;
    border-color: #00d4aa;
    color: #ffffff;
}
QPushButton:disabled {
    color: #444466;
    border-color: #1a1a30;
}
QPushButton#open_btn {
    background-color: #00d4aa22;
    border-color: #00d4aa;
    color: #00d4aa;
    font-weight: bold;
}
QPushButton#open_btn:hover {
    background-color: #00d4aa44;
}
QPushButton#monitor_btn {
    border-color: #8855ff;
    color: #aa88ff;
}
QPushButton#monitor_btn:hover {
    background-color: #8855ff22;
}
QPushButton#more_btn {
    border-color: #336688;
    color: #88aacc;
}
QPushButton#more_btn:hover {
    background-color: #33668822;
}
QFrame#divider {
    background-color: #1a1a30;
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
        self._start_fetch(reset=True)

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

    # ── Fetch ────────────────────────────────────────────────────────────────

    def _start_fetch(self, reset: bool) -> None:
        if reset:
            self._current_page = 0
            self._pubs = []
            self._list.clear()

        self._open_btn.setEnabled(False)
        self._monitor_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._more_btn.setEnabled(False)
        self._status.setText(
            "Fetching publications…" if reset
            else f"Loading more… (page {self._current_page + 1})"
        )

        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait()

        self._thread = _FetchThread(self._auth, page=self._current_page)
        self._thread.results_ready.connect(
            lambda pubs: self._on_results(pubs, reset)
        )
        self._thread.error_occurred.connect(self._on_error)
        self._thread.start()

    def _load_more(self) -> None:
        self._current_page += 1
        self._start_fetch(reset=False)

    def _on_results(self, pubs: list, was_reset: bool) -> None:
        self._refresh_btn.setEnabled(True)
        self._pubs.extend(pubs)

        if not pubs and was_reset:
            self._status.setText("No publications found.")
            return

        # Append the new items to the list
        for pub in pubs:
            self._list.addItem(self._make_item(pub))

        total = len(self._pubs)
        self._status.setText(f"{total} publication(s) loaded")
        self._sub.setText(
            f"Showing {total} entries from pnp.ligo.org"
            if total > PAGE_SIZE
            else f"Showing the {total} most recent entries from pnp.ligo.org"
        )

        # Only show "Get More" if a full page came back (there may be more)
        self._more_btn.setEnabled(len(pubs) == PAGE_SIZE)
        if len(pubs) < PAGE_SIZE and not was_reset:
            self._status.setText(f"{total} publication(s) loaded — no more available")

    def _on_error(self, msg: str) -> None:
        self._refresh_btn.setEnabled(True)
        # On a "load more" error, revert the page counter so retry works
        if self._current_page > 0:
            self._current_page -= 1
            self._more_btn.setEnabled(True)
        self._status.setText(f"Error: {msg}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _make_item(pub: Publication) -> QListWidgetItem:
        top_line = pub.title or "(no title)"
        meta_parts: list[str] = []
        if pub.doc_number:
            meta_parts.append(pub.doc_number)
        if pub.date:
            meta_parts.append(pub.date)
        meta = "  ·  ".join(meta_parts)

        item = QListWidgetItem(f"{top_line}\n{meta}" if meta else top_line)
        item.setData(Qt.ItemDataRole.UserRole, pub.url)
        item.setData(Qt.ItemDataRole.UserRole + 1, pub.title)
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
        url = item.data(Qt.ItemDataRole.UserRole)
        label = item.data(Qt.ItemDataRole.UserRole + 1) or url
        label = label[:60] + ("…" if len(label) > 60 else "")
        self._storage.add_page(url, label)
        self.add_to_monitor.emit(url, label)
        item.setText(item.text() + "  ✓ monitoring")
        item.setForeground(QColor("#00d4aa"))
        self._monitor_btn.setEnabled(False)

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait()
        super().closeEvent(event)
