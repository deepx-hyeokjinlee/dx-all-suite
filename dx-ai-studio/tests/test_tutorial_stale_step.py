"""스텝이 교체되면 이전 스텝의 시각물이 남아 있으면 안 된다.

`_showStep()` 은 타깃이 안 보이면 최대 2초(20×100ms) 폴링한다. 그 사이 사용자가
Next 를 누르면 `_stepToken` 가드가 걸려 아무것도 렌더하지 않고 빠져나간다. 그
동안 화면에는 **이전 스텝의 스포트라이트와 툴팁**이 그대로 남는다 — 사용자는
이미 지나간 스텝의 상자를 보고 있고, 툴팁 내용도 앞 스텝의 것이다.

그 상태가 튜토리얼 e2e 게이트에서는 `TARGET_MISSING` 으로 보고됐다. 셀렉터가
썩어서가 아니라(측정한 셀렉터는 처음부터 0개였다) 엔진이 아직 그것을 찾는
중이었기 때문이다. instrumented run 으로 확인했다: 문제 스텝은 전부
"렌더된 적 없음" 이었고 직전 렌더는 바로 앞 스텝이었다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    yield br
    br.close()
    pw.stop()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    try:
        yield pg
    finally:
        pg.close()
        ctx.close()

TARGETLESS_STEP = """() => {
  const e = window._dxTutorial;
  const probe = {
    id: 'probe',
    title: { en: 'Probe' },
    steps: [
      { target: '#dxToolbar', title: { en: 'one' }, content: { en: 'anchored step' } },
      { target: '#definitely-not-here-xyz', title: { en: 'two' }, content: { en: 'missing target' } },
    ],
  };
  // startSection() 이 _buildDOM() 을 부르므로 정식 경로로 들어간다.
  e.sections = [probe];
  e._sections = [probe];
  return e.startSection('probe');
}"""


def _state(page):
    return page.evaluate(
        """() => {
      const sp = document.querySelector('.dxt-spotlight');
      const tip = document.querySelector('.dxt-tooltip');
      return {
        spotlightActive: !!(sp && sp.classList.contains('active')),
        tooltipText: tip ? tip.innerText : '',
        floating: !!(tip && tip.getAttribute('data-dxt-floating')),
      };
    }"""
    )


def test_no_stale_spotlight_while_polling_for_a_missing_target(page):
    server, port = start_module_server("dx_modelzoo")
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function("() => window._dxTutorial", timeout=20000)
        page.evaluate(TARGETLESS_STEP)
        page.wait_for_timeout(400)

        first = _state(page)
        assert first["spotlightActive"], "앵커된 첫 스텝이 스포트라이트를 걸어야 한다"
        assert "anchored step" in first["tooltipText"]

        # 타깃이 없는 다음 스텝으로 — 엔진은 이제 폴링에 들어간다.
        page.evaluate("() => window._dxTutorial.next()")
        page.wait_for_timeout(300)  # 폴링(2초)이 끝나기 한참 전

        during = _state(page)
        assert not during["spotlightActive"], (
            "폴링 중 이전 스텝의 스포트라이트가 남아 있다 — 사용자는 지나간 스텝의 상자를 본다"
        )
        assert "anchored step" not in during["tooltipText"], (
            "폴링 중 툴팁이 아직 이전 스텝 내용이다"
        )
        assert "missing target" in during["tooltipText"], (
            "새 스텝의 내용이 즉시 보여야 한다"
        )
    finally:
        server.shutdown()


def test_anchored_steps_are_unaffected(page):
    """첫 조회에 성공하는 스텝은 지금 경로 그대로여야 한다 (툴팁 깜빡임 없음)."""
    server, port = start_module_server("dx_modelzoo")
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function("() => window._dxTutorial", timeout=20000)
        page.evaluate(TARGETLESS_STEP)
        page.wait_for_timeout(400)
        st = _state(page)
        assert st["spotlightActive"]
        assert not st["floating"], "타깃이 있는 스텝이 floating 으로 떨어졌다"
    finally:
        server.shutdown()
