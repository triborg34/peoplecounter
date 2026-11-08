"""Unit tests for the counting logic."""
from __future__ import annotations

import math

import pytest

from app.engine.counter import (
    CROSS_A_TO_B,
    CROSS_B_TO_A,
    CountingEngine,
    cross_classify,
    point_in_polygon,
    segments_intersect,
)
from app.engine.types import AreaSpec, LineSpec, TrackedPoint

HORIZONTAL = LineSpec(id=1, name="Entrance", x1=0.25, y1=0.5, x2=0.75, y2=0.5, direction="BOTH")
SQUARE = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]


def point(track_id: int, x: float, y: float) -> TrackedPoint:
    return TrackedPoint(track_id=track_id, x=x, y=y, confidence=0.9)


def engine_for(direction: str = "A_TO_B", **kwargs) -> CountingEngine:
    line = LineSpec(id=1, name="Entrance", x1=0.25, y1=0.5, x2=0.75, y2=0.5, direction=direction)
    return CountingEngine(lines=[line], **kwargs)


# -- geometry ----------------------------------------------------------
def test_segments_intersect_crossing():
    assert segments_intersect((0.4, 0.2), (0.4, 0.8), (0.2, 0.5), (0.8, 0.5)) is True


def test_segments_intersect_missing():
    assert segments_intersect((0.1, 0.1), (0.2, 0.2), (0.6, 0.6), (0.9, 0.9)) is False


def test_point_in_polygon_inside_and_outside():
    assert point_in_polygon((0.5, 0.5), SQUARE) is True
    assert point_in_polygon((0.1, 0.1), SQUARE) is False


def test_cross_classify_perpendicular_and_parallel():
    a = (0.25, 0.5)
    b = (0.75, 0.5)
    # walking down the screen across a left to right line
    assert cross_classify((0.5, 0.3), (0.5, 0.7), a, b) == CROSS_A_TO_B
    # walking up the screen
    assert cross_classify((0.5, 0.7), (0.5, 0.3), a, b) == CROSS_B_TO_A
    # walking along the line towards B
    assert cross_classify((0.3, 0.5), (0.7, 0.5), a, b) == CROSS_A_TO_B
    # walking along the line back to A
    assert cross_classify((0.7, 0.5), (0.3, 0.5), a, b) == CROSS_B_TO_A


# -- line counting -----------------------------------------------------
def test_first_frame_never_counts():
    engine = engine_for("A_TO_B")
    assert engine.update(1, [point(1, 0.5, 0.3)], now=100.0) == []


def test_crossing_a_to_b_counts_in():
    engine = engine_for("A_TO_B")
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.7)], now=100.5)
    assert len(events) == 1
    assert events[0].direction == "IN"
    assert events[0].kind == "line"
    assert events[0].target_id == 1
    assert engine.camera_summary(1) == {"in": 1, "out": 0, "total": 1, "occupancy": 0}


def test_crossing_b_to_a_is_ignored_for_a_to_b_lines():
    engine = engine_for("A_TO_B")
    engine.update(1, [point(1, 0.5, 0.7)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.3)], now=100.5)
    assert events == []
    assert engine.camera_summary(1)["total"] == 0


def test_crossing_b_to_a_counts_in_for_b_to_a_lines():
    engine = engine_for("B_TO_A")
    engine.update(1, [point(1, 0.5, 0.7)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.3)], now=100.5)
    assert len(events) == 1
    assert events[0].direction == "IN"


def test_both_directions_counts_in_and_out_separately():
    engine = engine_for("BOTH")
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    first = engine.update(1, [point(1, 0.5, 0.7)], now=100.5)
    engine.update(1, [point(2, 0.5, 0.7)], now=101.0)
    second = engine.update(1, [point(2, 0.5, 0.3)], now=101.5)
    assert first[0].direction == "IN"
    assert second[0].direction == "OUT"
    assert engine.camera_summary(1) == {"in": 1, "out": 1, "total": 2, "occupancy": 0}


def test_jitter_does_not_count_twice():
    """The same track wobbling over the line must only count once."""
    engine = engine_for("BOTH", cooldown_s=5.0, min_displacement=0.05)
    engine.update(1, [point(1, 0.5, 0.45)], now=100.0)
    events = []
    for index in range(6):
        y = 0.55 if index % 2 == 0 else 0.45
        events += engine.update(1, [point(1, 0.5, y)], now=100.1 + index * 0.05)
    assert len(events) == 1


def test_cooldown_blocks_immediate_second_crossing():
    engine = engine_for("BOTH", cooldown_s=10.0, min_displacement=0.0)
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    engine.update(1, [point(1, 0.5, 0.7)], now=100.5)
    events = engine.update(1, [point(1, 0.5, 0.3)], now=101.0)
    assert events == []


def test_different_track_ids_are_counted_independently():
    engine = engine_for("A_TO_B")
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    engine.update(1, [point(2, 0.5, 0.3)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.7), point(2, 0.5, 0.7)], now=100.5)
    assert len(events) == 2
    assert engine.camera_summary(1)["total"] == 2


def test_disabled_lines_are_ignored():
    line = LineSpec(id=1, name="Off", x1=0.25, y1=0.5, x2=0.75, y2=0.5, direction="BOTH", enabled=False)
    engine = CountingEngine(lines=[line])
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    assert engine.update(1, [point(1, 0.5, 0.7)], now=100.5) == []


def test_zones_of_another_camera_are_ignored():
    """A line of camera 2 must never count a person of camera 1."""
    line_one = LineSpec(id=1, name="One", x1=0.25, y1=0.5, x2=0.75, y2=0.5,
                        direction="BOTH", camera_id=1)
    line_two = LineSpec(id=2, name="Two", x1=0.25, y1=0.5, x2=0.75, y2=0.5,
                        direction="BOTH", camera_id=2)
    engine = CountingEngine(lines=[line_one, line_two])

    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.7)], now=100.5)
    assert len(events) == 1
    assert events[0].target_id == 1
    assert engine.camera_summary(1)["total"] == 1
    assert engine.camera_summary(2)["total"] == 0


def test_set_camera_zones_keeps_the_zones_of_other_cameras():
    engine = CountingEngine()
    engine.set_camera_zones(
        1, [LineSpec(id=1, name="A", x1=0.25, y1=0.5, x2=0.75, y2=0.5, camera_id=1)], []
    )
    engine.set_camera_zones(
        2, [LineSpec(id=2, name="B", x1=0.25, y1=0.5, x2=0.75, y2=0.5, camera_id=2)], []
    )
    assert sorted(line.id for line in engine.lines) == [1, 2]

    # reloading one camera replaces only its own zones
    engine.set_camera_zones(
        1, [LineSpec(id=3, name="C", x1=0.25, y1=0.5, x2=0.75, y2=0.5, camera_id=1)], []
    )
    assert sorted(line.id for line in engine.lines) == [2, 3]


def test_reset_clears_counters():
    engine = engine_for("A_TO_B")
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    engine.update(1, [point(1, 0.5, 0.7)], now=100.5)
    assert engine.camera_summary(1)["total"] == 1
    engine.reset(1)
    assert engine.camera_summary(1)["total"] == 0


# -- area counting -----------------------------------------------------
def test_area_enter_and_exit_with_occupancy():
    area = AreaSpec(id=5, name="Lobby", points=SQUARE)
    engine = CountingEngine(areas=[area])
    engine.update(1, [point(1, 0.1, 0.1)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.5)], now=100.5)
    assert len(events) == 1
    assert events[0].direction == "IN"
    assert events[0].kind == "area"
    assert engine.occupancy(1)[5] == 1
    assert engine.camera_summary(1)["occupancy"] == 1

    events = engine.update(1, [point(1, 0.9, 0.9)], now=103.0)
    assert len(events) == 1
    assert events[0].direction == "OUT"
    assert engine.occupancy(1)[5] == 0
    assert engine.camera_summary(1) == {"in": 1, "out": 1, "total": 2, "occupancy": 0}


def test_area_occupancy_counts_every_person_inside():
    area = AreaSpec(id=5, name="Lobby", points=SQUARE)
    engine = CountingEngine(areas=[area])
    engine.update(1, [point(1, 0.1, 0.1), point(2, 0.1, 0.1)], now=100.0)
    engine.update(1, [point(1, 0.4, 0.4), point(2, 0.6, 0.6)], now=100.5)
    assert engine.occupancy(1)[5] == 2
    assert engine.camera_summary(1)["occupancy"] == 2


def test_area_jitter_does_not_count_twice():
    area = AreaSpec(id=5, name="Lobby", points=SQUARE)
    engine = CountingEngine(areas=[area], cooldown_s=5.0, min_displacement=0.05)
    events = []
    events += engine.update(1, [point(1, 0.1, 0.1)], now=100.0)
    events += engine.update(1, [point(1, 0.3, 0.3)], now=100.2)
    events += engine.update(1, [point(1, 0.31, 0.31)], now=100.4)
    assert len(events) == 1
    assert events[0].direction == "IN"


def test_line_and_area_together():
    door = [(0.4, 0.35), (0.6, 0.35), (0.6, 0.65), (0.4, 0.65)]
    engine = CountingEngine(lines=[HORIZONTAL], areas=[AreaSpec(id=5, name="Lobby", points=door)])
    engine.update(1, [point(1, 0.5, 0.3)], now=100.0)
    events = engine.update(1, [point(1, 0.5, 0.55)], now=100.5)
    kinds = sorted(event.kind for event in events)
    assert kinds == ["area", "line"]
    summary = engine.camera_summary(1)
    assert summary["in"] == 2   # one line crossing and one area entry
    assert summary["occupancy"] == 1


def test_global_summary_sums_all_cameras():
    engine = engine_for("A_TO_B")
    for camera_id in (1, 2):
        engine.update(camera_id, [point(camera_id, 0.5, 0.3)], now=100.0)
        engine.update(camera_id, [point(camera_id, 0.5, 0.7)], now=100.5)
    assert engine.global_summary() == {"in": 2, "out": 0, "total": 2, "occupancy": 0}
