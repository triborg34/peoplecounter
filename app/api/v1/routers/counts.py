"""Live counting endpoints."""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db.models import Camera, CountEvent
from ....services import audit
from ....services import auth as auth_service
from ...deps import client_ip, get_db, require_permission
from ..schemas import CountEventOut, CountsOut, GlobalCountsOut

log = logging.getLogger(__name__)
router = APIRouter(prefix="/counts", tags=["counts"])


@router.get("", response_model=GlobalCountsOut)
def global_counts(request: Request,
                  _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> GlobalCountsOut:
    runtime = request.app.state.runtime
    snapshot = runtime.counts_snapshot()
    return GlobalCountsOut(summary=snapshot["global"], per_camera=snapshot["per_camera"])


@router.get("/camera/{camera_id}", response_model=CountsOut)
def camera_counts(camera_id: int, request: Request, session: Session = Depends(get_db),
                  _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> CountsOut:
    runtime = request.app.state.runtime
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    data = runtime.camera_counts(camera_id)
    return CountsOut(**data)


@router.get("/events", response_model=List[CountEventOut])
def recent_events(
    limit: int = 100,
    camera_id: Optional[int] = None,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> List[CountEventOut]:
    statement = select(CountEvent).order_by(CountEvent.id.desc()).limit(min(limit, 1000))
    if camera_id is not None:
        statement = statement.where(CountEvent.camera_id == camera_id)
    events = session.execute(statement).scalars().all()
    names = {camera.id: camera.name for camera in session.execute(select(Camera)).scalars()}
    return [
        CountEventOut(
            id=event.id,
            timestamp=event.ts,
            camera_id=event.camera_id,
            camera_name=names.get(event.camera_id, ""),
            kind=event.kind,
            target_id=event.target_id,
            target_name=event.target_name,
            direction=event.direction,
            track_id=event.track_id,
            confidence=event.confidence,
        )
        for event in events
    ]


@router.post("/reset")
def reset_counters(
    request: Request,
    camera_id: Optional[int] = None,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_COUNTERS_RESET)),
) -> dict:
    runtime = request.app.state.runtime
    runtime.reset_counters(camera_id)
    audit.record(session, "counters_reset", user=user, entity_type="counter",
                 entity_id=camera_id, details="camera=%s" % (camera_id or "all"),
                 ip_address=client_ip(request))
    session.commit()
    return {"ok": True, "camera_id": camera_id}
