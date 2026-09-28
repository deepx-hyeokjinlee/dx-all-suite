"""home 의 효과 (spec 2026-09-23 §7) — 움직이는 방식의 계약.

화면에 무엇이 보이는지는 browser 테스트가 본다. 여기서는 규칙을 본다: transform · opacity 만,
JS 는 Web Animations API, 효과 줄이기를 존중, 공용 스크립트는 opt-in 한 문서에서만.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "launcher" / "static"
SHARED = ROOT / "shared" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
CSS = (STATIC / "home-stage.css").read_text(encoding="utf-8")


def _effects() -> str:
    path = STATIC / "home-effects.js"
    assert path.is_file(), "launcher/static/home-effects.js 가 없다"
    return path.read_text(encoding="utf-8")


def _rule(selector: str) -> str:
    m = re.search(r"(?:^|\n)" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert m, f"{selector} 규칙이 없다"
    return m.group(1)


def test_the_effects_script_is_served_and_loaded():
    launcher = (ROOT / "launcher" / "launcher.py").read_text(encoding="utf-8")
    assert 'path == "/home-effects.js"' in launcher
    assert 'src="/home-effects.js"' in HTML


def test_js_effects_respect_reduced_motion():
    js = _effects()
    assert "prefers-reduced-motion: reduce" in js


def test_js_effects_use_web_animations_not_class_reinsertion():
    """class 를 떼고 offsetWidth 로 reflow 한 뒤 다시 붙이는 트릭은 키 입력마다 layout 을 부른다."""
    js = _effects()
    assert ".animate(" in js
    assert "offsetWidth" not in js and "offsetHeight" not in js


def test_the_stage_background_belongs_to_the_home_only():
    frame = (STATIC / "launcher-app-frame.js").read_text(encoding="utf-8")
    assert "classList.toggle('home-visible', viewName === 'home')" in frame
    body = _rule("body.home-visible")
    assert "radial-gradient" in body and "background-attachment: fixed" in body


def test_the_input_glow_is_a_grid_item_not_a_positioned_layer():
    assert "display: grid" in _rule(".ask-box")
    glow = _rule(".ask-box::after")
    assert "grid-row: 1 / -1" in glow and "pointer-events: none" in glow
    assert "opacity: 0" in glow


def test_the_input_glow_is_driven_on_its_pseudo_element():
    js = _effects()
    assert "pseudoElement: '::after'" in js
    assert "240" in js, "키 입력 빛은 240ms 에 가라앉는다 (spec §7 #3)"


def test_book_hover_tilts_the_cover_with_transform():
    hover = re.search(r"\.about-book-card:is\(:hover, :focus-visible\) \.orbital-icon\s*\{([^}]*)\}", CSS)
    assert hover and "rotateY(-8deg)" in hover.group(1)


def test_the_poster_thumbnail_grows_on_hover():
    hover = re.search(r"\.stage-film:is\(:hover, :focus-visible\) img\s*\{([^}]*)\}", CSS)
    assert hover and "scale(1.06)" in hover.group(1)


def test_theme_and_language_fade_only_where_a_page_opts_in():
    """공용 스크립트다 — 모듈 9개가 모두 교차 fade 를 얻지 않게, 문서가 고른다."""
    for name in ("dx-theme.js", "i18n.js"):
        js = (SHARED / name).read_text(encoding="utf-8")
        assert "startViewTransition" in js, name
        assert "dxFade" in js, f"{name} 가 opt-in 을 보지 않는다"
        assert "prefers-reduced-motion: reduce" in js, name
    assert re.search(r"<html [^>]*data-dx-fade", HTML), "launcher 가 opt-in 하지 않았다"


def test_the_fade_lengths_are_the_spec_ones():
    for kind, ms in (("theme", 600), ("lang", 200)):
        pat = (r'html\[data-dx-fading="' + kind + r'"\]::view-transition-old\(root\),\s*'
               r'html\[data-dx-fading="' + kind + r'"\]::view-transition-new\(root\)\s*\{[^}]*'
               r"animation-duration:\s*" + str(ms) + "ms")
        assert re.search(pat, CSS), kind
