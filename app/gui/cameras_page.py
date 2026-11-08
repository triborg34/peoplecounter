"""Cameras page: add, edit, enable, disable and delete cameras."""
from __future__ import annotations

import logging
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db.models import Camera
from ..services import auth as auth_service
from .camera_dialog import CameraDialog

log = logging.getLogger(__name__)

COLUMNS = ("Name", "Location", "Source", "Status", "Enabled")


class CamerasPage(QWidget):
    """Inventory of all configured cameras."""

    def __init__(self, runtime, user, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user
        self._cameras: List[Camera] = []

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Cameras")
        title.setObjectName("HeaderTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.add_button = QPushButton("Add camera")
        self.add_button.setObjectName("PrimaryButton")
        self.add_button.clicked.connect(self._add_camera)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._edit_camera)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.clicked.connect(self._delete_camera)
        self.toggle_button = QPushButton("Enable / disable")
        self.toggle_button.clicked.connect(self._toggle_camera)
        self.zones_button = QPushButton("Lines and areas")
        self.zones_button.clicked.connect(self._edit_zones)
        for button in (self.add_button, self.edit_button, self.delete_button,
                       self.toggle_button, self.zones_button):
            header.addWidget(button)
        layout.addLayout(header)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(list(COLUMNS))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.doubleClicked.connect(lambda *_: self._edit_camera())
        layout.addWidget(self.table)

        self.hint = QLabel("Double click a row to edit the camera.")
        self.hint.setObjectName("Muted")
        layout.addWidget(self.hint)

        self._apply_permissions()

    def _apply_permissions(self) -> None:
        allowed = auth_service.can(self.user.role, auth_service.PERM_CAMERAS_MANAGE)
        for button in (self.add_button, self.edit_button, self.delete_button,
                       self.toggle_button, self.zones_button):
            button.setEnabled(allowed)

    def refresh(self) -> None:
        with self.runtime.db.session_scope() as session:
            self._cameras = session.query(Camera).order_by(Camera.name).all()
            rows = [
                (
                    camera.name,
                    camera.location or "",
                    camera.source_type,
                    camera.enabled,
                    camera.id,
                )
                for camera in self._cameras
            ]
        status_map = {info["camera_id"]: info for info in self.runtime.camera_manager.camera_status()}
        self.table.setRowCount(len(rows))
        for row, (name, location, source_type, enabled, camera_id) in enumerate(rows):
            info = status_map.get(camera_id, {})
            values = [
                name,
                location,
                source_type,
                info.get("status", "offline"),
                "yes" if enabled else "no",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, camera_id)
                self.table.setItem(row, column, item)

    def _selected_camera_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Cameras", "Please select a camera first.")
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # -- actions ---------------------------------------------------------
    def _add_camera(self) -> None:
        dialog = CameraDialog(self.runtime, None, self)
        if dialog.exec() != CameraDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        from ..services.cameras import camera_stream_url

        with self.runtime.db.session_scope() as session:
            if session.query(Camera).filter(Camera.name == values["name"]).first():
                QMessageBox.warning(self, "Cameras", "A camera with this name already exists.")
                return
            camera = Camera(
                name=values["name"],
                location=values["location"],
                fps_limit=values["fps_limit"],
                detection_enabled=values["detection_enabled"],
                enabled=values["enabled"],
            )
            self._apply_values(camera, values)
            session.add(camera)
            session.flush()
            camera_id = camera.id
        self.runtime.sync_camera(camera_id)
        self.refresh()

    def _apply_values(self, camera: Camera, values: dict) -> None:
        secret_box = self.runtime.secret_box
        mode = values["mode"]
        if mode == "file":
            camera.source_type = "file"
            camera.file_path = values["file_path"]
            camera.rtsp_url = None
            camera.host = None
            camera.username = None
            camera.password_enc = None
        elif mode == "url":
            from ..engine.sources import parse_source, strip_credentials

            parsed = parse_source(values["url"])
            camera.source_type = "rtsp"
            camera.rtsp_url = strip_credentials(values["url"])
            camera.host = parsed.host
            camera.port = parsed.port or 554
            camera.username = values["username"] or parsed.username
            camera.rtsp_path = parsed.path or ""
            if values["password"]:
                camera.password_enc = secret_box.encrypt(values["password"])
            elif parsed.password:
                camera.password_enc = secret_box.encrypt(parsed.password)
        else:
            camera.source_type = "rtsp"
            camera.host = values["host"]
            camera.port = values["port"]
            camera.username = values["username"]
            camera.rtsp_path = values["rtsp_path"]
            camera.rtsp_url = None
            camera.file_path = None
            if values["password"]:
                camera.password_enc = secret_box.encrypt(values["password"])

    def _edit_camera(self) -> None:
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        with self.runtime.db.session_scope() as session:
            camera = session.get(Camera, camera_id)
            if camera is None:
                return
            dialog = CameraDialog(self.runtime, camera, self)
            if dialog.exec() != CameraDialog.DialogCode.Accepted:
                return
            values = dialog.values()
            camera.name = values["name"]
            camera.location = values["location"]
            camera.enabled = values["enabled"]
            camera.detection_enabled = values["detection_enabled"]
            camera.fps_limit = values["fps_limit"]
            self._apply_values(camera, values)
        self.runtime.sync_camera(camera_id)
        self.refresh()

    def _toggle_camera(self) -> None:
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        with self.runtime.db.session_scope() as session:
            camera = session.get(Camera, camera_id)
            if camera is None:
                return
            camera.enabled = not camera.enabled
        self.runtime.sync_camera(camera_id)
        self.refresh()

    def _delete_camera(self) -> None:
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        answer = QMessageBox.question(
            self, "Delete camera", "Delete this camera and all its counting zones?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.runtime.remove_camera(camera_id)
        with self.runtime.db.session_scope() as session:
            camera = session.get(Camera, camera_id)
            if camera is not None:
                session.delete(camera)
        self.refresh()

    def _edit_zones(self) -> None:
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        window = self.window()
        if hasattr(window, "open_zone_editor"):
            window.open_zone_editor(camera_id)
