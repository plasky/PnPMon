import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .core.auth import AuthManager
from .core.monitor import PageMonitor
from .core.notifier import Notifier
from .core.scheduler import MonitorScheduler
from .core.storage import StorageManager
from .gui.main_window import MainWindow
from .gui.waveform_widget import make_tray_icon_pixmap


class PnPMonitorApp:
    def __init__(self) -> None:
        self._qapp = QApplication.instance() or QApplication(sys.argv)
        self._qapp.setApplicationName("PnPMonitor")
        self._qapp.setQuitOnLastWindowClosed(False)

        # Core objects
        self._storage = StorageManager()
        self._auth = AuthManager()
        self._monitor = PageMonitor(self._auth, self._storage)
        self._notifier = Notifier()
        self._scheduler = MonitorScheduler(self._monitor, self._storage)

        # GUI
        self._window = MainWindow(self._auth, self._storage)
        self._tray = self._build_tray()

        # Wire signals
        self._scheduler.check_started.connect(self._window.on_check_started)
        self._scheduler.check_finished.connect(self._window.on_check_finished)
        self._scheduler.session_expired.connect(self._window.on_session_expired)
        self._scheduler.page_changed.connect(self._window.on_page_changed)
        self._scheduler.page_changed.connect(self._on_page_changed)
        self._notifier.notify.connect(self._show_notification)

        # Wire Check Now button
        self._window._check_btn.clicked.disconnect()
        self._window._check_btn.clicked.connect(self._scheduler.trigger_now)

    def _build_tray(self) -> QSystemTrayIcon:
        pixmap = make_tray_icon_pixmap(22)
        icon = QIcon(pixmap)
        tray = QSystemTrayIcon(icon, self._qapp)
        tray.setToolTip("LIGO P&P Monitor")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #12121f;
                color: #cccccc;
                border: 1px solid #2a2a4a;
            }
            QMenu::item:selected {
                background-color: #1e2040;
                color: #ffffff;
            }
        """)

        open_action = menu.addAction("Open Monitor")
        open_action.triggered.connect(self._show_window)

        check_action = menu.addAction("Check Now")
        check_action.triggered.connect(self._scheduler.trigger_now)

        menu.addSeparator()

        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self._quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self._on_tray_activated)
        return tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _show_window(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def _on_page_changed(self, url: str, label: str, summary: str) -> None:
        notify_on = self._storage.get_setting("notify_on_change", "true")
        if notify_on.lower() == "true":
            self._notifier.send(label, url, summary)

    def _show_notification(self, title: str, body: str) -> None:
        self._tray.showMessage(
            title, body,
            QSystemTrayIcon.MessageIcon.Information,
            8000,
        )

    def _quit(self) -> None:
        self._scheduler.stop()
        self._qapp.quit()

    def run(self) -> int:
        self._tray.show()
        self._window.show()
        self._scheduler.start()
        return self._qapp.exec()


def main() -> None:
    app = PnPMonitorApp()
    sys.exit(app.run())
