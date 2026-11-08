"""Tests for the REST API."""
from __future__ import annotations

import json

from conftest import auth_headers, login


def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_login_rejects_wrong_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_login_and_me(client):
    token = login(client)
    response = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["username"] == "admin"
    assert response.json()["role"] == "admin"


def test_protected_endpoints_require_a_token(client):
    assert client.get("/api/v1/cameras").status_code == 401
    assert client.get("/api/v1/counts").status_code == 401


def test_refresh_token_grants_a_new_access_token(client):
    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )
    refresh_token = response.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refreshed.status_code == 200
    token = refreshed.json()["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth_headers(token)).status_code == 200


def test_camera_crud_with_manual_fields(client, runtime):
    token = login(client)
    headers = auth_headers(token)

    created = client.post(
        "/api/v1/cameras",
        headers=headers,
        json={
            "name": "Front door",
            "location": "Ground floor",
            "mode": "manual",
            "host": "192.168.1.64",
            "port": 554,
            "username": "admin",
            "password": "sup3r-secret",
            "rtsp_path": "/stream1",
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["name"] == "Front door"
    assert payload["has_password"] is True
    assert "sup3r-secret" not in created.text

    # the password is stored encrypted, never in clear text
    from app.db.models import Camera

    with runtime.db.session_scope() as session:
        camera = session.query(Camera).filter(Camera.name == "Front door").one()
        assert camera.password_enc != "sup3r-secret"
        assert runtime.secret_box.decrypt(camera.password_enc) == "sup3r-secret"

    listed = client.get("/api/v1/cameras", headers=headers)
    assert listed.status_code == 200
    assert any(item["name"] == "Front door" for item in listed.json())

    updated = client.patch(
        "/api/v1/cameras/{camera_id}".format(camera_id=payload["id"]),
        headers=headers,
        json={"name": "Front door 2", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Front door 2"
    assert updated.json()["enabled"] is False

    deleted = client.delete(
        "/api/v1/cameras/{camera_id}".format(camera_id=payload["id"]), headers=headers
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/cameras", headers=headers).json() == []


def test_camera_with_direct_rtsp_url_extracts_the_credentials(client, runtime):
    token = login(client)
    headers = auth_headers(token)
    created = client.post(
        "/api/v1/cameras",
        headers=headers,
        json={
            "name": "Direct url camera",
            "mode": "url",
            "url": "rtsp://joe:pw@cam.local:8554/Streaming/Channels/101",
        },
    )
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["host"] == "cam.local"
    assert payload["port"] == 8554
    assert payload["username"] == "joe"
    assert payload["rtsp_path"] == "/Streaming/Channels/101"
    assert "pw" not in payload["rtsp_url"]

    from app.db.models import Camera

    with runtime.db.session_scope() as session:
        camera = session.query(Camera).filter(Camera.name == "Direct url camera").one()
        assert runtime.secret_box.decrypt(camera.password_enc) == "pw"
        assert runtime.camera_url(camera) == (
            "rtsp://joe:pw@cam.local:8554/Streaming/Channels/101"
        )


def test_camera_with_video_file_source(client):
    token = login(client)
    created = client.post(
        "/api/v1/cameras",
        headers=auth_headers(token),
        json={"name": "Simulation", "mode": "file", "file_path": "C:/videos/sample.mp4"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["source_type"] == "file"
    assert created.json()["file_path"] == "C:/videos/sample.mp4"


def test_lines_and_areas_crud(client):
    token = login(client)
    headers = auth_headers(token)
    camera = client.post(
        "/api/v1/cameras",
        headers=headers,
        json={"name": "Zone camera", "mode": "file", "file_path": "x.mp4"},
    ).json()
    camera_id = camera["id"]

    line = client.post(
        "/api/v1/cameras/{camera_id}/lines".format(camera_id=camera_id),
        headers=headers,
        json={"name": "Main door", "x1": 0.2, "y1": 0.5, "x2": 0.8, "y2": 0.5, "direction": "A_TO_B"},
    )
    assert line.status_code == 201, line.text
    assert line.json()["direction"] == "A_TO_B"

    lines = client.get(
        "/api/v1/cameras/{camera_id}/lines".format(camera_id=camera_id), headers=headers
    )
    assert lines.status_code == 200
    assert len(lines.json()) == 1

    patched = client.patch(
        "/api/v1/cameras/{camera_id}/lines/{line_id}".format(
            camera_id=camera_id, line_id=line.json()["id"]
        ),
        headers=headers,
        json={"direction": "BOTH", "enabled": False},
    )
    assert patched.status_code == 200
    assert patched.json()["direction"] == "BOTH"
    assert patched.json()["enabled"] is False

    area = client.post(
        "/api/v1/cameras/{camera_id}/areas".format(camera_id=camera_id),
        headers=headers,
        json={"name": "Lobby", "points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]},
    )
    assert area.status_code == 201, area.text
    assert area.json()["points"][0] == [0.1, 0.1]

    areas = client.get(
        "/api/v1/cameras/{camera_id}/areas".format(camera_id=camera_id), headers=headers
    )
    assert areas.status_code == 200
    assert len(areas.json()) == 1

    removed = client.delete(
        "/api/v1/cameras/{camera_id}/lines/{line_id}".format(
            camera_id=camera_id, line_id=line.json()["id"]
        ),
        headers=headers,
    )
    assert removed.status_code == 204


def test_counts_endpoints(client):
    token = login(client)
    headers = auth_headers(token)
    global_counts = client.get("/api/v1/counts", headers=headers)
    assert global_counts.status_code == 200
    assert "in" in global_counts.json()["summary"]


def test_reports_summary_and_exports(client):
    token = login(client)
    headers = auth_headers(token)
    summary = client.get("/api/v1/reports/summary", headers=headers)
    assert summary.status_code == 200
    assert "timeseries" in summary.json()

    csv_report = client.get("/api/v1/reports/export?format=csv", headers=headers)
    assert csv_report.status_code == 200
    assert "text/csv" in csv_report.headers["content-type"]

    excel_report = client.get("/api/v1/reports/export?format=excel", headers=headers)
    assert excel_report.status_code == 200
    assert excel_report.content[:2] == b"PK"

    pdf_report = client.get("/api/v1/reports/export?format=pdf", headers=headers)
    assert pdf_report.status_code == 200
    assert pdf_report.content[:4] == b"%PDF"


def test_viewer_role_cannot_manage_cameras(client):
    admin_token = login(client)
    headers = auth_headers(admin_token)
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "username": "watcher",
            "password": "watcher-pass-1",
            "full_name": "Watch only",
            "role": "viewer",
        },
    )
    assert created.status_code == 201, created.text

    viewer_token = login(client, "watcher", "watcher-pass-1")
    viewer_headers = auth_headers(viewer_token)

    assert client.get("/api/v1/cameras", headers=viewer_headers).status_code == 200
    denied = client.post(
        "/api/v1/cameras",
        headers=viewer_headers,
        json={"name": "Not allowed", "mode": "file", "file_path": "x.mp4"},
    )
    assert denied.status_code == 403
    assert client.get("/api/v1/users", headers=viewer_headers).status_code == 403


def test_operator_can_manage_cameras_but_not_users(client):
    admin_token = login(client)
    headers = auth_headers(admin_token)
    client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "operator1", "password": "operator-pass", "role": "operator"},
    )
    operator_token = login(client, "operator1", "operator-pass")
    operator_headers = auth_headers(operator_token)
    created = client.post(
        "/api/v1/cameras",
        headers=operator_headers,
        json={"name": "Operator camera", "mode": "file", "file_path": "x.mp4"},
    )
    assert created.status_code == 201
    assert client.get("/api/v1/users", headers=operator_headers).status_code == 403


def test_api_key_authentication(client):
    admin_token = login(client)
    headers = auth_headers(admin_token)
    created = client.post("/api/v1/users/api-keys", headers=headers, json={"name": "integration"})
    assert created.status_code == 201, created.text
    key = created.json()["key"]

    response = client.get("/api/v1/cameras", headers={"X-API-Key": key})
    assert response.status_code == 200
    assert client.get("/api/v1/cameras", headers={"X-API-Key": "pcc_bogus_key"}).status_code == 401


def test_audit_log_records_the_login(client):
    login(client)
    admin_token = login(client)
    audit = client.get("/api/v1/users/audit", headers=auth_headers(admin_token))
    assert audit.status_code == 200
    actions = [entry["action"] for entry in audit.json()]
    assert "login" in actions


def test_change_password_flow(client):
    admin_token = login(client)
    headers = auth_headers(admin_token)
    created = client.post(
        "/api/v1/users",
        headers=headers,
        json={"username": "pwuser", "password": "first-pass-1", "role": "viewer"},
    )
    assert created.status_code == 201

    user_token = login(client, "pwuser", "first-pass-1")
    changed = client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(user_token),
        json={"current_password": "first-pass-1", "new_password": "second-pass-2"},
    )
    assert changed.status_code == 200
    assert login(client, "pwuser", "second-pass-2")


def test_login_is_rate_limited(client, runtime, monkeypatch):
    """Too many login attempts from one address are rejected."""
    monkeypatch.setattr(runtime.settings, "rate_limit_login_per_minute", 2)
    statuses = []
    for _ in range(4):
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "wrong"}
        )
        statuses.append(response.status_code)
    assert 429 in statuses
