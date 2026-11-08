"""Report queries and aggregation over the stored count events."""
from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Camera, CountEvent, CounterArea, CounterLine

INTERVALS = ("minute", "hour", "day", "week", "month")


@dataclass
class ReportFilters:
    start: Optional[dt.datetime] = None
    end: Optional[dt.datetime] = None
    camera_ids: List[int] = field(default_factory=list)
    kind: Optional[str] = None          # line | area
    target_id: Optional[int] = None
    direction: Optional[str] = None     # IN | OUT

    def describe(self) -> str:
        parts = []
        if self.start:
            parts.append("from " + self.start.isoformat(sep=" ", timespec="minutes"))
        if self.end:
            parts.append("to " + self.end.isoformat(sep=" ", timespec="minutes"))
        if self.camera_ids:
            parts.append("cameras " + ",".join(str(c) for c in self.camera_ids))
        if self.kind:
            parts.append("kind " + self.kind)
        if self.direction:
            parts.append("direction " + self.direction)
        return ", ".join(parts) or "all events"


def _apply_filters(statement, filters: ReportFilters):
    if filters.start:
        statement = statement.where(CountEvent.ts >= filters.start)
    if filters.end:
        statement = statement.where(CountEvent.ts <= filters.end)
    if filters.camera_ids:
        statement = statement.where(CountEvent.camera_id.in_(filters.camera_ids))
    if filters.kind:
        statement = statement.where(CountEvent.kind == filters.kind)
    if filters.target_id is not None:
        statement = statement.where(CountEvent.target_id == filters.target_id)
    if filters.direction:
        statement = statement.where(CountEvent.direction == filters.direction)
    return statement


def fetch_events(session: Session, filters: ReportFilters) -> List[CountEvent]:
    statement = select(CountEvent).where(CountEvent.id > 0)
    statement = _apply_filters(statement, filters).order_by(CountEvent.ts)
    return list(session.execute(statement).scalars())


def floor_bucket(timestamp: dt.datetime, interval: str) -> dt.datetime:
    timestamp = timestamp.replace(second=0, microsecond=0)
    if interval == "minute":
        return timestamp
    if interval == "hour":
        return timestamp.replace(minute=0)
    if interval == "day":
        return timestamp.replace(hour=0)
    if interval == "week":
        start = timestamp - dt.timedelta(days=timestamp.weekday())
        return start.replace(hour=0)
    if interval == "month":
        return timestamp.replace(day=1, hour=0)
    raise ValueError("unsupported interval: " + str(interval))


def bucket_label(bucket: dt.datetime, interval: str) -> str:
    if interval == "minute":
        return bucket.strftime("%Y-%m-%d %H:%M")
    if interval == "hour":
        return bucket.strftime("%Y-%m-%d %H:00")
    if interval == "day":
        return bucket.strftime("%Y-%m-%d")
    if interval == "week":
        return bucket.strftime("%Y-W%V")
    if interval == "month":
        return bucket.strftime("%Y-%m")
    return bucket.strftime("%Y-%m-%d %H:%M")


def timeseries(session: Session, filters: ReportFilters, interval: str = "hour") -> List[Dict[str, Any]]:
    events = fetch_events(session, filters)
    buckets: Dict[dt.datetime, Dict[str, int]] = {}
    for event in events:
        key = floor_bucket(event.ts, interval)
        entry = buckets.setdefault(key, {"in": 0, "out": 0, "total": 0})
        entry["out" if event.direction == "OUT" else "in"] += 1
        entry["total"] += 1
    return [
        {"bucket": bucket_label(key, interval), "start": key.isoformat(), **buckets[key]}
        for key in sorted(buckets)
    ]


def summary_by_camera(session: Session, filters: ReportFilters) -> List[Dict[str, Any]]:
    events = fetch_events(session, filters)
    names = {camera.id: camera.name for camera in session.execute(select(Camera)).scalars()}
    result: Dict[int, Dict[str, Any]] = {}
    for event in events:
        entry = result.setdefault(
            event.camera_id,
            {"camera_id": event.camera_id, "camera_name": names.get(event.camera_id, ""),
             "in": 0, "out": 0, "total": 0},
        )
        entry["out" if event.direction == "OUT" else "in"] += 1
        entry["total"] += 1
    return sorted(result.values(), key=lambda item: item["camera_id"])


def summary_by_target(session: Session, filters: ReportFilters) -> List[Dict[str, Any]]:
    events = fetch_events(session, filters)
    result: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for event in events:
        key = (event.kind, event.target_id or 0)
        entry = result.setdefault(
            key,
            {"kind": event.kind, "target_id": event.target_id, "target_name": event.target_name,
             "in": 0, "out": 0, "total": 0},
        )
        entry["out" if event.direction == "OUT" else "in"] += 1
        entry["total"] += 1
    return sorted(result.values(), key=lambda item: (item["kind"], item["target_id"] or 0))


def peak_hours(session: Session, filters: ReportFilters) -> List[Dict[str, Any]]:
    """Busiest hour of the day, based on the number of counted events."""
    events = fetch_events(session, filters)
    counter: Dict[int, int] = {}
    for event in events:
        counter[event.ts.hour] = counter.get(event.ts.hour, 0) + 1
    return [
        {"hour": hour, "label": "{:02d}:00".format(hour), "count": count}
        for hour, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def totals(session: Session, filters: ReportFilters) -> Dict[str, int]:
    events = fetch_events(session, filters)
    in_count = sum(1 for event in events if event.direction == "IN")
    out_count = sum(1 for event in events if event.direction == "OUT")
    return {"in": in_count, "out": out_count, "total": in_count + out_count, "events": len(events)}


def daily_totals(session: Session, filters: ReportFilters) -> List[Dict[str, Any]]:
    series = timeseries(session, filters, "day")
    return series


def event_rows(session: Session, filters: ReportFilters) -> List[Dict[str, Any]]:
    events = fetch_events(session, filters)
    cameras = {camera.id: camera.name for camera in session.execute(select(Camera)).scalars()}
    rows = []
    for event in events:
        rows.append(
            {
                "timestamp": event.ts.isoformat(sep=" "),
                "camera_id": event.camera_id,
                "camera_name": cameras.get(event.camera_id, ""),
                "kind": event.kind,
                "target_id": event.target_id,
                "target_name": event.target_name,
                "direction": event.direction,
                "track_id": event.track_id,
                "confidence": round(event.confidence, 3),
            }
        )
    return rows
