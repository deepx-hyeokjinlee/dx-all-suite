"""인트로의 픽셀 축.

랜딩 baseline 은 캡처 전에 dx-splash-seen 을 심어 인트로를 건너뛴다. 그래서
72/72 초록은 "splash 이후 화면이 안 움직였다"는 뜻일 뿐, 인트로가 의도대로
그려지는지는 말해 주지 않는다. 구조 계약(tests/launcher/test_home_portal.py)이
문법을 붙잡고 있지만, 문법이 맞아도 그림은 틀릴 수 있다 — 이 세션에서 실제로
그랬다: 로고 마스크가 움직이는 레이어에 붙어 X 가 두 개로 보였고, 면이 너무
밝아 스페큘러가 묻혔고, 반사 마스크가 뒤집혀 워드마크가 하나 더 누워 있었다.
셋 다 계약은 통과한 상태였고 프레임을 봐야 보였다.

시간으로 찍지 않는다. 상태를 최종값으로 세운 뒤 animations="disabled" 로 찍어,
타이밍을 조정해도 붉어지지 않고 구도가 바뀌면 붉어지게 한다.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
pytest.importorskip("PIL")

from tests.server_helpers import start_module_server  # noqa: E402
from tests.visual.baseline_spec import (  # noqa: E402
    INTRO_STATES,
    VIEWPORT,
    intro_baseline_name,
)
from tests.visual.compare import compare  # noqa: E402
from tests.visual.test_visual_regression import (  # noqa: E402
    ARTIFACT_DIR,
    BASELINE_DIR,
    MAX_CHANGED_RATIO,
    UPDATE,
)

# 시퀀스를 재생하지 않고 한 상태로 세운다. 문구는 launcher-splash.js 의 _WORK 와
# 같아야 하므로, 어긋나면 test_home_portal 의 working-beat 계약이 먼저 잡는다.
_DRIVE = """(state) => {
  const ov = document.getElementById('splashOverlay');
  if (!ov) return false;
  // 예약된 타이머를 먼저 끈다. 안 끄면 시퀀스가 제 갈 길을 가서 is-through 를
  // 얹거나 skipSplash 로 오버레이를 걷어 버리고, 캡처에는 인트로가 아니라 홈이
  // 찍힌다 — 그런 캡처끼리는 당연히 0픽셀로 일치하므로 결정성 측정도 속는다.
  const ns = window.DXLauncher;
  if (ns && ns._splashTimers) {
    ns._splashTimers.forEach(clearTimeout);
    ns._splashTimers.length = 0;
  }
  ov.className = 'splash-overlay is-running' + (state === 'work' ? ' is-working' : '');
  if (state === 'work') {
    const cue = document.getElementById('splashCue');
    cue.setAttribute('data-beat', '1');
    cue.classList.remove('is-out');
    cue.classList.add('is-answered');
    document.getElementById('splashCueText').textContent = 'segment a video file';
    document.getElementById('splashCueAnswer').textContent = 'App';
  }
  return true;
}"""


def _capture_intro(browser, state: str, out: Path) -> None:
    server, port = start_module_server("launcher")
    try:
        # reduced_motion 은 여기서 쓰지 않는다. 인트로에는 전용 reduced-motion
        # 경로(is-still)가 있어서, 켜면 다른 디자인을 찍은 뒤 700ms 만에 걷힌다.
        # 움직임은 animations="disabled" 가 최종 상태로 고정한다.
        ctx = browser.new_context(viewport=VIEWPORT)
        page = ctx.new_page()
        try:
            page.goto(f"http://127.0.0.1:{port}/", wait_until="load", timeout=60_000)
            page.wait_for_selector("#splashOverlay", timeout=10_000)
            assert page.evaluate(_DRIVE, state), "the intro overlay never rendered"
            page.wait_for_timeout(700)
            out.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(out), animations="disabled")
        finally:
            page.close()
            ctx.close()
    finally:
        server.shutdown()


@pytest.mark.visual
@pytest.mark.parametrize("state", INTRO_STATES)
def test_intro_state_matches_baseline(visual_browser, state, tmp_path):
    engine, browser = visual_browser
    name = intro_baseline_name(state)

    baseline = BASELINE_DIR / engine / name
    if UPDATE:
        _capture_intro(browser, state, baseline)
        pytest.skip(f"baseline written: {baseline.relative_to(BASELINE_DIR.parent)}")

    if not baseline.is_file():
        pytest.skip(
            f"no baseline for {engine}/{name} — create it with "
            f"DX_VISUAL_UPDATE=1 pytest tests/visual/"
        )

    candidate = tmp_path / name
    _capture_intro(browser, state, candidate)

    diff_out = ARTIFACT_DIR / engine / f"{name[:-4]}-diff.png"
    result = compare(baseline, candidate, diff_out)

    assert result["same_size"], (
        f"{engine}/{name}: viewport changed — baseline {result['baseline_size']} "
        f"vs current {result['candidate_size']}"
    )
    assert result["changed_ratio"] <= MAX_CHANGED_RATIO, (
        f"{engine}/{name}: {result['changed_pixels']} px "
        f"({result['changed_ratio'] * 100:.4f}%) differ, limit "
        f"{MAX_CHANGED_RATIO * 100:.4f}%. Diff: {diff_out}"
    )
