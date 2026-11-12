"""One worker thread per camera: capture, reconnect, FPS limiting.

The worker never blocks the consumer: frames are published onto a shared bus
that keeps only the latest frame per camera, so a slow consumer never creates
a growing buffer of stale frames.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from ..config import Settings, get_settings
from .types import CameraStatus

log = logging.getLogger(__name__)

Frame = np.ndarray
FrameItem = Tuple[int, Frame, float]


class FrameBus:
    """Latest-frame bus shared by all camera workers and the inference loop."""

    def __init__(self, maxsize: int = 64):
        self._queue: "queue.Queue[FrameItem]" = queue.Queue(maxsize=maxsize)
        self._lock = threading.Lock()
        self._latest: Dict[int, Tuple[Frame, float]] = {}

    def publish(self, camera_id: int, frame: Frame, timestamp: float) -> None:
        with self._lock:
            self._latest[camera_id] = (frame, timestamp)
        try:
            self._queue.put_nowait((camera_id, frame, timestamp))
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.put_nowait((camera_id, frame, timestamp))
            except queue.Empty:  # pragma: no cover
                pass

    def latest(self, camera_id: int) -> Optional[Tuple[Frame, float]]:
        with self._lock:
            return self._latest.get(camera_id)

    def collect_batch(self, max_batch: int, window_s: float) -> List[FrameItem]:
        """Collect up to max_batch frames, waiting at most window_s in total."""
        batch: List[FrameItem] = []
        try:
            first = self._queue.get(timeout=max(0.01, window_s))
            batch.append(first)
        except queue.Empty:
            return batch

        deadline = time.monotonic() + window_s
        while len(batch) < max_batch:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(self._queue.get(timeout=remaining))
            except queue.Empty:
                break
        return batch

    def clear_camera(self, camera_id: int) -> None:
        with self._lock:
            self._latest.pop(camera_id, None)


@dataclass
class CameraSource:
    camera_id: int
    name: str
    source_type: str = "rtsp"      # rtsp | file
    url: str = ""
    fps_limit: float = 10.0
    detection_enabled: bool = True
    use_gpu: bool = False


class CameraWorker:
    """Captures frames from a single camera in its own thread."""

    def __init__(
        self,
        source: CameraSource,
        bus: FrameBus,
        settings: Optional[Settings] = None,
        on_status: Optional[Callable[[int, str, str], None]] = None,
    ):
        self.source = source
        self.bus = bus
        self.settings = settings or get_settings()
        self.on_status = on_status

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._capture = None
        self._reader = None
        self._status = CameraStatus.STOPPED.value
        self._error = ""
        self._attempts = 0
        self._frames = 0
        self._fps = 0.0
        self._fps_window: List[float] = []
        self._last_frame_ts = 0.0

    # -- properties -----------------------------------------------------
    @property
    def status(self) -> str:
        return self._status

    @property
    def error(self) -> str:
        return self._error

    @property
    def attempts(self) -> int:
        return self._attempts

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def frames(self) -> int:
        return self._frames

    @property
    def last_frame_ts(self) -> float:
        return self._last_frame_ts

    def info(self) -> dict:
        return {
            "camera_id": self.source.camera_id,
            "name": self.source.name,
            "status": self._status,
            "fps": round(self._fps, 2),
            "frames": self._frames,
            "error": self._error,
            "reconnect_attempts": self._attempts,
        }

    # -- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="camera-" + str(self.source.camera_id), daemon=True
        )
        self._thread.start()
        self._set_status(CameraStatus.STARTING.value, "")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        # Wake the RTSP reader if it is blocked waiting for a new frame.
        reader = self._reader
        if reader is not None:
            try:
                reader.release()
            except Exception:
                pass
            self._reader = None
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        self._release()
        self._set_status(CameraStatus.STOPPED.value, "")

    def restart(self) -> None:
        self.stop(timeout=2.0)
        self._attempts = 0
        self.start()

    def _set_status(self, status: str, error: str = "") -> None:
        self._status = status
        self._error = error
        if self.on_status:
            try:
                self.on_status(self.source.camera_id, status, error)
            except Exception:  # pragma: no cover
                log.exception("status callback failed")

    # -- capture --------------------------------------------------------
    def _open(self) -> bool:
        import cv2

        self._release()
        url = self.source.url
        if self.source.source_type == "file":
            capture = cv2.VideoCapture(url)
        else:
            # timeouts keep a dead camera from blocking the worker for minutes
            timeout_ms = int(max(1000, self.settings.camera_frame_timeout_s * 1000))
            try:
                params = [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms,
                ]
                capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
            except Exception:
                try:
                    capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                except Exception:
                    capture = cv2.VideoCapture(url)
        if not capture.isOpened():
            try:
                capture.release()
            except Exception:
                pass
            self._set_status(CameraStatus.OFFLINE.value, "cannot open " + self._describe())
            return False
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        self._capture = capture
        self._attempts = 0
        self._set_status(CameraStatus.ONLINE.value, "")
        log.info("Camera '%s' connected (%s)", self.source.name, self._describe())
        return True

    def _describe(self) -> str:
        from .sources import describe_source

        return describe_source(self.source.url) if self.source.source_type != "file" else self.source.url

    def _release(self) -> None:
        if self._capture is not None:
            try:
                self._capture.release()
            except Exception:
                pass
            self._capture = None

    def _run(self) -> None:
        if self.source.source_type != "file":
            self._run_fresh()
        else:
            self._run_file()

    def _run_fresh(self) -> None:
        """RTSP path: a decoder thread keeps the newest frame, we consume it.

        Reading the capture directly here would couple decoding to publishing
        and let the driver's buffer fill, so detected frames drift seconds
        behind reality. FreshestFrame always hands us the current frame.
        """
        from .rtsp import FreshestFrame

        min_interval = 1.0 / self.source.fps_limit if self.source.fps_limit > 0 else 0.0
        timeout_ms = int(max(1000, self.settings.camera_frame_timeout_s * 1000)) if self.settings else 5000

        reader = FreshestFrame(
            self.source.url,
            name="decode-" + str(self.source.camera_id),
            open_timeout_ms=timeout_ms,
            on_status=self._on_reader_status,
        )
        self._reader = reader
        last_seq = -1
        try:
            while not self._stop.is_set():
                started = time.monotonic()
                seq, frame = reader.read(wait=True, timeout=1.0)
                if frame is None or seq == last_seq:
                    # Nothing new yet: avoid spinning, and do not republish.
                    if self._stop.wait(0.01):
                        break
                    continue
                last_seq = seq
                self._publish(frame)
                elapsed = time.monotonic() - started
                if min_interval > elapsed:
                    self._stop.wait(min_interval - elapsed)
        finally:
            self._reader = None
            reader.release()

    def _on_reader_status(self, status: str) -> None:
        if status == "online":
            self._attempts = 0
            self._set_status(CameraStatus.ONLINE.value, "")
            log.info("Camera '%s' connected (%s)", self.source.name, self._describe())
        elif status == "reconnecting":
            self._attempts += 1
            self._set_status(CameraStatus.RECONNECTING.value, "stream disconnected")

    def _publish(self, frame: Frame) -> None:
        now = time.time()
        self.bus.publish(self.source.camera_id, frame, now)
        self._frames += 1
        self._last_frame_ts = now
        self._fps_window.append(now)
        if len(self._fps_window) > 30:
            self._fps_window.pop(0)
        if len(self._fps_window) > 1:
            span = self._fps_window[-1] - self._fps_window[0]
            self._fps = (len(self._fps_window) - 1) / span if span > 0 else 0.0

    def _run_file(self) -> None:
        min_interval = 1.0 / self.source.fps_limit if self.source.fps_limit > 0 else 0.0
        while not self._stop.is_set():
            if self._capture is None:
                if not self._open():
                    self._sleep_backoff()
                    continue

            started = time.monotonic()
            ok, frame = self._capture.read()
            if not ok or frame is None:
                # A video file that reached its end is simply looped.
                log.debug("Video file ended, restarting %s", self.source.name)
                self._release()
                continue

            self._publish(frame)
            elapsed = time.monotonic() - started
            if min_interval > elapsed:
                self._stop.wait(min_interval - elapsed)

    def _sleep_backoff(self) -> None:
        self._attempts += 1
        base = self.settings.reconnect_base_delay
        maximum = self.settings.reconnect_max_delay
        delay = min(maximum, base * (2 ** min(self._attempts - 1, 10)))
        delay *= 0.8 + 0.4 * ((self._attempts * 37) % 10) / 10.0  # jitter
        self._stop.wait(delay)
