"""Camera CRUD, status, snapshots and MJPEG streaming."""
from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db.models import Camera
from ....engine.sources import build_rtsp_url, parse_source, strip_credentials
from ....services import audit
from ....services import auth as auth_service
from ....services.cameras import camera_stream_url, test_connection
from ...deps import client_ip, get_current_user, get_db, get_runtime, require_permission
from ..schemas import (
    CameraCreate,
    CameraOut,
    CameraStatusOut,
    CameraUpdate,
    TestConnectionResult,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/cameras", tags=["cameras"])


def _camera_out(camera: Camera, runtime) -> CameraOut:
    status_info = {}
    for info in runtime.camera_manager.camera_status():
        if info["camera_id"] == camera.id:
            status_info = info
            break
    return CameraOut(
        id=camera.id,
        name=camera.name,
        location=camera.location or "",
        source_type=camera.source_type,
        enabled=camera.enabled,
        host=camera.host,
        port=camera.port,
        username=camera.username,
        has_password=bool(camera.password_enc),
        rtsp_path=camera.rtsp_path or "",
        rtsp_url=camera.rtsp_url,
        file_path=camera.file_path,
        fps_limit=camera.fps_limit,
        detection_enabled=camera.detection_enabled,
        use_gpu=camera.use_gpu,
        color=camera.color,
        status=status_info.get("status", "offline"),
        live_fps=status_info.get("fps", 0.0),
        last_error=status_info.get("error", ""),
    )


@router.get("", response_model=List[CameraOut])
def list_cameras(request: Request, session: Session = Depends(get_db),
                 _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> List[CameraOut]:
    runtime = request.app.state.runtime
    cameras = session.execute(select(Camera).order_by(Camera.name)).scalars().all()
    return [_camera_out(camera, runtime) for camera in cameras]


@router.post("", response_model=CameraOut, status_code=201)
def create_camera(
    payload: CameraCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_CAMERAS_MANAGE)),
) -> CameraOut:
    runtime = request.app.state.runtime
    if session.query(Camera).filter(Camera.name == payload.name).first():
        raise HTTPException(status_code=409, detail="A camera with this name already exists")

    camera = Camera(name=payload.name, location=payload.location or "", fps_limit=payload.fps_limit,
                     detection_enabled=payload.detection_enabled, enabled=payload.enabled)
    _apply_payload(camera, payload, runtime)
    session.add(camera)
    session.flush()
    audit.record(session, "camera_created", user=user, entity_type="camera", entity_id=camera.id,
                 details=camera.name, ip_address=client_ip(request))
    session.commit()
    runtime.sync_camera(camera.id)
    return _camera_out(camera, runtime)


def _apply_payload(camera: Camera, payload, runtime) -> None:
    """Write the request payload onto the camera row (secrets get encrypted)."""
    secret_box = runtime.secret_box
    mode = getattr(payload, "mode", None)

    if mode == "url" or (mode is None and payload.url):
        url = (payload.url or "").strip()
        if not url:
            raise HTTPException(status_code=400, detail="An RTSP url is required")
        parsed = parse_source(url)
        camera.source_type = "rtsp"
        camera.rtsp_url = strip_credentials(url)
        camera.host = parsed.host
        camera.port = parsed.port or 554
        camera.username = payload.username or parsed.username
        camera.rtsp_path = parsed.path or ""
        if payload.password:
            camera.password_enc = secret_box.encrypt(payload.password)
        elif parsed.password:
            camera.password_enc = secret_box.encrypt(parsed.password)
        else:
            camera.password_enc = None
        camera.file_path = None
        return

    if mode == "file" or (mode is None and payload.file_path):
        path = (payload.file_path or "").strip()
        if not path:
            raise HTTPException(status_code=400, detail="A video file path is required")
        camera.source_type = "file"
        camera.file_path = path
        camera.rtsp_url = None
        camera.host = None
        camera.username = None
        camera.password_enc = None
        return

    # manual mode
    if not payload.host:
        raise HTTPException(status_code=400, detail="Host is required in manual mode")
    camera.source_type = "rtsp"
    camera.host = payload.host.strip()
    camera.port = payload.port or 554
    camera.username = payload.username or None
    camera.rtsp_path = payload.rtsp_path or ""
    camera.file_path = None
    camera.rtsp_url = None
    if payload.password:
        camera.password_enc = secret_box.encrypt(payload.password)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: int, request: Request, session: Session = Depends(get_db),
               _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> CameraOut:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _camera_out(camera, request.app.state.runtime)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: int,
    payload: CameraUpdate,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_CAMERAS_MANAGE)),
) -> CameraOut:
    runtime = request.app.state.runtime
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")

    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        if session.query(Camera).filter(Camera.name == data["name"], Camera.id != camera_id).first():
            raise HTTPException(status_code=409, detail="A camera with this name already exists")
        camera.name = data["name"]
    if "location" in data and data["location"] is not None:
        camera.location = data["location"]
    if "enabled" in data and data["enabled"] is not None:
        camera.enabled = data["enabled"]
    if "fps_limit" in data and data["fps_limit"] is not None:
        camera.fps_limit = data["fps_limit"]
    if "detection_enabled" in data and data["detection_enabled"] is not None:
        camera.detection_enabled = data["detection_enabled"]
    if data.get("host"):
        camera.host = data["host"]
    if data.get("port"):
        camera.port = data["port"]
    if "username" in data:
        camera.username = data["username"]
    if "rtsp_path" in data and data["rtsp_path"] is not None:
        camera.rtsp_path = data["rtsp_path"]
    if data.get("password"):
        camera.password_enc = runtime.secret_box.encrypt(data["password"])
    if data.get("url"):
        parsed = parse_source(data["url"])
        camera.source_type = "rtsp"
        camera.rtsp_url = strip_credentials(data["url"])
        camera.host = parsed.host
        camera.port = parsed.port or 554
        camera.rtsp_path = parsed.path or ""
        if parsed.username:
            camera.username = parsed.username
        if parsed.password:
            camera.password_enc = runtime.secret_box.encrypt(parsed.password)
    if data.get("file_path"):
        camera.source_type = "file"
        camera.file_path = data["file_path"]

    audit.record(session, "camera_updated", user=user, entity_type="camera", entity_id=camera.id,
                 details=camera.name, ip_address=client_ip(request))
    session.commit()
    runtime.sync_camera(camera_id)
    return _camera_out(camera, runtime)


@router.delete("/{camera_id}", status_code=204)
def delete_camera(
    camera_id: int,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_CAMERAS_MANAGE)),
) -> None:
    runtime = request.app.state.runtime
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    name = camera.name
    runtime.remove_camera(camera_id)
    session.delete(camera)
    audit.record(session, "camera_deleted", user=user, entity_type="camera", entity_id=camera_id,
                 details=name, ip_address=client_ip(request))
    session.commit()


@router.post("/{camera_id}/test", response_model=TestConnectionResult)
def test_camera_connection(
    camera_id: int,
    request: Request,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_CAMERAS_MANAGE)),
) -> TestConnectionResult:
    runtime = request.app.state.runtime
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    url = camera_stream_url(camera, runtime.secret_box)
    outcome = test_connection(url, camera.source_type)
    return TestConnectionResult(**outcome)


@router.get("/{camera_id}/status", response_model=CameraStatusOut)
def camera_status(
    camera_id: int,
    request: Request,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> CameraStatusOut:
    runtime = request.app.state.runtime
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    for info in runtime.camera_manager.camera_status():
        if info["camera_id"] == camera_id:
            return CameraStatusOut(**info)
    return CameraStatusOut(camera_id=camera_id, name=camera.name, status="offline")


@router.get("/{camera_id}/snapshot")
def camera_snapshot(
    camera_id: int,
    request: Request,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> Response:
    runtime = request.app.state.runtime
    frame = runtime.camera_manager.latest_frame(camera_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="No frame available for this camera")
    import cv2

    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise HTTPException(status_code=500, detail="Could not encode the snapshot")
    return Response(content=buffer.tobytes(), media_type="image/jpeg")


def _mjpeg(runtime, camera_id: int, annotated: bool, target_fps: float = 10.0):
    import cv2

    interval = 1.0 / max(1.0, target_fps)
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    while True:
        frame = (
            runtime.camera_manager.latest_frame(camera_id)
            if annotated
            else runtime.camera_manager.raw_frame(camera_id)
        )
        if frame is None:
            time.sleep(0.05)
            continue
        ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            continue
        yield boundary + buffer.tobytes() + b"\r\n"
        time.sleep(interval)


@router.get("/{camera_id}/stream")
def stream_camera(
    camera_id: int,
    request: Request,
    fps: float = 10.0,
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> StreamingResponse:
    runtime = request.app.state.runtime
    return StreamingResponse(
        _mjpeg(runtime, camera_id, True, fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )


@router.get("/{camera_id}/stream/raw")
def stream_camera_raw(
    camera_id: int,
    request: Request,
    fps: float = 10.0,
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> StreamingResponse:
    runtime = request.app.state.runtime
    return StreamingResponse(
        _mjpeg(runtime, camera_id, False, fps),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
    )
