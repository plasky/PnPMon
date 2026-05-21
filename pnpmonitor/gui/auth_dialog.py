from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton,
    QHBoxLayout, QSizePolicy,
)


_STYLE = """
QDialog {
    background-color: #12121f;
}
QLabel {
    color: #cccccc;
}
QLabel#heading {
    color: #00d4aa;
    font-size: 15px;
    font-weight: bold;
}
QLabel#info {
    color: #aaaaaa;
    font-size: 12px;
}
QPushButton {
    background-color: #1e1e35;
    color: #cccccc;
    border: 1px solid #333366;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #252545;
    border-color: #00d4aa;
}
"""


class _PlaywrightThread(QThread):
    cookies_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def run(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                # Prefer the user's installed Chrome; fall back to bundled Chromium.
                # (Safari cannot be automated for cookie extraction on macOS.)
                try:
                    browser = pw.chromium.launch(channel="chrome", headless=False)
                except Exception:
                    browser = pw.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://pnp.ligo.org", timeout=30_000)
                # Wait up to 5 minutes for the user to complete SSO login
                page.wait_for_url("https://pnp.ligo.org/**", timeout=300_000)
                cookies = context.cookies("https://pnp.ligo.org")
                browser.close()
            self.cookies_ready.emit(cookies)
        except Exception as exc:
            self.error_occurred.emit(str(exc))


class AuthDialog(QDialog):
    auth_complete = pyqtSignal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LIGO SSO Login")
        self.setFixedSize(420, 200)
        self.setStyleSheet(_STYLE)
        self._thread: _PlaywrightThread | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        heading = QLabel("LIGO Single Sign-On")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        self._status = QLabel(
            "A browser window will open.\n"
            "Log in with your institutional LIGO credentials,\n"
            "then return here — this dialog will close automatically."
        )
        self._status.setObjectName("info")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    def start_login(self) -> None:
        self._status.setText(
            "Chrome will open — please log in to LIGO SSO.\n"
            "This dialog will close automatically after login."
        )
        self._cancel_btn.setEnabled(True)
        self._thread = _PlaywrightThread(self)
        self._thread.cookies_ready.connect(self._on_success)
        self._thread.error_occurred.connect(self._on_error)
        self._thread.start()

    def _on_success(self, cookies: list) -> None:
        self.auth_complete.emit(cookies)
        self.accept()

    def _on_error(self, msg: str) -> None:
        self._status.setText(f"Login failed:\n{msg}\n\nClose and try again.")
        self._cancel_btn.setText("Close")

    def _on_cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.terminate()
            self._thread.wait()
        self.reject()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.start_login()
