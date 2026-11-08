"""Integration test with the real detection model.

It is skipped unless the sample data has been generated:

    python -m app.tools.sample_data
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")

from app.engine.counter import CountingEngine
from app.engine.detector import Detector
from app.engine.tracker import ByteTrackWrapper
from app.engine.types import LineSpec, TrackedPoint

# the sample data lives in the project directory, not in the test database
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MODEL = DATA_DIR / "models" / "yolov8n.pt"
SAMPLE = DATA_DIR / "sample" / "sample_walk.mp4"

pytestmark = pytest.mark.skipif(
    not MODEL.exists() or not SAMPLE.exists(),
    reason="run 'python -m app.tools.sample_data' to generate the sample data first",
)


def read_frames(path: Path, limit: int = 40):
    capture = cv2.VideoCapture(str(path))
    frames = []
    while len(frames) < limit:
        ok, frame = capture.read()
        if not ok:
            break
        frames.append(frame)
    capture.release()
    return frames


def test_real_model_detects_and_counts_a_person_crossing_the_line():
    settings_env = os.environ.get("PCC_MODEL_NAME")
    os.environ["PCC_MODEL_NAME"] = str(MODEL)
    from app.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    settings.model_name = str(MODEL)

    detector = Detector(settings)
    assert detector.load(), detector.error

    frames = read_frames(SAMPLE, limit=40)
    assert len(frames) > 10, "the sample video could not be read"

    results = detector.detect(frames)
    assert any(len(detections) for detections in results), "no person was detected"

    tracker = ByteTrackWrapper(frame_rate=30)
    assert tracker.backend == "bytetrack", "ByteTrack should be the active tracker"

    line = LineSpec(id=1, name="Door", x1=0.5, y1=0.0, x2=0.5, y2=1.0, direction="BOTH")
    counter = CountingEngine(lines=[line], cooldown_s=0.5, min_displacement=0.005)

    track_ids = set()
    events = []
    for index, (frame, detections) in enumerate(zip(frames, results)):
        tracks = tracker.update(detections, frame)
        track_ids.update(track.track_id for track in tracks)
        height, width = frame.shape[:2]
        points = [
            TrackedPoint(
                track_id=track.track_id,
                x=((track.bbox[0] + track.bbox[2]) / 2.0) / width,
                y=track.bbox[3] / height,
                confidence=track.confidence,
            )
            for track in tracks
        ]
        events += counter.update(1, points, now=1000.0 + index * 0.125)

    assert len(track_ids) == 1, "the person must keep one stable track id"
    assert len(events) == 1, "the person must cross the line exactly once"
    assert events[0].direction in ("IN", "OUT")
    assert counter.camera_summary(1)["total"] == 1

    if settings_env is not None:
        os.environ["PCC_MODEL_NAME"] = settings_env
