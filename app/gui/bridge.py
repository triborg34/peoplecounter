"""Bridges the headless engine into Qt signals.

The GUI never blocks: a timer polls the latest frames and the engine pushes
count events through signals (queued across threads by Qt).
"""
from __future__ import annotations

import logging
import sys
from typing import Dict, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

log = logging.getLogger(__name__)


class EngineBridge(QObject):
    """Emits Qt signals for frames, counters and camera status."""

    frameReady = pyqtSignal(int, object)        # camera_id, QImage
    countsChanged = pyqtSignal(dict)             # global summary
    cameraCountsChanged = pyqtSignal(int, dict)  # camera_id, summary
    countEvent = pyqtSignal(dict)                # serialised count event
    cameraStatusChanged = pyqtSignal(int, str)   # camera_id, status
    detectorStatus = pyqtSignal(bool, str)       # available, message

    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self._last_seq: Dict[int, int] = {}
        self._last_status: Dict[int, str] = {}
        runtime.subscribe_counts(self._on_count_event)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(100)  # 10 fps

    def stop(self) -> None:
        """Stop polling (called when the window is closed)."""
        self._timer.stop()

    # -- engine callbacks ------------------------------------------------
    def _on_count_event(self, event) -> None:
        try:
            self.countEvent.emit(event.to_dict())
        except BaseException as exc:  # pragma: no cover
            log.exception("Failed to forward count event")
            if isinstance(exc, KeyboardInterrupt):
                self._request_quit()

    @staticmethod
    def _request_quit() -> None:
        """Ctrl+C / SIGINT during a slot: exit the GUI loop cleanly instead of
        letting the KeyboardInterrupt (a BaseException, so the usual
        ``except Exception`` does not catch it) kill the app mid-poll."""
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # -- polling ---------------------------------------------------------
    def _poll(self) -> None:
        runtime = self.runtime
        try:
            snapshot = runtime.counts_snapshot()
            for packet in list(runtime.camera_manager.latest.values()):
                if packet.seq == self._last_seq.get(packet.camera_id):
                    continue
                self._last_seq[packet.camera_id] = packet.seq
                image = self._to_image(packet.frame)
                if image is not None:
                    self.frameReady.emit(packet.camera_id, image)
                status = packet.status
                if self._last_status.get(packet.camera_id) != status:
                    self._last_status[packet.camera_id] = status
                    self.cameraStatusChanged.emit(packet.camera_id, status)
            self.countsChanged.emit(snapshot["global"])
            for entry in snapshot["per_camera"]:
                self.cameraCountsChanged.emit(entry["camera_id"], entry)
        except BaseException as exc:  # pragma: no cover - guard the event loop
            log.exception("Engine bridge poll failed")
            if isinstance(exc, KeyboardInterrupt):
                self._request_quit()

    @staticmethod
    def _to_image(frame) -> Optional[object]:
        if frame is None:
            return None
        try:
            import cv2
            from PyQt6.QtGui import QImage

            height, width = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return QImage(rgb.data, width, height, 3 * width, QImage.Format.Format_RGB888).copy()
        except Exception:  # pragma: no cover
            log.exception("Frame conversion failed")
            return None
