"""home 과 Agent Dev 가 같은 실행에 붙는지.

`test_live_run.py` 는 버퍼를, `test_server_reattach.py` 는 HTTP 배선을 지킨다.
여기서는 화면이 실제로 그것을 쓰는지 본다 — 서버가 옳아도 콘솔이 붙지 않으면
사용자에게는 여전히 "작업이 사라진" 것이다.

원래 증상: home 에서 에이전트가 도는 중 `Open in DX Agent Dev` 를 누르면 Agent Dev
에서는 아무 일도 일어나지 않고, home 으로 돌아오면 작업이 없어져 있었다.
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

RUNNING = {
    "available": True, "busy": True, "agents": [{"name": "mock"}],
    "showcase_count": 0, "run_id": "abc123", "event_count": 3, "run_done": False,
}
IDLE = {
    "available": True, "busy": False, "agents": [{"name": "mock"}],
    "showcase_count": 0, "run_id": None, "event_count": 0, "run_done": True,
}
EVENTS = (
    'data: {"type":"status","text":"thinking"}\n\n'
    'data: {"type":"message","text":"building the baseball game"}\n\n'
    'data: {"type":"done"}\n\n'
)


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


def _open(browser, status):
    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": 1512, "height": 900})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    page.route("**/agent/api/agent/status", lambda r, *_: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(status)))
    page.route("**/agent/api/agent/run/events**", lambda r, *_: r.fulfill(
        status=200, content_type="text/event-stream", body=EVENTS))
    page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
    page.wait_for_timeout(3500)
    page.evaluate(_QUIET)
    page.wait_for_timeout(800)
    return server, ctx, page


def test_home_picks_up_a_run_that_is_already_going(browser):
    """떠났다 돌아온 창이 이어받는 길."""
    server, ctx, page = _open(browser, RUNNING)
    try:
        shown = page.evaluate(
            "() => { const v = document.getElementById('homeWork');"
            " return !!(v && v.offsetParent !== null); }")
        assert shown, "실행 중인데 작업 뷰가 열리지 않았다"
        text = page.evaluate(
            "() => (document.getElementById('workNarration') || {}).textContent || ''")
        assert "baseball" in text, f"붙었는데 내용이 없다: {text[:120]!r}"
    finally:
        page.close(); ctx.close(); server.shutdown()


def test_home_stays_quiet_when_nothing_is_running(browser):
    """돌지 않는데 작업 뷰가 열리면 그건 유령이다."""
    server, ctx, page = _open(browser, IDLE)
    try:
        shown = page.evaluate(
            "() => { const v = document.getElementById('homeWork');"
            " return !!(v && v.offsetParent !== null); }")
        assert not shown, "도는 게 없는데 작업 뷰가 열렸다"
    finally:
        page.close(); ctx.close(); server.shutdown()


def test_the_move_button_does_not_leave_the_shell(browser):
    """전체 이동이면 스트림이 끊기고, 예전에는 그것이 실행을 죽였다."""
    src = (__import__("pathlib").Path(__file__).resolve().parents[2]
           / "launcher" / "static" / "home-console.js").read_text(encoding="utf-8")
    body = src[src.index("workOpenModule"):]
    body = body[: body.index("\n    }")]
    assert "location.href" not in body, (
        "이동 버튼이 여전히 전체 페이지 이동을 쓴다"
    )
