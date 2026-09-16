"""home 에 쓰던 문장은 모듈을 다녀와도 남아 있어야 한다.

"make baseball game" 을 치고 Agent Dev 로 갔다가 home 으로 돌아오면 입력이 비어
있었다. home 에서 나가는 길이 둘인데 하나만 파괴적이기 때문이다:

* 모듈 카드 — 셸 안에서 pushState. 문서가 그대로라 입력도 그대로다.
* 답변 패널의 라우트 / 에이전트 넘기기 — `window.location.href`. SPA 를 떠나므로
  돌아오면 새 문서다.

길을 하나로 모으고, 그와 별개로 쓰던 문장을 초안으로 보존한다. 진짜 새로고침
(F5, 링크로 직접 진입)에서도 잃지 않으려면 저장이 필요하다 — 쓰다 만 문장을
잃는 것은 작업을 잃는 것이다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

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
def launcher(browser):
    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": 1512, "height": 900})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    try:
        yield page, port
    finally:
        page.close(); ctx.close(); server.shutdown()


def _home(page, port):
    page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
    page.wait_for_timeout(3000)
    page.evaluate(_QUIET)
    page.wait_for_timeout(300)


def _ask(page):
    return page.evaluate(
        "() => { const e = document.getElementById('homeAsk'); return e ? e.value : null; }")


def test_the_sentence_survives_a_real_reload(launcher):
    """전체 이동으로 나갔다 돌아온 경우와 같은 상황이다."""
    page, port = launcher
    _home(page, port)
    page.evaluate(
        """() => { const e = document.getElementById('homeAsk');
             e.value = 'make baseball game';
             e.dispatchEvent(new Event('input', { bubbles: true })); }""")
    page.wait_for_timeout(400)

    _home(page, port)          # 새 문서
    assert _ask(page) == "make baseball game", (
        f"새로 열었더니 쓰던 문장이 사라졌다: {_ask(page)!r}"
    )


def test_sending_it_clears_the_draft(launcher):
    """보낸 문장이 다음에 또 떠 있으면 그건 남은 게 아니라 고장이다."""
    page, port = launcher
    _home(page, port)
    page.evaluate(
        """() => { const e = document.getElementById('homeAsk');
             e.value = 'pose estimation on webcam';
             e.dispatchEvent(new Event('input', { bubbles: true })); }""")
    page.wait_for_timeout(300)
    page.evaluate(
        "() => { if (window.DXLauncher && DXLauncher.homeAsk)"
        " DXLauncher.homeAsk('pose estimation on webcam'); }")
    page.wait_for_timeout(1500)

    _home(page, port)
    assert not _ask(page), f"보낸 뒤에도 초안이 남았다: {_ask(page)!r}"


def test_leaving_home_keeps_the_shell(launcher):
    """답변 패널에서 나가는 길도 셸 안이어야 한다 — 모듈 카드와 같게."""
    src = (__import__("pathlib").Path(__file__).resolve().parents[2]
           / "launcher" / "static" / "home-answer.js").read_text(encoding="utf-8")
    assert "_leaveHome" in src, "나가는 길이 한 곳으로 모이지 않았다"
    # location.href 로 직접 나가는 자리가 남아 있으면 그쪽으로 새어 나간다.
    body = src[src.index("function _leaveHome"):]
    body = body[: body.index("\n  }")]
    assert "loadAppIframeIfNeeded" in body or "pushState" in body, (
        "셸 안 이동을 시도하지 않는다"
    )
