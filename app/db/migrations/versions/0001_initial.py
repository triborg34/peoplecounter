"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2024-01-01 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=128)),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="rtsp"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("host", sa.String(length=128)),
        sa.Column("port", sa.Integer(), nullable=False, server_default="554"),
        sa.Column("username", sa.String(length=128)),
        sa.Column("password_enc", sa.Text()),
        sa.Column("rtsp_path", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("rtsp_url", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("fps_limit", sa.Float(), nullable=False, server_default="10.0"),
        sa.Column("detection_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("use_gpu", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#22c55e"),
        sa.Column("reconnect_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_cameras_name", "cameras", ["name"], unique=True)

    op.create_table(
        "counter_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#22c55e"),
        sa.Column("x1", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("y1", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("x2", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("y2", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("direction", sa.String(length=16), nullable=False, server_default="BOTH"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("camera_id", "name", name="uq_line_camera_name"),
    )
    op.create_index("ix_counter_lines_camera_id", "counter_lines", ["camera_id"])

    op.create_table(
        "counter_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("color", sa.String(length=16), nullable=False, server_default="#3b82f6"),
        sa.Column("points", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("camera_id", "name", name="uq_area_camera_name"),
    )
    op.create_index("ix_counter_areas_camera_id", "counter_areas", ["camera_id"])

    op.create_table(
        "count_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("camera_id", sa.Integer(), sa.ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="line"),
        sa.Column("target_id", sa.Integer()),
        sa.Column("target_name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("direction", sa.String(length=8), nullable=False, server_default="IN"),
        sa.Column("track_id", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("point_x", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("point_y", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_count_events_ts", "count_events", ["ts"])
    op.create_index("ix_count_events_camera_id", "count_events", ["camera_id"])
    op.create_index("ix_count_events_target_id", "count_events", ["target_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("user_id", sa.Integer()),
        sa.Column("username", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=32)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
        sa.Column("ip_address", sa.String(length=64), nullable=False, server_default=""),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=64)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_used_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_api_keys_prefix", "api_keys", ["prefix"])

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("api_keys")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_count_events_target_id", table_name="count_events")
    op.drop_index("ix_count_events_camera_id", table_name="count_events")
    op.drop_index("ix_count_events_ts", table_name="count_events")
    op.drop_table("count_events")
    op.drop_index("ix_counter_areas_camera_id", table_name="counter_areas")
    op.drop_table("counter_areas")
    op.drop_index("ix_counter_lines_camera_id", table_name="counter_lines")
    op.drop_table("counter_lines")
    op.drop_index("ix_cameras_name", table_name="cameras")
    op.drop_table("cameras")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
