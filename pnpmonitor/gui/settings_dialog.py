from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QSpinBox, QPushButton, QCheckBox,
    QGroupBox, QFormLayout, QDialogButtonBox,
)

from ..core.storage import StorageManager


_STYLE = """
QDialog, QGroupBox {
    background-color: #12121f;
    color: #cccccc;
}
QGroupBox {
    border: 1px solid #2a2a4a;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 8px;
    font-weight: bold;
    color: #00d4aa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLabel {
    color: #bbbbbb;
}
QLineEdit, QSpinBox {
    background-color: #1e1e35;
    color: #eeeeee;
    border: 1px solid #333366;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #00d4aa;
}
QLineEdit:focus, QSpinBox:focus {
    border-color: #00d4aa;
}
QCheckBox {
    color: #cccccc;
}
QCheckBox::indicator:checked {
    background-color: #00d4aa;
    border: 1px solid #00d4aa;
}
QPushButton {
    background-color: #1e1e35;
    color: #cccccc;
    border: 1px solid #333366;
    border-radius: 4px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: #252545;
    border-color: #00d4aa;
}
QPushButton#save_btn {
    background-color: #00d4aa;
    color: #0a0a1a;
    font-weight: bold;
    border: none;
}
QPushButton#save_btn:hover {
    background-color: #00f0c0;
}
"""


class SettingsDialog(QDialog):
    settings_saved = pyqtSignal()

    def __init__(self, storage: StorageManager, parent=None) -> None:
        super().__init__(parent)
        self._storage = storage
        self.setWindowTitle("Settings")
        self.setMinimumWidth(380)
        self.setStyleSheet(_STYLE)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Monitoring group
        mon_group = QGroupBox("Monitoring")
        mon_form = QFormLayout(mon_group)
        mon_form.setSpacing(10)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 1440)
        self._interval_spin.setSuffix(" minutes")
        self._interval_spin.setToolTip("How often to check for page changes")
        mon_form.addRow("Check interval:", self._interval_spin)

        self._notify_check = QCheckBox("Show macOS notification on change")
        mon_form.addRow("Notifications:", self._notify_check)

        layout.addWidget(mon_group)

        # Save / Cancel
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setObjectName("save_btn")
        save_btn.clicked.connect(self._save)
        btn_box.addWidget(save_btn)
        layout.addLayout(btn_box)

    def _load_values(self) -> None:
        self._interval_spin.setValue(
            int(self._storage.get_setting("check_interval_minutes", "60"))
        )
        self._notify_check.setChecked(
            self._storage.get_setting("notify_on_change", "true").lower() == "true"
        )

    def _save(self) -> None:
        self._storage.set_setting(
            "check_interval_minutes", str(self._interval_spin.value())
        )
        self._storage.set_setting(
            "notify_on_change", "true" if self._notify_check.isChecked() else "false"
        )
        self.settings_saved.emit()
        self.accept()
