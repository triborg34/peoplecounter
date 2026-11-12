"""Counting lines and areas (per camera)."""
from __future__ import annotations

import json
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db.models import Camera, CounterArea, CounterLine
from ....services import audit
from ....services import auth as auth_service
from ...deps import client_ip, get_db, require_permission
from ..schemas import AreaCreate, AreaOut, AreaUpdate, LineCreate, LineOut, LineUpdate

log = logging.getLogger(__name__)
router = APIRouter(tags=["zones"])


def _sync_runtime(request: Request, camera_id: int) -> None:
    """Push zone changes into the running engine, without failing the request.

    The DB transaction is already committed at this point, so the change is
    durable whether or not the live engine accepts it. Letting an exception
    escape here (a dying camera, a stalled capture) turned a successful delete
    into a 500: the row was gone but the client saw an error and left the
    deleted item on screen until a manual refresh.
    """
    try:
        request.app.state.runtime.sync_camera(camera_id)
    except Exception:
        log.exception("Failed to sync camera %s into the live engine", camera_id)


def _require_camera(session: Session, camera_id: int) -> Camera:
    camera = session.get(Camera, camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


# -- lines -------------------------------------------------------------
@router.get("/cameras/{camera_id}/lines", response_model=List[LineOut])
def list_lines(camera_id: int, session: Session = Depends(get_db),
               _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> List[LineOut]:
    _require_camera(session, camera_id)
    lines = session.execute(
        select(CounterLine).where(CounterLine.camera_id == camera_id).order_by(CounterLine.id)
    ).scalars().all()
    return [LineOut.model_validate(line) for line in lines]


@router.post("/cameras/{camera_id}/lines", response_model=LineOut, status_code=201)
def create_line(
    camera_id: int,
    payload: LineCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_LINES_MANAGE)),
) -> LineOut:
    _require_camera(session, camera_id)
    line = CounterLine(
        camera_id=camera_id,
        name=payload.name,
        color=payload.color,
        x1=payload.x1, y1=payload.y1, x2=payload.x2, y2=payload.y2,
        direction=payload.direction,
        enabled=payload.enabled,
    )
    session.add(line)
    session.flush()
    audit.record(session, "line_created", user=user, entity_type="line", entity_id=line.id,
                 details=payload.name, ip_address=client_ip(request))
    session.commit()
    _sync_runtime(request, camera_id)
    return LineOut.model_validate(line)


@router.get("/cameras/{camera_id}/lines/{line_id}", response_model=LineOut)
def get_line(camera_id: int, line_id: int, session: Session = Depends(get_db),
             _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> LineOut:
    line = session.get(CounterLine, line_id)
    if line is None or line.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Line not found")
    return LineOut.model_validate(line)


@router.patch("/cameras/{camera_id}/lines/{line_id}", response_model=LineOut)
def update_line(
    camera_id: int,
    line_id: int,
    payload: LineUpdate,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_LINES_MANAGE)),
) -> LineOut:
    line = session.get(CounterLine, line_id)
    if line is None or line.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Line not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if value is not None:
            setattr(line, key, value)
    audit.record(session, "line_updated", user=user, entity_type="line", entity_id=line.id,
                 details=line.name, ip_address=client_ip(request))
    session.commit()
    _sync_runtime(request, camera_id)
    return LineOut.model_validate(line)


@router.delete("/cameras/{camera_id}/lines/{line_id}", status_code=204)
def delete_line(
    camera_id: int,
    line_id: int,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_LINES_MANAGE)),
) -> None:
    line = session.get(CounterLine, line_id)
    if line is None or line.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Line not found")
    name = line.name
    session.delete(line)
    audit.record(session, "line_deleted", user=user, entity_type="line", entity_id=line_id,
                 details=name, ip_address=client_ip(request))
    session.commit()
    _sync_runtime(request, camera_id)


# -- areas -------------------------------------------------------------
@router.get("/cameras/{camera_id}/areas", response_model=List[AreaOut])
def list_areas(camera_id: int, session: Session = Depends(get_db),
               _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> List[AreaOut]:
    _require_camera(session, camera_id)
    areas = session.execute(
        select(CounterArea).where(CounterArea.camera_id == camera_id).order_by(CounterArea.id)
    ).scalars().all()
    return [_area_out(area) for area in areas]


def _area_out(area: CounterArea) -> AreaOut:
    return AreaOut(
        id=area.id,
        camera_id=area.camera_id,
        name=area.name,
        color=area.color,
        points=[list(point) for point in area.points_list],
        enabled=area.enabled,
    )


@router.post("/cameras/{camera_id}/areas", response_model=AreaOut, status_code=201)
def create_area(
    camera_id: int,
    payload: AreaCreate,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_LINES_MANAGE)),
) -> AreaOut:
    _require_camera(session, camera_id)
    area = CounterArea(
        camera_id=camera_id,
        name=payload.name,
        color=payload.color,
        points=json.dumps([[float(x), float(y)] for x, y in payload.points]),
        enabled=payload.enabled,
    )
    session.add(area)
    session.flush()
    audit.record(session, "area_created", user=user, entity_type="area", entity_id=area.id,
                 details=payload.name, ip_address=client_ip(request))
    session.commit()
    _sync_runtime(request, camera_id)
    return _area_out(area)


@router.get("/cameras/{camera_id}/areas/{area_id}", response_model=AreaOut)
def get_area(camera_id: int, area_id: int, session: Session = Depends(get_db),
             _: object = Depends(require_permission(auth_service.PERM_VIEW))) -> AreaOut:
    area = session.get(CounterArea, area_id)
    if area is None or area.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Area not found")
    return _area_out(area)


@router.patch("/cameras/{camera_id}/areas/{area_id}", response_model=AreaOut)
def update_area(
    camera_id: int,
    area_id: int,
    payload: AreaUpdate,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_LINES_MANAGE)),
) -> AreaOut:
    area = session.get(CounterArea, area_id)
    if area is None or area.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Area not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("points"):
        area.points = json.dumps([[float(x), float(y)] for x, y in data["points"]])
    if data.get("name") is not None:
        area.name = data["name"]
    if data.get("color") is not None:
        area.color = data["color"]
    if data.get("enabled") is not None:
        area.enabled = data["enabled"]
    audit.record(session, "area_updated", user=user, entity_type="area", entity_id=area.id,
                 details=area.name, ip_address=client_ip(request))
    session.commit()
    _sync_runtime(request, camera_id)
    return _area_out(area)


@router.delete("/cameras/{camera_id}/areas/{area_id}", status_code=204)
def delete_area(
    camera_id: int,
    area_id: int,
    request: Request,
    session: Session = Depends(get_db),
    user: object = Depends(require_permission(auth_service.PERM_LINES_MANAGE)),
) -> None:
    area = session.get(CounterArea, area_id)
    if area is None or area.camera_id != camera_id:
        raise HTTPException(status_code=404, detail="Area not found")
    name = area.name
    session.delete(area)
    audit.record(session, "area_deleted", user=user, entity_type="area", entity_id=area_id,
                 details=name, ip_address=client_ip(request))
    session.commit()
    _sync_runtime(request, camera_id)
