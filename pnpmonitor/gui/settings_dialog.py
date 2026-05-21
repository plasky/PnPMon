from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QPushButton, QCheckBox,
    QGroupBox, QFormLayout,
)

from ..core.storage import StorageManager


_STYLE = """
QDialog {
    background-color: #06080f;
}
QGroupBox {
    background-color: #0b0f19;
    border: 1px solid #1a2236;
    border-radius: 10px;
    margin-top: 10px;
    padding: 14px 14px 10px 14px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.5px;
    color: #00e0b0;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    color: #00e0b080;
}
QLabel {
    color: #7a8fa8;
    font-size: 12px;
}
QSpinBox {
    background-color: #101520;
    color: #dde4ed;
    border: 1px solid #1c2b3d;
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
    selection-background-color: #00e0b0;
    selection-color: #06080f;
    min-width: 120px;
}
QSpinBox:focus {
    border-color: #00e0b060;
}
QSpinBox::up-button, QSpinBox::down-button {
    width: 20px;
    border: none;
    background-color: #1a2236;
    border-radius: 4px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #223048;
}
QCheckBox {
    color: #b0bec8;
    font-size: 12px;
    spacing: 8px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: 1px solid #1c2b3d;
    background-color: #101520;
}
QCheckBox::indicator:checked {
    background-color: #00e0b0;
    border-color: #00e0b0;
    image: none;
}
QCheckBox::indicator:hover {
    border-color: #00e0b060;
}
QPushButton {
    background-color: #101520;
    color: #b0bec8;
    border: 1px solid #1c2b3d;
    border-radius: 16px;
    padding: 7px 20px;
    font-size: 12px;
    font-weight: 500;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #17203080;
    border-color: #2a3f55;
    color: #e0e8f4;
}
QPushButton#save_btn {
    background-color: #00e0b0;
    color: #06080f;
    font-weight: 700;
    border: none;
    padding: 7px 28px;
}
QPushButton#save_btn:hover {
    background-color: #00f5c5;
}
"""


class SettingsDialog(QDialog):
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
        self.accept()
