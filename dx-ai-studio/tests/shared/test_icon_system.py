"""스튜디오의 아이콘 한 벌 (spec 2026-09-29 아이콘 체계 §2–3).

모든 아이콘은 `shared/static/dx-icons.svg` 의 symbol 이다. home 의 모듈 glyph 와 같은 두 겹 — 24 격자,
옅은 면 + 2px 선 — 이고, 색은 currentColor 뿐이다. `<use>` 의 그림자 트리 안은 바깥 CSS 가 닿지 않으므로
모양은 상속되는 CSS 변수 (--ico-fill · --ico-fill-o · --ico-stroke) 로만 바꾼다.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPRITE = (ROOT / "shared" / "static" / "dx-icons.svg").read_text(encoding="utf-8")
COMPONENTS = (ROOT / "shared" / "static" / "dx-components.css").read_text(encoding="utf-8")

MODULES = ["app", "stream", "zoo", "compiler", "edge", "bench", "monitor", "agent"]
EXISTING = MODULES + ["home", "setup", "models", "run", "demo", "compare", "download", "lab", "folder",
                      "book", "dev", "chev", "chevd", "dots", "dashboard", "puzzle", "wrench"]
NEW = ["library", "globe", "theme", "graduation", "gear", "check", "alert", "x", "info", "spinner", "lock",
       "trash", "chat", "send", "play", "stop", "refresh", "search", "upload", "image", "video", "camera",
       "file", "clipboard", "copy", "eye", "external"]
# 선만으로 뜻이 되는 표시 — 면이 있으면 오히려 흐려진다.
MARKS = {"chev", "chevd", "dots", "check", "x", "external", "send", "refresh", "spinner", "search", "circle", "menu", "plus", "minus"}
DOCUMENTS = [
    "launcher/static/index.html",
    "dx_app/templates/index.html",
    "dx_stream/templates/index.html",
    "dx_modelzoo/templates/index.html",
    "dx_compiler/templates/base.html",
    "dx_benchmark/templates/index.html",
    "dx_planner/templates/index.html",
    "dx_monitor/templates/index.html",
    "dx_agent_dev/templates/index.html",
]


def _symbols() -> dict[str, str]:
    return {m.group(1): m.group(0) for m in re.finditer(r'<symbol id="([^"]+)"[^>]*>.*?</symbol>', SPRITE, re.S)}


def test_every_name_the_studio_uses_is_there():
    missing = [n for n in EXISTING + NEW if n not in _symbols()]
    assert not missing, missing


@pytest.mark.parametrize("name", EXISTING + NEW)
def test_each_symbol_is_the_home_glyph_style(name):
    sym = _symbols()[name]
    assert 'viewBox="0 0 24 24"' in sym, f"{name}: 24 격자가 아니다"
    assert '<g class="l"' in sym, f"{name}: 선 층이 없다"
    if name not in MARKS:
        assert '<g class="f"' in sym, f"{name}: 면 층이 없다"


def test_the_layers_take_their_shape_from_inherited_variables():
    line = re.search(r'<g class="l" style="([^"]+)"', SPRITE).group(1)
    fill = re.search(r'<g class="f" style="([^"]+)"', SPRITE).group(1)
    assert "stroke: currentColor" in line and "var(--ico-stroke" in line
    assert "fill: currentColor" in fill and "var(--ico-fill" in fill and "var(--ico-fill-o" in fill


def test_the_sprite_names_no_colour_of_its_own():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", SPRITE)
    assert not re.search(r'(fill|stroke)="(?!none|currentColor)[^"]+"', SPRITE)


def test_the_module_glyphs_are_the_home_ones():
    """레일 · 탭과 home 에서 같은 모듈이 다르게 생겼었다 (20 격자 한 겹 vs 24 격자 두 겹)."""
    app = _symbols()["app"]
    assert 'd="M10.5 8.2v4.6l4-2.3z"' in app, "home 의 App glyph 가 아니다"


def test_the_icon_class_is_shared():
    rule = re.search(r"\.dx-ico\s*\{([^}]*)\}", COMPONENTS)
    assert rule and "width: 1em" in rule.group(1) and "height: 1em" in rule.group(1)


@pytest.mark.parametrize("doc", DOCUMENTS)
def test_every_document_loads_the_helper_before_the_toolbar(doc):
    html = (ROOT / doc).read_text(encoding="utf-8")
    assert "/static/shared/dx-icon.js" in html, doc
    assert html.index("/static/shared/dx-icon.js") < html.index("/static/shared/toolbar.js"), doc


def test_the_helper_hides_decoration_and_names_meaning():
    js = (ROOT / "shared" / "static" / "dx-icon.js").read_text(encoding="utf-8")
    assert "window.DXIcon" in js
    assert "aria-hidden" in js and "role" in js and "aria-label" in js
    assert "/static/shared/dx-icons.svg#" in js


def test_the_home_uses_the_sprite_for_its_glyphs():
    html = (ROOT / "launcher" / "static" / "index.html").read_text(encoding="utf-8")
    for key in ["app", "stream", "zoo", "compiler", "edge", "bench", "monitor", "agent", "library", "book"]:
        assert f'<use href="/static/shared/dx-icons.svg#{key}"' in html, key
    assert 'class="g-fill"' not in html, "인라인 glyph 가 남아 있다"
