"""Tests for the RTSP url helpers."""
from __future__ import annotations

from app.engine.sources import build_rtsp_url, describe_source, parse_source, strip_credentials


def test_build_rtsp_url_with_credentials():
    url = build_rtsp_url("192.168.1.10", 554, "admin", "secret", "/stream1")
    assert url == "rtsp://admin:secret@192.168.1.10:554/stream1"


def test_build_rtsp_url_encodes_special_characters():
    url = build_rtsp_url("10.0.0.1", 554, "user name", "p@ss/word", "/live")
    assert "user%20name" in url
    assert "p%40ss%2Fword" in url
    parsed = parse_source(url)
    assert parsed.username == "user name"
    assert parsed.password == "p@ss/word"


def test_build_rtsp_url_without_credentials():
    assert build_rtsp_url("10.0.0.1", 554, None, None, "/stream2") == "rtsp://10.0.0.1:554/stream2"


def test_build_rtsp_url_adds_missing_slash():
    assert build_rtsp_url("10.0.0.1", 554, None, None, "stream3") == "rtsp://10.0.0.1:554/stream3"


def test_parse_source_extracts_parts():
    parsed = parse_source("rtsp://joe:pw@cam.local:8554/Streaming/Channels/101")
    assert parsed.host == "cam.local"
    assert parsed.port == 8554
    assert parsed.username == "joe"
    assert parsed.password == "pw"
    assert parsed.path == "/Streaming/Channels/101"


def test_strip_credentials_removes_user_info():
    assert strip_credentials("rtsp://joe:pw@cam.local:8554/live") == "rtsp://cam.local:8554/live"


def test_describe_source_never_leaks_the_password():
    text = describe_source("rtsp://joe:supersecret@cam.local:554/live")
    assert "supersecret" not in text
    assert "cam.local" in text
