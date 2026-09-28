"""home 의 Build 는 검색창이 아니라 작업을 시작하는 자리여야 한다.

앞 작업에서 제목 위계를 잡고 입력을 17→21px 로 키웠는데도 "여전히 뭔지 안 보인다"
는 평가를 받았다. 맞는 지적이었다 — 블록이 화면 900px 중 217px 를 쓰면서 여전히
"검색창 하나" 로 읽혔다.

그래서 이 파일이 지키는 것은 두 가지다: 그 덩어리가 첫 화면에서 가장 크다는 것과,
한 줄짜리 질문이 아니라 여러 줄을 쓸 수 있다는 것.

모듈의 배치 (5×2, 좁으면 접힘) 는 test_home_stage_browser.py 가 본다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

_QUIET = """() => {
  const t = window._dxTutorial;
  if (t) { try { t.stop && t.stop(); } catch (e) {} }
  document.querySelectorAll('.dxt-toc,.dxt-overlay,.dxt-tooltip,.dxt-toc-backdrop')
    .forEach(e => e.remove());
}"""


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


def _open(browser, width=1512, height=900):
    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": width, "height": height})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
    page.wait_for_timeout(3500)
    page.evaluate(_QUIET)
    page.wait_for_timeout(400)
    return server, ctx, page


@pytest.fixture()
def home(browser):
    server, ctx, page = _open(browser)
    try:
        yield page
    finally:
        page.close(); ctx.close(); server.shutdown()


def _h(page, sel):
    return page.evaluate(
        "(s) => { const e = document.querySelector(s);"
        " return e ? Math.round(e.getBoundingClientRect().height) : 0; }", sel)


def test_the_build_block_is_the_largest_thing_on_the_first_screen(home):
    """hero 가 양옆 위젯보다 커야 한다 — 제품의 주장이 상태보다 작은 자리를 쓰면 안 된다."""
    build = _h(home, "#homeStage")
    for widget in ("#homeDevice", "#homeMeasured"):
        other = _h(home, widget)
        assert other > 0, f"{widget} 가 그려지지 않았다 — 비교가 공짜로 참이 된다"
        assert build > other, f"Build {build}px 가 {widget} {other}px 보다 작다"


def test_you_can_write_more_than_one_line(home):
    tag = home.evaluate(
        "() => { const e = document.getElementById('homeAsk');"
        " return e ? e.tagName.toLowerCase() : null; }")
    assert tag == "textarea", (
        f"입력이 <{tag}> 다 — 한 줄짜리 질문만 받는 자리로 읽힌다"
    )


def test_the_input_reads_at_least_as_large_as_the_subtitle(home):
    """무대 (spec 2026-09-23 §5.2) 에서 가장 큰 글자는 56px 제목이다. 예전 계약 ("입력이 이
    블록에서 가장 크다") 은 제목이 없던 판의 것이라, 입력이 부제보다 작아지지 않는 것만 남긴다."""
    ask = home.evaluate(
        "() => parseFloat(getComputedStyle(document.getElementById('homeAsk')).fontSize)")
    note = home.evaluate(
        "() => { const e = document.querySelector('#homeStage .stage-sub');"
        " return e ? parseFloat(getComputedStyle(e).fontSize) : 0; }")
    # 설명이 없으면 0 과 비교해 공짜로 통과한다 — 예전 판이 .ws-note 를 잃고 그랬다.
    assert note > 0, "hero 부제가 없다"
    assert ask >= note, f"입력 {ask}px 가 부제 {note}px 보다 작다"
    assert ask >= 21, f"입력 글자가 {ask}px — 작업 공간으로 읽히기에 작다"


def test_the_examples_belong_to_the_input_not_the_page(home):
    """칩이 입력 밖에 떠 있으면 무엇의 예시인지 보이지 않는다."""
    inside = home.evaluate(
        """() => {
          const chips = document.getElementById('homeAskChips');
          const form = document.getElementById('homeAskForm');
          return !!(chips && form && form.contains(chips));
        }"""
    )
    assert inside, "예시 칩이 입력 덩어리 밖에 있다"
