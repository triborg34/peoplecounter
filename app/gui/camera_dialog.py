"""Add / edit camera dialog with manual fields, direct url and video file modes."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..engine.sources import describe_source, parse_source
from ..services.cameras import test_connection

log = logging.getLogger(__name__)


class CameraDialog(QDialog):
    """Dialog with three source modes: manual, direct RTSP url and video file."""

    def __init__(self, runtime, camera=None, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.camera = camera
        self.setWindowTitle("Edit camera" if camera else "Add camera")
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)

        common = QFormLayout()
        self.name_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.enabled_check = QCheckBox("Camera enabled")
        self.enabled_check.setChecked(True)
        self.detection_check = QCheckBox("Run person detection on this camera")
        self.detection_check.setChecked(True)
        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.5, 60.0)
        self.fps_spin.setValue(10.0)
        self.fps_spin.setSuffix(" fps")
        common.addRow("Name", self.name_edit)
        common.addRow("Location", self.location_edit)
        common.addRow("Frame rate", self.fps_spin)
        common.addRow("", self.enabled_check)
        common.addRow("", self.detection_check)
        root.addLayout(common)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_manual_tab(), "Manual (IP / user / pass)")
        self.tabs.addTab(self._build_url_tab(), "Direct RTSP URL")
        self.tabs.addTab(self._build_file_tab(), "Video file (simulation)")
        root.addWidget(self.tabs)

        # preview / test
        preview_row = QHBoxLayout()
        self.preview_label = QLabel("no preview")
        self.preview_label.setFixedSize(240, 135)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet(
            "background-color: #0f1115; border-radius: 6px; color: #8b95a5;"
        )
        preview_row.addWidget(self.preview_label)
        buttons_col = QVBoxLayout()
        self.test_button = QPushButton("Test connection")
        self.test_button.clicked.connect(self._test_connection)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("Muted")
        buttons_col.addWidget(self.test_button)
        buttons_col.addWidget(self.status_label)
        buttons_col.addStretch(1)
        preview_row.addLayout(buttons_col, 1)
        root.addLayout(preview_row)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_button = QPushButton("Save")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._validate)
        action_row.addWidget(cancel)
        action_row.addWidget(self.save_button)
        root.addLayout(action_row)

        if camera is not None:
            self._load_camera(camera)

    # -- tabs ------------------------------------------------------------
    def _build_manual_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("192.168.1.64")
        self.port_spin = QComboBox()
        self.port_spin.setEditable(True)
        for port in (554, 8554, 80, 443):
            self.port_spin.addItem(str(port))
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("leave empty to keep the stored password")
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("/stream1")
        form.addRow("IP address", self.host_edit)
        form.addRow("Port", self.port_spin)
        form.addRow("Username", self.username_edit)
        form.addRow("Password", self.password_edit)
        form.addRow("RTSP path", self.path_edit)
        return page

    def _build_url_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Paste the full stream url (credentials are stored encrypted):"))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("rtsp://user:password@192.168.1.64:554/stream1")
        layout.addWidget(self.url_edit)
        parse_button = QPushButton("Fill from url")
        parse_button.clicked.connect(self._fill_from_url)
        layout.addWidget(parse_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _build_file_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(
            QLabel("Use a video file as source - perfect for testing without a real camera.")
        )
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("C:/videos/people.mp4")
        layout.addWidget(self.file_edit)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_file)
        layout.addWidget(browse, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        return page

    def _browse_file(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Select a video file", "", "Videos (*.mp4 *.avi *.mkv *.mov *.webm)"
        )
        if path:
            self.file_edit.setText(path)
            self.tabs.setCurrentIndex(2)

    # -- loading ---------------------------------------------------------
    def _load_camera(self, camera) -> None:
        self.name_edit.setText(camera.name)
        self.location_edit.setText(camera.location or "")
        self.enabled_check.setChecked(camera.enabled)
        self.detection_check.setChecked(camera.detection_enabled)
        self.fps_spin.setValue(camera.fps_limit or 10.0)
        if camera.source_type == "file":
            self.tabs.setCurrentIndex(2)
            self.file_edit.setText(camera.file_path or "")
            return
        self.host_edit.setText(camera.host or "")
        self.port_spin.setCurrentText(str(camera.port or 554))
        self.username_edit.setText(camera.username or "")
        self.path_edit.setText(camera.rtsp_path or "")
        if camera.rtsp_url:
            self.tabs.setCurrentIndex(1)
            self.url_edit.setText(camera.rtsp_url)

    def _fill_from_url(self) -> None:
        url = self.url_edit.text().strip()
        if not url:
            return
        parsed = parse_source(url)
        self.host_edit.setText(parsed.host)
        self.port_spin.setCurrentText(str(parsed.port or 554))
        self.username_edit.setText(parsed.username or "")
        self.path_edit.setText(parsed.path or "")
        self.status_label.setText("Parsed: " + describe_source(url))

    # -- actions ---------------------------------------------------------
    def current_mode(self) -> str:
        return ("manual", "url", "file")[self.tabs.currentIndex()]

    def _test_connection(self) -> None:
        try:
            url, source_type = self._resolve_source()
        except Exception as exc:
            self.status_label.setText(str(exc))
            return
        if not url:
            self.status_label.setText("Please fill in the connection details first.")
            return
        self.status_label.setText("Testing connection...")
        self.test_button.setEnabled(False)
        from PyQt6.QtWidgets import QApplication

        QApplication.processEvents()
        result = test_connection(url, source_type)
        self.test_button.setEnabled(True)
        self.status_label.setText(result.get("message", ""))
        if result.get("ok"):
            self.status_label.setText(
                "Connection successful - {w}x{h} @ {fps:.1f} fps".format(
                    w=result.get("width", 0), h=result.get("height", 0), fps=result.get("fps", 0.0)
                )
            )

    def _resolve_source(self):
        mode = self.current_mode()
        if mode == "file":
            return self.file_edit.text().strip(), "file"
        if mode == "url":
            url = self.url_edit.text().strip()
            if not url:
                raise ValueError("Please enter an RTSP url.")
            return url, "rtsp"
        host = self.host_edit.text().strip()
        if not host:
            raise ValueError("Please enter the camera IP address.")
        port = self.port_spin.currentText().strip() or "554"
        from ..engine.sources import build_rtsp_url

        url = build_rtsp_url(
            host,
            int(port) if port.isdigit() else 554,
            self.username_edit.text().strip() or None,
            self.password_edit.text() or None,
            self.path_edit.text().strip(),
        )
        return url, "rtsp"

    def _validate(self) -> None:
        if not self.name_edit.text().strip():
            self.status_label.setText("Please enter a camera name.")
            return
        try:
            self._resolve_source()
        except Exception as exc:
            self.status_label.setText(str(exc))
            return
        self.accept()

    def values(self) -> dict:
        """The collected form values (used by the caller to persist)."""
        mode = self.current_mode()
        port_text = self.port_spin.currentText().strip()
        data = {
            "name": self.name_edit.text().strip(),
            "location": self.location_edit.text().strip(),
            "enabled": self.enabled_check.isChecked(),
            "detection_enabled": self.detection_check.isChecked(),
            "fps_limit": float(self.fps_spin.value()),
            "mode": mode,
            "host": self.host_edit.text().strip(),
            "port": int(port_text) if port_text.isdigit() else 554,
            "username": self.username_edit.text().strip() or None,
            "password": self.password_edit.text() or None,
            "rtsp_path": self.path_edit.text().strip(),
            "url": self.url_edit.text().strip() or None,
            "file_path": self.file_edit.text().strip() or None,
        }
        return data
