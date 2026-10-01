"""test 가 진짜 agent CLI 를 돌리지 않는다 (2026-09-30).

`test_server_reattach.py` 가 agent 를 지정하지 않고 실행을 보냈고, server 기본 adapter 는 copilot 이다.
이 기기에 copilot CLI 가 없을 때는 아무 일도 없었지만, 설치 · 로그인하자 test 한 번에 실제 실행이 12번
돌았다 (계정의 premium request). test 전체에 `DX_AGENT_NO_REAL_RUN=1` 을 켜고, 켜져 있으면 adapter 는
PATH 의 진짜 CLI 를 실행하지 않는다 — 가짜 script (tmp) 로 하는 test 는 그대로 돈다.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path


def test_the_test_session_forbids_real_agent_runs():
    assert os.environ.get("DX_AGENT_NO_REAL_RUN") == "1"


def test_a_real_cli_on_path_is_refused(tmp_path, monkeypatch):
    from dx_agent_dev.core.adapters.copilot import CopilotAdapter

    real = tmp_path / "bin" / "copilot"
    real.parent.mkdir()
    real.write_text("#!/bin/sh\necho SHOULD-NOT-RUN > \"$HOME/ran\"\n")
    real.chmod(real.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(real.parent))
    monkeypatch.setenv("HOME", str(tmp_path))
    events = list(CopilotAdapter().run("hi", tmp_path, [str(tmp_path)]))
    assert events and events[0]["type"] == "error", events
    assert "test" in events[0]["text"].lower()
    assert not (tmp_path / "ran").exists(), "진짜 CLI 가 돌았다"


def test_a_fake_cli_path_still_runs(tmp_path):
    """adapter 를 가짜 script 로 시험하는 test 들 — PATH 의 CLI 가 아니면 막지 않는다."""
    from dx_agent_dev.core.adapters.copilot import CopilotAdapter

    fake = tmp_path / "fake-copilot"
    fake.write_text("#!/bin/sh\necho hello\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    events = list(CopilotAdapter(cli_path=str(fake)).run("hi", tmp_path, [str(tmp_path)]))
    assert not any(e.get("type") == "error" and "test" in e.get("text", "").lower() for e in events), events
