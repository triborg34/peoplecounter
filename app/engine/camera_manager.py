"""Owns every camera worker plus the shared detector, tracker and counter."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..config import Settings, get_settings
from .shutdown import parallel_stop
from ..db.session import Database
from .camera_worker import CameraSource, FrameBus, CameraWorker
from .counter import CountingEngine
from .detector import Detector
from .event_queue import EventWriter
from .annotator import draw_frame
from .tracker import TrackerFactory
from .types import AreaSpec, CountEvent, FramePacket, LineSpec, TrackedPoint

log = logging.getLogger(__name__)


class CameraManager:
    """Runs the capture + inference pipeline for every enabled camera."""

    def __init__(
        self,
        db: Database,
        event_writer: EventWriter,
        settings: Optional[Settings] = None,
        detector: Optional[Detector] = None,
        bus: Optional[FrameBus] = None,
    ):
        self.db = db
        self.event_writer = event_writer
        self.settings = settings or get_settings()
        self.detector = detector or Detector(self.settings)
        self.bus = bus or FrameBus()
        self.counter = CountingEngine(point_mode=self.settings.track_point)
        self.trackers: Dict[int, object] = {}
        self.workers: Dict[int, CameraWorker] = {}
        self.latest: Dict[int, FramePacket] = {}
        self._lock = threading.RLock()
        self._seq = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._count_listeners: List[Callable[[CountEvent], None]] = []
        self._sources: Dict[int, Tuple[str, str, str]] = {}

    # -- configuration --------------------------------------------------
    def register_source(self, camera_id: int, name: str, source_type: str, url: str) -> None:
        with self._lock:
            self._sources[camera_id] = (name, source_type, url)

    def unregister(self, camera_id: int) -> None:
        self.stop_camera(camera_id)
        with self._lock:
            self.workers.pop(camera_id, None)
            self.trackers.pop(camera_id, None)
            self.latest.pop(camera_id, None)
            self._sources.pop(camera_id, None)
        self.bus.clear_camera(camera_id)

    def set_zones(self, camera_id: int, lines: List[LineSpec], areas: List[AreaSpec]) -> None:
        with self._lock:
            self.counter.set_camera_zones(camera_id, lines, areas)

    def add_count_listener(self, callback: Callable[[CountEvent], None]) -> None:
        self._count_listeners.append(callback)

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.detector.load()
        self._thread = threading.Thread(target=self._inference_loop, name="inference", daemon=True)
        self._thread.start()
        log.info("Camera manager started")

    def stop(self, timeout: float = 8.0) -> None:
        self._running = False
        workers: List[CameraWorker] = []
        with self._lock:
            workers = list(self.workers.values())
        parallel_stop(workers, per_timeout=2.0, max_total=timeout)
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        log.info("Camera manager stopped")

    def start_camera(self, source: CameraSource) -> None:
        with self._lock:
            worker = self.workers.get(source.camera_id)
            if worker is None:
                worker = CameraWorker(source, self.bus, self.settings, on_status=self._on_camera_status)
                self.workers[source.camera_id] = worker
            else:
                worker.source = source
                worker.restart()
            if source.camera_id not in self.trackers:
                self.trackers[source.camera_id] = TrackerFactory(
                    self.settings.confidence
                ).create(source.camera_id)
        worker.start()

    def stop_camera(self, camera_id: int) -> None:
        with self._lock:
            worker = self.workers.get(camera_id)
        if worker:
            worker.stop(timeout=2.0)

    def _on_camera_status(self, camera_id: int, status: str, error: str) -> None:
        log.info("Camera %s status -> %s %s", camera_id, status, error)

    # -- inference ------------------------------------------------------
    def _inference_loop(self) -> None:
        while self._running:
            try:
                batch = self.bus.collect_batch(
                    max_batch=max(1, int(self.settings.batch_size)),
                    window_s=max(0.005, self.settings.batch_window_ms / 1000.0),
                )
                if not batch:
                    continue
                self._process_batch(batch)
            except Exception:  # pragma: no cover - the loop must never die
                log.exception("Inference loop error")
                time.sleep(0.1)

    def _process_batch(self, batch) -> None:
        # Only the newest frame per camera is processed.
        newest: Dict[int, tuple] = {}
        for camera_id, frame, ts in batch:
            previous = newest.get(camera_id)
            if previous is None or ts >= previous[1]:
                newest[camera_id] = (frame, ts)

        camera_ids = list(newest.keys())
        frames = [newest[cid][0] for cid in camera_ids]

        detections: List[List] = [[] for _ in frames]
        if self.detector.available:
            try:
                detections = self.detector.detect(frames)
            except Exception:
                log.exception("Detection failed")

        for index, camera_id in enumerate(camera_ids):
            frame, ts = newest[camera_id]
            found = detections[index] if index < len(detections) else []
            self._process_camera(camera_id, frame, ts, found)

    def _process_camera(self, camera_id: int, frame: np.ndarray, ts: float, dets: List) -> None:
        with self._lock:
            worker = self.workers.get(camera_id)
            tracker = self.trackers.get(camera_id)
            if tracker is None:
                tracker = TrackerFactory(self.settings.confidence).create(camera_id)
                self.trackers[camera_id] = tracker

        # only humans are counted - every other class is dropped here
        person_class = int(self.settings.person_class_id)
        dets = [d for d in dets if int(getattr(d, "class_id", 0)) == person_class]

        tracks = tracker.update(dets, frame) if dets else []

        height, width = frame.shape[:2]
        points = []
        for track in tracks:
            if self.settings.track_point == "center":
                px, py = track.center
            else:
                px, py = track.bottom_center
            points.append(
                TrackedPoint(
                    track_id=track.track_id,
                    x=px / max(1, width),
                    y=py / max(1, height),
                    confidence=track.confidence,
                    bbox=track.bbox,
                )
            )

        events = self.counter.update(camera_id, points, now=ts)
        for event in events:
            with self._lock:
                info = self._sources.get(camera_id)
            if info:
                event.camera_name = info[0]
            self.event_writer.submit(event)
            self._notify(event)

        counters = {key: totals.to_dict() for key, totals in self.counter.counters(camera_id).items()}
        status = worker.status if worker else "offline"
        annotated = draw_frame(
            frame,
            tracks,
            lines=self.counter.lines,
            areas=self.counter.areas,
            counters=counters,
            status=status,
            show_overlay=True,
        )

        with self._lock:
            self._seq += 1
            self.latest[camera_id] = FramePacket(
                camera_id=camera_id,
                frame=annotated,
                raw_frame=frame,
                timestamp=ts,
                seq=self._seq,
                detections=list(dets),
                tracks=list(tracks),
                fps=worker.fps if worker else 0.0,
                status=status,
                width=width,
                height=height,
            )

    def _notify(self, event: CountEvent) -> None:
        for listener in list(self._count_listeners):
            try:
                listener(event)
            except BaseException:  # pragma: no cover
                log.exception("count listener failed")

    # -- accessors ------------------------------------------------------
    def latest_packet(self, camera_id: int) -> Optional[FramePacket]:
        with self._lock:
            return self.latest.get(camera_id)

    def latest_frame(self, camera_id: int) -> Optional[np.ndarray]:
        packet = self.latest_packet(camera_id)
        return packet.frame if packet else None

    def raw_frame(self, camera_id: int) -> Optional[np.ndarray]:
        packet = self.latest_packet(camera_id)
        return packet.raw_frame if packet else None

    def camera_status(self) -> List[dict]:
        with self._lock:
            workers = dict(self.workers)
        result = []
        for camera_id, worker in workers.items():
            item = worker.info()
            item["source_type"] = worker.source.source_type
            item["detection_enabled"] = worker.source.detection_enabled
            result.append(item)
        return result

    def counts(self) -> dict:
        return self.counter.global_summary()
