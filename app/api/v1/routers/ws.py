"""WebSocket endpoints for live counts and detections."""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Optional


async def a_wait_event(event: threading.Event) -> None:
    """Await a threading.Event from the asyncio loop."""
    while not event.is_set():
        await asyncio.sleep(0.1)

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ....db.models import User
from ....services import auth as auth_service
from ...ws_manager import get_broadcaster

log = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])


def _authenticate(websocket: WebSocket, token: Optional[str]) -> Optional[User]:
    runtime = websocket.app.state.runtime
    if token:
        try:
            claims = auth_service.decode_token(token, runtime.settings)
        except Exception:
            return None
        session = runtime.db.session()
        try:
            user = session.query(User).filter(User.username == claims.get("sub")).first()
            if user is not None and user.is_active:
                return user
        finally:
            session.close()
        return None

    header = websocket.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return _authenticate(websocket, header.split(" ", 1)[1])
    return None


@router.websocket("/ws/counts")
async def ws_counts(websocket: WebSocket, token: Optional[str] = Query(default=None)) -> None:
    user = _authenticate(websocket, token)
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    broadcaster = get_broadcaster()
    queue = await broadcaster.subscribe("counts")
    runtime = websocket.app.state.runtime
    stop_event = threading.Event()
    runtime.api_ws_loop(stop_event)
    try:
        await websocket.send_json({"type": "snapshot", "data": runtime.counts_snapshot()})
        while not stop_event.is_set():
            payload_task = asyncio.create_task(queue.get())
            stop_task = asyncio.create_task(a_wait_event(stop_event))
            done, _ = await asyncio.wait(
                {payload_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
            )
            if stop_task in done:
                payload_task.cancel()
                break
            refresh = stop_event.is_set()
            await websocket.send_json({"type": "count", "data": payload_task.result()})
            if refresh:
                break
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # pragma: no cover
        log.debug("ws counts closed: %s", exc)
    finally:
        runtime.release_api_ws_loop(stop_event)
        await broadcaster.unsubscribe("counts", queue)


@router.websocket("/ws/cameras/{camera_id}/detections")
async def ws_detections(
    websocket: WebSocket,
    camera_id: int,
    token: Optional[str] = Query(default=None),
    fps: float = 5.0,
) -> None:
    user = _authenticate(websocket, token)
    if user is None:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    runtime = websocket.app.state.runtime
    stop_event = threading.Event()
    runtime.api_ws_loop(stop_event)
    interval = 1.0 / max(0.5, fps)
    last_seq = -1
    try:
        while not stop_event.is_set():
            packet = runtime.camera_manager.latest_packet(camera_id)
            if packet is not None and packet.seq != last_seq:
                last_seq = packet.seq
                await websocket.send_json(
                    {
                        "type": "detections",
                        "camera_id": camera_id,
                        "seq": packet.seq,
                        "timestamp": packet.timestamp,
                        "width": packet.width,
                        "height": packet.height,
                        "status": packet.status,
                        "detections": [
                            {
                                "bbox": [round(v, 1) for v in track.bbox],
                                "track_id": track.track_id,
                                "confidence": round(track.confidence, 3),
                                "class_id": track.class_id,
                            }
                            for track in packet.tracks
                        ],
                    }
                )
            await asyncio.sleep(min(interval, 0.2))
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        pass
    except Exception as exc:  # pragma: no cover
        log.debug("ws detections closed: %s", exc)
    finally:
        runtime.release_api_ws_loop(stop_event)
