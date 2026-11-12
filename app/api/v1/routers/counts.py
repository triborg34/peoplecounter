"""Live counting endpoints."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ....db.models import Camera, CountEvent, CounterLine, CounterArea
from ....services import audit
from ....services import auth as auth_service
from ...deps import client_ip, get_db, require_permission
from ..schemas import CountEventOut, CountsOut, GlobalCountsOut, CountStatsOut, LiveCountOut

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


@router.get("/stats", response_model=CountStatsOut)
def count_stats(
    interval: str = Query("day", pattern="^(hour|day|week|month)$"),
    camera_id: Optional[int] = None,
    zone_id: Optional[int] = None,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> CountStatsOut:
    """Get aggregated count statistics with time series."""
    from datetime import datetime, timedelta, timezone
    
    # Determine time window based on interval
    now = datetime.now(timezone.utc)
    if interval == "hour":
        start_time = now - timedelta(hours=1)
        group_format = "%Y-%m-%d %H:%M"
        delta = timedelta(minutes=1)
    elif interval == "day":
        start_time = now - timedelta(days=1)
        group_format = "%Y-%m-%d %H:00"
        delta = timedelta(hours=1)
    elif interval == "week":
        start_time = now - timedelta(weeks=1)
        group_format = "%Y-%m-%d"
        delta = timedelta(days=1)
    else:  # month
        start_time = now - timedelta(days=30)
        group_format = "%Y-%m-%d"
        delta = timedelta(days=1)
    
    # Base query
    query = session.query(
        CountEvent.ts,
        CountEvent.camera_id,
        CountEvent.target_id,
        CountEvent.direction
    ).filter(CountEvent.ts >= start_time)
    
    if camera_id is not None:
        query = query.filter(CountEvent.camera_id == camera_id)
    if zone_id is not None:
        query = query.filter(CountEvent.target_id == zone_id)
    
    events = query.all()
    
    # Aggregate
    total_in = 0
    total_out = 0
    by_camera: Dict[str, Dict[str, int]] = {}
    by_zone: Dict[str, Dict[str, int]] = {}
    timeline: Dict[str, Dict[str, int]] = {}
    
    camera_names = {c.id: c.name for c in session.query(Camera).all()}
    zone_names = {z.id: z.name for z in session.query(CounterArea).all()}

    for event in events:
        ts = event.ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        key = ts.strftime(group_format)
        
        if key not in timeline:
            timeline[key] = {"in": 0, "out": 0}
        
        # The engine stores direction as "IN"/"OUT"; compare case-insensitively
        # so either casing aggregates correctly.
        is_in = (event.direction or "").strip().upper() == "IN"
        
        if is_in:
            total_in += 1
            timeline[key]["in"] += 1
        else:
            total_out += 1
            timeline[key]["out"] += 1
        
        cam_name = camera_names.get(event.camera_id, f"camera_{event.camera_id}")
        if cam_name not in by_camera:
            by_camera[cam_name] = {"in": 0, "out": 0, "net": 0}
        if is_in:
            by_camera[cam_name]["in"] += 1
        else:
            by_camera[cam_name]["out"] += 1
        by_camera[cam_name]["net"] = by_camera[cam_name]["in"] - by_camera[cam_name]["out"]
        
        # CountEvent has no zone_id column: zone/line identity is target_id.
        if event.target_id is not None:
            zone_name = zone_names.get(event.target_id, f"zone_{event.target_id}")
            if zone_name not in by_zone:
                by_zone[zone_name] = {"in": 0, "out": 0, "net": 0}
            if is_in:
                by_zone[zone_name]["in"] += 1
            else:
                by_zone[zone_name]["out"] += 1
            by_zone[zone_name]["net"] = by_zone[zone_name]["in"] - by_zone[zone_name]["out"]
    
    # Convert timeline to list
    timeline_list = [
        {"timestamp": k, "in": v["in"], "out": v["out"]}
        for k, v in sorted(timeline.items())
    ]
    
    return CountStatsOut(
        total_in=total_in,
        total_out=total_out,
        net_count=total_in - total_out,
        by_camera=by_camera,
        by_zone=by_zone,
        timeline=timeline_list
    )


@router.get("/live", response_model=List[LiveCountOut])
def live_counts(
    request: Request,
    session: Session = Depends(get_db),
    _: object = Depends(require_permission(auth_service.PERM_VIEW)),
) -> List[LiveCountOut]:
    """Get live counts for all cameras."""
    runtime = request.app.state.runtime
    snapshot = runtime.counts_snapshot()
    
    camera_names = {c.id: c.name for c in session.query(Camera).all()}
    zone_names = {z.id: z.name for z in session.query(CounterArea).all()}

    # Get recent events for last_event
    recent = session.query(CountEvent).order_by(CountEvent.id.desc()).limit(1000).all()
    last_events_by_camera: Dict[int, CountEvent] = {}
    for event in recent:
        if event.camera_id not in last_events_by_camera:
            last_events_by_camera[event.camera_id] = event
    
    result = []
    for cam_data in snapshot["per_camera"]:
        camera_id = cam_data["camera_id"]
        camera_name = camera_names.get(camera_id, f"camera_{camera_id}")
        
        # Get zone info if available
        zone_id = cam_data.get("zone_id")
        zone_name = zone_names.get(zone_id) if zone_id else None
        
        last_event = last_events_by_camera.get(camera_id)
        last_event_out = None
        if last_event:
            last_event_out = CountEventOut(
                id=last_event.id,
                timestamp=last_event.ts,
                camera_id=last_event.camera_id,
                camera_name=camera_name,
                kind=last_event.kind,
                target_id=last_event.target_id,
                target_name=last_event.target_name,
                direction=last_event.direction,
                track_id=last_event.track_id,
                confidence=last_event.confidence,
            )
        
        result.append(LiveCountOut(
            camera_id=camera_id,
            camera_name=camera_name,
            zone_id=zone_id,
            zone_name=zone_name,
            current_count=cam_data.get("total_in", 0) - cam_data.get("total_out", 0),
            total_in=cam_data.get("total_in", 0),
            total_out=cam_data.get("total_out", 0),
            last_event=last_event_out
        ))
    
    return result


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