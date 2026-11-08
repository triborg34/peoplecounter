"""Multi-object tracking.

Uses the Ultralytics ByteTrack implementation (persistent track ids).  Each
camera gets its own tracker instance so ids never leak between cameras.
A dependency free IoU tracker is used as a fallback when the ultralytics
internals are unavailable.
"""
from __future__ import annotations

import logging
from typing import Any, List, Optional, Sequence

import numpy as np

from .types import Detection, Track

log = logging.getLogger(__name__)


def _iou(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


class SimpleIoUTracker:
    """Minimal IoU tracker - fallback when ultralytics trackers are unusable."""

    def __init__(self, iou_threshold: float = 0.3, max_age: int = 30):
        self.iou_threshold = iou_threshold
        self.max_age = max_age
        self.next_id = 1
        self._tracks: List[dict] = []

    def update(self, detections: Sequence[Detection]) -> List[Track]:
        for track in self._tracks:
            track["age"] += 1
        assigned: List[Optional[Detection]] = [None] * len(self._tracks)
        for det in detections:
            best_iou, best_index = 0.0, -1
            for track_index, track in enumerate(self._tracks):
                if assigned[track_index] is not None:
                    continue
                score = _iou(track["bbox"], det.bbox)
                if score > best_iou:
                    best_iou, best_index = score, track_index
            if best_index >= 0 and best_iou >= self.iou_threshold:
                assigned[best_index] = det

        for track_index, det in enumerate(assigned):
            if det is None:
                continue
            track = self._tracks[track_index]
            track["bbox"] = list(det.bbox)
            track["conf"] = det.confidence
            track["age"] = 0

        for det in detections:
            if any(det is d for d in assigned):
                continue
            self._tracks.append(
                {"id": self.next_id, "bbox": list(det.bbox), "conf": det.confidence, "age": 0}
            )
            self.next_id += 1

        alive = []
        result: List[Track] = []
        for track in self._tracks:
            if track["age"] > self.max_age:
                continue
            alive.append(track)
            result.append(
                Track(
                    track_id=int(track["id"]),
                    bbox=tuple(track["bbox"]),  # type: ignore[arg-type]
                    confidence=float(track.get("conf", 0.0)),
                )
            )
        self._tracks = alive
        return result


class ByteTrackWrapper:
    """Thin adapter around the ultralytics BYTETracker.

    The ultralytics tracker interface changed between releases, therefore
    several call strategies are tried and the working one is remembered.
    """

    def __init__(self, frame_rate: int = 30, track_buffer: int = 30, conf: float = 0.25):
        self.frame_rate = max(1, int(frame_rate))
        self._tracker = None
        self._fallback = SimpleIoUTracker()
        self._backend = "iou"
        self._strategy = "boxes"
        try:
            from types import SimpleNamespace

            from ultralytics.trackers.byte_tracker import BYTETracker

            args = SimpleNamespace(
                tracker_type="bytetrack",
                tracker_budget=30,
                track_buffer=int(track_buffer),
                track_high_thresh=max(0.35, conf),
                track_low_thresh=max(0.1, conf * 0.5),
                new_track_thresh=max(0.4, conf),
                match_thresh=0.8,
                fuse_score=False,
                match_focal_loss=False,
                with_reid=False,
                reid_weights="",
                proximity_thresh=0.5,
                visualise=False,
                augment=False,
                classes=None,
                conf=conf,
                iou=0.7,
                agnostic_nms=False,
                max_det=300,
                frame_rate=self.frame_rate,
            )
            try:
                self._tracker = BYTETracker(args)
            except TypeError:
                # older releases expect the frame rate as a separate argument
                self._tracker = BYTETracker(args, frame_rate=self.frame_rate)
            self._backend = "bytetrack"
            log.info("ByteTrack initialised (buffer=%d, fps=%d)", track_buffer, self.frame_rate)
        except Exception as exc:
            log.warning("ByteTrack unavailable (%s) - using IoU fallback tracker", exc)

    @property
    def backend(self) -> str:
        return self._backend

    def update(self, detections: Sequence[Detection], frame: Optional[np.ndarray] = None) -> List[Track]:
        if self._tracker is None:
            return self._fallback.update(detections)
        try:
            return self._update_bytetrack(detections, frame)
        except Exception as exc:
            log.warning("ByteTrack update failed (%s) - using IoU fallback tracker", exc)
            self._tracker = None
            self._backend = "iou"
            return self._fallback.update(detections)

    def _update_bytetrack(self, detections: Sequence[Detection], frame: Optional[np.ndarray]) -> List[Track]:
        import torch

        if detections:
            arr = np.array(
                [[d.bbox[0], d.bbox[1], d.bbox[2], d.bbox[3], d.confidence, float(d.class_id)] for d in detections],
                dtype=np.float32,
            )
        else:
            arr = np.zeros((0, 6), dtype=np.float32)
        tensor = torch.from_numpy(arr).reshape(-1, 6)

        output = None
        if self._strategy in ("boxes", "results"):
            try:
                from ultralytics.engine.results import Boxes, Results

                orig = frame if frame is not None else np.zeros((2, 2, 3), dtype=np.uint8)
                height, width = orig.shape[:2]
                try:
                    boxes = Boxes(tensor, (height, width))
                except TypeError:  # releases without orig_shape
                    boxes = Boxes(tensor)
                if self._strategy == "boxes":
                    output = self._tracker.update(boxes, frame)
                else:
                    try:
                        results = Results(orig_img=orig, path="", names={0: "person"}, boxes=boxes)
                    except TypeError:  # releases without the path argument
                        results = Results(orig_img=orig, names={0: "person"}, boxes=boxes)
                    output = self._tracker.update(results, frame)
            except Exception as exc:
                if self._strategy == "boxes":
                    log.debug("ByteTrack boxes strategy failed (%s), trying results", exc)
                    self._strategy = "results"
                    return self._update_bytetrack(detections, frame)
                raise
        if output is None:
            output = self._tracker.update(tensor, frame)

        rows: List[Sequence[float]] = []
        if output is None:
            rows = []
        elif isinstance(output, np.ndarray):
            rows = list(output)
        else:  # some releases return a list of arrays
            for item in output:
                if isinstance(item, np.ndarray):
                    rows.extend(list(item))
                elif item is not None:
                    rows.extend(list(np.asarray(item).reshape(-1, 8)))

        tracks: List[Track] = []
        for row in rows:
            values = list(row) + [0.0] * (8 - len(row))
            x1, y1, x2, y2, track_id, score, cls = values[:7]
            tracks.append(
                Track(
                    track_id=int(track_id),
                    bbox=(float(x1), float(y1), float(x2), float(y2)),
                    confidence=float(score),
                    class_id=int(cls),
                )
            )
        return tracks


class TrackerFactory:
    """Creates one tracker per camera."""

    def __init__(self, conf: float = 0.25):
        self.conf = conf

    def create(self, camera_id: int, fps: float = 30.0) -> ByteTrackWrapper:
        return ByteTrackWrapper(frame_rate=int(max(5, round(fps or 30))), conf=self.conf)
