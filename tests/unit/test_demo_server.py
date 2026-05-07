"""Tests for the dependency-light recording demo server."""
from __future__ import annotations

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

from demo_server import HOST, RecordingDemoHandler, _teach_payload, web_demo_payload


def test_web_demo_payload_has_fixed_recording_data() -> None:
    payload = web_demo_payload()

    assert payload["ok"] is True
    assert payload["mode"] == "recording_demo"
    assert payload["material"]
    assert payload["goal"]
    assert len(payload["cards"]) == 3
    assert payload["cards"][0]["title"] == "番茄工作法"


def test_demo_teach_payload_direct_mode_has_no_follow_up() -> None:
    card = web_demo_payload()["cards"][0]

    result = _teach_payload({"card": card, "supportMode": "direct_explain"})

    assert result["ok"] is True
    assert result["source"] == "recording_demo"
    assert result["askFollowUp"] is False
    assert "番茄工作法" in result["content"]


def test_demo_server_health_endpoint() -> None:
    server = ThreadingHTTPServer((HOST, 0), RecordingDemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        raw = urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=5).read()
        payload = json.loads(raw.decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()

    assert payload["ok"] is True
    assert payload["mode"] == "recording_demo"
    assert "recording_demo" in payload["supports"]

