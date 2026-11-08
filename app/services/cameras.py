"""Camera helper services shared by the GUI and the API."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


def test_connection(url: str, source_type: str = "rtsp", timeout: float = 8.0) -> Dict[str, Any]:
    """Try to open a stream and grab a single frame.

    The capture runs in a worker thread so a hanging RTSP connection cannot
    block the caller beyond the timeout.
    """
    import cv2

    result: Dict[str, Any] = {"ok": False, "message": "", "width": 0, "height": 0, "fps": 0.0}
    if not url:
        result["message"] = "No source configured"
        return result

    def worker() -> None:
        capture = None
        try:
            if source_type == "file":
                capture = cv2.VideoCapture(url)
            else:
                try:
                    capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
                except Exception:
                    capture = cv2.VideoCapture(url)
            if not capture.isOpened():
                result["message"] = "Could not open the stream"
                return
            ok, frame = capture.read()
            if not ok or frame is None:
                result["message"] = "Stream opened but no frame could be read"
                return
            height, width = frame.shape[:2]
            result.update(
                {
                    "ok": True,
                    "message": "Connection successful",
                    "width": int(width),
                    "height": int(height),
                    "fps": float(capture.get(cv2.CAP_PROP_FPS) or 0.0),
                }
            )
        except Exception as exc:
            result["message"] = "Connection failed: " + str(exc)
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        result["message"] = "Connection timed out after " + str(int(timeout)) + "s"
    return result


def camera_stream_url(camera, secret_box) -> str:
    """Resolve the effective url of a camera row (decrypting the password)."""
    from ..engine.sources import build_rtsp_url, parse_source

    if camera.source_type == "file":
        return camera.file_path or ""
    if camera.rtsp_url:
        parsed = parse_source(camera.rtsp_url)
        password = secret_box.decrypt(camera.password_enc) or ""
        if parsed.username or camera.username:
            return build_rtsp_url(
                parsed.host, parsed.port, parsed.username or camera.username,
                password, parsed.path, parsed.scheme,
            )
        return camera.rtsp_url
    password = secret_box.decrypt(camera.password_enc) or ""
    return build_rtsp_url(
        camera.host or "", camera.port, camera.username, password, camera.rtsp_path or ""
    )


def split_direct_url(url: str):
    """Split a pasted RTSP url into host/port/user/password/path."""
    from ..engine.sources import parse_source

    parsed = parse_source(url)
    return parsed
