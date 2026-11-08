"""The engine runtime: one shared instance used by the GUI and the API.

The runtime owns the detector, the camera manager and the database writer.
It is completely free of any GUI or HTTP dependency so it can run headless.
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Dict, List, Optional

from ..config import Settings, get_settings
from ..crypto import SecretBox
from ..db.session import Database
from .camera_manager import CameraManager
from .camera_worker import CameraSource
from .detector import Detector
from .event_queue import EventWriter
from .sources import build_rtsp_url, parse_source, strip_credentials
from .types import AreaSpec, CountEvent, LineSpec

log = logging.getLogger(__name__)


class EngineRuntime:
    """Owns every long lived engine object."""

    def __init__(self, settings: Optional[Settings] = None, db: Optional[Database] = None):
        self.settings = settings or get_settings()
        self.db = db or Database()
        self.secret_box = SecretBox(self.settings.secret_key)
        self.detector = Detector(self.settings)
        self.event_writer = EventWriter(self.db, on_persist=self._on_persisted)
        self.camera_manager = CameraManager(
            self.db, self.event_writer, self.settings, self.detector
        )
        self._listeners: List[Callable[[CountEvent], None]] = []
        # stop signals of the running API WebSocket loops (see server.stop)
        self.api_ws_loops: List[object] = []
        self._lock = threading.RLock()
        self._started = False

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        self.db.create_all()
        self.event_writer.start()
        self.camera_manager.add_count_listener(self._on_count_event)
        self.camera_manager.start()
        self.load_cameras()
        log.info("Engine runtime started")

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
        self.stop_api_ws_loops()
        self.camera_manager.stop()
        self.event_writer.stop()
        log.info("Engine runtime stopped")

    def api_ws_loop(self, event: object) -> None:
        """Register the stop event of a WebSocket loop (called by the API)."""
        self.api_ws_loops.append(event)

    def release_api_ws_loop(self, event: object) -> None:
        try:
            self.api_ws_loops.remove(event)
        except ValueError:
            pass

    def stop_api_ws_loops(self) -> None:
        """Wake every WebSocket loop so a graceful shutdown does not wait on it."""
        loops = list(self.api_ws_loops)
        self.api_ws_loops.clear()
        for event in loops:
            try:
                event.set()
            except Exception:  # pragma: no cover - defensive
                pass
        if loops:
            log.info("Signalled %d API WebSocket loop(s) to stop", len(loops))

    # -- cameras --------------------------------------------------------
    def camera_url(self, camera) -> str:
        """Resolve the effective stream url of a camera row."""
        if camera.source_type == "file":
            return camera.file_path or ""
        if camera.rtsp_url:
            parsed = parse_source(camera.rtsp_url)
            if parsed.username or camera.username:
                password = self.secret_box.decrypt(camera.password_enc) or ""
                return build_rtsp_url(
                    parsed.host,
                    parsed.port,
                    parsed.username or camera.username,
                    password,
                    parsed.path,
                    parsed.scheme,
                )
            return camera.rtsp_url
        password = self.secret_box.decrypt(camera.password_enc) or ""
        return build_rtsp_url(
            camera.host or "",
            camera.port,
            camera.username,
            password,
            camera.rtsp_path or "",
        )

    def load_cameras(self) -> None:
        """(Re)start every enabled camera and load its zones."""
        from ..db.models import Camera, CounterArea, CounterLine

        with self.db.session_scope() as session:
            cameras = session.query(Camera).all()
            for camera in cameras:
                self._apply_camera(session, camera)

    def _apply_camera(self, session, camera) -> None:
        from ..db.models import CounterArea, CounterLine

        lines = [
            LineSpec(
                id=line.id, name=line.name, x1=line.x1, y1=line.y1, x2=line.x2, y2=line.y2,
                direction=line.direction, enabled=line.enabled, color=line.color,
                camera_id=camera.id,
            )
            for line in session.query(CounterLine).filter(CounterLine.camera_id == camera.id).all()
        ]
        areas = []
        for area in session.query(CounterArea).filter(CounterArea.camera_id == camera.id).all():
            areas.append(
                AreaSpec(
                    id=area.id, name=area.name, points=area.points_list,
                    enabled=area.enabled, color=area.color,
                    camera_id=camera.id,
                )
            )
        self.camera_manager.set_zones(camera.id, lines, areas)

        url = self.camera_url(camera)
        self.camera_manager.register_source(camera.id, camera.name, camera.source_type, url)
        if camera.enabled and url:
            source = CameraSource(
                camera_id=camera.id,
                name=camera.name,
                source_type=camera.source_type,
                url=url,
                fps_limit=camera.fps_limit or 10.0,
                detection_enabled=camera.detection_enabled,
                use_gpu=camera.use_gpu,
            )
            self.camera_manager.start_camera(source)
        else:
            self.camera_manager.stop_camera(camera.id)

    def sync_camera(self, camera_id: int) -> None:
        """Apply DB changes of one camera to the running engine."""
        from ..db.models import Camera

        with self.db.session_scope() as session:
            camera = session.get(Camera, camera_id)
            if camera is not None:
                self._apply_camera(session, camera)

    def stop_camera(self, camera_id: int) -> None:
        self.camera_manager.stop_camera(camera_id)

    def remove_camera(self, camera_id: int) -> None:
        self.camera_manager.unregister(camera_id)

    # -- counting -------------------------------------------------------
    def subscribe_counts(self, callback: Callable[[CountEvent], None]) -> None:
        self._listeners.append(callback)

    def _on_count_event(self, event: CountEvent) -> None:
        for listener in list(self._listeners):
            try:
                listener(event)
            except BaseException:  # pragma: no cover
                log.exception("runtime count listener failed")

    def _on_persisted(self, events: List[CountEvent]) -> None:
        """Fired after events were written to the database (webhooks)."""
        from ..services.webhooks import get_dispatcher

        dispatcher = get_dispatcher(self.settings)
        for event in events:
            try:
                dispatcher.dispatch(event)
            except Exception:  # pragma: no cover
                log.exception("webhook dispatch failed")

    def counts_snapshot(self) -> Dict:
        summary = self.camera_manager.counts()
        per_camera = []
        for camera_id in sorted(self.camera_manager.counter._totals.keys()):
            per_camera.append({"camera_id": camera_id, **self.camera_manager.counter.camera_summary(camera_id)})
        return {"global": summary, "per_camera": per_camera}

    def camera_counts(self, camera_id: int) -> Dict:
        counter = self.camera_manager.counter
        lines = {}
        areas = {}
        for (kind, target_id), totals in counter.counters(camera_id).items():
            entry = {**totals.to_dict(), "name": self._target_name(kind, target_id)}
            if kind == "line":
                lines[str(target_id)] = entry
            else:
                areas[str(target_id)] = entry
        summary = counter.camera_summary(camera_id)
        return {
            "camera_id": camera_id,
            "summary": summary,
            "lines": lines,
            "areas": areas,
            "occupancy": {str(k): v for k, v in counter.occupancy(camera_id).items()},
        }

    def _target_name(self, kind: str, target_id: int) -> str:
        for spec in (self.camera_manager.counter.lines if kind == "line" else self.camera_manager.counter.areas):
            if spec.id == target_id:
                return spec.name
        return ""

    def reset_counters(self, camera_id: Optional[int] = None) -> None:
        """Reset the live counters (and optionally the stored events)."""
        from ..db.models import CountEvent as CountEventRow

        self.camera_manager.counter.reset(camera_id)
        with self.db.session_scope() as session:
            query = session.query(CountEventRow)
            if camera_id is not None:
                query = query.filter(CountEventRow.camera_id == camera_id)
            query.delete(synchronize_session=False)
        log.info("Counters reset (camera=%s)", camera_id)
