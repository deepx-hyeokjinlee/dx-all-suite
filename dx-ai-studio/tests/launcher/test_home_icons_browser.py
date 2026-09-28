"""아이콘과 책이 화면에서 약속한 모양인지 (spec 2026-09-23 §5.3–5.4)."""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

_SEEN = ("try{sessionStorage.setItem('dx-splash-seen','1');localStorage.setItem('dx-splash-seen','1');"
         "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}")
_QUIET = """() => {
  const t = window._dxTutorial;
  if (t) { try { t.hideTOC && t.hideTOC(); t.stop && t.stop(); } catch (e) {} }
  document.querySelectorAll('.dxt-toc,.dxt-overlay,.dxt-tooltip,.dxt-toc-backdrop').forEach(e => e.remove());
}"""


@pytest.fixture(scope="module")
def server():
    srv, port = start_module_server("launcher")
    yield port
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


@pytest.fixture()
def page(browser, server):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script(_SEEN)
    pg = ctx.new_page()
    pg.goto(f"http://127.0.0.1:{server}/", wait_until="load")
    pg.wait_for_selector("#studioGrid .orbital-card", state="visible")
    pg.evaluate(_QUIET)
    pg.wait_for_timeout(300)
    yield pg
    ctx.close()


def _box(page, sel):
    return page.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect();"
                         " return [Math.round(r.width), Math.round(r.height)]; }", sel)


def _opacity(page, sel):
    return page.evaluate("(s) => parseFloat(getComputedStyle(document.querySelector(s)).opacity)", sel)


def _becomes_opaque(page, sel):
    """말풍선은 --dur (0.24s) 동안 나타난다. 전환 중에 읽으면 0 과 1 사이다."""
    page.wait_for_function(
        "(s) => parseFloat(getComputedStyle(document.querySelector(s)).opacity) === 1", arg=sel, timeout=2000)
    return _opacity(page, sel)


def test_icons_are_72_and_48_in_the_dock(page):
    assert _box(page, '#studioGrid .orbital-card[data-app="app"] .mod-tile') == [72, 72]
    page.evaluate("() => { document.getElementById('homeAnswer').hidden = false; }")
    page.wait_for_timeout(100)
    assert _box(page, '#studioGrid .orbital-card[data-app="app"] .mod-tile') == [48, 48]


def test_the_name_shows_and_the_description_waits(page):
    card = '#studioGrid .orbital-card[data-app="stream"]'
    assert page.locator(f"{card} .orbital-name").is_visible()
    assert _opacity(page, f"{card} .card-desc") == 0
    page.hover(card)
    assert _becomes_opaque(page, f"{card} .card-desc") == 1


def test_keyboard_focus_shows_the_description_too(page):
    card = '#studioGrid .orbital-card[data-app="zoo"]'
    page.focus(card)
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert _becomes_opaque(page, f"{card} .card-desc") == 1


def test_only_a_module_that_is_down_is_dimmed(page):
    page.evaluate("""() => { const L = window.DXLauncher; const h = {};
      document.querySelectorAll('.orbital-card[data-app]').forEach(c => {
        const k = (L._HEALTH_KEY && L._HEALTH_KEY[c.dataset.app]) || c.dataset.app;
        h[k] = { alive: c.dataset.app !== 'benchmark' }; });
      L._healthStatus = h; L.refreshModuleState(); }""")
    page.wait_for_timeout(50)
    down = _opacity(page, '#studioGrid .orbital-card[data-app="benchmark"] .mod-tile')
    up = _opacity(page, '#studioGrid .orbital-card[data-app="app"] .mod-tile')
    assert up == 1 and down < 1, (up, down)


def test_books_are_covers(page):
    assert _box(page, "#studioGrid .about-book-card .orbital-icon") == [56, 72]
    assert _box(page, "#studioGrid .about-book-card.sdk-card .orbital-icon") == [56, 72]


def test_icons_and_covers_share_one_baseline(page):
    """아이콘 (72) 과 표지 (72) 의 아래 끝이 같은 줄이라야 이름이 한 줄에 선다."""
    bottoms = page.evaluate("""() => [...document.querySelectorAll('#studioGrid > *')].slice(0, 5)
      .map(t => Math.round((t.querySelector('.mod-tile') || t.querySelector('.orbital-icon')).getBoundingClientRect().bottom))""")
    assert len(set(bottoms)) == 1, bottoms


def test_the_two_rows_stand_in_the_same_columns(page):
    """말풍선이 칸의 열을 넓혀 설명이 긴 칸일수록 아이콘이 밀렸다 — 두 줄이 어긋났다."""
    centres = page.evaluate("""() => [...document.querySelectorAll('#studioGrid > *')].map(t => {
      const i = t.querySelector('.mod-tile') || t.querySelector('.orbital-icon');
      const r = i.getBoundingClientRect(); return Math.round(r.left + r.width / 2); })""")
    top, bottom = centres[:5], centres[5:]
    assert all(abs(a - b) <= 1 for a, b in zip(top, bottom)), (top, bottom)
