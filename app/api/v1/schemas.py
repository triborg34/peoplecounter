"""Pydantic schemas for the REST API."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# -- auth --------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    full_name: str = ""
    email: Optional[str] = None
    role: str
    is_active: bool = True
    must_change_password: bool = False
    last_login_at: Optional[dt.datetime] = None
    created_at: Optional[dt.datetime] = None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)
    full_name: str = ""
    email: Optional[str] = None
    role: str = "viewer"

    @field_validator("role")
    @classmethod
    def _role(cls, value: str) -> str:
        value = (value or "viewer").lower()
        if value not in ("admin", "operator", "viewer"):
            raise ValueError("role must be admin, operator or viewer")
        return value


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


# -- cameras -----------------------------------------------------------
class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location: str = ""
    source_type: str = "rtsp"
    enabled: bool = True
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    has_password: bool = False
    rtsp_path: str = ""
    rtsp_url: Optional[str] = None
    file_path: Optional[str] = None
    fps_limit: float = 10.0
    detection_enabled: bool = True
    use_gpu: bool = False
    color: str = "#22c55e"
    status: str = "offline"
    live_fps: float = 0.0
    last_error: str = ""


class CameraCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    location: str = ""
    mode: str = "manual"          # manual | url | file
    host: Optional[str] = None
    port: Optional[int] = 554
    username: Optional[str] = None
    password: Optional[str] = None
    rtsp_path: str = ""
    url: Optional[str] = None
    file_path: Optional[str] = None
    fps_limit: float = 10.0
    detection_enabled: bool = True
    enabled: bool = True

    @field_validator("mode")
    @classmethod
    def _mode(cls, value: str) -> str:
        value = (value or "manual").lower()
        if value not in ("manual", "url", "file"):
            raise ValueError("mode must be manual, url or file")
        return value


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    enabled: Optional[bool] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    rtsp_path: Optional[str] = None
    url: Optional[str] = None
    file_path: Optional[str] = None
    fps_limit: Optional[float] = None
    detection_enabled: Optional[bool] = None


class CameraStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    camera_id: int
    name: str
    status: str
    fps: float = 0.0
    last_error: str = ""
    reconnect_attempts: int = 0
    detection_enabled: bool = True


class TestConnectionResult(BaseModel):
    ok: bool
    message: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0


# -- zones -------------------------------------------------------------
class LineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    name: str
    color: str = "#22c55e"
    x1: float
    y1: float
    x2: float
    y2: float
    direction: str = "BOTH"
    enabled: bool = True


class LineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)
    x2: float = Field(ge=0, le=1)
    y2: float = Field(ge=0, le=1)
    direction: str = "BOTH"
    color: str = "#22c55e"
    enabled: bool = True

    @field_validator("direction")
    @classmethod
    def _direction(cls, value: str) -> str:
        value = (value or "BOTH").upper()
        if value not in ("A_TO_B", "B_TO_A", "BOTH"):
            raise ValueError("direction must be A_TO_B, B_TO_A or BOTH")
        return value


class LineUpdate(BaseModel):
    name: Optional[str] = None
    x1: Optional[float] = Field(default=None, ge=0, le=1)
    y1: Optional[float] = Field(default=None, ge=0, le=1)
    x2: Optional[float] = Field(default=None, ge=0, le=1)
    y2: Optional[float] = Field(default=None, ge=0, le=1)
    direction: Optional[str] = None
    color: Optional[str] = None
    enabled: Optional[bool] = None

    @field_validator("direction")
    @classmethod
    def _direction(cls, value: Optional[str]) -> Optional[str]:
        # Keep PATCH as strict as POST: an unvalidated value here would be
        # stored verbatim, and a casing slip then makes both directions
        # silently behave as BOTH in the engine and draw the same arrow.
        if value is None:
            return None
        normalised = (value or "").strip().upper()
        if normalised not in ("A_TO_B", "B_TO_A", "BOTH"):
            raise ValueError("direction must be A_TO_B, B_TO_A or BOTH")
        return normalised


class AreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: int
    name: str
    color: str = "#3b82f6"
    points: List[List[float]] = Field(default_factory=list)
    enabled: bool = True


class AreaCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    points: List[List[float]] = Field(min_length=3)
    color: str = "#3b82f6"
    enabled: bool = True

    @field_validator("points")
    @classmethod
    def _points(cls, value: List[List[float]]) -> List[List[float]]:
        for point in value:
            if len(point) != 2:
                raise ValueError("each point must be [x, y]")
        return value


class AreaUpdate(BaseModel):
    name: Optional[str] = None
    points: Optional[List[List[float]]] = None
    color: Optional[str] = None
    enabled: Optional[bool] = None


# -- counts / reports --------------------------------------------------
class CountsOut(BaseModel):
    camera_id: Optional[int] = None
    summary: Dict[str, int]
    lines: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    areas: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    occupancy: Dict[str, int] = Field(default_factory=dict)


class GlobalCountsOut(BaseModel):
    summary: Dict[str, int]
    per_camera: List[Dict[str, Any]] = Field(default_factory=list)


class CountEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: dt.datetime
    camera_id: int
    camera_name: str = ""
    kind: str
    target_id: Optional[int] = None
    target_name: str = ""
    direction: str
    track_id: int
    confidence: float = 0.0


class CountStatsOut(BaseModel):
    total_in: int
    total_out: int
    net_count: int
    by_camera: Dict[str, Dict[str, int]]
    by_zone: Dict[str, Dict[str, int]]
    timeline: List[Dict[str, Any]]


class LiveCountOut(BaseModel):
    camera_id: int
    camera_name: str
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    current_count: int
    total_in: int
    total_out: int
    last_event: Optional[CountEventOut] = None


class ReportResponse(BaseModel):
    filters: Dict[str, Any]
    totals: Dict[str, int]
    timeseries: List[Dict[str, Any]] = Field(default_factory=list)
    by_camera: List[Dict[str, Any]] = Field(default_factory=list)
    by_target: List[Dict[str, Any]] = Field(default_factory=list)
    peak_hours: List[Dict[str, Any]] = Field(default_factory=list)
    events: List[Dict[str, Any]] = Field(default_factory=list)


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    prefix: str
    is_active: bool
    created_at: Optional[dt.datetime] = None
    last_used_at: Optional[dt.datetime] = None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class ApiKeyCreated(BaseModel):
    id: int
    name: str
    key: str
    prefix: str
