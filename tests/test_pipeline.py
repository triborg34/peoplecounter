"""End to end test of the capture -> detection -> tracking -> counting pipeline."""
from __future__ import annotations

import time

import numpy as np

from app.db.models import Camera, CountEvent, CounterLine
from app.engine.types import Detection, Track


class FakeTracker:
    """Assigns a stable track id per detection slot."""

    def __init__(self):
        self.ids = {}
        self.next_id = 1

    def update(self, detections, frame=None):
        tracks = []
        for index, detection in enumerate(detections):
            if index not in self.ids:
                self.ids[index] = self.next_id
                self.next_id += 1
            tracks.append(
                Track(
                    track_id=self.ids[index],
                    bbox=detection.bbox,
                    confidence=detection.confidence,
                    class_id=detection.class_id,
                )
            )
        return tracks


def make_camera(runtime, direction: str = "A_TO_B") -> int:
    with runtime.db.session_scope() as session:
        camera = Camera(name="Test camera", source_type="file", file_path="n/a", enabled=False)
        session.add(camera)
        session.flush()
        line = CounterLine(
            camera_id=camera.id,
            name="Entrance",
            x1=0.25, y1=0.5, x2=0.75, y2=0.5,
            direction=direction,
            enabled=True,
        )
        session.add(line)
        camera_id = camera.id
    runtime.sync_camera(camera_id)
    runtime.camera_manager.trackers[camera_id] = FakeTracker()
    return camera_id


def frame_of(size: int = 200) -> np.ndarray:
    return np.zeros((size, size, 3), dtype=np.uint8)


def feed(runtime, camera_id: int, box, timestamp: float, class_id: int = 0):
    detection = Detection(bbox=box, confidence=0.9, class_id=class_id)
    runtime.camera_manager._process_camera(camera_id, frame_of(), timestamp, [detection])


def test_person_crossing_the_line_is_counted_and_persisted(runtime):
    camera_id = make_camera(runtime, "A_TO_B")
    feed(runtime, camera_id, (90, 60, 110, 90), 1000.0)
    feed(runtime, camera_id, (90, 95, 110, 125), 1000.5)

    summary = runtime.camera_manager.counter.camera_summary(camera_id)
    assert summary["in"] == 1
    assert summary["total"] == 1

    runtime.event_writer.flush()
    with runtime.db.session_scope() as session:
        rows = session.query(CountEvent).filter(CountEvent.camera_id == camera_id).all()
        assert len(rows) == 1
        assert rows[0].direction == "IN"
        assert rows[0].kind == "line"
        assert rows[0].track_id >= 0


def test_reverse_crossing_is_not_counted_for_a_to_b_lines(runtime):
    camera_id = make_camera(runtime, "A_TO_B")
    feed(runtime, camera_id, (90, 95, 110, 125), 1000.0)
    feed(runtime, camera_id, (90, 60, 110, 90), 1000.5)
    assert runtime.camera_manager.counter.camera_summary(camera_id)["total"] == 0


def test_both_direction_line_counts_in_and_out(runtime):
    camera_id = make_camera(runtime, "BOTH")
    feed(runtime, camera_id, (90, 60, 110, 90), 1000.0)
    feed(runtime, camera_id, (90, 95, 110, 125), 1000.5)
    feed(runtime, camera_id, (90, 95, 110, 125), 1003.0)
    feed(runtime, camera_id, (90, 60, 110, 90), 1003.5)
    summary = runtime.camera_manager.counter.camera_summary(camera_id)
    assert summary["in"] == 1
    assert summary["out"] == 1


def test_non_person_classes_are_never_counted(runtime):
    camera_id = make_camera(runtime, "BOTH")
    feed(runtime, camera_id, (90, 60, 110, 90), 1000.0, class_id=0)
    feed(runtime, camera_id, (90, 95, 110, 125), 1000.5, class_id=2)   # a car
    assert runtime.camera_manager.counter.camera_summary(camera_id)["total"] == 0


def test_counters_are_reset_on_request(runtime):
    camera_id = make_camera(runtime, "A_TO_B")
    feed(runtime, camera_id, (90, 60, 110, 90), 1000.0)
    feed(runtime, camera_id, (90, 95, 110, 125), 1000.5)
    assert runtime.camera_manager.counter.camera_summary(camera_id)["total"] == 1
    runtime.reset_counters(camera_id)
    assert runtime.camera_manager.counter.camera_summary(camera_id)["total"] == 0
    with runtime.db.session_scope() as session:
        assert session.query(CountEvent).filter(CountEvent.camera_id == camera_id).count() == 0
