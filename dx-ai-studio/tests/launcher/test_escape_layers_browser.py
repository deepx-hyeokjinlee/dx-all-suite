"""Escape closes the topmost thing first, and only then leaves the module (2026-10-02 release audit X-1 / A-1 / L-5).

Escape anywhere in the launcher document called goHome() while a module was open: pressed in the chat input it
left the module (and aborted the reply) with the chat still open; pressed with the Tutorial Guide open it left the
module too; in the SDK Library search box it left the view instead of clearing the search.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

_QUIET = ("try{sessionStorage.setItem('dx-splash-seen','1');localStorage.setItem('dx-splash-seen','1');"
          "localStorage.setItem('dx-tutorial-launcher-autostarted','1');localStorage.setItem('dx-tutorial-mode','off');"
          "}catch(e){}")


@pytest.fixture(scope="module")
def port():
    server, port = start_module_server("launcher")
    yield port
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright
    from tests.browser_support import resolve_chromium_executable

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True, executable_path=resolve_chromium_executable())
    yield br
    br.close()
    pw.stop()


def _open(browser, port, app):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(_QUIET)
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_function("!!(window.DXLauncher && DXLauncher.launch && typeof DXChat !== 'undefined' && document.querySelector('.dx-chat-fab'))", timeout=30000)
    opener = {"sdk-library": "DXLauncher.showSdkLibrary()", "about": "DXLauncher.showAboutView()"}.get(
        app, f"DXLauncher.launch('{app}')")
    page.evaluate(opener)
    page.wait_for_function(f"DXLauncher.currentApp === '{app}'", timeout=15000)
    return ctx, page


def test_escape_in_the_chat_closes_the_chat_and_stays_in_the_view(port, browser):
    # launcher 채팅은 launcher 의 화면 (홈 · SDK Library · About) 에 있다 — 모듈 안에서는 모듈 자신의 채팅 (아래 시험)
    ctx, page = _open(browser, port, "sdk-library")
    try:
        page.click(".dx-chat-fab")
        page.wait_for_selector(".dx-chat-window.open")
        page.focus(".dx-chat-window textarea, .dx-chat-window input")
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.dx-chat-window.open')")
        assert page.evaluate("DXLauncher.currentApp") == "sdk-library"
    finally:
        ctx.close()


def test_escape_with_the_tutorial_guide_open_closes_the_guide_first(port, browser):
    ctx, page = _open(browser, port, "zoo")
    try:
        page.evaluate("document.getElementById('dxToolbarTutorial').click()")
        page.wait_for_selector(".dxt-toc.open", timeout=10000)
        page.keyboard.press("Escape")
        page.wait_for_function("!document.querySelector('.dxt-toc.open')")
        assert page.evaluate("DXLauncher.currentApp") == "zoo"
    finally:
        ctx.close()


def test_escape_in_the_sdk_search_clears_it_and_stays(port, browser):
    ctx, page = _open(browser, port, "sdk-library")
    try:
        page.fill("#sdkLibSearch", "compiler")
        page.focus("#sdkLibSearch")
        page.keyboard.press("Escape")
        assert page.input_value("#sdkLibSearch") == ""
        assert page.evaluate("DXLauncher.currentApp") == "sdk-library"
    finally:
        ctx.close()


def test_inside_a_module_only_the_modules_own_chat_button_is_there(port, browser):
    """launcher 의 채팅 버튼이 모듈 iframe 의 채팅 버튼을 같은 자리에서 덮어, 모듈 전용 도움말 (모듈 지식 · 오프라인 답) 을
    열 수 없었다 (2026-10-02 release audit X-2 / A-2). 모듈 안에서는 launcher 의 것을 숨긴다."""
    ctx, page = _open(browser, port, "zoo")
    try:
        assert not page.locator("body > .dx-chat-fab, .dx-chat-fab").first.is_visible()
        page.evaluate("DXLauncher.goHome()")
        page.wait_for_function("!DXLauncher.currentApp")
        page.locator(".dx-chat-fab").first.wait_for(state="visible", timeout=10000)
    finally:
        ctx.close()


def test_opening_the_sdk_library_does_not_add_a_second_chat_button(port, browser):
    """SDK Library 가 DXChat.init 을 다시 불러 위젯이 하나 더 생겼다 — 같은 자리에 버튼 두 개 (2026-10-02)."""
    ctx, page = _open(browser, port, "sdk-library")
    try:
        assert page.evaluate("document.querySelectorAll('.dx-chat-fab').length") == 1
        assert page.evaluate("document.querySelectorAll('.dx-chat-window').length") == 1
        page.evaluate("DXLauncher.goHome()")
        page.evaluate("DXLauncher.showSdkLibrary()")
        assert page.evaluate("document.querySelectorAll('.dx-chat-fab').length") == 1
    finally:
        ctx.close()
