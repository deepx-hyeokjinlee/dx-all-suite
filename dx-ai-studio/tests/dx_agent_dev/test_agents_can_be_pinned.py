"""DX_AGENT_DEV_PIN_AGENTS 로 감지 결과를 고정할 수 있어야 한다.

비주얼 회귀 스위트가 에이전트 콘솔을 찍을 때, 드롭다운은 개발자 PATH 에 무엇이
있는지 · 어느 CLI 에 로그인돼 있는지를 그대로 그렸다. VS Code 세션이 copilot 을
PATH 에 올리자 첫 항목이 claude → copilot 으로 바뀌고 로그인 안내 줄이 끼어들어
dx_agent_dev 스크린샷 8장이 코드 변경 없이 깨졌다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "dx_agent_dev"))


def _boom(*_a, **_k):
    raise AssertionError("고정 모드에서는 실제 PATH/자격증명을 보지 않아야 한다")


def test_pinned_agents_ignore_path_and_credentials(monkeypatch):
    from core import environment
    from core import adapters
    monkeypatch.setenv("DX_AGENT_DEV_PIN_AGENTS", "claude")
    monkeypatch.setattr(environment.shutil, "which", _boom)
    monkeypatch.setattr(adapters, "make_adapter", _boom)
    agents = environment.detect_available_agents()
    assert [a["name"] for a in agents] == ["claude"]
    assert agents[0]["authenticated"] is True
    assert agents[0]["models"] and agents[0]["default_model"]


def test_pinned_order_is_the_given_order_and_unknown_names_drop(monkeypatch):
    from core import environment
    monkeypatch.setenv("DX_AGENT_DEV_PIN_AGENTS", "codex, nope ,claude")
    assert [a["name"] for a in environment.detect_available_agents()] == ["codex", "claude"]


def test_unset_pin_still_uses_real_detection(monkeypatch):
    from core import environment
    monkeypatch.delenv("DX_AGENT_DEV_PIN_AGENTS", raising=False)
    monkeypatch.setattr(environment.shutil, "which", lambda n: None)
    assert environment.detect_available_agents() == []


def test_visual_suite_pins_agents():
    conftest = Path(__file__).resolve().parents[1] / "visual" / "conftest.py"
    assert 'os.environ.setdefault("DX_AGENT_DEV_PIN_AGENTS"' in conftest.read_text(encoding="utf-8")
