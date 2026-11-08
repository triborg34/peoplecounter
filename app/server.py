"""Headless API server.

Usage:
    python -m app.server                 # uses the configured host/port
    python -m app.server --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from typing import List, Optional

from .config import Settings, get_settings
from .logging_setup import setup_logging

log = logging.getLogger(__name__)


def run_server(
    settings: Optional[Settings] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    runtime=None,
) -> None:
    import uvicorn

    from .api.app import create_app

    settings = settings or get_settings()
    setup_logging(settings.log_level, settings.log_dir, settings.log_max_bytes, settings.log_backup_count)
    app = create_app(runtime=runtime, settings=settings)
    uvicorn.run(
        app,
        host=host or settings.api_host,
        port=int(port or settings.api_port),
        log_level=settings.log_level.lower(),
        # Bound the graceful phase: MJPEG / WebSocket clients that never
        # disconnect would otherwise stall the shutdown forever.
        timeout_graceful_shutdown=2.0,
    )


class EmbeddedApiServer:
    """Runs the FastAPI app inside the desktop application."""

    def __init__(self, runtime, host: Optional[str] = None, port: Optional[int] = None,
                 settings: Optional[Settings] = None):
        import uvicorn

        from .api.app import create_app

        self.settings = settings or get_settings()
        self.host = host or self.settings.api_host
        self.port = int(port or self.settings.api_port)
        self.runtime = runtime
        self.app = create_app(runtime=runtime, settings=self.settings, manage_runtime=False)
        self._config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level=self.settings.log_level.lower(),
            lifespan="on",
            # Bound the graceful phase: MJPEG / WebSocket clients that never
            # disconnect would otherwise stall the GUI shutdown for the whole
            # join timeout below (and keep the port bound afterwards).
            timeout_graceful_shutdown=2.0,
        )
        self._server = uvicorn.Server(self._config)
        self._thread: Optional[threading.Thread] = None

    @property
    def running(self) -> bool:
        return self._server is not None and self._server.started

    @property
    def url(self) -> str:
        return "http://" + self.host + ":" + str(self.port)

    def _pending_ws_loops(self, limit: int = 50) -> List[threading._Event]:
        """Events for the WebSocket loops still waiting for the next event.

        uvicorn's graceful shutdown waits for every open WebSocket until its
        client disconnects.  That would stall the GUI shutdown for the whole
        timeout, because MJPEG views and WebSocket feeds are long lived.  The
        same events are used by each ws loop as its stop flag, so we can wake
        them up here to let uvicorn finish quickly.
        """
        found: List[threading._Event] = []
        for loop in self.runtime.api_ws_loops:
            if len(found) >= limit:
                break
            if isinstance(loop, threading.Event):
                found.append(loop)
        return found

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _run() -> None:
            try:
                self._server.run()
            except Exception:
                log.exception("Embedded API server crashed")

        self._thread = threading.Thread(target=_run, name="api-server", daemon=True)
        self._thread.start()
        log.info("Embedded API server starting on %s", self.url)

    def stop(self, timeout: float = 6.0) -> None:
        # Remember the ws loops we started so we can wake them below; new
        # WebSocket connections are no longer accepted after should_exit is set.
        loops = self._pending_ws_loops()
        if self._server is not None:
            self._server.should_exit = True
        self._wake_ws_loops(loops)
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None
        if self._wake_ws_loops(loops):
            log.info("Embedded API server stopped (forced %d lingering WebSocket(s) closed)", len(loops))
        else:
            log.info("Embedded API server stopped")

    @staticmethod
    def _wake_ws_loops(loops: List[threading._Event]) -> int:
        """Signal the wake-up loop and return how many were signalled."""
        joined = 0
        for loop in loops:
            try:
                loop.set()
                joined += 1
            except Exception:  # pragma: no cover - defensive
                pass
        return joined


def main() -> None:
    parser = argparse.ArgumentParser(description="People counter API server")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", default=None, type=int)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
