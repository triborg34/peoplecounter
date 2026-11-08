"""Buffered persistence of count events.

Inference threads never touch the database directly: they push events onto a
queue and a dedicated writer thread batches them into a single transaction.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, List, Optional

from ..db.models import CountEvent, utcnow
from ..db.session import Database
from .types import CountEvent as EngineCountEvent

log = logging.getLogger(__name__)


class EventWriter:
    """Background thread that persists count events in batches."""

    def __init__(
        self,
        db: Database,
        batch_size: int = 50,
        flush_interval_s: float = 1.0,
        on_persist: Optional[Callable[[List[EngineCountEvent]], None]] = None,
    ):
        self.db = db
        self.batch_size = batch_size
        self.flush_interval_s = flush_interval_s
        self.on_persist = on_persist
        self._queue: "queue.Queue[EngineCountEvent]" = queue.Queue(maxsize=10000)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._dropped = 0
        self._persisted = 0

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="event-writer", daemon=True)
        self._thread.start()
        log.info("Event writer started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        self.flush()
        log.info("Event writer stopped")

    # -- producing ------------------------------------------------------
    def submit(self, event: EngineCountEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            # Never block the inference path - drop the oldest pending event.
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(event)
                self._dropped += 1
                log.warning("Event queue full, dropped an event")
            except queue.Empty:  # pragma: no cover - race
                self._dropped += 1

    @property
    def stats(self) -> dict:
        return {
            "pending": self._queue.qsize(),
            "persisted": self._persisted,
            "dropped": self._dropped,
        }

    def flush(self) -> int:
        """Persist everything that is pending right now (blocking)."""
        batch: List[EngineCountEvent] = []
        while True:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        self._persist(batch)
        return len(batch)

    # -- worker ---------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set() or not self._queue.empty():
            try:
                first = self._queue.get(timeout=self.flush_interval_s)
            except queue.Empty:
                continue
            batch = [first]
            while len(batch) < self.batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            self._persist(batch)

    def _persist(self, batch: List[EngineCountEvent]) -> None:
        if not batch:
            return
        rows = [
            CountEvent(
                ts=utcnow(),
                camera_id=ev.camera_id,
                kind=ev.kind,
                target_id=ev.target_id,
                target_name=ev.target_name,
                direction=ev.direction,
                track_id=ev.track_id,
                confidence=ev.confidence,
                point_x=ev.x,
                point_y=ev.y,
            )
            for ev in batch
        ]
        try:
            with self.db.session_scope() as session:
                session.add_all(rows)
            self._persisted += len(rows)
            if self.on_persist:
                try:
                    self.on_persist(batch)
                except Exception:  # pragma: no cover - callback must not break persistence
                    log.exception("on_persist callback failed")
        except Exception:
            log.exception("Failed to persist %d count events", len(rows))
