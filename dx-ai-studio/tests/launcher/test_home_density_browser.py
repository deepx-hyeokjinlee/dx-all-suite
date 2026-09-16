"""home 의 모듈 행이 각자 숫자를 들고, 정상일 때는 조용한지.

모듈 여덟 개를 실제로 띄우지 않는다 — 런처 프록시로 가는 요청을 가로채 가짜로
응답한다. 계약은 "각 모듈 API 의 응답을 이 화면이 어떻게 읽는가" 이므로 진짜 서버는
필요 없고, 여덟 프로세스를 띄우는 비용도 치르지 않는다.

이 파일이 존재하는 이유: 기존 home 계약은 `home-sections.js` 를 문자열로 읽는 정적
검사뿐이었다. ModelZoo 가상화가 죽어 있던 동안에도 같은 종류의 검사는 전부 초록이었다.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

CATALOG = {"ok": True, "models": [
    {"id": f"m{i}", "display": {"task": f"task{i % 3}"}} for i in range(12)
]}
APP_DEMOS = {"demos": [{"idx": i, "group": f"g{i % 4}"} for i in range(9)]}
STREAM_DEMOS = [{"id": i} for i in range(5)]
SHOWCASES = {"showcases": [{"id": f"s{i}"} for i in range(3)]}
BENCH = [{"hw_id": "A", "runs": [{"run_id": "1"}, {"run_id": "2"}]},
         {"hw_id": "B", "runs": [{"run_id": "3"}]}]
HW = {"available": True, "npus": [{"id": 0, "cores": 3, "temperatures": [40.0, 39.0, 39.0]}]}

ROUTES = {
    "**/zoo/api/catalog": CATALOG,
    "**/app/api/demos": APP_DEMOS,
    "**/stream/api/demos": STREAM_DEMOS,
    "**/agent/api/agent/showcases": SHOWCASES,
    "**/benchmark/api/results": BENCH,
    "**/dx_monitor/api/hw_status": HW,
}


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


def _open(browser, port, *, serve=None, health=None):
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    # Playwright 는 핸들러를 (route, request) 로 부른다. 기본 인자로 payload 를
    # 넘기면 두 번째 자리에 Request 가 들어와 덮어쓴다 — 팩토리로 닫아 둔다.
    def _fulfil(payload):
        def handler(route, *_):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(payload))
        return handler

    for pattern, payload in (serve or ROUTES).items():
        page.route(pattern, _fulfil(payload))
    if health is not None:
        page.route("**/api/health", _fulfil(health))
    page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
    page.wait_for_timeout(4000)
    page.evaluate(
        "() => { const t=window._dxTutorial; if(t){try{t.stop&&t.stop();}catch(e){}}"
        " document.querySelectorAll('.dxt-toc,.dxt-overlay,.dxt-tooltip,.dxt-toc-backdrop')"
        ".forEach(e=>e.remove()); }"
    )
    page.wait_for_timeout(400)
    return ctx, page


def _desc(page, app):
    return page.evaluate(
        "(a) => { const e=document.querySelector('.orbital-card[data-app=\"'+a+'\"] .card-desc');"
        " return e ? e.textContent.trim() : null; }", app)


@pytest.fixture()
def home(browser):
    server, port = start_module_server("launcher")
    ctx, page = _open(browser, port)
    try:
        yield page
    finally:
        page.close(); ctx.close(); server.shutdown()


def test_each_module_carries_its_own_number(home):
    assert "12" in _desc(home, "zoo"), _desc(home, "zoo")
    assert "3" in _desc(home, "zoo"), "task 수도 들어야 한다"
    assert "9" in _desc(home, "app"), _desc(home, "app")
    assert "5" in _desc(home, "stream"), _desc(home, "stream")
    assert "3" in _desc(home, "agent"), _desc(home, "agent")
    assert "2" in _desc(home, "benchmark"), _desc(home, "benchmark")
    assert "40" in _desc(home, "dx_monitor"), _desc(home, "dx_monitor")


def test_modules_with_nothing_to_count_keep_their_prose(home):
    for app in ("compiler", "planner"):
        d = _desc(home, app)
        assert d, f"{app} 설명이 비었다"
        assert not any(ch.isdigit() for ch in d), f"{app} 에 숫자가 붙었다: {d!r}"


def test_a_module_that_is_down_does_not_block_the_others(browser):
    """한 모듈의 응답 실패가 나머지 행을 막으면 안 된다."""
    server, port = start_module_server("launcher")
    broken = dict(ROUTES)
    broken.pop("**/app/api/demos")
    ctx, page = _open(browser, port, serve=broken)
    try:
        page.route("**/app/api/demos", lambda route: route.abort())
        page.wait_for_timeout(500)
        assert "12" in _desc(page, "zoo"), "다른 모듈이 실패에 휩쓸렸다"
        assert "3" in _desc(page, "agent")
    finally:
        page.close(); ctx.close(); server.shutdown()


# ── 정상일 때는 조용해야 한다 ──────────────────────────────────
#
# 모듈이 전부 돌면(평상시) 화면은 같은 사실을 세 번 말했다: 목록 위 "8 of 8 running",
# 행마다 "Running" 여덟 번, 오른쪽 패널에 같은 이름 여덟 개. 이 파일이 지키는 것은
# "예외를 드러내고 평상시엔 침묵한다" 이다. 같은 파일의 기존 주석이 이미 같은 함정을
# 다룬다 — "start → 여덟 개는 행동 유도가 여덟 개라는 뜻이고, 그러면 아무것도 행동
# 유도가 아니다."

# health 키는 카드의 data-app 과 다르다 (dx_monitor → monitor). 목록을 손으로
# 적으면 매핑이 바뀔 때 조용히 어긋나므로, 페이지가 실제로 쓰는 매핑에서 뽑는다.
_KEYS_FROM_PAGE = """() => {
  const map = (window.DXLauncher && window.DXLauncher._HEALTH_KEY) || null;
  return [...document.querySelectorAll('.orbital-card[data-app]')]
    .map(c => (map && map[c.dataset.app]) || c.dataset.app);
}"""


def _page_health_keys(page):
    keys = page.evaluate(_KEYS_FROM_PAGE)
    assert keys, "모듈 카드를 못 찾았다"
    return keys


def _health(alive_keys, all_keys):
    return {k: {"alive": k in alive_keys} for k in all_keys}


def _set_health(page, health):
    """페이지가 들고 있는 health 를 바꿔 다시 그리게 한다.

    /api/health 를 가로채는 대신 이렇게 하는 이유: 폴링이 이미 한 번 돌아 결과를
    캐시해 둔 뒤라 route 만으로는 다음 주기까지 반영되지 않는다.
    """
    page.evaluate(
        "(h) => { window.DXLauncher._healthStatus = h;"
        " window.DXLauncher.refreshModuleState(); }", health)


def _state_labels(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('.orbital-card [data-role=\"state\"]')]"
        ".map(e => e.textContent.trim()).filter(Boolean)")


def _running_panel_visible(page):
    return page.evaluate(
        "() => { const l=document.getElementById('wsRunning'); if(!l) return false;"
        " const p=l.closest('.ws-panel'); return !!(p && !p.hidden); }")


def test_when_everything_runs_the_screen_stops_repeating_itself(browser):
    server, port = start_module_server("launcher")
    ctx, page = _open(browser, port)
    try:
        keys = _page_health_keys(page)
        _set_health(page, _health(keys, keys))
        page.wait_for_timeout(1200)
        assert not _state_labels(page), (
            f"전부 도는데 행마다 상태 라벨이 있다: {_state_labels(page)}"
        )
        assert not _running_panel_visible(page), (
            "전부 도는데 Running 패널이 같은 목록을 되풀이한다"
        )
        count = page.evaluate(
            "() => { const e=document.getElementById('moduleUpCount');"
            " return e ? e.textContent.trim() : ''; }")
        assert "8" in count, f"그 사실은 한 줄로 남아야 한다: {count!r}"
    finally:
        page.close(); ctx.close(); server.shutdown()


def test_when_one_is_down_the_screen_says_so(browser):
    server, port = start_module_server("launcher")
    ctx, page = _open(browser, port)
    try:
        keys = _page_health_keys(page)
        alive = [k for k in keys if k != "benchmark"]
        _set_health(page, _health(alive, keys))
        page.wait_for_timeout(1200)
        assert _running_panel_visible(page), (
            "하나가 꺼졌는데 Running 패널이 나타나지 않는다"
        )
        assert _state_labels(page), "예외 상태일 때는 행 라벨이 정보가 된다"
    finally:
        page.close(); ctx.close(); server.shutdown()
