r"""Application settings, loaded from environment / .env file.

Every value can be overridden with a \PCC_ prefixed environment variable, e.g.
PCC_DATABASE_URL=postgresql+psycopg://user:pass@host/db
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PCC_",
        env_file=(BASE_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- general -------------------------------------------------------
    app_name: str = "People Counter"
    log_level: str = "INFO"
    log_dir: str = str(BASE_DIR / "logs")
    log_max_bytes: int = 5_000_000
    log_backup_count: int = 5
    data_dir: str = str(DATA_DIR)

    # --- database ------------------------------------------------------
    # SQLite by default; switch to PostgreSQL with a single value:
    #   PCC_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/people_counter
    database_url: str = f"sqlite:///{(DATA_DIR / 'people_counter.db').as_posix()}"
    db_echo: bool = False

    # --- security ------------------------------------------------------
    secret_key: str = "dev-secret-change-me-please-set-your-own-32b-key"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 14
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"
    force_password_change: bool = True

    # --- api -----------------------------------------------------------
    api_enabled: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    # auto: serve web-ui/dist when built, else spawn the Vite dev server
    # off/0/false: never start or open the web UI
    web_ui: str = "auto"
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    rate_limit_login_per_minute: int = 10
    webhook_urls: List[str] = Field(default_factory=list)
    webhook_timeout_s: float = 3.0

    # --- detection -----------------------------------------------------
    model_name: str = "yolov8n.pt"
    confidence: float = 0.4
    iou: float = 0.7
    imgsz: int = 640
    device: str = "auto"          # auto | cpu | 0 | 0,1 ...
    person_class_id: int = 0
    batch_size: int = 4           # frames inferred together across cameras
    batch_window_ms: int = 40     # max wait to gather a batch

    # --- camera workers ------------------------------------------------
    capture_buffer_size: int = 1  # always read the latest frame only
    reconnect_base_delay: float = 1.0
    reconnect_max_delay: float = 30.0
    camera_frame_timeout_s: float = 10.0

    # --- counting ------------------------------------------------------
    track_point: str = "bottom"   # bottom (feet) | center
    counting_cooldown_s: float = 1.5
    counting_min_displacement: float = 0.015

    # --- reports -------------------------------------------------------
    report_output_dir: str = str(BASE_DIR / "reports")
    scheduled_reports: bool = False
    scheduled_report_interval_h: int = 24

    @field_validator("cors_origins", "webhook_urls", mode="before")
    @classmethod
    def _split_csv(cls, v: Any) -> Any:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def resolved_device(self) -> str:
        if self.device and self.device.lower() != "auto":
            return self.device
        try:  # pragma: no cover - depends on host hardware
            import torch

            return "0" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def ensure_dirs(self) -> None:
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        Path(self.report_output_dir).mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
