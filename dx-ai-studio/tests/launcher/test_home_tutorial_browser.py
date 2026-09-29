"""launcher 튜토리얼을 처음부터 끝까지 걸어 본다 (spec 2026-09-23 §9).

정적 계약은 대상 목록만 본다. 배열에 빈 칸 (`},,`) 이 생기자 엔진은 SDK Library 다음에서 투어를
멈췄고, 정적 계약도 journey 도 그것을 보지 못했다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.launcher.test_home_tutorial_contract import ORDER  # noqa: E402
from tests.server_helpers import start_module_server  # noqa: E402

_SEEN = ("try{sessionStorage.setItem('dx-splash-seen','1');localStorage.setItem('dx-splash-seen','1');"
         "localStorage.setItem('dx-tutorial-launcher-autostarted','1');sessionStorage.setItem('dx-home-entered','1');"
         "}catch(e){}")


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


@pytest.mark.parametrize("lang", ["en", "ko"])
def test_every_step_is_shown_on_its_target_to_the_end(browser, server, lang):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script(_SEEN + f"try{{localStorage.setItem('dx-lang','{lang}');}}catch(e){{}}")
    page = ctx.new_page()
    try:
        page.goto(f"http://127.0.0.1:{server}/", wait_until="load")
        page.wait_for_selector("#studioGrid .orbital-card", state="visible")
        page.wait_for_timeout(1200)
        page.evaluate("() => { const t = window._dxTutorial; t.hideTOC && t.hideTOC(); t.startAll(); }")
        seen = []
        for _ in ORDER:
            page.wait_for_function("""() => { const t = window._dxTutorial;
              return t._curSection && document.querySelector('.dxt-spotlight.active'); }""", timeout=5000)
            seen.append(page.evaluate("() => { const t = window._dxTutorial; return t._curSection.steps[t._curStep].target; }"))
            page.evaluate("() => { window._dxTutorial.next(); }")   # 마지막 next 는 완료 창을 await 한다
            page.wait_for_timeout(250)
        assert seen == ORDER, seen
    finally:
        ctx.close()
