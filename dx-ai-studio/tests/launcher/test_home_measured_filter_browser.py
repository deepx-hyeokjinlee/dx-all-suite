"""home 의 측정값 표를 검색하고 카테고리로 고를 수 있어야 한다.

`Measured on DX-M1` 은 task 당 하나씩 다섯 줄 고정이었다. 그건 "이 칩으로 무엇을
할 수 있나" 에는 답하지만 "내 모델이 여기서 몇 FPS 인가" 에는 답하지 못한다.

카탈로그는 이미 통째로 받아와 있다 — 347개 중 344개가 `performance.fps` 를 갖고,
task 는 22개다. 그러니 새 API 없이 그 위에 검색과 필터만 얹으면 된다. 행을 누르면
지금처럼 ModelZoo 의 그 모델로 간다.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

# task 셋, FPS 를 일부러 흩어 두어 "빠른 순" 과 "거르기" 를 구분해 볼 수 있게 한다.
MODELS = [
    {"id": "det-fast", "display": {"task": "object_detection", "class_name": "DetFast"},
     "performance": {"fps": 900}},
    {"id": "det-slow", "display": {"task": "object_detection", "class_name": "DetSlow"},
     "performance": {"fps": 100}},
    {"id": "pose-one", "display": {"task": "pose_estimation", "class_name": "PoseOne"},
     "performance": {"fps": 400}},
    {"id": "cls-top", "display": {"task": "classification", "class_name": "ClsTop"},
     "performance": {"fps": 7000}},
    {"id": "cls-mid", "display": {"task": "classification", "class_name": "ClsMid"},
     "performance": {"fps": 300}},
    {"id": "seg-one", "display": {"task": "semantic_segmentation", "class_name": "SegOne"},
     "performance": {"fps": 500}},
    {"id": "face-one", "display": {"task": "face_detection", "class_name": "FaceOne"},
     "performance": {"fps": 4200}},
]
CATALOG = {"ok": True, "models": MODELS}

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


@pytest.fixture()
def home(browser):
    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": 1512, "height": 900})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()

    def catalog(route, *_):
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps(CATALOG))

    page.route("**/zoo/api/catalog", catalog)
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
        page.wait_for_timeout(3500)
        page.evaluate(_QUIET)
        page.wait_for_timeout(400)
        yield page
    finally:
        page.close(); ctx.close(); server.shutdown()


def _rows(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('#perfRows tr')]"
        ".map(tr => tr.querySelector('.perf-name')?.textContent.trim()).filter(Boolean)")


def _search(page, text):
    page.evaluate(
        """(t) => { const i = document.getElementById('measuredSearch');
             i.value = t; i.dispatchEvent(new Event('input', { bubbles: true })); }""", text)
    page.wait_for_timeout(350)


def test_the_default_still_answers_what_this_chip_can_do(home):
    """기본은 바뀌지 않는다 — task 당 하나씩, 그 task 에서 가장 빠른 것."""
    rows = _rows(home)
    assert rows, "기본 표가 비었다"
    assert "DetFast" in rows, f"object_detection 의 최고가 없다: {rows}"
    assert "DetSlow" not in rows, "기본에서 같은 task 를 두 번 보여준다"


def test_searching_narrows_to_what_was_asked(home):
    _search(home, "cls")
    rows = _rows(home)
    assert rows, "검색 결과가 비었다"
    assert all(r.lower().startswith("cls") for r in rows), rows


def test_search_orders_by_speed(home):
    _search(home, "cls")
    rows = _rows(home)
    assert rows[0] == "ClsTop", f"빠른 순이 아니다: {rows}"


def test_clearing_the_search_returns_to_the_default(home):
    _search(home, "cls")
    _search(home, "")
    rows = _rows(home)
    assert "DetFast" in rows, f"기본으로 돌아오지 않았다: {rows}"


def test_a_category_chip_filters_to_that_task(home):
    home.evaluate(
        """() => { const c = document.querySelector('#measuredCats [data-task="classification"]');
             if (c) c.click(); }""")
    home.wait_for_timeout(350)
    rows = _rows(home)
    assert rows, "카테고리 결과가 비었다"
    assert set(rows) <= {"ClsTop", "ClsMid"}, rows


def test_no_match_says_so_instead_of_going_blank(home):
    """조용히 비면 고장처럼 보인다."""
    _search(home, "zzzznotamodel")
    empty = home.evaluate(
        "() => { const e = document.getElementById('measuredEmpty');"
        " return !!(e && e.offsetParent !== null); }")
    assert empty, "결과가 없는데 아무 말도 하지 않는다"


def test_a_row_still_opens_that_model_in_the_zoo(home):
    src = home.evaluate("() => document.querySelector('#perfRows tr') ? 'ok' : ''")
    assert src == "ok"
    href = home.evaluate(
        """() => { const tr = document.querySelector('#perfRows tr');
             return tr ? (tr.dataset.modelId || '') : ''; }""")
    assert href, "행이 어느 모델인지 들고 있지 않다"
