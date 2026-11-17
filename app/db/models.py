"""SQLAlchemy ORM models.

Table layout
------------
users          application accounts and roles
cameras        camera inventory (rtsp manual fields, direct url or video file)
counter_lines  named counting lines per camera (normalised coordinates)
counter_areas  named counting polygons per camera (normalised coordinates)
count_events   one row per counted crossing / area transition
audit_log      security and administration audit trail
api_keys       machine-to-machine keys for the REST API
app_settings   key/value runtime settings
"""
from __future__ import annotations

import datetime as dt
import json
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), default="")
    email: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="viewer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username} ({self.role})>"


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    location: Mapped[str] = mapped_column(String(255), default="")
    source_type: Mapped[str] = mapped_column(String(16), default="rtsp", nullable=False)  # rtsp | file
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # manual rtsp fields
    host: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    port: Mapped[int] = mapped_column(default=554)
    username: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    password_enc: Mapped[Optional[str]] = mapped_column(Text, default=None)
    rtsp_path: Mapped[str] = mapped_column(String(255), default="")
    # direct rtsp url (may embed credentials) - credentials are stripped out
    # into username/password_enc when the camera is saved.
    rtsp_url: Mapped[Optional[str]] = mapped_column(Text, default=None)
    # simulation / video file source
    file_path: Mapped[Optional[str]] = mapped_column(Text, default=None)

    fps_limit: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)
    detection_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_gpu: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#22c55e", nullable=False)
    reconnect_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    lines: Mapped[List["CounterLine"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan", lazy="selectin"
    )
    areas: Mapped[List["CounterArea"]] = relationship(
        back_populates="camera", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Camera {self.name}>"


class CounterLine(Base):
    __tablename__ = "counter_lines"
    __table_args__ = (UniqueConstraint("camera_id", "name", name="uq_line_camera_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#22c55e", nullable=False)
    # normalised coordinates in the range 0..1
    x1: Mapped[float] = mapped_column(Float, default=0.0)
    y1: Mapped[float] = mapped_column(Float, default=0.0)
    x2: Mapped[float] = mapped_column(Float, default=0.0)
    y2: Mapped[float] = mapped_column(Float, default=0.0)
    direction: Mapped[str] = mapped_column(String(16), default="BOTH", nullable=False)
    # Two slots, "<A->B><B->A>", each I (IN) / O (OUT) / X (ignored), for example
    # "IO" = A->B is IN and B->A is OUT. Legacy A_TO_B / B_TO_A / BOTH rows are
    # still interpreted by CountingEngine._line_direction.
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    camera: Mapped["Camera"] = relationship(back_populates="lines")


class CounterArea(Base):
    __tablename__ = "counter_areas"
    __table_args__ = (UniqueConstraint("camera_id", "name", name="uq_area_camera_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    color: Mapped[str] = mapped_column(String(16), default="#3b82f6", nullable=False)
    points: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list of [x, y]
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    camera: Mapped["Camera"] = relationship(back_populates="areas")

    @property
    def points_list(self):
        """Polygon points as a list of (x, y) tuples in normalised space."""
        try:
            data = json.loads(self.points or "[]")
            return [(float(point[0]), float(point[1])) for point in data]
        except Exception:
            return []


class CountEvent(Base):
    __tablename__ = "count_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), default="line", nullable=False)  # line | area
    target_id: Mapped[Optional[int]] = mapped_column(Integer, default=None, index=True)
    target_name: Mapped[str] = mapped_column(String(128), default="")
    direction: Mapped[str] = mapped_column(String(8), default="IN", nullable=False)  # IN | OUT
    track_id: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    point_x: Mapped[float] = mapped_column(Float, default=0.0)
    point_y: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, default=None)
    details: Mapped[str] = mapped_column(Text, default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, default=None)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
