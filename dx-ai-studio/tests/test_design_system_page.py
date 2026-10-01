"""카탈로그가 공유 파운데이션만으로 렌더되는지.

여기서 자기 색을 정의하면 카탈로그와 실제 제품이 어긋나고,
카탈로그는 존재 의미를 잃는다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs" / "design-system.html"


def read() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_page_exists():
    assert PAGE.is_file(), "docs/design-system.html 가 없다"


def test_page_loads_the_shared_foundation_in_order():
    html = read()
    order = [
        "dx-tokens.css", "dx-semantic.css", "dx-theme-light.css",
        "dx-base.css", "dx-components.css", "dx-shell.css",
    ]
    positions = [html.index(name) for name in order]
    assert positions == sorted(positions), f"CSS 로드 순서가 틀렸다: {order}"


def test_page_defines_no_colours_of_its_own():
    style = re.search(r"<style>(.*?)</style>", read(), re.S)
    assert style, "<style> 블록이 없다"
    body = re.sub(r"--[\w-]+\s*:[^;}]*", "", style.group(1))
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", body)
    assert not hexes, f"카탈로그가 리터럴 색을 썼다: {sorted(set(hexes))}"
    assert "rgba(" not in body, "카탈로그가 리터럴 rgba를 썼다"


def test_page_renders_every_semantic_token():
    from tests.test_shared_css_foundation import SEMANTIC_TOKENS

    html = read()
    missing = [t for t in SEMANTIC_TOKENS if t not in html]
    assert not missing, f"카탈로그에 빠진 토큰: {missing}"


def test_page_shows_the_resolved_theme_state():
    """system 상태에서 실제로 무엇이 적용됐는지 못 보면 3-상태를 검수할 수 없다."""
    html = read()
    assert "DXTheme.resolved()" in html
    assert "DXTheme.cycle()" in html


def test_page_demonstrates_the_shell_skeleton():
    html = read()
    for cls in ("dx-shell-rail", "dx-shell-header", "dx-shell-tabs", "dx-shell-main"):
        assert cls in html, f"카탈로그에 {cls} 예시가 없다"
