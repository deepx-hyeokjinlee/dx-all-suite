"""home 의 Build 는 검색창이 아니라 작업을 시작하는 자리여야 한다.

앞 작업에서 제목 위계를 잡고 입력을 17→21px 로 키웠는데도 "여전히 뭔지 안 보인다"
는 평가를 받았다. 맞는 지적이었다 — 블록이 화면 900px 중 217px 를 쓰면서 여전히
"검색창 하나" 로 읽혔다.

그래서 이 파일이 지키는 것은 두 가지다: 그 덩어리가 첫 화면에서 가장 크다는 것과,
한 줄짜리 질문이 아니라 여러 줄을 쓸 수 있다는 것.

모듈도 같은 문제였다. 세 묶음으로 나눴지만 여덟 행이 여전히 733px 를 세로로 흘렀다.
묶음이 생겼을 뿐 형태는 그대로였으므로, 형태를 바꾼다 — 세 열.
"""
from __future__ import annotations

import json

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


# #measured 가 그려지지 않으면 높이가 0 이라 "Build 가 가장 크다" 가 공짜로 참이
# 된다 — 처음에 그렇게 써서 통과를 잘못 읽었다. 카탈로그를 고정해 실제로 그리게 한다.
CATALOG = {"ok": True, "models": [
    {"id": "a", "display": {"task": "object_detection", "class_name": "SSD"},
     "performance": {"fps": 1847}},
    {"id": "b", "display": {"task": "pose_estimation", "class_name": "PoseNet"},
     "performance": {"fps": 357}},
    {"id": "c", "display": {"task": "semantic_segmentation", "class_name": "DeepLabV3"},
     "performance": {"fps": 501}},
    {"id": "d", "display": {"task": "face_detection", "class_name": "ULFGFD"},
     "performance": {"fps": 4201}},
    {"id": "e", "display": {"task": "classification", "class_name": "ShuffleNetV2"},
     "performance": {"fps": 7449}},
]}


def _open(browser, width=1512, height=900):
    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": width, "height": height})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    page.route("**/zoo/api/catalog", lambda route, *_: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(CATALOG)))
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


BUILD = ".ws-block:not(#measured):not(#studio)"


def test_the_build_block_is_the_largest_thing_on_the_first_screen(home):
    build = _h(home, BUILD)
    measured = _h(home, "#measured")
    assert measured > 0, "#measured 가 그려지지 않았다 — 비교가 공짜로 참이 된다"
    assert build > measured, (
        f"Build {build}px 가 Measured {measured}px 보다 작다 — 제품의 주장이 "
        "증거보다 작은 자리를 쓴다"
    )


def test_you_can_write_more_than_one_line(home):
    tag = home.evaluate(
        "() => { const e = document.getElementById('homeAsk');"
        " return e ? e.tagName.toLowerCase() : null; }")
    assert tag == "textarea", (
        f"입력이 <{tag}> 다 — 한 줄짜리 질문만 받는 자리로 읽힌다"
    )


def test_the_placeholder_is_the_biggest_words_in_that_block(home):
    ask = home.evaluate(
        "() => parseFloat(getComputedStyle(document.getElementById('homeAsk')).fontSize)")
    note = home.evaluate(
        "() => { const e = document.querySelector('.ws-note');"
        " return e ? parseFloat(getComputedStyle(e).fontSize) : 0; }")
    assert ask > note, f"입력 {ask}px 가 설명 {note}px 보다 크지 않다"
    assert ask >= 24, f"입력 글자가 {ask}px — 작업 공간으로 읽히기에 작다"


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


def test_the_modules_stand_in_three_columns(home):
    tops = home.evaluate(
        "() => [...document.querySelectorAll('#studioGrid .studio-col')]"
        ".map(e => Math.round(e.getBoundingClientRect().top))")
    assert len(tops) == 3, f"모듈 열이 {len(tops)}개다"
    assert len(set(tops)) == 1, f"세 열이 나란하지 않다: {tops}"


def test_the_modules_reflow_when_the_width_runs_out(browser):
    """좁아지면 열이 줄어야 한다 — 몇 행이 되는지는 고정하지 않는다.

    이 검사는 한때 "좁으면 세 행" 이었다. 그때는 768px media query 로 1열을 강제했기
    때문이다. 지금은 `repeat(auto-fit, minmax(280px, 1fr))` 이라 폭에 맞춰 스스로
    접히므로, 700px 에서는 2행(2+1)이 된다. 행 수를 세는 것은 구현을 베끼는 것이고,
    지켜야 할 성질은 "넓을 때보다 열이 적어진다" 이다.
    (auto-fit 으로 바꾸면서 이 테스트를 같이 고치지 않아 한동안 빨간불이었다 —
    run_ci 가 브라우저 스위트를 제외하므로 드러나지 않았다.)
    """
    def rows(width):
        server, ctx, page = _open(browser, width=width, height=900)
        try:
            tops = page.evaluate(
                "() => [...document.querySelectorAll('#studioGrid .studio-col')]"
                ".map(e => Math.round(e.getBoundingClientRect().top))")
            assert len(tops) == 3, f"열이 셋이 아니다: {tops}"
            return len(set(tops))
        finally:
            page.close(); ctx.close(); server.shutdown()

    wide, narrow = rows(1512), rows(700)
    assert wide == 1, f"넓은데 한 행이 아니다: {wide}행"
    assert narrow > wide, f"좁아졌는데 접히지 않았다: {wide}행 → {narrow}행"
