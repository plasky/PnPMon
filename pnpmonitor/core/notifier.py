from PyQt6.QtCore import QObject, pyqtSignal


class Notifier(QObject):
    # Emitted when a notification should be shown; the app connects this to the tray
    notify = pyqtSignal(str, str)  # (title, body)

    def send(self, label: str, url: str, summary: str) -> None:
        page_name = label or url.split("/")[-1] or url
        title = f"PnP Monitor: {page_name} changed"
        body = f"{summary}\n{url}"
        self.notify.emit(title, body)
