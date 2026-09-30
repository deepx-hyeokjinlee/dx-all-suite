"""terminal 줄은 command 를 다 보이고, status 는 도는 실행이 무엇인지 알린다 (spec 2026-09-30 home agent run).

- `_tool_arg_hint` 가 command 를 50자에서 잘라 home 의 terminal 이 칸의 절반만 찼다 (JSON 폭주를 막으려던
  자르기가 command 까지 먹었다). 다른 key (prompt · url …) 는 지금처럼 짧게.
- Agent Dev 가 home 이 시작한 실행을 이어받을 때 첫 줄 (사용자의 요청) 과 대화를 알아야 한다.
"""
from __future__ import annotations

import json
import time
import urllib.request

import pytest

from tests.server_helpers import start_module_server


def test_a_command_is_shown_whole():
    from dx_agent_dev.core.adapters.base import _tool_arg_hint

    cmd = "cd /home/deepx/hj_ws/dx-all-suite/dx-runtime/dx_app && ./build.sh --clean --verbose  && ls -la build"
    assert _tool_arg_hint({"command": cmd}) == " ".join(cmd.split())
    assert _tool_arg_hint({"cmd": "  a\n  b  "}) == "a b"


def test_other_hints_stay_short():
    from dx_agent_dev.core.adapters.base import _tool_arg_hint

    long_prompt = "x" * 120
    got = _tool_arg_hint({"prompt": long_prompt})
    assert len(got) <= 51 and got.endswith("…")


@pytest.fixture()
def agent(monkeypatch):
    monkeypatch.setenv("DX_AGENT_ADAPTER", "mock")
    monkeypatch.setenv("DX_AGENT_MOCK_DELAY", "0.3")
    server, port = start_module_server("dx_agent_dev")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def test_status_names_the_running_request_and_its_conversation(agent):
    req = urllib.request.Request(agent + "/api/agent/run", data=json.dumps(
        {"prompt": "make a pose demo", "mode": "autopilot"}).encode(),
        headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    resp.readline()
    resp.close()
    time.sleep(0.2)
    with urllib.request.urlopen(agent + "/api/agent/status", timeout=10) as r:
        st = json.loads(r.read().decode())
    assert not st["run_done"]
    assert st["run_prompt"] == "make a pose demo"
    assert st["run_conversation_id"]
    assert st["run_mode"] == "autopilot"
