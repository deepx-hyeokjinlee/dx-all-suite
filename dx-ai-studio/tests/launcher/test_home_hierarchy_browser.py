"""home 첫 화면에 눈이 들어갈 입구가 하나 있어야 한다.

실측(1512×900)에서 `Build` · `Measured on DX-M1` · `Modules` 가 전부 24px/600 으로
같았다. 제목이 셋이면 주인공이 없고, 그러면 화면은 "무엇을 하는 곳인지" 를 말하지
못한다. 게다가 화면에서 가장 크고 유일하게 색을 가진 글자가 `DX-M1 · 1 device`
(28px, 초록)였다 — 성취가 아니라 사실인데 경고 세기를 쓰고 있었다.

색은 예외에 쓴다. 장치가 붙어 있는 것은 정상이므로 색이 없고, 붙어 있지 않을 때
나타난다. 같은 원칙을 앞선 작업에서 `Running` 표시에 적용했다.
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
def home(browser):
    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": 1512, "height": 900})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
        page.wait_for_timeout(3500)
        page.evaluate(_QUIET)
        page.wait_for_timeout(300)
        yield page
    finally:
        page.close(); ctx.close(); server.shutdown()


def _px(page, selector, prop="fontSize"):
    return page.evaluate(
        "([s, p]) => { const e = document.querySelector(s); if (!e) return null;"
        " const v = getComputedStyle(e)[p]; return parseFloat(v); }", [selector, prop])


# 무대 (spec 2026-09-23): hero 제목 하나와, 양옆 위젯의 제목 둘.
BUILD_H = "#homeStage .stage-title"
MEASURED_H = "#homeMeasured .stage-widget-title"
MODULES_H = "#homeDevice .stage-widget-title"


def test_build_is_the_one_heading_that_leads(home):
    build, measured, modules = (_px(home, s) for s in (BUILD_H, MEASURED_H, MODULES_H))
    assert build and measured and modules, (build, measured, modules)
    assert build > measured, f"Build {build}px 가 Measured 위젯 제목 {measured}px 보다 크지 않다"
    assert build > modules, f"Build {build}px 가 Device 위젯 제목 {modules}px 보다 크지 않다"


def test_the_two_supporting_headings_agree_with_each_other(home):
    """양옆 위젯의 제목. 둘 중 하나만 내리면 위계가 셋이 되어 다시 읽기 어려워진다."""
    assert _px(home, MEASURED_H) == _px(home, MODULES_H)


def test_the_hero_input_is_big_enough_to_be_the_hero(home):
    """히어로는 입력 요소가 아니라 그 바(.home-ask) 전체다.

    실측에서 바의 글자가 17px 였다. 제품의 문장("말로 설명하면 스튜디오가 만든다")을
    담는 자리인데 본문과 같은 크기였다.
    """
    bar = home.evaluate(
        "() => { const e = document.querySelector('.home-ask');"
        " return e ? Math.round(e.getBoundingClientRect().height) : 0; }")
    assert bar >= 56, f"히어로 바 높이가 {bar}px — 첫 화면을 이끌기에 작다"

    size = _px(home, ".ask-input")
    assert size >= 21, f"히어로 입력 글자가 {size}px — 본문과 구분되지 않는다"


def _device_colour(browser, hw):
    """hw_status 응답을 고정하고 장치 표시의 색을 읽는다.

    환경에 맡기면 이 검사가 뒤집힌다 — 테스트 하네스는 런처만 띄우므로 monitor 가
    없고, 그러면 '정상' 을 검사하려던 것이 실제로는 '미검출' 을 검사하게 된다.
    (처음에 그렇게 써서 한 번 틀렸다.)
    """
    import json

    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": 1512, "height": 900})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    try:
        def handler(route, *_):
            route.fulfill(status=200, content_type="application/json",
                          body=json.dumps(hw))

        page.route("**/dx_monitor/api/hw_status", handler)
        page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
        page.wait_for_timeout(3500)
        page.evaluate(_QUIET)
        page.wait_for_timeout(400)
        return page.evaluate(
            "() => { const e = document.getElementById('heroDeviceChip');"
            " return e ? { colour: getComputedStyle(e).color, cls: e.className,"
            "   text: e.textContent.trim(),"
            "   off: document.getElementById('homeDevice').classList.contains('is-off'),"
            "   heading: getComputedStyle(document.querySelector('"
            + BUILD_H + "')).color } : null; }")
    finally:
        page.close(); ctx.close(); server.shutdown()


def test_a_healthy_device_does_not_shout_in_colour(browser):
    """정상은 색을 쓰지 않는다. 색을 여기 써버리면 진짜 예외가 묻힌다."""
    got = _device_colour(browser, {"available": True, "count": 1,
                                   "npus": [{"id": 0, "cores": 3}]})
    assert "is-live" in got["cls"], got["cls"]
    assert got["colour"] == got["heading"], (
        f"정상 상태의 장치 표시가 제목과 다른 색이다: {got['colour']} vs {got['heading']}"
    )


def test_a_missing_device_turns_the_widget_off(browser):
    """없는 장치는 조명이 꺼진다 — 색으로 외치지 않는다 (spec 2026-09-23 §5.5).

    이 테스트의 전 판은 "없는 장치가 색을 갖는다" 였다 (f6b4192: 정상은 조용하고 예외가
    색을 갖는다). 무대에서도 예외는 드러나지만, 드러내는 수단이 색이 아니라 조명이다 —
    위젯 전체가 가라앉고 조용한 한 줄만 남는다. 정상과 구분되는 것은 그대로다.
    """
    got = _device_colour(browser, {"available": False, "count": 0})
    assert got["off"], "장치가 없는데 위젯이 켜져 있다"
    assert "is-missing" in got["cls"], got["cls"]
    assert got["text"] == "No DX-M1 connected", got["text"]
    assert got["colour"] != got["heading"], "없음이 정상과 같은 모습이다"


def test_the_agent_settings_do_not_compete_with_the_hero(home):
    """설정은 히어로 바로 아래에서 두 번째로 눈에 띌 일이 아니다.

    `Agent [copilot] Model [claude-sonnet-4.6] 29 models Effort [medium] ● not
    signed in  Sign in with copilot (first run opens GitHub device login)` 이
    파란 monospace 칩까지 달고 입력 바로 아래 있었다. 에이전트를 바꾸고 싶은
    순간은 "무엇을 만들지 생각할 때" 가 아니다 — 접어 두고 필요할 때 편다.
    """
    state = home.evaluate(
        """() => {
          const row = document.getElementById('setupForm');
          if (!row) return { missing: true };
          const box = row.closest('details');
          const sel = document.getElementById('setupModel');
          return {
            wrapped: !!box,
            open: box ? box.open : null,
            modelVisible: !!(sel && sel.offsetParent !== null),
          };
        }"""
    )
    assert not state.get("missing"), "setupForm 이 사라졌다"
    assert state["wrapped"], "설정 줄이 접히지 않는다 (details 로 감싸야 한다)"
    assert state["open"] is False, "기본이 펼쳐져 있다"
    assert not state["modelVisible"], "접혔는데 Model 셀렉트가 보인다"


def test_the_agent_settings_open_when_asked(home):
    """접는 것과 숨기는 것은 다르다 — 펼치면 나와야 한다.

    하네스에는 agent 모듈이 없어 setupForm 이 hidden 인 채로 온다. 그 상태를
    그대로 두고 '펼쳐도 안 나온다' 고 하면 환경을 재는 것이지 계약을 재는 것이
    아니므로, 모듈이 살아 있는 경우를 만들어 준다.
    """
    home.evaluate(
        """() => {
          document.getElementById('setupForm').hidden = false;
          document.getElementById('setupFold').hidden = false;
          document.getElementById('setupFold').open = true;
        }"""
    )
    home.wait_for_timeout(300)
    visible = home.evaluate(
        "() => { const s = document.getElementById('setupModel');"
        " return !!(s && s.offsetParent !== null); }")
    assert visible, "펼쳤는데 설정이 나오지 않는다"


def test_the_fold_summary_says_what_is_selected(home):
    """접혀 있어도 무엇이 골라져 있는지는 보여야 한다."""
    src = (ROOT_JS := __import__("pathlib").Path(__file__).resolve().parents[2]
           / "launcher" / "static" / "home-agent-setup.js").read_text(encoding="utf-8")
    assert "_paintFoldSummary" in src, "요약을 그리는 코드가 없다"
    assert "setupFoldValue" in src, "요약이 쓰일 자리가 없다"
    # 에이전트/모델을 바꾸면 요약이 따라가야 한다.
    assert src.count("_paintFoldSummary") >= 4, (
        "요약이 초기화 때만 그려진다 — 선택이 바뀌면 어긋난다"
    )


# ── 리듬과 rail ────────────────────────────────────────────────


def test_the_grid_is_ten_tiles_in_two_rows(home):
    """그룹 라벨 셋 (Build · Models · Measure) 은 세로 목록의 리듬이었다. 무대에서는
    도구가 칸이고, 칸의 자리가 곧 순서다 (spec 2026-09-23 §4.1): 1행 App · Stream ·
    Model Zoo · Compiler · SDK Library, 2행 Benchmark · EdgeGuide · Monitor · Agent Dev ·
    About DEEPX. 튜토리얼은 #studioGrid 와 .orbital-card 를 가리키므로 둘 다 남는다.
    """
    assert home.evaluate("() => document.querySelectorAll('#studioGrid .studio-group').length") == 0
    tiles = home.evaluate(
        "() => [...document.querySelectorAll('#studioGrid > *')].map(e =>"
        " e.dataset.app || (e.classList.contains('sdk-card') ? 'sdk' : 'about'))")
    assert tiles == ["app", "stream", "zoo", "compiler", "sdk",
                     "benchmark", "planner", "dx_monitor", "agent", "about"], tiles
    rows = home.evaluate(
        "() => new Set([...document.querySelectorAll('#studioGrid > *')]"
        ".map(e => Math.round(e.getBoundingClientRect().top))).size")
    assert rows == 2, f"1512 폭에서 {rows}줄이다"

def test_the_device_card_carries_what_the_device_is_doing(browser):
    """Running 패널을 접으면서 짧아진 rail 을, 카드가 자기 주제로 채운다.

    SDK 버전과 포트는 변하지 않는 값이다. 온도·코어는 변하고, 이미 받아오고 있다.
    """
    got = _device_colour(browser, {
        "available": True, "count": 1,
        "npus": [{"id": 0, "cores": 3, "temperatures": [41.0, 39.0, 40.0]}],
    })
    assert got is not None


def test_device_facts_show_live_values_when_a_device_is_there(browser):
    import json

    server, port = start_module_server("launcher")
    ctx = browser.new_context(viewport={"width": 1512, "height": 900})
    ctx.add_init_script(
        "try{sessionStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-splash-seen','1');"
        "localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"
    )
    page = ctx.new_page()
    hw = {"available": True, "count": 1,
          "npus": [{"id": 0, "cores": 3, "temperatures": [41.0, 39.0, 40.0]}]}
    page.route("**/dx_monitor/api/hw_status",
               lambda route, *_: route.fulfill(
                   status=200, content_type="application/json", body=json.dumps(hw)))
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60000)
        page.wait_for_timeout(3500)
        page.evaluate(_QUIET)
        page.wait_for_timeout(600)
        # 변하는 값은 코어 막대 (코어 수만큼) 와 한 줄 (온도 · clock · 전력) 이다 (spec §5.5).
        cores = page.evaluate("() => document.querySelectorAll('#homeCores .dev-core').length")
        line = page.inner_text("#homeDeviceLine")
        assert cores == 3, f"코어 3개인 장치에 막대가 {cores}개다"
        assert "41°C" in line, f"장치가 있는데 온도가 없다: {line!r}"
    finally:
        page.close(); ctx.close(); server.shutdown()
