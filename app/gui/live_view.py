"""Live view: grid of camera tiles plus the global summary bar."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..services import auth as auth_service
from .camera_tile import CameraTile

log = logging.getLogger(__name__)

LAYOUTS = {1: (1, 1), 2: (2, 2), 3: (3, 3), 4: (4, 4)}


class SummaryBar(QFrame):
    """Global totals across every camera plus a per camera breakdown."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SummaryBar")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)

        top = QHBoxLayout()
        title = QLabel("GLOBAL TOTALS")
        title.setObjectName("Muted")
        top.addWidget(title)
        top.addStretch(1)
        self.in_label = self._make_value(top, "IN")
        self.out_label = self._make_value(top, "OUT")
        self.total_label = self._make_value(top, "TOTAL")
        self.occupancy_label = self._make_value(top, "OCCUPANCY")
        layout.addLayout(top)

        self.breakdown_label = QLabel("No cameras yet")
        self.breakdown_label.setObjectName("Muted")
        self.breakdown_label.setWordWrap(True)
        layout.addWidget(self.breakdown_label)

    def _make_value(self, layout, caption: str) -> QLabel:
        box = QWidget()
        row = QHBoxLayout(box)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(6)
        value = QLabel("0")
        value.setObjectName("SummaryValue")
        row.addWidget(value)
        row.addWidget(QLabel(caption))
        layout.addWidget(box)
        return value

    def update_counts(self, summary: Dict[str, int], per_camera: Optional[List[dict]] = None) -> None:
        self.in_label.setText(str(summary.get("in", 0)))
        self.out_label.setText(str(summary.get("out", 0)))
        self.total_label.setText(str(summary.get("total", 0)))
        self.occupancy_label.setText(str(summary.get("occupancy", 0)))
        if per_camera:
            parts = []
            for entry in per_camera:
                parts.append(
                    "{name}: IN {in} / OUT {out} / TOT {total} / OCC {occ}".format(
                        name=entry.get("name", "camera " + str(entry.get("camera_id"))),
                        **{k: entry.get(k, 0) for k in ("in", "out", "total")},
                        occ=entry.get("occupancy", 0),
                    )
                )
            self.breakdown_label.setText("   |   ".join(parts))
        else:
            self.breakdown_label.setText("No cameras yet")


class LiveView(QWidget):
    """The main live page."""

    openZoneEditor = pyqtSignal(int)
    openCameraDialog = pyqtSignal(int)

    def __init__(self, runtime, user, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.user = user
        self.tiles: Dict[int, CameraTile] = {}
        self._overlay_enabled: Dict[int, bool] = {}
        self._layout_key = 2

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Layout"))
        self.layout_combo = QComboBox()
        for key, label in ((1, "1 x 1"), (2, "2 x 2"), (3, "3 x 3"), (4, "4 x 4")):
            self.layout_combo.addItem(label, key)
        self.layout_combo.setCurrentIndex(1)
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        toolbar.addWidget(self.layout_combo)
        toolbar.addStretch(1)
        self.reset_button = QPushButton("Reset counters")
        self.reset_button.setObjectName("DangerButton")
        self.reset_button.setVisible(auth_service.can(self.user.role, auth_service.PERM_COUNTERS_RESET))
        self.reset_button.clicked.connect(self._reset_counters)
        toolbar.addWidget(self.reset_button)
        root.addLayout(toolbar)

        self.summary_bar = SummaryBar()
        root.addWidget(self.summary_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

    # -- cameras ---------------------------------------------------------
    def set_cameras(self, cameras: List[dict]) -> None:
        """(Re)build the tiles for the given camera list."""
        existing = set(self.tiles.keys())
        wanted = {camera["id"] for camera in cameras}
        for camera_id in list(existing - wanted):
            tile = self.tiles.pop(camera_id)
            self.grid.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()
        for camera in cameras:
            tile = self.tiles.get(camera["id"])
            if tile is None:
                tile = CameraTile(camera["id"], camera["name"])
                tile.fullscreenRequested.connect(self._toggle_fullscreen)
                tile.toggleOverlay.connect(self._set_overlay)
                self.tiles[camera["id"]] = tile
            else:
                tile.camera_name = camera["name"]
                tile.name_label.setText(camera["name"])
        self._rebuild_grid()

    def _rebuild_grid(self) -> None:
        for tile in self.tiles.values():
            self.grid.removeWidget(tile)
        rows, columns = LAYOUTS.get(self._layout_key, (2, 2))
        for index, tile in enumerate(self.tiles.values()):
            self.grid.addWidget(tile, index // columns, index % columns)
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.grid.setRowStretch(0, 1)

    def _on_layout_changed(self, index: int) -> None:
        self._layout_key = self.layout_combo.itemData(index)
        self._rebuild_grid()

    # -- live updates ----------------------------------------------------
    def on_frame(self, camera_id: int, image: QImage) -> None:
        tile = self.tiles.get(camera_id)
        if tile is not None:
            tile.set_image(image)

    def on_camera_counts(self, camera_id: int, counts: dict) -> None:
        tile = self.tiles.get(camera_id)
        if tile is not None:
            tile.set_counts(counts)

    def on_status(self, camera_id: int, status: str) -> None:
        tile = self.tiles.get(camera_id)
        if tile is not None:
            tile.set_status(status)

    def update_global(self, summary: dict) -> None:
        snapshot = self.runtime.counts_snapshot()
        self.summary_bar.update_counts(summary, snapshot.get("per_camera"))

    # -- actions ---------------------------------------------------------
    def _set_overlay(self, camera_id: int, enabled: bool) -> None:
        self._overlay_enabled[camera_id] = enabled
        camera = self.runtime.camera_manager.workers.get(camera_id)
        if camera is not None:
            camera.source.detection_enabled = enabled
        packet = self.runtime.camera_manager.latest_packet(camera_id)
        if packet is not None:
            self.runtime.camera_manager._process_camera(
                camera_id, packet.raw_frame, packet.timestamp, packet.detections
            )

    def _toggle_fullscreen(self, camera_id: int) -> None:
        tile = self.tiles.get(camera_id)
        if tile is None:
            return
        if tile.parent() is self.grid_host:
            self._fullscreen_tile = tile
            tile.setParent(None)
            self.layout().addWidget(tile)
            tile.raise_()
        else:
            tile.setParent(self.grid_host)
            self._rebuild_grid()

    def _reset_counters(self) -> None:
        answer = QMessageBox.question(
            self,
            "Reset counters",
            "Reset the counters of every camera? The stored counting events are deleted too.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.runtime.reset_counters(None)
        self.update_global(self.runtime.counts_snapshot()["global"])
