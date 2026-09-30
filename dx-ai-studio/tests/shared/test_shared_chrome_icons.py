"""모든 모듈이 함께 쓰는 chrome 의 아이콘 (spec 2026-09-29 아이콘 체계 단계 1).

툴바 · 챗 · 튜토리얼 · NPU 떠 있는 창 · 차트 표시는 한 번 바꾸면 아홉 화면이 함께 바뀐다. 여기에 이모지가
남으면 모든 모듈에 남는다 — 이 파일들의 이모지는 0 이다.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "shared"
gate = importlib.import_module("scripts.emoji_gate")

CHROME = {
    "toolbar.js": SHARED / "static" / "toolbar.js",
    "chat-widget.js": SHARED / "chat" / "static" / "chat-widget.js",
    "tutorial-engine.js": SHARED / "static" / "tutorial-engine.js",
    "tutorial-init.js": SHARED / "static" / "tutorial-init.js",
    "widget.html": SHARED / "hw_widget" / "widget.html",
    "dx-charts.js": SHARED / "static" / "dx-charts.js",
    "toolbar.css": SHARED / "static" / "toolbar.css",
}
DOCUMENTS = [
    "launcher/static/index.html", "dx_app/templates/index.html", "dx_stream/templates/index.html",
    "dx_modelzoo/templates/index.html", "dx_compiler/templates/base.html", "dx_benchmark/templates/index.html",
    "dx_planner/templates/index.html", "dx_monitor/templates/index.html", "dx_agent_dev/templates/index.html",
]


def _src(name: str) -> str:
    return CHROME[name].read_text(encoding="utf-8")


@pytest.mark.parametrize("name", list(CHROME))
def test_the_shared_chrome_has_no_emoji_left(name):
    text = _src(name)
    left = sorted({ch for ch in text if gate.count(ch)})
    assert gate.count(text) == 0, f"{name}: {left}"


def test_the_toolbar_draws_its_buttons_from_the_sprite():
    js = _src("toolbar.js")
    for name in ("globe", "chevd", "graduation", "gear"):
        assert f"'{name}'" in js, name
    theme = re.search(r"THEME_ICON\s*=\s*\{([^}]*)\}", js)
    assert theme, "테마 세 상태의 아이콘 표가 없다"
    assert "dark: 'moon'" in theme.group(1) and "light: 'sun'" in theme.group(1) and "system: 'theme'" in theme.group(1)
    assert "DXIcon.el(" in js


def test_the_chat_draws_its_buttons_from_the_sprite():
    js = _src("chat-widget.js")
    for name in ("chat", "gear", "trash", "x", "send", "alert"):
        # _ico 는 DXIcon 을 부르는 챗의 얇은 감싸개 (dx-icon.js 가 없어도 챗이 멈추지 않게).
        assert re.search(r"(DXIcon(\.el)?|_ico)\('" + name + "'", js), name


def test_no_dictionary_key_carries_an_icon():
    """키에 이모지가 있으면 아이콘을 바꿀 때 키 · 호출 · 6개 언어를 한꺼번에 바꿔야 한다."""
    js = _src("chat-widget.js")
    keys = re.findall(r"^\s*'([^']+)':\s*\{", js[js.index("window._DX_CHAT_I18N"):js.index("window._DX_CHAT_HEADER_TITLES")], re.M)
    assert keys and not [k for k in keys if gate.count(k)]


def test_the_tutorial_draws_its_marks_from_the_sprite():
    js = _src("tutorial-engine.js")
    for name in ("graduation", "check", "lock", "circle", "play", "refresh", "clipboard", "x", "file"):
        assert f"'{name}'" in js, name
    assert re.search(r"/\^\[a-z0-9_-\]\+\$/", js), "구역 아이콘이 sprite 이름 (task-object_detection 포함) 이면 그리는 분기가 없다"


def test_the_npu_widget_uses_the_sprite():
    html = _src("widget.html")
    for name in ("menu", "thermometer", "bench", "memory", "clock", "bolt", "cpu", "disk", "chevd"):
        assert f"dx-icons.svg#{name}\"" in html, name


def test_the_new_symbols_exist():
    sprite = (SHARED / "static" / "dx-icons.svg").read_text(encoding="utf-8")
    for name in ("sun", "moon", "circle", "menu", "thermometer", "bolt", "cpu", "memory", "disk", "clock"):
        assert f'<symbol id="{name}"' in sprite, name


@pytest.mark.parametrize("doc", DOCUMENTS)
def test_the_helper_loads_right_after_the_theme(doc):
    scripts = re.findall(r'<script src="/static/shared/([^"?]+)', (ROOT / doc).read_text(encoding="utf-8"))
    assert scripts[:2] == ["dx-theme.js", "dx-icon.js"], (doc, scripts[:3])
