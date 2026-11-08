"""YOLO person detector.

A single model instance is shared by every camera.  Frames coming from
different cameras are handed to the model as one batch, so several cameras are
inferred in a single forward pass.

If CUDA is available it is used automatically; otherwise the detector falls
back to the CPU.  If the weights cannot be loaded at all the detector stays
available but returns no detections, so the rest of the application keeps
working.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

from ..config import Settings, get_settings
from .types import Detection

log = logging.getLogger(__name__)


class Detector:
    """Thread safe wrapper around the Ultralytics YOLO model."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.device = self.settings.resolved_device
        self.imgsz = int(self.settings.imgsz)
        self.confidence = float(self.settings.confidence)
        self.iou = float(self.settings.iou)
        self.class_id = int(self.settings.person_class_id)
        self._model: Any = None
        self._lock = threading.Lock()
        self._available = False
        self._error: str = ""
        self._frames_seen = 0

    # -- lifecycle ------------------------------------------------------
    @property
    def available(self) -> bool:
        return self._available

    @property
    def error(self) -> str:
        return self._error

    def load(self) -> bool:
        """Load the model. Returns True on success."""
        with self._lock:
            if self._model is not None:
                return self._available
            try:
                from ultralytics import YOLO

                model_path = self._resolve_model_path()
                log.info("Loading YOLO model %s on %s", model_path, self.device)
                model = YOLO(str(model_path))
                try:
                    model.fuse()
                except Exception:  # pragma: no cover - optional optimisation
                    pass
                self._model = model
                self._available = True
                self._error = ""
                log.info("YOLO model ready (device=%s, imgsz=%d)", self.device, self.imgsz)
            except Exception as exc:
                self._available = False
                self._error = str(exc)
                log.error("Failed to load detection model: %s", exc)
            return self._available

    def _resolve_model_path(self) -> Path:
        name = self.settings.model_name
        candidate = Path(name)
        if candidate.exists():
            return candidate
        models_dir = Path(self.settings.data_dir) / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir / Path(name).name

    # -- inference ------------------------------------------------------
    def detect(self, frames: Sequence[np.ndarray]) -> List[List[Detection]]:
        """Detect persons in a batch of frames (one list of detections per frame)."""
        frames = [f for f in frames if f is not None]
        if not frames:
            return []
        if not self._available and not self.load():
            return [[] for _ in frames]
        with self._lock:
            self._frames_seen += len(frames)
            try:
                return self._detect_batch(frames)
            except Exception as exc:
                log.warning("Batched inference failed (%s), falling back to single frames", exc)
                try:
                    return self._detect_single_loop(frames)
                except Exception:
                    log.exception("Inference failed")
                    return [[] for _ in frames]

    def _detect_batch(self, frames: Sequence[np.ndarray]) -> List[List[Detection]]:
        """One forward pass for all frames of the batch."""
        outcome = self._model.predict(
            list(frames),
            imgsz=self.imgsz,
            conf=self.confidence,
            iou=self.iou,
            classes=[self.class_id],
            device=self.device,
            verbose=False,
        )
        if not isinstance(outcome, (list, tuple)):
            outcome = [outcome]
        results = [self._extract(item) for item in outcome]
        while len(results) < len(frames):
            results.append([])
        return results[: len(frames)]

    def _detect_single_loop(self, frames: Sequence[np.ndarray]) -> List[List[Detection]]:
        results: List[List[Detection]] = []
        for frame in frames:
            outcome = self._model.predict(
                frame,
                imgsz=self.imgsz,
                conf=self.confidence,
                iou=self.iou,
                classes=[self.class_id],
                device=self.device,
                verbose=False,
            )
            results.append(self._extract(outcome))
        return results

    @staticmethod
    def _extract(outcome: Any) -> List[Detection]:
        """Turn an ultralytics result into a list of detections."""
        if outcome is None:
            return []
        if isinstance(outcome, (list, tuple)):
            for item in outcome:
                found = Detector._extract(item)
                if found:
                    return found
            return []
        boxes = getattr(outcome, "boxes", None)
        if boxes is None:
            return []
        try:
            if len(boxes) == 0:
                return []
            xyxy = boxes.xyxy.cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            classes = boxes.cls.cpu().numpy()
        except Exception:  # pragma: no cover - unexpected result layout
            log.exception("Could not read the detection boxes")
            return []
        items: List[Detection] = []
        for (x1, y1, x2, y2), conf, cls in zip(xyxy, confs, classes):
            items.append(
                Detection(
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    confidence=float(conf),
                    class_id=int(cls),
                )
            )
        return items

    @property
    def stats(self) -> dict:
        return {
            "available": self._available,
            "frames": self._frames_seen,
            "device": self.device,
            "error": self._error,
        }
