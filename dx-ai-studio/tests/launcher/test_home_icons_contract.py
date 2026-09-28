"""무대의 아이콘과 책 (spec 2026-09-23 §5.3–5.4) — 모양의 계약.

크기와 상태는 test_home_icons_browser.py 가 화면에서 잰다. 여기는 마크업과 규칙이
그 모양을 약속하는지 본다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "launcher" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
APPS = ["app", "stream", "zoo", "compiler", "benchmark", "planner", "dx_monitor", "agent"]


def _css() -> str:
    path = STATIC / "home-stage.css"
    assert path.is_file(), "launcher/static/home-stage.css 가 없다"
    return re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)


def _glyph(app: str) -> str:
    m = re.search(r'<span class="mod-tile" data-mod="' + app + r'"[^>]*>(<svg.*?</svg>)</span>', HTML, re.S)
    assert m, f"{app} 의 glyph 가 없다"
    return m.group(1)


def test_icon_size_is_one_variable():
    """평소 72, Dock 48 — 두 상태가 같은 규칙을 쓰게 크기는 변수 하나다."""
    css = _css()
    assert re.search(r"--icon:\s*72px", css)
    assert re.search(r"--icon:\s*48px", css), "Dock 크기가 없다"
    tile = re.search(r"\.stage-deck \.mod-tile\s*\{([^}]*)\}", css)
    assert tile and "var(--icon)" in tile.group(1)


def test_icon_glass_is_mixed_from_the_module_colour():
    """모듈 색은 style.css 의 --mod-tint 하나에서 온다 — 새 hex 를 들이지 않는다."""
    tile = re.search(r"\.stage-deck \.mod-tile\s*\{([^}]*)\}", _css()).group(1)
    assert "var(--mod-tint)" in tile
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", _css()), "home-stage.css 에 hex 가 생겼다"


@pytest.mark.parametrize("app", APPS)
def test_each_glyph_is_two_layers_of_glass(app):
    """가는 한 겹 선 (stroke 1.7) 은 유리 판 위에서 사라졌다. 굵은 선 + 뒤쪽 채움 면."""
    g = _glyph(app)
    assert 'class="g-fill"' in g, f"{app}: 채움 층이 없다"
    assert 'class="g-line"' in g, f"{app}: 선 층이 없다"


def test_glyph_line_weight_reads_on_glass():
    css = _css()
    rule = re.search(r"\.stage-deck \.mod-glyph\s*\{([^}]*)\}", css)
    assert rule, "무대의 glyph 규칙이 없다"
    width = re.search(r"stroke-width:\s*([\d.]+)", rule.group(1))
    assert width and float(width.group(1)) >= 2


def test_description_is_a_tooltip_not_a_second_line():
    """설명은 DOM 에 남는다 (숫자를 쓰는 _paintFacts, 화면 낭독기). 평소에는 보이지 않는다."""
    css = _css()
    rest = re.search(r"\.stage-deck \.studio-grid :is\(\.card-desc, \.orbital-port\)\s*\{([^}]*)\}", css)
    assert rest and re.search(r"opacity:\s*0\b", rest.group(1))
    assert re.search(r":is\(:hover, :focus-visible\)[^{]*:is\(\.card-desc, \.orbital-port\)\s*\{[^}]*opacity:\s*1", css)
    assert HTML.count('class="card-desc"') == 8


def test_a_module_that_is_down_is_dimmed_not_hidden():
    """꺼졌다고 확인된 것만 (is-down). 'is-up 이 없으면' 이면 첫 health 응답 전에 전부 흐리다."""
    css = _css()
    assert re.search(r"\.orbital-card\.is-down[^{]*\{[^}]*opacity", css)
    assert not re.search(r"\.orbital-card:not\(\.is-up\)", css)
    js = (STATIC / "home-sections.js").read_text(encoding="utf-8")
    assert "classList.toggle('is-down', !alive)" in js


def test_books_have_a_cover():
    css = _css()
    cover = re.search(r"\.stage-deck \.about-book-card \.orbital-icon\s*\{([^}]*)\}", css)
    assert cover, "책 표지 규칙이 없다"
    body = cover.group(1)
    assert "56px" in body and "72px" in body
