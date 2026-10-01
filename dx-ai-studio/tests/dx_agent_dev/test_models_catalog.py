"""model 목록이 오늘의 것이고, copilot 은 이 계정이 쓸 수 있는 것만 고르게 한다 (spec 2026-09-30 home agent run).

- claude CLI 에는 model 목록 명령이 없어 정적 표가 유일한 소스다 — 표가 2026-07-19 에 멈춰 Fable 5.1 ·
  Sonnet/Opus 5.5 가 없었다. alias (opus · sonnet · fable · haiku) 는 CLI 가 늘 최신으로 풀어 준다.
- copilot 은 계정의 요금제 · 회사 정책이 반영된 목록을 ACP (`copilot --acp --stdio`) 의 `session/new` 가
  준다 (prompt 없음). 실측 계정에서 정적 표의 기본 `claude-sonnet-4.6` 은 쓸 수 없는 model 이었다.
- VS Code 가 PATH 에 넣는 설치 안내 shim 은 설치된 CLI 가 아니다 — 실행하면 "Install? [y/N]" 에서 멈춘다.
"""
from __future__ import annotations

import json
import os
import stat
import sys
import textwrap
from pathlib import Path

import pytest

from dx_agent_dev.core.agents_config import AGENTS

FAKE_MODELS = [
    {"modelId": "auto", "name": "Auto", "description": ""},
    {"modelId": "auto", "name": "Auto", "description": "", "_meta": {"copilotUsage": "1x", "copilotEnablement": "enabled"}},
    {"modelId": "claude-sonnet-5", "name": "Claude Sonnet 5", "description": "",
     "_meta": {"copilotUsage": "1x", "copilotEnablement": "enabled"}},
    {"modelId": "claude-opus-5.5", "name": "Claude Opus 5.5", "description": "",
     "_meta": {"copilotUsage": "15x", "copilotEnablement": "enabled"}},
]


def _fake_copilot(tmp_path: Path, mode: str = "ok") -> Path:
    """최소한의 ACP 만 말하는 가짜 copilot. session/new 때 실제 CLI 처럼 session 폴더를 만든다."""
    script = tmp_path / "bin" / "copilot"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(textwrap.dedent(f"""\
        #!{sys.executable}
        import json, os, sys, uuid
        if {mode!r} == "fail":
            sys.exit(1)
        for line in sys.stdin:
            req = json.loads(line)
            rid, method = req.get("id"), req.get("method")
            if method == "initialize":
                res = {{"protocolVersion": 1}}
            elif method == "session/new":
                sid = str(uuid.uuid4())
                d = os.path.join(os.environ["HOME"], ".copilot", "session-state", sid)
                os.makedirs(d)
                open(os.path.join(d, "workspace.yaml"), "w").write("cwd: x\\n")
                res = {{"sessionId": sid, "models": {{"availableModels": {json.dumps(FAKE_MODELS)!s},
                                                     "currentModelId": "claude-sonnet-5"}}}}
            else:
                res = {{}}
            sys.stdout.write(json.dumps({{"jsonrpc": "2.0", "id": rid, "result": res}}) + "\\n")
            sys.stdout.flush()
    """), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


# ── claude ─────────────────────────────────────────────────────────────────


def test_claude_offers_the_aliases_first_and_todays_models():
    models = AGENTS["claude"]["models"]
    assert models[:4] == ["opus", "sonnet", "fable", "haiku"]
    for m in ("claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"):
        assert m in models, m
    assert AGENTS["claude"]["default_model"] == "claude-sonnet-5-5"
    assert AGENTS["claude"]["default_model"] in models


# ── copilot: 계정의 목록 ───────────────────────────────────────────────────


def test_copilot_reads_the_accounts_models_over_acp_and_cleans_up(tmp_path, monkeypatch):
    from dx_agent_dev.core.adapters.copilot import CopilotAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    adapter = CopilotAdapter(cli_path=str(_fake_copilot(tmp_path)))
    got = adapter.account_models()
    assert got["default"] == "claude-sonnet-5"
    assert [m["id"] for m in got["models"]] == ["auto", "claude-sonnet-5", "claude-opus-5.5"], "auto 는 한 번만"
    opus = next(m for m in got["models"] if m["id"] == "claude-opus-5.5")
    assert opus == {"id": "claude-opus-5.5", "name": "Claude Opus 5.5", "usage": "15x", "enabled": True}
    left = list((tmp_path / ".copilot" / "session-state").iterdir())
    assert left == [], f"목록을 받으려고 연 session 폴더가 남았다: {left}"


def test_copilot_catalog_shows_everything_but_only_the_accounts_models_are_pickable(tmp_path, monkeypatch):
    from dx_agent_dev.core import environment
    from dx_agent_dev.core.adapters import copilot as copilot_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    fake = str(_fake_copilot(tmp_path))
    monkeypatch.setattr(copilot_mod, "find_cli", lambda name: fake)
    environment._models_cache.clear()
    info = environment.agent_model_info("copilot")
    assert info["default_model"] == "claude-sonnet-5"
    assert info["models"] == ["auto", "claude-sonnet-5", "claude-opus-5.5"]
    by_id = {m["id"]: m for m in info["catalog"]}
    assert by_id["claude-opus-5.5"]["enabled"] and by_id["claude-opus-5.5"]["usage"] == "15x"
    blocked = [m for m in info["catalog"] if not m["enabled"]]
    assert blocked, "정적 표에만 있는 model 은 보이되 고를 수 없다"
    assert all(m["id"] in AGENTS["copilot"]["models"] for m in blocked)
    assert [m["id"] for m in info["catalog"]][:3] == ["auto", "claude-sonnet-5", "claude-opus-5.5"]


def test_copilot_falls_back_to_the_static_table_when_acp_fails(tmp_path, monkeypatch):
    from dx_agent_dev.core import environment
    from dx_agent_dev.core.adapters import copilot as copilot_mod

    monkeypatch.setenv("HOME", str(tmp_path))
    fake = str(_fake_copilot(tmp_path, mode="fail"))
    monkeypatch.setattr(copilot_mod, "find_cli", lambda name: fake)
    environment._models_cache.clear()
    info = environment.agent_model_info("copilot")
    assert info["models"] == AGENTS["copilot"]["models"]
    assert info.get("catalog") is None
    assert info["default_model"] == AGENTS["copilot"]["default_model"]
    assert AGENTS["copilot"]["default_model"] == "auto", "계정마다 쓸 수 있는 model 이 달라 기본은 CLI 에 맡긴다"


# ── copilot: 감지 · 로그인 ────────────────────────────────────────────────


def _exe(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o755)
    return path


def test_the_vscode_install_shim_is_not_an_installed_cli(tmp_path, monkeypatch):
    from dx_agent_dev.core.adapters.base import find_cli

    shim = _exe(tmp_path / "vscode" / "github.copilot-chat" / "copilotCli" / "copilot")
    real = _exe(tmp_path / "local" / "bin" / "copilot")
    monkeypatch.setenv("PATH", f"{shim.parent}{os.pathsep}{real.parent}")
    assert find_cli("copilot") == str(real)
    monkeypatch.setenv("PATH", str(shim.parent))
    assert find_cli("copilot") is None


@pytest.mark.parametrize("config, expected", [
    ('// comment line\n{"loggedInUsers": [{"host": "https://github.com", "login": "me"}]}', True),
    ('{"loggedInUsers": []}', False),
    (None, False),
])
def test_copilot_sign_in_is_read_from_its_config(tmp_path, monkeypatch, config, expected):
    from dx_agent_dev.core.adapters.copilot import CopilotAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    if config is not None:
        (tmp_path / ".copilot").mkdir()
        (tmp_path / ".copilot" / "config.json").write_text(config)
    assert CopilotAdapter(cli_path="/bin/true").is_authenticated() is expected
