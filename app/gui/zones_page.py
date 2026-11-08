"""Overview of the counting lines and areas of every camera."""
from __future__ import annotations

import logging

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db.models import Camera, CounterArea, CounterLine

log = logging.getLogger(__name__)


class ZonesPage(QWidget):
    """Lists cameras with their lines and areas and opens the editor."""

    def __init__(self, runtime, user, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Lines and areas")
        title.setObjectName("HeaderTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.edit_button = QPushButton("Open editor")
        self.edit_button.clicked.connect(self._open_editor)
        header.addWidget(self.edit_button)
        layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Camera", "Lines", "Areas", "IN", "OUT"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        self.hint = QLabel(
            "Select a camera and press 'Open editor' to draw lines (click A then B) "
            "or areas (click points, double click to close)."
        )
        self.hint.setObjectName("Muted")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

    def refresh(self) -> None:
        with self.runtime.db.session_scope() as session:
            cameras = session.query(Camera).order_by(Camera.name).all()
            rows = []
            for camera in cameras:
                lines = session.query(CounterLine).filter(CounterLine.camera_id == camera.id).count()
                areas = session.query(CounterArea).filter(CounterArea.camera_id == camera.id).count()
                rows.append((camera.id, camera.name, lines, areas))
        self.table.setRowCount(len(rows))
        for row, (camera_id, name, lines, areas) in enumerate(rows):
            counts = self.runtime.camera_manager.counter.camera_summary(camera_id)
            values = [name, str(lines), str(areas), str(counts.get("in", 0)), str(counts.get("out", 0))]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, camera_id)
                self.table.setItem(row, column, item)

    def _open_editor(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        camera_id = item.data(Qt.ItemDataRole.UserRole)
        window = self.window()
        if hasattr(window, "open_zone_editor"):
            window.open_zone_editor(camera_id)
