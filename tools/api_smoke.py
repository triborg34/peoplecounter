"""Live smoke test of the HTTP API.

    python tools/api_smoke.py

Starts the real server, logs in, exercises the REST endpoints and checks the
MJPEG stream and the WebSocket feed.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import uvicorn

from app.bootstrap import ensure_default_admin
from app.config import get_settings
from app.db.models import Camera, CounterLine
from app.engine.runtime import EngineRuntime

PORT = int(os.environ.get("PCC_SMOKE_PORT", "8123"))
BASE = "http://127.0.0.1:" + str(PORT)


def prepare(runtime) -> int:
    settings = runtime.settings
    with runtime.db.session_scope() as session:
        camera = session.query(Camera).filter(Camera.name == "Smoke camera").first()
        if camera is None:
            camera = Camera(
                name="Smoke camera",
                location="Test",
                source_type="file",
                file_path=str(Path(settings.data_dir) / "sample" / "sample_walk.mp4"),
                enabled=True,
                fps_limit=6.0,
            )
            session.add(camera)
            session.flush()
            session.add(
                CounterLine(
                    camera_id=camera.id, name="Main door",
                    x1=0.5, y1=0.0, x2=0.5, y2=1.0, direction="BOTH",
                )
            )
            session.commit()
            return camera.id
        return camera.id


async def check_websocket(token: str, camera_id: int) -> None:
    import websockets

    url = "ws://127.0.0.1:" + str(PORT) + "/api/v1/ws/counts?token=" + token
    async with websockets.connect(url) as socket:
        first = json.loads(await asyncio.wait_for(socket.recv(), timeout=10))
        assert first["type"] == "snapshot", first
        print("  ws /ws/counts snapshot:", first["data"]["global"])

    url = (
        "ws://127.0.0.1:" + str(PORT)
        + "/api/v1/ws/cameras/" + str(camera_id) + "/detections?token=" + token
    )
    async with websockets.connect(url) as socket:
        message = json.loads(await asyncio.wait_for(socket.recv(), timeout=15))
        assert message["type"] == "detections", message
        print(
            "  ws /ws/cameras/%s/detections: %d detections, track ids %s"
            % (
                camera_id,
                len(message["detections"]),
                [d["track_id"] for d in message["detections"]],
            )
        )


def main() -> int:
    settings = get_settings()
    runtime = EngineRuntime(settings)
    runtime.db.create_all()
    ensure_default_admin(runtime.db, settings)
    camera_id = prepare(runtime)
    runtime.start()
    print("engine started, camera id", camera_id)

    from app.api.app import create_app

    app = create_app(runtime=runtime, settings=settings)
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(100):
        try:
            if httpx.get(BASE + "/health", timeout=2).status_code == 200:
                break
        except Exception:
            time.sleep(0.2)
    else:
        raise SystemExit("the API server did not come up")

    print("health:", httpx.get(BASE + "/health", timeout=5).json())
    print("docs:", httpx.get(BASE + "/docs", timeout=5).status_code)

    response = httpx.post(
        BASE + "/api/v1/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10,
    )
    response.raise_for_status()
    token = response.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    print("login ok, token length", len(token))

    cameras = httpx.get(BASE + "/api/v1/cameras", headers=headers, timeout=10).json()
    print("cameras:", [(c["id"], c["name"], c["status"]) for c in cameras])

    counts = httpx.get(BASE + "/api/v1/counts", headers=headers, timeout=10).json()
    print("live counts:", counts["summary"])

    # the MJPEG stream must deliver real frames
    frames = 0
    with httpx.stream(
        "GET", BASE + "/api/v1/cameras/" + str(camera_id) + "/stream",
        headers=headers, timeout=30,
    ) as stream:
        assert stream.status_code == 200, stream.status_code
        assert "multipart/x-mixed-replace" in stream.headers["content-type"], stream.headers
        buffer = b""
        deadline = time.time() + 30
        for chunk in stream.iter_bytes():
            buffer += chunk
            frames = buffer.count(b"--frame")
            if frames >= 3 or time.time() > deadline:
                break
        print("mjpeg stream: %d frames received, %d bytes" % (frames, len(buffer)))
        assert frames >= 1, "no frame was delivered"

    snapshot = httpx.get(
        BASE + "/api/v1/cameras/" + str(camera_id) + "/snapshot", headers=headers, timeout=10
    )
    print("snapshot:", snapshot.status_code, snapshot.headers.get("content-type"),
          len(snapshot.content), "bytes")
    assert snapshot.status_code == 200 and snapshot.content[:2] == b"\xff\xd8"

    asyncio.run(check_websocket(token, camera_id))

    # wait until the person in the sample video has crossed the line
    deadline = time.time() + 60
    live = {}
    while time.time() < deadline:
        live = httpx.get(BASE + "/api/v1/counts", headers=headers, timeout=10).json()
        if live["summary"]["total"] > 0:
            break
        time.sleep(1.0)
    print("live counts after the crossing:", live["summary"])
    assert live["summary"]["total"] > 0, "the person never crossed the line"

    report = httpx.get(
        BASE + "/api/v1/reports/summary", headers=headers, timeout=20
    ).json()
    print("report totals:", report["totals"])
    assert report["totals"]["events"] > 0, "no counting event was stored"

    server.should_exit = True
    thread.join(timeout=10)
    runtime.stop()
    print("API SMOKE OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
