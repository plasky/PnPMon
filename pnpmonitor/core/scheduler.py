from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from PyQt6.QtCore import QObject, pyqtSignal

from .monitor import CheckResult, PageMonitor
from .storage import StorageManager


class MonitorScheduler(QObject):
    page_changed = pyqtSignal(str, str, str)  # (url, label, summary)
    session_expired = pyqtSignal()
    check_started = pyqtSignal()
    check_finished = pyqtSignal(list)  # list[CheckResult]

    def __init__(self, monitor: PageMonitor, storage: StorageManager) -> None:
        super().__init__()
        self._monitor = monitor
        self._storage = storage
        self._scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 300}
        )

    def start(self) -> None:
        interval = int(self._storage.get_setting("check_interval_minutes", "60"))
        self._scheduler.add_job(
            self._run_check,
            trigger="interval",
            minutes=interval,
            id="page_check",
            replace_existing=True,
            next_run_time=datetime.now(),
        )
        self._scheduler.start()

    def trigger_now(self) -> None:
        self._scheduler.modify_job("page_check", next_run_time=datetime.now())

    def update_interval(self, minutes: int) -> None:
        self._scheduler.reschedule_job(
            "page_check", trigger="interval", minutes=minutes
        )

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def _run_check(self) -> None:
        self.check_started.emit()
        results = self._monitor.check_all_pages()

        if not results and not self._monitor._auth.has_cookies():
            self.session_expired.emit()
            self.check_finished.emit([])
            return

        for r in results:
            if r.changed:
                self.page_changed.emit(r.url, r.label, r.summary)

        self.check_finished.emit(results)
