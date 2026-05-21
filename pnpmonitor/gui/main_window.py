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
    background-color: #06080f;
}
QLabel#status_bar {
    color: #7a8fa8;
    font-size: 11px;
    padding: 5px 14px;
    background-color: #0b0f19;
    border-bottom: 1px solid #1a2236;
}
QTableWidget {
    background-color: #06080f;
    color: #dde4ed;
    gridline-color: transparent;
    border: none;
    font-size: 13px;
    selection-background-color: #151c28;
    alternate-background-color: #080c14;
}
QTableWidget::item {
    padding: 8px 12px;
    border-bottom: 1px solid #0e1522;
}
QTableWidget::item:selected {
    background-color: #151c28;
    color: #e0e8f4;
}
QHeaderView::section {
    background-color: #0b0f19;
    color: #00e0b0;
    border: none;
    border-bottom: 1px solid #1a2236;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
QPlainTextEdit {
    background-color: #040609;
    color: #3d5168;
    border: none;
    border-top: 1px solid #0e1522;
    font-family: "SF Mono", "Menlo", "Monaco", monospace;
    font-size: 11px;
    padding: 6px 10px;
    selection-background-color: #1a2236;
    selection-color: #00e0b0;
}
QPushButton {
    background-color: #101520;
    color: #b0bec8;
    border: 1px solid #1c2b3d;
    border-radius: 18px;
    padding: 6px 18px;
    font-size: 12px;
    font-weight: 500;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #17203080;
    border-color: #2a3f55;
    color: #e0e8f4;
}
QPushButton:pressed {
    background-color: #0e1520;
}
QPushButton#check_btn {
    background-color: #00e0b018;
    border-color: #00e0b060;
    color: #00e0b0;
    font-weight: 600;
    padding: 6px 20px;
}
QPushButton#check_btn:hover {
    background-color: #00e0b030;
    border-color: #00e0b0;
}
QPushButton#login_btn {
    color: #ffb830;
    border-color: #ffb83050;
    background-color: #ffb83010;
}
QPushButton#login_btn:hover {
    background-color: #ffb83025;
    border-color: #ffb830;
}
QPushButton#search_btn {
    color: #b27fff;
    border-color: #b27fff50;
    background-color: #b27fff10;
}
QPushButton#search_btn:hover {
    background-color: #b27fff25;
    border-color: #b27fff;
}
QFrame#toolbar_frame {
    background-color: #0b0f19;
    border-bottom: 1px solid #1a2236;
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
            url_item.setForeground(QColor("#3d6080"))
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
                fg    = "#ffb830" if state.get("last_changed") else "#3ddc97"
                bg    = "#ffb83018" if state.get("last_changed") else "#3ddc9718"
            else:
                status_text = "● PENDING"
                fg = "#3d5168"
                bg = "#3d516812"

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(fg))
            status_item.setBackground(QColor(bg))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, status_item)

            # Column 4: "Mark as Read" button, only shown for CHANGED rows
            if status_text == "CHANGED":
                url_for_btn = page["url"]
                label_for_btn = page["label"] or url_for_btn
                btn = QPushButton("✓  Mark as Read")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3ddc9715;
                        color: #3ddc97;
                        border: 1px solid #3ddc9740;
                        border-radius: 14px;
                        padding: 4px 14px;
                        font-size: 11px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background-color: #3ddc9730;
                        border-color: #3ddc97;
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
        session_color = "#00e0b0" if session_ok else "#ff6b6b"
        self._status_label.setText(
            f'<span style="color:{session_color}">{session_text}</span>'
            f'<span style="color:#3d5168">  ·  Double-click a row to open in browser</span>'
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
