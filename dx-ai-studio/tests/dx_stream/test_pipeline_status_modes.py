"""/api/pipeline/status 는 어떤 출력 방식으로 돌든 실행 중인 것을 말한다 (release audit S-15).

예전에는 WebRTC 파이프라인 관리자만 보아, MJPEG · fMP4 로 돌고 있는 demo 를 대시보드가 Idle 이라고 했고,
어느 demo 인지는 알 길이 없었다.
"""
from __future__ import annotations

import json
import sys
import urllib.request

import pytest

from tests.server_helpers import start_module_server


@pytest.fixture()
def stream():
    srv, port = start_module_server("dx_stream")
    server = sys.modules["dx_stream.server"]
    yield server, port
    server._current_output_mode = None
    server._current_pipeline_id = None
    server._current_demo_id = None
    srv.shutdown()


def _status(port):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/pipeline/status", timeout=5) as r:
        return json.loads(r.read())


def test_idle_says_nothing_runs(stream):
    _, port = stream
    assert _status(port) == {"running": False, "pipeline_id": None, "output_mode": None, "demo_id": None}


def test_an_mjpeg_demo_is_running_and_named(stream, monkeypatch):
    server, port = stream
    from dx_stream.core import mjpeg
    monkeypatch.setattr(mjpeg, "is_streaming", lambda: True)
    server._current_output_mode = "mjpeg"
    server._current_pipeline_id = "mjpeg-demo-4"
    server._current_demo_id = 4
    assert _status(port) == {"running": True, "pipeline_id": "mjpeg-demo-4", "output_mode": "mjpeg", "demo_id": 4}


def test_a_stopped_mjpeg_stream_is_not_running(stream, monkeypatch):
    server, port = stream
    from dx_stream.core import mjpeg
    monkeypatch.setattr(mjpeg, "is_streaming", lambda: False)
    server._current_output_mode = "mjpeg"
    server._current_demo_id = 4
    assert _status(port)["running"] is False


def test_stopping_playback_forgets_the_demo(stream, monkeypatch):
    server, _ = stream
    server._current_demo_id = 2
    server._stop_all_playback()
    assert server._current_demo_id is None
