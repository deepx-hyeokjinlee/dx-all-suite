"""P4: CLI 백엔드 챗 provider("agent-cli") — 로그인된 코딩 에이전트 CLI로 채팅.

claude 로그인 1회로 챗봇 + dx_agent_dev 양쪽을 커버(별도 API 키 불필요).
provider="agent-cli", model=<agent 이름>(claude/opencode/…).
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from shared.chat import providers
from shared.chat.providers import stream_chat, stream_agent_cli, ChatAPIError, _flatten_prompt


def _fake_run(stdout="hello from agent", returncode=0, stderr=""):
    def run(cmd, capture_output=True, text=True, timeout=None):
        return SimpleNamespace(stdout=stdout, returncode=returncode, stderr=stderr)
    return run


def test_flatten_prompt_joins_roles():
    msgs = [
        {"role": "system", "content": "You are X."},
        {"role": "user", "content": "hi"},
    ]
    out = _flatten_prompt(msgs)
    assert "You are X." in out and "hi" in out


def test_agent_cli_yields_stdout():
    with patch.object(providers.shutil, "which", lambda b: "/usr/bin/" + b), \
         patch.object(providers.subprocess, "run", _fake_run("ANSWER")):
        out = list(stream_agent_cli("claude", None, [{"role": "user", "content": "q"}]))
    assert out == ["ANSWER"]


def test_agent_cli_builds_claude_command():
    captured = {}

    def run(cmd, capture_output=True, text=True, timeout=None):
        captured["cmd"] = cmd
        return SimpleNamespace(stdout="ok", returncode=0, stderr="")

    with patch.object(providers.shutil, "which", lambda b: "/usr/bin/" + b), \
         patch.object(providers.subprocess, "run", run):
        list(stream_agent_cli("claude", None, [{"role": "user", "content": "q"}]))
    assert captured["cmd"][0] == "/usr/bin/claude"
    assert "-p" in captured["cmd"]


def test_agent_cli_unknown_agent_raises():
    with pytest.raises(ChatAPIError):
        list(stream_agent_cli("nope", None, [{"role": "user", "content": "q"}]))


def test_agent_cli_missing_binary_raises():
    with patch.object(providers.shutil, "which", lambda b: None):
        with pytest.raises(ChatAPIError):
            list(stream_agent_cli("claude", None, [{"role": "user", "content": "q"}]))


def test_stream_chat_dispatches_agent_cli():
    with patch.object(providers.shutil, "which", lambda b: "/usr/bin/" + b), \
         patch.object(providers.subprocess, "run", _fake_run("ROUTED")):
        out = list(stream_chat(provider="agent-cli", api_key="", model="claude",
                               messages=[{"role": "user", "content": "q"}]))
    assert out == ["ROUTED"]
