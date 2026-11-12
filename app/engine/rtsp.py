"""RTSP capture with a dedicated decoder thread (freshest-frame strategy).

The plain approach - calling ``VideoCapture.read()`` on the same loop that also
publishes frames - ties decoding speed to downstream speed. On a network RTSP
camera the driver keeps filling its internal buffer while we are busy, so the
frames we finally read are already seconds old. The result is laggy video and
counting driven by a growing backlog.

``FreshestFrame`` decouples the two:

* one thread reads ``cap.read()`` as fast as the camera delivers and keeps only
  the newest frame (older ones are dropped - nobody wants them),
* consumers call :meth:`read` and get the freshest frame, blocking only until a
  frame newer than the sequence number they already processed exists.

So the consumer always works on "now", and a slow detector can never make the
stream drift. Reconnection is handled in the reader thread with exponential
backoff plus jitter, and every wait is interruptible so ``release()`` stays
responsive.

Adapted from the standalone ``camera.py`` prototype: threading model and
semantics are kept, but OpenCV is imported lazily and the module sets no global
environment as an import side effect.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

Frame = np.ndarray


def _configure_ffmpeg_once() -> None:
    """Prefer TCP for RTSP and keep FFmpeg quiet. Runs at most once per process.

    ``rtsp_transport;tcp`` avoids the corrupted/ghosted frames that UDP RTSP
    produces under packet loss on busy networks.
    """
    global _FFMPEG_CONFIGURED
    if _FFMPEG_CONFIGURED:
        return
    _FFMPEG_CONFIGURED = True
    existing = os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS", "")
    if "rtsp_transport" not in existing:
        extra = "rtsp_transport;tcp"
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            f"{existing}|{extra}" if existing else extra
        )
    os.environ.setdefault("OPENCV_FFMPEG_FFMPEG_LOGLEVEL", "8")


_FFMPEG_CONFIGURED = False


class FreshestFrame:
    """Keeps the newest decoded frame of one stream in a background thread.

    Usable roughly like ``cv2.VideoCapture``: call :meth:`read` to get frames and
    :meth:`release` to stop.
    """

    RECONNECT_INITIAL_DELAY = 2.0
    RECONNECT_MAX_DELAY = 30.0
    RELEASE_TIMEOUT = 5.0

    def __init__(
        self,
        url: str,
        name: str = "FreshestFrame",
        open_timeout_ms: Optional[int] = None,
        use_tcp: bool = True,
        on_status: Optional[callable] = None,
    ):
        self.url = url
        self.on_status = on_status
        self._open_timeout_ms = open_timeout_ms
        self._use_tcp = use_tcp

        # Lets read() block until a new frame exists, allows graceful stop.
        self.cond = threading.Condition()
        self.running = False
        self.frame: Optional[Frame] = None
        self.latestnum = 0
        self._thread: Optional[threading.Thread] = None
        self._cap = None
        self._fps_window = []

        self._create_capture()

        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self.running = True
        self._thread.start()

    # -- capture lifecycle ----------------------------------------------
    def _create_capture(self) -> None:
        import cv2

        _configure_ffmpeg_once()
        cap = None
        try:
            if self._use_tcp and self._open_timeout_ms:
                params = [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self._open_timeout_ms,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, self._open_timeout_ms,
                ]
                try:
                    cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG, params)
                except Exception:
                    cap = None
            if cap is None:
                cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        except Exception:
            cap = cv2.VideoCapture(self.url)

        if not cap.isOpened():
            log.warning("VideoCapture failed to open %s", self.url)
            try:
                cap.release()
            except Exception:
                pass
            self._cap = None
            return

        try:
            # Only the newest frame matters; a large buffer would defeat that.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        self._cap = cap
        self._notify_status("online")

    def _notify_status(self, status: str) -> None:
        if self.on_status is None:
            return
        try:
            self.on_status(status)
        except Exception:  # pragma: no cover
            log.exception("status callback failed")

    def release(self, timeout: Optional[float] = None) -> None:
        self.running = False
        # Wake any reader blocked in read() so shutdown is immediate.
        with self.cond:
            self.cond.notify_all()
        thread = self._thread
        if thread is not None and thread.is_alive():
            join_timeout = timeout if timeout is not None else self.RELEASE_TIMEOUT
            thread.join(timeout=join_timeout)
            if thread.is_alive():
                log.warning("FreshestFrame thread did not stop within %ss", join_timeout)
        self._thread = None
        cap, self._cap = self._cap, None
        if cap is not None:
            try:
                cap.release()
            except Exception:
                log.warning("Error releasing VideoCapture")

    # -- reader thread ---------------------------------------------------
    def _run(self) -> None:
        consecutive_failures = 0
        counter = 0
        while self.running:
            cap = self._cap
            if cap is None:
                self._interruptible_sleep(self._backoff(consecutive_failures or 1))
                if not self.running:
                    break
                self._create_capture()
                continue

            try:
                ok, img = cap.read()
            except Exception as exc:
                log.warning("cap.read() raised: %s", exc)
                ok, img = False, None

            if not ok or img is None:
                consecutive_failures += 1
                if self.running:
                    self._notify_status("reconnecting")
                log.warning(
                    "Lost frame (consecutive=%s), reconnecting", consecutive_failures
                )
                old, self._cap = self._cap, None
                if old is not None:
                    try:
                        old.release()
                    except Exception:
                        pass
                self._interruptible_sleep(self._backoff(consecutive_failures))
                if not self.running:
                    break
                self._create_capture()
                continue

            consecutive_failures = 0
            with self.cond:
                self.frame = img
                self.latestnum = counter
                self.cond.notify_all()
            counter += 1

    def _backoff(self, failures: int) -> float:
        delay = min(
            self.RECONNECT_INITIAL_DELAY * (2 ** max(0, failures - 1)),
            self.RECONNECT_MAX_DELAY,
        )
        # Jitter so several cameras do not reconnect in lockstep.
        return delay * (0.8 + 0.4 * ((failures * 37) % 10) / 10.0)

    def _interruptible_sleep(self, duration: float) -> None:
        """Sleep without making release() wait for the whole backoff."""
        slept = 0.0
        while slept < duration and self.running:
            step = min(0.25, duration - slept)
            time.sleep(step)
            slept += step

    # -- consumer API ----------------------------------------------------
    def read(
        self,
        wait: bool = True,
        seqnumber: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[int, Optional[Frame]]:
        """Return ``(seq, frame)``.

        ``wait=True`` blocks until a frame newer than ``seqnumber`` arrives, so
        callers never process the same frame twice. With ``wait=False`` the
        current frame is returned immediately. ``timeout`` bounds the wait; on
        timeout the current frame (possibly the same one) is returned.
        """
        with self.cond:
            if not wait:
                return self.latestnum, self.frame
            target = self.latestnum + 1 if seqnumber is None else max(1, seqnumber)
            self.cond.wait_for(lambda: self.latestnum >= target, timeout=timeout)
            return self.latestnum, self.frame

    @property
    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def get(self, prop) -> float:
        cap = self._cap
        if cap is None:
            return 0.0
        try:
            return cap.get(prop)
        except Exception:
            return 0.0
