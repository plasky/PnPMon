from datetime import datetime

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QInputDialog, QMessageBox,
    QFrame, QSizePolicy, QToolBar,
)

from ..core.auth import AuthManager
from ..core.monitor import CheckResult
from ..core.storage import StorageManager
from .auth_dialog import AuthDialog
from .search_dialog import SearchDialog
from .settings_dialog import SettingsDialog
from .waveform_widget import WaveformWidget


_STYLE = """
QMainWindow, QWidget#central {
    background-color: #111111;
}
QLabel#status_bar {
    color: #666666;
    font-size: 11px;
    padding: 5px 14px;
    background-color: #161616;
    border-bottom: 1px solid #2a2a2a;
}
QTableWidget {
    background-color: #111111;
    color: #e8e8e8;
    gridline-color: transparent;
    border: none;
    font-size: 13px;
    selection-background-color: #1f1f1f;
    alternate-background-color: #141414;
}
QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #1c1c1c;
}
QTableWidget::item:selected {
    background-color: #1f1f1f;
    color: #f2f2f2;
}
QHeaderView::section {
    background-color: #161616;
    color: #888888;
    border: none;
    border-bottom: 1px solid #2a2a2a;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
QPlainTextEdit {
    background-color: #0d0d0d;
    color: #555555;
    border: none;
    border-top: 1px solid #1c1c1c;
    font-family: "SF Mono", "Menlo", "Monaco", monospace;
    font-size: 11px;
    padding: 6px 10px;
    selection-background-color: #4f86e030;
    selection-color: #ececec;
}
QPushButton {
    background-color: #1a1a1a;
    color: #aaaaaa;
    border: 1px solid #2e2e2e;
    border-radius: 18px;
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
QPushButton:pressed {
    background-color: #161616;
}
QPushButton#check_btn {
    background-color: #4f86e018;
    border-color: #4f86e060;
    color: #7aa8f0;
    font-weight: 600;
    padding: 6px 20px;
}
QPushButton#check_btn:hover {
    background-color: #4f86e030;
    border-color: #4f86e0;
    color: #a0c0f8;
}
QPushButton#login_btn {
    color: #aaaaaa;
    border-color: #2e2e2e;
    background-color: #1a1a1a;
}
QPushButton#login_btn:hover {
    background-color: #222222;
    border-color: #444444;
    color: #ececec;
}
QPushButton#search_btn {
    color: #aaaaaa;
    border-color: #2e2e2e;
    background-color: #1a1a1a;
}
QPushButton#search_btn:hover {
    background-color: #222222;
    border-color: #444444;
    color: #ececec;
}
QFrame#toolbar_frame {
    background-color: #161616;
    border-bottom: 1px solid #2a2a2a;
}
"""


class MainWindow(QMainWindow):
    page_marked_read = pyqtSignal()
    settings_changed = pyqtSignal()  # emitted when settings dialog is saved

    def __init__(
        self,
        auth: AuthManager,
        storage: StorageManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._auth = auth
        self._storage = storage

        self.setWindowTitle("LIGO P&P Monitor")
        self.setMinimumSize(720, 520)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._refresh_table()
        self._update_status_bar()

    # ── Build UI ────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Waveform banner
        layout.addWidget(WaveformWidget())

        # Status bar
        self._status_label = QLabel()
        self._status_label.setObjectName("status_bar")
        layout.addWidget(self._status_label)

        # Toolbar
        toolbar_frame = QFrame()
        toolbar_frame.setObjectName("toolbar_frame")
        tb_layout = QHBoxLayout(toolbar_frame)
        tb_layout.setContentsMargins(10, 8, 10, 8)
        tb_layout.setSpacing(8)

        self._check_btn = QPushButton("⟳  Check Now")
        self._check_btn.setObjectName("check_btn")
        tb_layout.addWidget(self._check_btn)

        add_btn = QPushButton("+ Add Page")
        add_btn.clicked.connect(self._on_add_page)
        tb_layout.addWidget(add_btn)

        self._remove_btn = QPushButton("− Remove")
        self._remove_btn.clicked.connect(self._on_remove_page)
        tb_layout.addWidget(self._remove_btn)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.clicked.connect(self._on_settings)
        tb_layout.addWidget(settings_btn)

        self._search_btn = QPushButton("🔍  Search Publications")
        self._search_btn.setObjectName("search_btn")
        self._search_btn.clicked.connect(self._on_search)
        tb_layout.addWidget(self._search_btn)

        tb_layout.addStretch()

        self._login_btn = QPushButton("Login")
        self._login_btn.setObjectName("login_btn")
        self._login_btn.clicked.connect(self._on_login)
        tb_layout.addWidget(self._login_btn)

        layout.addWidget(toolbar_frame)

        # Pages table
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Label", "URL", "Last Changed", "Status", ""])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_open_url)
        layout.addWidget(self._table, stretch=1)

        # Log panel
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(90)
        self._log.setPlaceholderText("Event log…")
        layout.addWidget(self._log)

    # ── Slots ───────────────────────────────────────────────────────────────

    def on_check_started(self) -> None:
        self._check_btn.setEnabled(False)
        self._check_btn.setText("⟳  Checking…")
        self._log_line("Checking pages…")

    def on_check_finished(self, results: list) -> None:
        self._check_btn.setEnabled(True)
        self._check_btn.setText("⟳  Check Now")
        changed = sum(1 for r in results if r.changed)
        errors = sum(1 for r in results if r.error)
        parts = [f"Checked {len(results)} page(s)"]
        if changed:
            parts.append(f"{changed} change(s) detected")
        if errors:
            parts.append(f"{errors} error(s)")
        self._log_line("  ·  ".join(parts))
        self._refresh_table()
        self._update_status_bar()

    def on_session_expired(self) -> None:
        self._log_line("Session expired — please log in again.")
        self._update_status_bar()

    def on_page_changed(self, url: str, label: str, summary: str) -> None:
        self._log_line(f"CHANGED  {label or url}  —  {summary}")

    def _on_add_page(self) -> None:
        url, ok = QInputDialog.getText(
            self, "Add Page", "Enter the pnp.ligo.org URL to monitor:"
        )
        if not ok or not url.strip():
            return
        url = url.strip()
        if not url.startswith("http"):
            url = "https://pnp.ligo.org/" + url.lstrip("/")

        label, ok2 = QInputDialog.getText(
            self, "Page Label", "Enter a short label for this page:"
        )
        if not ok2:
            return
        self._storage.add_page(url, label.strip())
        self._refresh_table()
        self._log_line(f"Added: {label or url}")

    def _on_remove_page(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        url_item = self._table.item(row, 1)
        if url_item is None:
            return
        url = url_item.data(Qt.ItemDataRole.UserRole)
        answer = QMessageBox.question(
            self, "Remove Page",
            f"Remove this page from monitoring?\n\n{url}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._storage.remove_page(url)
            self._refresh_table()

    def _on_settings(self) -> None:
        dlg = SettingsDialog(self._storage, self)
        if dlg.exec():
            self.settings_changed.emit()

    def _on_login(self) -> None:
        dlg = AuthDialog(self)
        dlg.auth_complete.connect(self._on_auth_complete)
        dlg.exec()

    def _on_auth_complete(self, cookies: list) -> None:
        self._auth.save_cookies(cookies)
        self._log_line("Login successful — session stored in Keychain.")
        self._update_status_bar()

    def _on_search(self) -> None:
        if not self._auth.has_cookies():
            QMessageBox.information(
                self, "Not logged in",
                "Please log in first, then use Search Publications.",
            )
            return
        dlg = SearchDialog(self._auth, self._storage, self)
        dlg.add_to_monitor.connect(self._on_search_add_to_monitor)
        dlg.exec()

    def _on_search_add_to_monitor(self, url: str, label: str) -> None:
        self._refresh_table()
        self._log_line(f"Added from search: {label}")

    def _on_open_url(self, index) -> None:
        url_item = self._table.item(index.row(), 1)
        if url_item:
            url = url_item.data(Qt.ItemDataRole.UserRole)
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def _mark_as_read(self, url: str, label: str) -> None:
        self._storage.clear_last_changed(url)
        self._refresh_table()
        self._log_line(f"Marked as read: {label}")
        self.page_marked_read.emit()

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        pages = self._storage.get_monitored_pages()
        self._table.setRowCount(len(pages))
        for row, page in enumerate(pages):
            state = self._storage.get_page_status(page["url"])

            label_item = QTableWidgetItem(page["label"] or "—")
            self._table.setItem(row, 0, label_item)

            url_item = QTableWidgetItem(page["url"])
            url_item.setData(Qt.ItemDataRole.UserRole, page["url"])
            url_item.setForeground(QColor("#555555"))
            self._table.setItem(row, 1, url_item)

            changed_at = state.get("last_changed") or "—"
            if changed_at != "—":
                try:
                    dt = datetime.fromisoformat(changed_at)
                    today = datetime.now().date()
                    changed_at = (
                        f"Today {dt.strftime('%H:%M')}"
                        if dt.date() == today
                        else dt.strftime("%Y-%m-%d")
                    )
                except ValueError:
                    pass
            self._table.setItem(row, 2, QTableWidgetItem(changed_at))

            last_checked = state.get("last_checked")
            if last_checked:
                status_text = "● CHANGED" if state.get("last_changed") else "● OK"
                fg    = "#d4882a" if state.get("last_changed") else "#3d8a5a"
                bg    = "#d4882a18" if state.get("last_changed") else "#3d8a5a18"
            else:
                status_text = "● PENDING"
                fg = "#555555"
                bg = "#55555512"

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(fg))
            status_item.setBackground(QColor(bg))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, status_item)

            # Column 4: "Mark as Read" button, only shown for CHANGED rows
            if status_text == "● CHANGED":
                url_for_btn = page["url"]
                label_for_btn = page["label"] or url_for_btn
                btn = QPushButton("✓  Mark as Read")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3d8a5a18;
                        color: #3d8a5a;
                        border: 1px solid #3d8a5a40;
                        border-radius: 14px;
                        padding: 4px 14px;
                        font-size: 11px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #3d8a5a30;
                        border-color: #3d8a5a;
                    }
                """)
                btn.clicked.connect(
                    lambda checked, u=url_for_btn, l=label_for_btn: self._mark_as_read(u, l)
                )
                self._table.setCellWidget(row, 4, btn)
            else:
                self._table.setCellWidget(row, 4, None)

        self._table.resizeRowsToContents()

    def _update_status_bar(self) -> None:
        session_ok = self._auth.has_cookies()
        session_text = "● Session active" if session_ok else "● Not logged in"
        session_color = "#4f86e0" if session_ok else "#c05050"
        self._status_label.setText(
            f'<span style="color:{session_color}">{session_text}</span>'
            f'<span style="color:#444444">  ·  Double-click a row to open in browser</span>'
        )
        if session_ok:
            self._login_btn.setText("Re-login")
        else:
            self._login_btn.setText("Login")

    def _log_line(self, text: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._log.appendPlainText(f"{ts}  {text}")

    def closeEvent(self, event) -> None:
        # Hide to tray instead of closing
        event.ignore()
        self.hide()
