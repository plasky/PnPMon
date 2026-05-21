from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QPlainTextEdit, QInputDialog, QMessageBox,
    QFrame, QSizePolicy, QToolBar, QMenu,
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
    background-color: #0f0f1e;
}
QLabel#status_bar {
    color: #888888;
    font-size: 11px;
    padding: 4px 10px;
    background-color: #0c0c18;
    border-bottom: 1px solid #1a1a30;
}
QTableWidget {
    background-color: #0f0f1e;
    color: #cccccc;
    gridline-color: #1a1a30;
    border: none;
    font-size: 12px;
    selection-background-color: #1e2040;
}
QTableWidget::item {
    padding: 6px 8px;
}
QHeaderView::section {
    background-color: #0c0c18;
    color: #00d4aa;
    border: none;
    border-bottom: 1px solid #1a1a30;
    padding: 6px 8px;
    font-size: 11px;
    font-weight: bold;
}
QPlainTextEdit {
    background-color: #080812;
    color: #667799;
    border: none;
    border-top: 1px solid #1a1a30;
    font-family: monospace;
    font-size: 11px;
}
QPushButton {
    background-color: #1a1a30;
    color: #cccccc;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    padding: 5px 14px;
    font-size: 12px;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #202040;
    border-color: #00d4aa;
    color: #ffffff;
}
QPushButton#check_btn {
    background-color: #00d4aa22;
    border-color: #00d4aa;
    color: #00d4aa;
    font-weight: bold;
}
QPushButton#check_btn:hover {
    background-color: #00d4aa44;
}
QPushButton#login_btn {
    color: #ffaa44;
    border-color: #ffaa44;
}
QPushButton#login_btn:hover {
    background-color: #ffaa4422;
}
QPushButton#search_btn {
    color: #aa88ff;
    border-color: #8855ff;
}
QPushButton#search_btn:hover {
    background-color: #8855ff22;
}
QFrame#toolbar_frame {
    background-color: #0c0c18;
    border-bottom: 1px solid #1a1a30;
}
"""


class MainWindow(QMainWindow):
    def __init__(
        self,
        auth: AuthManager,
        storage: StorageManager,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._auth = auth
        self._storage = storage
        self._checking = False

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
        self._check_btn.clicked.connect(self.trigger_check)
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
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Label", "URL", "Last Changed", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_open_url)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        layout.addWidget(self._table, stretch=1)

        # Log panel
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(90)
        self._log.setPlaceholderText("Event log…")
        layout.addWidget(self._log)

    # ── Slots ───────────────────────────────────────────────────────────────

    def trigger_check(self) -> None:
        # Called by the scheduler signal or the Check Now button
        # The actual trigger goes through the scheduler; the button calls scheduler.trigger_now()
        # This method is wired up externally in app.py
        pass

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
        dlg.exec()

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

    def _on_table_context_menu(self, pos) -> None:
        row = self._table.rowAt(pos.y())
        if row < 0:
            return

        url_item = self._table.item(row, 1)
        status_item = self._table.item(row, 3)
        if not url_item or not status_item:
            return

        url = url_item.data(Qt.ItemDataRole.UserRole)
        is_changed = status_item.text() == "CHANGED"

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #12121f;
                color: #cccccc;
                border: 1px solid #2a2a4a;
            }
            QMenu::item { padding: 6px 20px; }
            QMenu::item:selected { background-color: #1e2040; color: #ffffff; }
            QMenu::item:disabled { color: #444466; }
            QMenu::separator { background-color: #2a2a4a; height: 1px; margin: 4px 0; }
        """)

        mark_read_action = menu.addAction("✓  Mark as Read")
        mark_read_action.setEnabled(is_changed)
        menu.addSeparator()
        open_action = menu.addAction("Open in Browser")

        action = menu.exec(self._table.viewport().mapToGlobal(pos))

        if action == mark_read_action:
            self._storage.clear_last_changed(url)
            label_item = self._table.item(row, 0)
            label = label_item.text() if label_item else url
            self._refresh_table()
            self._log_line(f"Marked as read: {label}")
        elif action == open_action:
            QDesktopServices.openUrl(QUrl(url))

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
            url_item.setForeground(QColor("#6688bb"))
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
                status_text = "CHANGED" if state.get("last_changed") else "OK"
                color = "#ffcc44" if state.get("last_changed") else "#44cc88"
            else:
                status_text = "PENDING"
                color = "#888888"

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, status_item)

        self._table.resizeRowsToContents()

    def _update_status_bar(self) -> None:
        session_ok = self._auth.has_cookies()
        session_text = "Session: Active" if session_ok else "Session: Not logged in"
        session_color = "#00d4aa" if session_ok else "#ff6644"
        self._status_label.setText(
            f'<span style="color:{session_color}">{session_text}</span>'
            f'  ·  Double-click a row to open page in browser'
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
