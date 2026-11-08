"""Shared value objects for the engine layer."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class CameraStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    RECONNECTING = "reconnecting"
    STOPPED = "stopped"
    STARTING = "starting"


class Direction(str, Enum):
    IN = "IN"
    OUT = "OUT"


class LineDirection(str, Enum):
    A_TO_B = "A_TO_B"
    B_TO_A = "B_TO_A"
    BOTH = "BOTH"


@dataclass
class Detection:
    """A single person detection in pixel coordinates of the source frame."""

    bbox: Tuple[float, float, float, float]  # x1, y1, x2, y2
    confidence: float = 0.0
    class_id: int = 0
    track_id: int = -1

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)


@dataclass
class Track:
    """A tracked person: detection + persistent track id."""

    track_id: int
    bbox: Tuple[float, float, float, float]
    confidence: float = 0.0
    class_id: int = 0

    @property
    def center(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)


@dataclass
class TrackedPoint:
    """Normalised (0..1) position of a tracked person used by the counter."""

    track_id: int
    x: float
    y: float
    confidence: float = 0.0
    bbox: Optional[Tuple[float, float, float, float]] = None


@dataclass
class LineSpec:
    id: int
    name: str
    x1: float
    y1: float
    x2: float
    y2: float
    direction: str = "BOTH"
    enabled: bool = True
    color: str = "#22c55e"
    camera_id: int = 0  # 0 means the zone applies to every camera


@dataclass
class AreaSpec:
    id: int
    name: str
    points: List[Tuple[float, float]]
    enabled: bool = True
    color: str = "#3b82f6"
    camera_id: int = 0  # 0 means the zone applies to every camera


@dataclass
class CountEvent:
    """A single counted crossing / area transition."""

    camera_id: int
    kind: str                # "line" | "area"
    target_id: int
    target_name: str
    direction: str           # IN | OUT
    track_id: int
    confidence: float = 0.0
    x: float = 0.0
    y: float = 0.0
    timestamp: float = field(default_factory=time.time)
    camera_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "kind": self.kind,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "direction": self.direction,
            "track_id": self.track_id,
            "confidence": round(self.confidence, 4),
            "x": round(self.x, 5),
            "y": round(self.y, 5),
            "timestamp": self.timestamp,
        }


@dataclass
class FramePacket:
    """Latest annotated frame of one camera, shared by every consumer."""

    camera_id: int
    frame: Any                     # numpy array (BGR), annotated
    timestamp: float
    raw_frame: Any = None          # numpy array (BGR), unannotated
    seq: int = 0
    detections: List[Detection] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    fps: float = 0.0
    status: str = CameraStatus.ONLINE.value
    width: int = 0
    height: int = 0


@dataclass
class CameraRuntimeInfo:
    camera_id: int
    name: str
    status: str = CameraStatus.OFFLINE.value
    fps: float = 0.0
    last_frame_ts: float = 0.0
    last_error: str = ""
    reconnect_attempts: int = 0
    detection_enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "name": self.name,
            "status": self.status,
            "fps": round(self.fps, 2),
            "last_error": self.last_error,
            "reconnect_attempts": self.reconnect_attempts,
            "detection_enabled": self.detection_enabled,
        }
