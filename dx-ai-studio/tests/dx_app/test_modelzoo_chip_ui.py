"""SETUP 화면이 세 티어를 모두 고를 수 있어야 한다.

백엔드가 Q-Master 를 받을 수 있게 돼도 화면에서 고를 수 없으면 "보이지만 받을 수
없다" 는 그대로다. 표시(1단계)와 설치(2단계) 사이의 마지막 한 칸이다.

파이썬 쪽에서 세 곳의 `qlite else qpro` 이진 분기를 `_CHIP_DIRS` 표로 바꿨다.
화면 쪽도 같은 수를 둔다 — 렌더러/카트/일괄선택이 chip 목록 위에서 돌면 다음
티어가 생겨도 목록만 고치면 된다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "dx_app" / "static" / "js" / "modelzoo.js"
HTML = ROOT / "dx_app" / "templates" / "index.html"


def _js() -> str:
    return JS.read_text(encoding="utf-8")


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def test_chip_list_is_the_single_source_of_truth():
    src = _js()
    match = re.search(r"var MZ_CHIPS\s*=\s*\[(.*?)\];", src, re.S)
    assert match, "MZ_CHIPS 목록이 없다 — 티어가 코드 곳곳에 흩어져 있다는 뜻"
    block = match.group(1)
    for key in ("'qlite'", "'qpro'", "'qmaster'"):
        assert key in block, f"MZ_CHIPS 에 {key} 가 없다"


def test_cart_emptiness_is_not_hardcoded_to_two_tiers():
    """`!cart.qlite && !cart.qpro` 는 세 번째 티어를 카트에서 지워버린다."""
    src = _js()
    assert "!MZ.cart[name].qlite && !MZ.cart[name].qpro" not in src, (
        "카트 비었는지 판정이 두 티어에 박혀 있다 — qmaster 만 담으면 즉시 삭제된다"
    )


def test_table_offers_a_qmaster_group():
    html = _html()
    assert "Q-Master" in html, "테이블에 Q-Master 그룹이 없다"
    assert "mzSelectChipAll('qmaster')" in html, "Q-Master 일괄 선택이 없다"


def test_empty_row_colspan_matches_the_header():
    """티어 그룹을 늘리면 '결과 없음' 행의 colspan 도 같이 늘어야 한다."""
    header = _html()
    js = _js()

    spans = [int(n) for n in re.findall(r'colspan="(\d+)"', header)]
    rowspans = len(re.findall(r'rowspan="2"', header))
    expected = rowspans + sum(spans)

    found = re.search(r'colspan="(\d+)"[^>]*>\'\s*\+\s*T\(\'No models found\'\)', js)
    if not found:
        found = re.search(r"colspan=\"(\d+)\"", js)
    assert found, "빈 상태 행의 colspan 을 찾을 수 없다"
    assert int(found.group(1)) == expected, (
        f"빈 상태 colspan={found.group(1)} 인데 헤더는 {expected} 칸이다"
    )


def test_qmaster_labels_are_translatable():
    html = _html()
    assert 'data-i18n="Q-Master All"' in html, "Q-Master 버튼에 i18n 키가 없다"
