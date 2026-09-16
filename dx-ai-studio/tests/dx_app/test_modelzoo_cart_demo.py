"""튜토리얼의 장바구니 시연이 카탈로그 로딩 순서에 지지 않아야 한다.

`tests/test_tutorial_spotlight_spot_check.py` 의 `#mz-cart` 검사가 드물게 빨간불을
냈다. 5회 연속 돌리면 통과해서 flaky 로 보이지만, 원인은 타이밍이 아니라 순서다:

    nav('modelzoo') → initModelZoo()  (async, await 되지 않는다)
                        └ MZ.models 가 비어 있으면 await mzLoadModels()
    _prepModelzooCartDemo() 는 동기로 계속 진행한다
                        └ 모델이 아직 없으니 _mockModelzooCartFallback()
                          (innerHTML 만 쓰고 MZ.cart 는 채우지 않는다)
    fetch 완료 → initModelZoo() 가 mzRenderCart() 를 다시 부른다
                        └ MZ.cart 가 비어 있으므로 display:none  ← 방금 만든 것을 지운다

카탈로그가 이미 로드된 상태면 첫 분기가 진짜 카트를 만들어 살아남는다. 그래서 대개
이기고 가끔 진다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "dx_app" / "static" / "js" / "tutorial.js"


def _prep_body() -> str:
    src = SRC.read_text(encoding="utf-8")
    start = src.index("function _prepModelzooCartDemo")
    return src[start: src.index("\n  }", start)]


def test_the_demo_does_not_block_the_step():
    """beforeStep 에서 기다리면 그 사이 스텝이 교체된다.

    처음에는 "카탈로그를 기다리게" 고쳤다가 되돌렸다. 저니 러너는 350ms 마다
    Next 를 누르므로, beforeStep 이 2.5초를 끌면 엔진의 _stepToken 이 바뀌어
    스텝이 렌더되지 않고 floating 으로 떨어진다 — 고치려던 것보다 나쁜 증상이다.
    해법은 기다리는 것이 아니라 나중에 덮이지 않게 하는 것이다.
    """
    body = _prep_body()
    assert "_waitForModels" not in body, "beforeStep 이 카탈로그를 기다린다"


def test_the_fallback_does_not_leave_the_cart_unowned():
    """innerHTML 만 쓰면 다음 mzRenderCart() 가 그것을 지운다."""
    src = SRC.read_text(encoding="utf-8")
    start = src.index("function _mockModelzooCartFallback")
    body = src[start: src.index("\n  }", start)]
    assert "MZ.cart" in body or "_dxtPinned" in body, (
        "fallback 이 만든 카트를 아무도 소유하지 않는다"
    )


def test_the_demo_cart_is_built_from_the_chip_table():
    """티어를 손으로 적으면 이름이 바뀔 때 조용히 어긋난다.

    `MZ_CHIPS` 가 생긴 뒤에도 여기에는 `{ qlite: true, qpro: false }` 리터럴이
    남아 있었다. 지금은 qmaster 가 undefined→falsy 라 동작하지만, 그건 우연이다.
    """
    body = _prep_body()
    assert not re.search(r"\{\s*qlite:", body), (
        "장바구니 모양을 손으로 적고 있다 — MZ_CHIPS 에서 만들어야 한다"
    )
