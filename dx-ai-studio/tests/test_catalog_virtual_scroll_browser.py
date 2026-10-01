"""ModelZoo 카탈로그 가상화가 실제로 스크롤을 따라가는지.

기존 "가상화 계약" 테스트(`tests/test_modelzoo_virtualized_performance.py`)는
catalog.js 를 문자열로 grep 해서 `renderViewport` 같은 이름이 있는지만 본다.
그래서 가상화가 통째로 죽어 있어도 전부 통과했다 — 실제로 죽어 있었다.

증상: 필터가 All 인데 347개 중 40장만 그려지고, 끝까지 내려도 늘지 않았다.
원인: 가상화가 스크롤러를 "자기 컨테이너 아니면 window" 로 가정했는데, 앱 셸이
통합되면서 overflow 가 조상(`main.dx-shell-main`)으로 옮겨갔다. 컨테이너도 window 도
스크롤 이벤트를 내지 않으니 `_getEffectiveScrollTop()` 이 영원히 0 이었다.

그래서 여기서는 스크롤러를 **이름으로 찾지 않는다.** DOM 에서 실제로 넘치는 조상을
찾아 스크롤한다 — 셸이 또 바뀌어도 이 테스트는 따라간다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

# 컨테이너에서 위로 올라가며 실제로 스크롤 가능한 첫 조상을 찾는다.
_FIND_SCROLLER = """() => {
  let node = document.getElementById('catalogContainer');
  while (node && node !== document.documentElement) {
    const st = getComputedStyle(node);
    if (/auto|scroll|overlay/.test(st.overflowY) && node.scrollHeight > node.clientHeight + 30) {
      return node.tagName.toLowerCase() + (node.className ? '.' + node.className.trim().split(/\\s+/).join('.') : '');
    }
    node = node.parentElement;
  }
  return null;
}"""

_CARD_IDS = """() => [...document.querySelectorAll('[data-model-id]')]
    .map(e => e.dataset.modelId).filter(Boolean)"""


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


@pytest.fixture()
def zoo(browser):
    server, port = start_module_server("dx_modelzoo")
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    page = ctx.new_page()
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
        page.wait_for_selector("[data-model-id]", timeout=30000)
        page.wait_for_timeout(2500)
        yield page
    finally:
        page.close()
        ctx.close()
        server.shutdown()


def _scroller(page):
    sel = page.evaluate(_FIND_SCROLLER)
    assert sel, "카탈로그를 담은 스크롤 컨테이너를 못 찾았다"
    return sel


def _scroll_to(page, sel, ratio):
    page.evaluate(
        """([sel, r]) => { const e = document.querySelector(sel);
             e.scrollTop = (e.scrollHeight - e.clientHeight) * r; }""",
        [sel, ratio],
    )
    page.wait_for_timeout(700)


def _total_models(page):
    return page.evaluate(
        "async () => { const r = await fetch('/api/catalog'); const j = await r.json(); return (j.models||[]).length; }"
    )


def test_scrolling_moves_the_rendered_window(zoo):
    sel = _scroller(zoo)
    first_before = _CARD_IDS and zoo.evaluate(_CARD_IDS)[0]
    _scroll_to(zoo, sel, 0.5)
    first_after = zoo.evaluate(_CARD_IDS)[0]
    assert first_after != first_before, (
        f"절반까지 스크롤했는데 첫 카드가 그대로다 ({first_before!r}) — "
        "가상화가 스크롤을 못 보고 있다"
    )


def test_scrolling_to_the_end_shows_models_the_top_never_showed(zoo):
    """끝까지 내렸을 때 맨 위에서 보이던 것과 겹치지 않는 모델이 나와야 한다.

    API 순서와 렌더 순서가 같다고 가정하지 않는다 — 카탈로그는 정렬을 따로 하므로
    'API 앞 40개' 와 비교하면 무의미하게 참이 된다. 화면이 실제로 이동했는지만 본다.
    """
    sel = _scroller(zoo)
    _scroll_to(zoo, sel, 0.0)
    top_ids = set(zoo.evaluate(_CARD_IDS))
    assert top_ids, "맨 위에서 렌더된 카드가 없다"

    _scroll_to(zoo, sel, 1.0)
    end_ids = set(zoo.evaluate(_CARD_IDS))
    assert end_ids, "끝까지 내렸는데 렌더된 카드가 없다"
    assert end_ids - top_ids, (
        f"끝까지 내렸는데 맨 위와 같은 모델만 보인다 ({len(end_ids)}장) — 화면이 이동하지 않았다"
    )


def test_virtualization_still_windows(zoo):
    """전부 그려버리는 '고침' 도 회귀다 — 347장을 한 번에 그리면 화면이 느려진다."""
    sel = _scroller(zoo)
    total = _total_models(zoo)
    for ratio in (0.0, 0.3, 0.6, 1.0):
        _scroll_to(zoo, sel, ratio)
        n = zoo.evaluate("() => document.querySelectorAll('[data-model-id]').length")
        assert n < total / 2, f"ratio={ratio} 에서 {n}장 렌더 — 가상화가 사라졌다 (총 {total})"


def test_list_view_scrolls_too(zoo):
    zoo.evaluate("() => { if (typeof setViewMode === 'function') setViewMode('list'); }")
    zoo.wait_for_timeout(1500)
    sel = _scroller(zoo)
    first_before = zoo.evaluate(_CARD_IDS)[0]
    _scroll_to(zoo, sel, 0.5)
    first_after = zoo.evaluate(_CARD_IDS)[0]
    assert first_after != first_before, (
        f"리스트 뷰에서 첫 행이 그대로다 ({first_before!r})"
    )
