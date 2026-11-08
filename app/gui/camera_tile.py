"""A single camera tile: header with status and counters plus the video."""
from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

STATUS_COLORS = {
    "online": "#22c55e",
    "offline": "#ef4444",
    "reconnecting": "#f59e0b",
    "starting": "#eab308",
    "stopped": "#6b7280",
}


class CameraTile(QWidget):
    """Shows the annotated video of one camera with its own counters."""

    toggleOverlay = pyqtSignal(int, bool)
    fullscreenRequested = pyqtSignal(int)

    def __init__(self, camera_id: int, name: str, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.camera_name = name
        self._image: Optional[QImage] = None
        self._status = "offline"
        self._counts = {"in": 0, "out": 0, "total": 0, "occupancy": 0}
        self.setMinimumSize(240, 180)
        self.setObjectName("CameraTile")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        self.status_dot.setStyleSheet("border-radius: 5px; background-color: #6b7280;")
        self.name_label = QLabel(name)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.counts_label = QLabel("IN 0  OUT 0  TOT 0  OCC 0")
        self.counts_label.setStyleSheet("color: #9aa4b2; font-size: 11px;")
        self.counts_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.status_dot)
        header.addWidget(self.name_label)
        header.addStretch(1)
        header.addWidget(self.counts_label)
        layout.addLayout(header)

        self.video = QLabel("waiting for frames...")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumHeight(140)
        self.video.setStyleSheet("background-color: #0f1115; border-radius: 6px; color: #8b95a5;")
        layout.addWidget(self.video, 1)

        footer = QHBoxLayout()
        self.overlay_toggle = QCheckBox("overlay")
        self.overlay_toggle.setChecked(True)
        self.overlay_toggle.toggled.connect(lambda value: self.toggleOverlay.emit(self.camera_id, value))
        self.overlay_toggle.setToolTip("Show detection boxes, tracks and counting lines")
        self.fullscreen_button = QPushButton("full screen")
        self.fullscreen_button.setFixedHeight(22)
        self.fullscreen_button.clicked.connect(lambda: self.fullscreenRequested.emit(self.camera_id))
        footer.addWidget(self.overlay_toggle)
        footer.addStretch(1)
        footer.addWidget(self.fullscreen_button)
        layout.addLayout(footer)

    # -- updates ---------------------------------------------------------
    def set_image(self, image: QImage) -> None:
        self._image = image
        self._repaint_video()

    def set_status(self, status: str) -> None:
        self._status = status
        color = STATUS_COLORS.get(status, "#6b7280")
        self.status_dot.setStyleSheet("border-radius: 5px; background-color: " + color + ";")
        self.status_dot.setToolTip("Camera status: " + status)

    def set_counts(self, counts: dict) -> None:
        self._counts = counts or {}
        self.counts_label.setText(
            "IN {in}  OUT {out}  TOT {total}  OCC {occupancy}".format(
                **{
                    "in": self._counts.get("in", 0),
                    "out": self._counts.get("out", 0),
                    "total": self._counts.get("total", 0),
                    "occupancy": self._counts.get("occupancy", 0),
                }
            )
        )

    def _repaint_video(self) -> None:
        if self._image is None:
            return
        scaled = self._image.scaled(
            self.video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        # setPixmap requires a QPixmap; QImage.scaled() returns a QImage
        self.video.setPixmap(QPixmap.fromImage(scaled))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._repaint_video()

    def mouseDoubleClickEvent(self, event):
        self.fullscreenRequested.emit(self.camera_id)
        super().mouseDoubleClickEvent(event)
