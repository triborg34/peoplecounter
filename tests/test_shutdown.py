"""Graceful shutdown regression tests.

A live WebSocket used to keep uvicorn from finishing, so the embedded API
server held the GUI shutdown for the whole join timeout (and leaked the port
afterwards).  The ws loops now expose a stop signal that the server sets
first, letting uvicorn finish inside its graceful window.
"""
from __future__ import annotations

import socket
import time

import pytest

ws_sync = pytest.importorskip("websockets.sync.client")


def _free_port() -> int:
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    return port


def _port_is_free(port: int) -> bool:
    probe = socket.socket()
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def test_embedded_api_shutdown_with_open_websocket(db, monkeypatch):
    import httpx

    from app.engine.detector import Detector
    from app.engine.runtime import EngineRuntime
    from app.server import EmbeddedApiServer

    monkeypatch.setattr(Detector, "load", lambda self: False)

    engine = EngineRuntime(db=db)
    engine.start()  # the desktop app owns the runtime; the embedded server must survive it
    server = EmbeddedApiServer(engine, "127.0.0.1", _free_port())
    server.start()
    try:
        deadline = time.time() + 15
        while time.time() < deadline and not server.running:
            time.sleep(0.05)

        token = httpx.post(
            server.url + "/api/v1/auth/login",
            json={"username": "admin", "password": "admin123"},
        ).json()["access_token"]
        url = server.url.replace("http://", "ws://") + "/api/v1/ws/counts?token=" + token

        # keep the WebSocket open for the whole shutdown
        with ws_sync.connect(url) as socket_:
            socket_.recv()
            started = time.time()
            server.stop(timeout=4.0)
            elapsed = time.time() - started
        try:
            socket_.recv()  # the other side should have closed the connection
        except Exception:
            pass

        assert elapsed < 2.5, "shutdown waited on the WebSocket for %.1fs" % elapsed
        assert not (server._thread and server._thread.is_alive())
        assert _port_is_free(server.port), "the shutdown leaked the port"
        assert engine._started, "stopping the embedded API also stopped the GUI runtime"
    finally:
        try:
            server.stop(timeout=2.0)
        finally:
            engine.stop()