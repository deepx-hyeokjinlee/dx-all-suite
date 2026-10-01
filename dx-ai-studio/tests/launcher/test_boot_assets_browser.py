"""Home 은 아이콘 · font 가 도착한 뒤에 열린다 — 단 상한 안에 (spec 2026-09-30 boot assets).

외부 sprite (`<use href="dx-icons.svg?v=…#id">`) 는 도착하기 전까지 빈칸이다. VS Code port-forward
tunnel 너머에서는 그 틈이 보였다: Home 이 먼저 열리고 아이콘이 나중에 튀어나왔다. boot gate 는
`studio_ready` 에 더해 font · sprite 를 기다리고, 무엇이 막혀도 문서 시작부터 3s 에 연다.
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

# boot-pending 이 풀린 순간 (performance.now) 을 적는다 — 한 번 pending 을 본 뒤에만.
_WATCH = """
try{sessionStorage.setItem('dx-splash-seen','1');localStorage.setItem('dx-splash-seen','1');
localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}
window.__gateOpenAt = null;
(function tick(){
  var h = document.documentElement;
  if (h && h.classList.contains('launcher-boot-pending')) window.__seenPending = true;
  else if (h && window.__seenPending) { window.__gateOpenAt = performance.now(); return; }
  requestAnimationFrame(tick);
})();
"""

_SPRITE_END = """() => Math.max(0, ...performance.getEntriesByType('resource')
  .filter(e => /dx-icons\\.svg/.test(e.name)).map(e => e.responseEnd))"""


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


@pytest.fixture(scope="module")
def port():
    server, port = start_module_server("launcher")
    yield port
    server.shutdown()


def _open(browser, port, sprite_delay_s):
    ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    ctx.add_init_script(_WATCH)

    def slow(route):
        time.sleep(sprite_delay_s)
        route.continue_()

    ctx.route("**/static/shared/dx-icons.svg*", slow)
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function("window.__gateOpenAt !== null", timeout=20000)
    return ctx, page


def test_the_home_waits_for_the_icons(browser, port):
    ctx, page = _open(browser, port, 1.2)
    try:
        opened = page.evaluate("window.__gateOpenAt")
        sprite = page.evaluate(_SPRITE_END)
        assert sprite > 1000, f"sprite 가 늦춰지지 않았다: {sprite}"
        assert opened >= sprite, f"gate 가 sprite ({sprite:.0f}ms) 보다 먼저 열렸다 ({opened:.0f}ms)"
    finally:
        ctx.close()


def test_a_stuck_sprite_does_not_hold_the_home(browser, port):
    ctx, page = _open(browser, port, 6.0)
    try:
        opened = page.evaluate("window.__gateOpenAt")
        assert 2500 <= opened <= 4500, f"상한 3s 근처에서 열려야 한다: {opened:.0f}ms"
    finally:
        ctx.close()


def test_the_home_names_the_hashed_sprite(browser, port):
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
        meta = page.evaluate("(document.querySelector('meta[name=\"dx-icons\"]')||{}).content || ''")
        assert "/static/shared/dx-icons.svg?v=" in meta
        hrefs = page.evaluate("[...document.querySelectorAll('use')].map(u => u.getAttribute('href'))")
        stale = [h for h in hrefs if not h.startswith(meta + "#")]
        assert hrefs and not stale, stale[:5]
    finally:
        ctx.close()
