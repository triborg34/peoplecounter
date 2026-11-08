"""Counting logic: line crossings and area occupancy.

Pure geometry, no OpenCV / numpy required, so it is cheap to unit test.

Coordinates are normalised to 0..1 so that the same geometry works at any
resolution.  A crossing is detected when the movement segment of a track
(previous point -> current point) intersects the line segment, and the
direction is derived from the sign of the projection of the movement onto the
line vector.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .types import AreaSpec, CountEvent, LineSpec, TrackedPoint

Point = Tuple[float, float]

# Movement classification for a line crossing.
CROSS_A_TO_B = "A_TO_B"
CROSS_B_TO_A = "B_TO_A"

# Anti-jitter thresholds
DEFAULT_COOLDOWN_S = 1.5
DEFAULT_MIN_DISPLACEMENT = 0.015
TRACK_TTL_S = 30.0


def cross_product(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def orientation(a: Point, b: Point, c: Point) -> float:
    """Sign of the cross product (b-a) x (c-a)."""
    return cross_product(b[0] - a[0], b[1] - a[1], c[0] - a[0], c[1] - a[1])


def on_segment(a: Point, b: Point, p: Point, eps: float = 1e-9) -> bool:
    return (
        min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
        and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps
    )


def segments_intersect(p1: Point, p2: Point, p3: Point, p4: Point) -> bool:
    """True when segment p1->p2 intersects segment p3->p4 (inclusive)."""
    d1 = orientation(p3, p4, p1)
    d2 = orientation(p3, p4, p2)
    d3 = orientation(p1, p2, p3)
    d4 = orientation(p1, p2, p4)

    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 != 0 and d2 != 0 and d3 != 0 and d4 != 0:
        return True

    # Collinear / touching cases
    if abs(d1) < 1e-12 and on_segment(p3, p4, p1):
        return True
    if abs(d2) < 1e-12 and on_segment(p3, p4, p2):
        return True
    if abs(d3) < 1e-12 and on_segment(p1, p2, p3):
        return True
    if abs(d4) < 1e-12 and on_segment(p1, p2, p4):
        return True
    return False


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray casting algorithm; points exactly on the edge count as inside."""
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        # boundary check
        if abs(cross_product(x2 - x1, y2 - y1, x - x1, y - y1)) < 1e-12 and on_segment(
            (x1, y1), (x2, y2), point
        ):
            return True
        if (y1 > y) != (y2 > y):
            x_int = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_int:
                inside = not inside
    return inside


@dataclass
class _TrackState:
    last_point: Optional[Point] = None
    last_ts: float = 0.0
    # line_id -> (timestamp, point) of the last accepted crossing
    line_crossings: Dict[int, Tuple[float, Point]] = field(default_factory=dict)
    # area_id -> inside?
    area_state: Dict[int, bool] = field(default_factory=dict)
    # area_id -> (timestamp, point) of the last accepted area transition
    area_crossings: Dict[int, Tuple[float, Point]] = field(default_factory=dict)


@dataclass
class CounterTotals:
    """Aggregated counters for one (camera, target) pair."""

    in_count: int = 0
    out_count: int = 0

    @property
    def total(self) -> int:
        return self.in_count + self.out_count

    def to_dict(self) -> Dict[str, int]:
        return {"in": self.in_count, "out": self.out_count, "total": self.total}


class CountingEngine:
    """Counts crossings of lines and transitions of areas for every camera."""

    def __init__(
        self,
        lines: Optional[Iterable[LineSpec]] = None,
        areas: Optional[Iterable[AreaSpec]] = None,
        point_mode: str = "bottom",
        cooldown_s: float = DEFAULT_COOLDOWN_S,
        min_displacement: float = DEFAULT_MIN_DISPLACEMENT,
    ):
        self.lines: List[LineSpec] = list(lines or [])
        self.areas: List[AreaSpec] = list(areas or [])
        self.point_mode = point_mode
        self.cooldown_s = cooldown_s
        self.min_displacement = min_displacement
        self._tracks: Dict[int, Dict[int, _TrackState]] = {}
        self._totals: Dict[int, Dict[Tuple[str, int], CounterTotals]] = {}
        self._occupancy: Dict[int, Dict[int, int]] = {}

    # -- configuration --------------------------------------------------
    def set_lines(self, lines: Iterable[LineSpec]) -> None:
        self.lines = list(lines)
        self._prune_missing_targets("line")

    def set_areas(self, areas: Iterable[AreaSpec]) -> None:
        self.areas = list(areas)
        self._prune_missing_targets("area")

    def set_camera_zones(
        self,
        camera_id: int,
        lines: Iterable[LineSpec],
        areas: Iterable[AreaSpec],
    ) -> None:
        """Replace the zones of one camera and leave the other cameras alone."""
        lines = list(lines)
        areas = list(areas)
        self.lines = [line for line in self.lines if line.camera_id != camera_id] + lines
        self.areas = [area for area in self.areas if area.camera_id != camera_id] + areas
        self._prune_missing_targets("line")
        self._prune_missing_targets("area")

    @staticmethod
    def _belongs_to(spec: Any, camera_id: int) -> bool:
        """Zones of another camera never affect this camera."""
        return not spec.camera_id or spec.camera_id == camera_id

    def _prune_missing_targets(self, kind: str) -> None:
        valid = {spec.id for spec in (self.lines if kind == "line" else self.areas)}
        for camera_totals in self._totals.values():
            for key in [k for k in camera_totals if k[0] == kind and k[1] not in valid]:
                camera_totals.pop(key, None)
        for camera_states in self._tracks.values():
            for state in camera_states.values():
                if kind == "line":
                    for line_id in [lid for lid in state.line_crossings if lid not in valid]:
                        state.line_crossings.pop(line_id, None)
                else:
                    for area_id in [aid for aid in state.area_state if aid not in valid]:
                        state.area_state.pop(area_id, None)
                    for area_id in [aid for aid in state.area_crossings if aid not in valid]:
                        state.area_crossings.pop(area_id, None)

    # -- state ----------------------------------------------------------
    def reset(self, camera_id: Optional[int] = None) -> None:
        """Clear counters (and optionally only for one camera)."""
        if camera_id is None:
            self._tracks.clear()
            self._totals.clear()
            self._occupancy.clear()
            return
        self._tracks.pop(camera_id, None)
        self._totals.pop(camera_id, None)
        self._occupancy.pop(camera_id, None)

    def counters(self, camera_id: int) -> Dict[Tuple[str, int], CounterTotals]:
        return self._totals.setdefault(camera_id, {})

    def totals_for(self, camera_id: int, kind: str, target_id: int) -> CounterTotals:
        return self.counters(camera_id).setdefault((kind, target_id), CounterTotals())

    def occupancy(self, camera_id: int) -> Dict[int, int]:
        return self._occupancy.setdefault(camera_id, {})

    def camera_summary(self, camera_id: int) -> Dict[str, int]:
        tot_in = sum(t.in_count for t in self._totals.get(camera_id, {}).values())
        tot_out = sum(t.out_count for t in self._totals.get(camera_id, {}).values())
        occupancy = sum(self._occupancy.get(camera_id, {}).values())
        return {"in": tot_in, "out": tot_out, "total": tot_in + tot_out, "occupancy": occupancy}

    def global_summary(self) -> Dict[str, int]:
        tot_in = tot_out = occupancy = 0
        for camera_id in self._totals:
            summary = self.camera_summary(camera_id)
            tot_in += summary["in"]
            tot_out += summary["out"]
            occupancy += summary["occupancy"]
        return {"in": tot_in, "out": tot_out, "total": tot_in + tot_out, "occupancy": occupancy}

    # -- counting -------------------------------------------------------
    def update(
        self,
        camera_id: int,
        points: Sequence[TrackedPoint],
        now: Optional[float] = None,
    ) -> List[CountEvent]:
        """Feed the current tracked points of one camera, get new count events."""
        now = time.time() if now is None else now
        camera_tracks = self._tracks.setdefault(camera_id, {})
        events: List[CountEvent] = []
        seen_ids = set()

        for point in points:
            seen_ids.add(point.track_id)
            state = camera_tracks.setdefault(point.track_id, _TrackState())
            current: Point = (point.x, point.y)

            # --- lines -------------------------------------------------
            if self.lines:
                prev = state.last_point
                if prev is not None:
                    for line in self.lines:
                        if not line.enabled:
                            continue
                        if not self._belongs_to(line, camera_id):
                            continue
                        if not segments_intersect(
                            prev, current, (line.x1, line.y1), (line.x2, line.y2)
                        ):
                            continue
                        movement = cross_classify(prev, current, (line.x1, line.y1), (line.x2, line.y2))
                        if movement is None:
                            continue
                        direction = self._line_direction(line.direction, movement)
                        if direction is None:
                            continue
                        if not self._debounce_line(state, line.id, current, now):
                            continue
                        events.append(
                            CountEvent(
                                camera_id=camera_id,
                                kind="line",
                                target_id=line.id,
                                target_name=line.name,
                                direction=direction,
                                track_id=point.track_id,
                                confidence=point.confidence,
                                x=current[0],
                                y=current[1],
                                timestamp=now,
                            )
                        )
                        totals = self.totals_for(camera_id, "line", line.id)
                        if direction == "IN":
                            totals.in_count += 1
                        else:
                            totals.out_count += 1

            # --- areas -------------------------------------------------
            if self.areas:
                for area in self.areas:
                    if not area.enabled:
                        continue
                    if not self._belongs_to(area, camera_id):
                        continue
                    inside = point_in_polygon(current, area.points)
                    previous_inside = state.area_state.get(area.id)
                    state.area_state[area.id] = inside
                    if previous_inside is None:
                        continue
                    if previous_inside == inside:
                        continue
                    if not self._debounce_area(state, area.id, current, now):
                        continue
                    direction = "IN" if inside else "OUT"
                    events.append(
                        CountEvent(
                            camera_id=camera_id,
                            kind="area",
                            target_id=area.id,
                            target_name=area.name,
                            direction=direction,
                            track_id=point.track_id,
                            confidence=point.confidence,
                            x=current[0],
                            y=current[1],
                            timestamp=now,
                        )
                    )
                    totals = self.totals_for(camera_id, "area", area.id)
                    if direction == "IN":
                        totals.in_count += 1
                    else:
                        totals.out_count += 1

            state.last_point = current
            state.last_ts = now

        self._update_occupancy(camera_id, camera_tracks)
        self._expire_tracks(camera_tracks, seen_ids, now)
        return events

    # -- helpers --------------------------------------------------------
    @staticmethod
    def _line_direction(configured: str, movement: str) -> Optional[str]:
        """Map a geometric crossing onto the configured line direction."""
        configured = (configured or "BOTH").upper()
        if configured == "A_TO_B":
            return "IN" if movement == CROSS_A_TO_B else None
        if configured == "B_TO_A":
            return "IN" if movement == CROSS_B_TO_A else None
        # BOTH: A->B counts as IN, B->A counts as OUT
        return "IN" if movement == CROSS_A_TO_B else "OUT"

    def _debounce_line(self, state: _TrackState, line_id: int, point: Point, now: float) -> bool:
        previous = state.line_crossings.get(line_id)
        if previous is not None:
            last_ts, last_point = previous
            if now - last_ts < self.cooldown_s:
                return False
            displacement = math.dist(point, last_point)
            if displacement < self.min_displacement:
                return False
        state.line_crossings[line_id] = (now, point)
        return True

    def _debounce_area(self, state: _TrackState, area_id: int, point: Point, now: float) -> bool:
        previous = state.area_crossings.get(area_id)
        if previous is not None:
            last_ts, last_point = previous
            if now - last_ts < self.cooldown_s:
                return False
            if math.dist(point, last_point) < self.min_displacement:
                return False
        state.area_crossings[area_id] = (now, point)
        return True

    def _update_occupancy(self, camera_id: int, camera_tracks: Dict[int, _TrackState]) -> None:
        occupancy = self._occupancy.setdefault(camera_id, {})
        for area in self.areas:
            if not area.enabled or not self._belongs_to(area, camera_id):
                occupancy.pop(area.id, None)
                continue
            count = sum(
                1
                for state in camera_tracks.values()
                if state.area_state.get(area.id) is True
            )
            occupancy[area.id] = count

    def _expire_tracks(self, camera_tracks: Dict[int, _TrackState], seen: set, now: float) -> None:
        stale = [tid for tid, state in camera_tracks.items() if tid not in seen and now - state.last_ts > TRACK_TTL_S]
        for tid in stale:
            camera_tracks.pop(tid, None)


def cross_classify(prev: Point, current: Point, a: Point, b: Point) -> Optional[str]:
    """Classify the movement of a track relative to the line A->B.

    The movement vector is compared with the line vector:

    * mostly parallel  -> the sign of the dot product decides (walking A to B
      or walking back B to A),
    * mostly perpendicular -> the sign of the cross product decides, which is
      exactly the half plane the track moves into: crossing from the
      "negative" side (right of A->B) to the "positive" side (left of A->B)
      is a crossing from A to B.

    Both rules together classify every crossing unambiguously.
    """
    vx = b[0] - a[0]
    vy = b[1] - a[1]
    mx = current[0] - prev[0]
    my = current[1] - prev[1]
    if abs(vx) < 1e-12 and abs(vy) < 1e-12:
        return None
    if abs(mx) < 1e-12 and abs(my) < 1e-12:
        return None
    dot = mx * vx + my * vy
    cross = vx * my - vy * mx
    if abs(dot) >= abs(cross):
        if dot > 0:
            return CROSS_A_TO_B
        if dot < 0:
            return CROSS_B_TO_A
        return None
    if cross > 0:
        return CROSS_A_TO_B
    if cross < 0:
        return CROSS_B_TO_A
    return None
