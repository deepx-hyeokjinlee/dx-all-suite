"""dx_stream 데모 카드가 화면에서 약속대로 보이는지 (spec 2026-09-29 아이콘 체계 단계 4).

/api/demos 는 fixture 로 고정한다.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright.sync_api")
from tests.server_helpers import start_module_server  # noqa: E402

DEMOS = [
    {"id": 0, "name_en": "Object Detection", "category": "object_detection", "model": "yolo26n.dxnn",
     "description_en": "Basic object detection with YOLOv26n", "pipeline_type": "standard", "available": True,
     "availability": {"available": True}},
    {"id": 1, "name_en": "Multi-Stream", "category": "multi_stream", "model": "YoloV5S_PPU.dxnn",
     "description_en": "Four channels at once", "pipeline_type": "multi", "available": False,
     "availability": {"available": False, "reason_items": [{"code": "missing_model", "path": "YoloV5S_PPU.dxnn"}]}},
]


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright

    srv, port = start_module_server("dx_stream")
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script("localStorage.setItem('dx-tutorial-mode','off');")
    pg = ctx.new_page()
    pg.route("**/api/demos", lambda route, *_: route.fulfill(
        status=200, content_type="application/json", body=json.dumps(DEMOS)))
    pg.goto(f"http://127.0.0.1:{port}/", wait_until="load")
    pg.click('.dx-tab[data-page="demo"]')
    pg.wait_for_selector('#demo-grid .demo-card[data-id="1"]', timeout=10000)
    yield pg
    ctx.close()
    br.close()
    pw.stop()
    srv.shutdown()


def test_cards_show_the_task_symbol_and_state(page):
    info = page.evaluate("""() => [...document.querySelectorAll('#demo-grid .demo-card')].map(c => [
      c.querySelector('.demo-task use').getAttribute('href').split('#')[1],
      c.querySelector('.demo-card-header .dx-step-state:not([style*="none"])') ? [...c.querySelectorAll('.demo-card-header .dx-step-state')]
        .filter(s => getComputedStyle(s).display !== 'none').map(s => s.textContent.trim()).join('|') : ''])""")
    assert info == [["task-object_detection", "Ready"], ["dashboard", "Needs setup"]], info


def test_a_not_ready_card_is_short_and_links_to_setup(page):
    assert page.query_selector("#start-demo-1") is None
    assert page.inner_text('.demo-card[data-id="1"] .demo-setup-link').strip() == "Set up"
    h0, h1 = page.evaluate("""() => [0, 1].map(i => document.querySelector('#demo-grid .demo-card[data-id="' + i + '"]').getBoundingClientRect().height)""")
    assert h1 < h0, (h0, h1)


def test_running_swaps_the_state_word(page):
    page.evaluate("""() => document.querySelector('#demo-grid .demo-card[data-id="0"]').classList.add('demo-running')""")
    shown = page.evaluate("""() => [...document.querySelectorAll('#demo-grid .demo-card[data-id="0"] .demo-card-header .dx-step-state')]
      .filter(s => getComputedStyle(s).display !== 'none').map(s => s.textContent.trim())""")
    assert shown == ["Running"], shown
