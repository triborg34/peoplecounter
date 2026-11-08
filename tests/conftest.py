"""Shared pytest fixtures.

The environment is configured before any application module is imported so
that the whole test session uses a throw away database.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="people-counter-tests-"))
os.environ["PCC_DATABASE_URL"] = "sqlite:///" + (_TMP / "test.db").as_posix()
os.environ["PCC_SECRET_KEY"] = "test-secret-key-for-the-test-suite"
os.environ["PCC_DEFAULT_ADMIN_USERNAME"] = "admin"
os.environ["PCC_DEFAULT_ADMIN_PASSWORD"] = "admin123"
os.environ["PCC_LOG_LEVEL"] = "WARNING"
os.environ["PCC_LOG_DIR"] = str(_TMP / "logs")
os.environ["PCC_DATA_DIR"] = str(_TMP / "data")
os.environ["PCC_REPORT_OUTPUT_DIR"] = str(_TMP / "reports")
# the suite logs in many times from the same client address
os.environ["PCC_RATE_LIMIT_LOGIN_PER_MINUTE"] = "1000"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture()
def db():
    from app.db.session import Database

    database = Database()
    database.drop_all()
    database.create_all()
    yield database
    database.dispose()


@pytest.fixture()
def runtime(db, monkeypatch):
    from app.engine.detector import Detector
    from app.engine.runtime import EngineRuntime

    # never download or load the detection weights during the tests
    monkeypatch.setattr(Detector, "load", lambda self: False)
    engine = EngineRuntime(db=db)
    engine.db.create_all()
    return engine


@pytest.fixture()
def client(runtime):
    from fastapi.testclient import TestClient

    from app.api.app import create_app

    app = create_app(runtime=runtime)
    with TestClient(app) as test_client:
        yield test_client


def login(client, username: str = "admin", password: str = "admin123") -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": "Bearer " + token}
