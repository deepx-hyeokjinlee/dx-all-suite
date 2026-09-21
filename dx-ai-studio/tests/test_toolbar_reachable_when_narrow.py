"""좁은 화면(= 높은 브라우저 줌)에서 툴바 버튼에 **닿을 수 있어야** 한다.

줌 감사의 사각지대를 조사하다 찾았다(2026-09-21). 그 감사는 문서 전체의 가로
넘침(`documentElement.scrollWidth - clientWidth`) 하나만 본다. 그래서 이런 것을
못 본다:

    vw=512
      .dx-shell-header       505/456  <- 49px 넘친다
      .dx-shell-body         overflow-x: hidden   <- 잘라낸다
      => 문서 넘침은 0. 게이트는 통과한다.
      => .dx-toolbar 가 l=366 r=561 로 화면(512) 밖으로 밀려
         '◑'(테마)와 '⚙️'(설정) 두 버튼이 사라진다.

`.dx-toolbar` 자체는 `overflow-x: auto` 를 갖고 있지만 그것은 툴바 **안쪽**
스크롤이다. 툴바 내용(195px)이 툴바 폭(195px)과 같아 스크롤할 것이 없고,
잘리는 것은 툴바 **전체** 다. 안쪽 스크롤은 바깥쪽 잘림을 구해 주지 못한다.

처음엔 `body.style.zoom` 으로 재서 `.dx-tab-overflow`("+2")도 닿지 않는 것처럼
보였다. **그것은 측정 착시였다** — style.zoom 은 resize 를 일으키지 않아 탭
오버플로 계산이 갱신되지 않는다. 실제 줌에 해당하는 좁은 뷰포트로 다시 재니
탭은 정상이고 툴바만 남았다. 착시와 진짜를 가르는 데 이 재측정이 필요했다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import sync_playwright  # noqa: E402

from tests.browser_support import launch_browser  # noqa: E402
from tests.server_helpers import start_module_server  # noqa: E402

# 1024 = 기본, 683 ≈ 150% 줌, 512 ≈ 200% 줌 (같은 물리 화면에서 CSS 폭이 줄어든다)
WIDTHS = (1024, 683, 512)

_UNREACHABLE_JS = """() => {
  const de = document.documentElement, vw = de.clientWidth;
  const out = [];
  for (const el of document.querySelectorAll('.dx-toolbar-btn, .dx-tab, .dx-tab-overflow')) {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if ((r.width === 0 && r.height === 0) || cs.display === 'none' || cs.visibility === 'hidden') continue;
    if (r.right <= vw + 2 && r.left >= -2) continue;
    // 스크롤 가능한 조상이 있으면 사용자가 스크롤해서 닿을 수 있다 — 결함이 아니다.
    let p = el.parentElement, reachable = false;
    while (p && p !== document.body) {
      const pcs = getComputedStyle(p);
      if (/(auto|scroll)/.test(pcs.overflowX) && p.scrollWidth > p.clientWidth + 2) { reachable = true; break; }
      p = p.parentElement;
    }
    if (!reachable) out.push(((el.textContent || '').trim().slice(0, 12)) + ' @' + Math.round(r.right));
  }
  return out;
}"""


# 셸(dx-shell.css)은 여덟 모듈이 공유한다. dx_app 에서 찾았지만 원인이 공유
# 스타일이므로 나머지도 같이 본다 — 한 곳만 고치고 넘어가면 다음에 다른 모듈에서
# 같은 제보가 온다.
MODULES = ("dx_app", "dx_compiler", "dx_modelzoo", "dx_benchmark",
           "dx_stream", "dx_planner", "dx_monitor", "dx_agent_dev")


@pytest.mark.parametrize("width", WIDTHS)
def test_no_toolbar_control_is_pushed_out_of_reach(width: int):
    server, port = start_module_server("dx_app")
    try:
        with sync_playwright() as p:
            browser = launch_browser(p, "chromium")
            ctx = browser.new_context(viewport={"width": width, "height": 768})
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            unreachable = page.evaluate(_UNREACHABLE_JS)
            ctx.close()
            browser.close()
    finally:
        server.shutdown()
    assert not unreachable, (
        f"{width}px 에서 스크롤로도 닿을 수 없는 컨트롤: {unreachable}\n"
        "문서 가로 넘침은 0 이라 줌 감사는 이것을 보지 못한다 — "
        "조상의 overflow-x:hidden 이 잘라내기 때문이다."
    )


@pytest.mark.parametrize("module", MODULES)
def test_every_module_shell_survives_the_narrowest_width(module: str):
    """가장 좁은 폭에서만 본다 — 여기서 통과하면 넓은 폭은 따라온다.

    여덟 모듈 × 세 폭을 다 돌면 24번 브라우저를 띄워야 해서 느리다. 폭은
    위 테스트가 dx_app 으로 덮고, 여기서는 **모듈 간 차이** 만 본다.
    """
    server, port = start_module_server(module)
    try:
        with sync_playwright() as p:
            browser = launch_browser(p, "chromium")
            ctx = browser.new_context(viewport={"width": min(WIDTHS), "height": 768})
            page = ctx.new_page()
            page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
            page.wait_for_timeout(2500)
            unreachable = page.evaluate(_UNREACHABLE_JS)
            ctx.close()
            browser.close()
    finally:
        server.shutdown()
    assert not unreachable, f"{module} @ {min(WIDTHS)}px: 닿을 수 없는 컨트롤 {unreachable}"
