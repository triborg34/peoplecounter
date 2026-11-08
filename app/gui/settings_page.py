"""Settings page: API server, detection parameters, appearance and account."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..db.models import AppSetting, User
from ..services import auth as auth_service
from .theme import apply_theme, current_theme

log = logging.getLogger(__name__)

SETTING_KEY = "app_settings"


def load_settings(runtime) -> Dict[str, Any]:
    with runtime.db.session_scope() as session:
        row = session.get(AppSetting, SETTING_KEY)
        if row is None or not row.value:
            return {}
        try:
            return json.loads(row.value)
        except json.JSONDecodeError:
            return {}


def save_settings(runtime, values: Dict[str, Any]) -> None:
    with runtime.db.session_scope() as session:
        row = session.get(AppSetting, SETTING_KEY)
        if row is None:
            row = AppSetting(key=SETTING_KEY)
            session.add(row)
        row.value = json.dumps(values)


class ChangePasswordDialog(QDialog):
    """Change the password of the signed in account."""

    def __init__(self, runtime, user: User, require_change: bool = False, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user
        self.require_change = require_change
        self.setWindowTitle("Change password")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)
        if require_change:
            label = QLabel("This is a temporary password - please choose a new one.")
            label.setObjectName("Muted")
            layout.addWidget(label)

        form = QFormLayout()
        self.current_edit = QLineEdit()
        self.current_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_edit = QLineEdit()
        self.new_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat_edit = QLineEdit()
        self.repeat_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Current password", self.current_edit)
        form.addRow("New password", self.new_edit)
        form.addRow("Repeat new password", self.repeat_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if not require_change:
            cancel = QPushButton("Cancel")
            cancel.clicked.connect(self.reject)
            buttons.addWidget(cancel)
        save = QPushButton("Change password")
        save.setObjectName("PrimaryButton")
        save.setDefault(True)
        save.clicked.connect(self._apply)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _apply(self) -> None:
        if self.new_edit.text() != self.repeat_edit.text():
            self.error_label.setText("The new passwords do not match.")
            return
        error = auth_service.password_strength_error(self.new_edit.text())
        if error:
            self.error_label.setText(error)
            return
        with self.runtime.db.session_scope() as session:
            user = session.get(User, self.user.id)
            if user is None:
                self.error_label.setText("The user no longer exists.")
                return
            if not auth_service.verify_password(self.current_edit.text(), user.password_hash):
                self.error_label.setText("The current password is incorrect.")
                return
            user.password_hash = auth_service.hash_password(self.new_edit.text())
            user.must_change_password = False
        self.accept()


class SettingsPage(QWidget):
    """Application settings (persisted in the database)."""

    def __init__(self, runtime, user, app=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user
        self.app = app
        self.api_server = None
        self.values = load_settings(runtime)

        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("HeaderTitle")
        layout.addWidget(title)

        # --- API -------------------------------------------------------
        api_group = QGroupBox("API server")
        api_form = QFormLayout(api_group)
        self.api_enabled = QCheckBox("Enable the REST / WebSocket API")
        self.api_enabled.setChecked(bool(self.values.get("api_enabled", runtime.settings.api_enabled)))
        self.api_host = QLineEdit(str(self.values.get("api_host", runtime.settings.api_host)))
        self.api_port = QSpinBox()
        self.api_port.setRange(1, 65535)
        self.api_port.setValue(int(self.values.get("api_port", runtime.settings.api_port)))
        api_form.addRow("", self.api_enabled)
        api_form.addRow("Host", self.api_host)
        api_form.addRow("Port", self.api_port)
        api_buttons = QHBoxLayout()
        self.start_api_button = QPushButton("Start / restart API")
        self.start_api_button.clicked.connect(self._start_api)
        self.stop_api_button = QPushButton("Stop API")
        self.stop_api_button.clicked.connect(self._stop_api)
        api_buttons.addWidget(self.start_api_button)
        api_buttons.addWidget(self.stop_api_button)
        api_buttons.addStretch(1)
        api_form.addRow("", api_buttons)
        self.api_status = QLabel("API server is stopped")
        self.api_status.setObjectName("Muted")
        api_form.addRow("", self.api_status)
        layout.addWidget(api_group)

        # --- detection -------------------------------------------------
        detection_group = QGroupBox("Detection")
        detection_form = QFormLayout(detection_group)
        self.imgsz_spin = QSpinBox()
        self.imgsz_spin.setRange(320, 1280)
        self.imgsz_spin.setSingleStep(32)
        self.imgsz_spin.setValue(int(self.values.get("imgsz", runtime.settings.imgsz)))
        self.confidence_spin = QDoubleSpinBox()
        self.confidence_spin.setRange(0.05, 0.95)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setValue(float(self.values.get("confidence", runtime.settings.confidence)))
        self.device_combo = QComboBox()
        for label, value in (("Auto (CUDA when available)", "auto"), ("CPU only", "cpu")):
            self.device_combo.addItem(label, value)
        index = self.device_combo.findData(self.values.get("device", runtime.settings.device))
        self.device_combo.setCurrentIndex(max(0, index))
        self.point_combo = QComboBox()
        self.point_combo.addItem("Bottom centre (feet)", "bottom")
        self.point_combo.addItem("Centre of the box", "center")
        self.point_combo.setCurrentIndex(
            0 if self.values.get("track_point", runtime.settings.track_point) == "bottom" else 1
        )
        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.0, 30.0)
        self.cooldown_spin.setValue(float(self.values.get("cooldown", runtime.settings.counting_cooldown_s)))
        self.batch_spin = QSpinBox()
        self.batch_spin.setRange(1, 16)
        self.batch_spin.setValue(int(self.values.get("batch_size", runtime.settings.batch_size)))
        detection_form.addRow("Inference size", self.imgsz_spin)
        detection_form.addRow("Confidence", self.confidence_spin)
        detection_form.addRow("Device", self.device_combo)
        detection_form.addRow("Counting point", self.point_combo)
        detection_form.addRow("Crossing cooldown (s)", self.cooldown_spin)
        detection_form.addRow("Batch size", self.batch_spin)
        layout.addWidget(detection_group)

        # --- appearance ------------------------------------------------
        appearance_group = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_group)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.setCurrentIndex(0 if current_theme(self.app) == "dark" else 1)
        appearance_form.addRow("Theme", self.theme_combo)
        self.tray_check = QCheckBox("Minimize to the system tray")
        self.tray_check.setChecked(bool(self.values.get("minimize_to_tray", True)))
        appearance_form.addRow("", self.tray_check)
        layout.addWidget(appearance_group)

        # --- account / data --------------------------------------------
        account_group = QGroupBox("Account and data")
        account_form = QFormLayout(account_group)
        account_form.addRow("Signed in as", QLabel(self.user.username + " (" + self.user.role + ")"))
        account_buttons = QHBoxLayout()
        change_button = QPushButton("Change my password")
        change_button.clicked.connect(self._change_password)
        logout_button = QPushButton("Log out")
        logout_button.clicked.connect(self._logout)
        account_buttons.addWidget(change_button)
        account_buttons.addWidget(logout_button)
        account_buttons.addStretch(1)
        account_form.addRow("", account_buttons)
        self.reset_button = QPushButton("Reset all counters")
        self.reset_button.setObjectName("DangerButton")
        self.reset_button.setVisible(auth_service.can(self.user.role, auth_service.PERM_COUNTERS_RESET))
        self.reset_button.clicked.connect(self._reset_counters)
        account_form.addRow("", self.reset_button)
        account_form.addRow("Database", QLabel(self.runtime.db.url))
        layout.addWidget(account_group)

        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_button = QPushButton("Save settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save)
        save_row.addWidget(save_button)
        layout.addLayout(save_row)
        layout.addStretch(1)

    # -- actions ---------------------------------------------------------
    def _save(self) -> None:
        values = {
            "api_enabled": self.api_enabled.isChecked(),
            "api_host": self.api_host.text().strip() or "127.0.0.1",
            "api_port": int(self.api_port.value()),
            "imgsz": int(self.imgsz_spin.value()),
            "confidence": float(self.confidence_spin.value()),
            "device": self.device_combo.currentData(),
            "track_point": self.point_combo.currentData(),
            "cooldown": float(self.cooldown_spin.value()),
            "batch_size": int(self.batch_spin.value()),
            "minimize_to_tray": self.tray_check.isChecked(),
            "theme": self.theme_combo.currentData(),
        }
        save_settings(self.runtime, values)
        self.values = values

        settings = self.runtime.settings
        settings.imgsz = values["imgsz"]
        settings.confidence = values["confidence"]
        settings.device = values["device"]
        settings.track_point = values["track_point"]
        settings.counting_cooldown_s = values["cooldown"]
        settings.batch_size = values["batch_size"]
        settings.api_enabled = values["api_enabled"]
        settings.api_host = values["api_host"]
        settings.api_port = values["api_port"]
        self.runtime.camera_manager.counter.cooldown_s = values["cooldown"]
        self.runtime.camera_manager.counter.point_mode = values["track_point"]
        self.runtime.detector.imgsz = values["imgsz"]
        self.runtime.detector.confidence = values["confidence"]
        self.runtime.detector.device = settings.resolved_device
        apply_theme(self.app, values["theme"])
        window = self.window()
        if hasattr(window, "apply_tray_setting"):
            window.apply_tray_setting(values["minimize_to_tray"])
        QMessageBox.information(self, "Settings", "Settings saved.")

    def _start_api(self) -> None:
        from ..server import EmbeddedApiServer

        self._stop_api()
        try:
            self.api_server = EmbeddedApiServer(
                self.runtime, self.api_host.text().strip() or "127.0.0.1", int(self.api_port.value())
            )
            self.api_server.start()
            self.api_status.setText(
                "API starting - documentation: " + self.api_server.url + "/docs"
            )
        except Exception as exc:
            self.api_status.setText("Could not start the API server: " + str(exc))

    def _stop_api(self) -> None:
        if self.api_server is not None:
            self.api_server.stop()
            self.api_server = None
            self.api_status.setText("API server is stopped")

    def _change_password(self) -> None:
        dialog = ChangePasswordDialog(self.runtime, self.user)
        dialog.exec()

    def _logout(self) -> None:
        window = self.window()
        if hasattr(window, "logout"):
            window.logout()

    def _reset_counters(self) -> None:
        answer = QMessageBox.question(
            self, "Reset counters", "Reset the counters of every camera?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.runtime.reset_counters(None)
