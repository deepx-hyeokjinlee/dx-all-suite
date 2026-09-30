"""intro 의 첫 작업 장면 — 16채널 pull-back (spec 2026-09-30 intro stream).

교차로 한 채널이 화면을 채우고 box 가 잡힌 뒤, 카메라가 한 번 물러나며 그 화면이 4×4 wall 의 자기
칸이 된다. 나머지 15칸의 box 는 대각선 물결로 잡힌다. 여기서는 그 약속을 실제 browser 에서 본다:
box 는 bake 한 수만큼 그려지고, 물러난 화면은 자기 칸에 정확히 앉고, debug 흔적은 없다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = json.loads((ROOT / "launcher/static/img/intro/stream/detections.json").read_text(encoding="utf-8"))
TOTAL = sum(len(t["boxes"]) for t in DATA["tiles"])
_FRESH = "try{sessionStorage.removeItem('dx-splash-seen');localStorage.setItem('dx-tutorial-launcher-autostarted','1');}catch(e){}"


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


def _open(browser, port, **ctx_opts):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, **ctx_opts)
    ctx.add_init_script(_FRESH)
    page = ctx.new_page()
    page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
    return ctx, page


def test_the_first_work_beat_is_the_sixteen_channel_wall(browser, port):
    ctx, page = _open(browser, port)
    try:
        page.wait_for_selector(".intro-stream.is-on", state="visible", timeout=15000)
        assert page.evaluate("document.getElementById('splashOverlay').classList.contains('is-scene')")
        n = page.evaluate("document.querySelectorAll('.intro-stream .ist-boxes .ist-b').length")
        assert n == TOTAL, f"bake 한 box {TOTAL} 개가 다 그려져야 한다: {n}"
        text = page.evaluate("document.querySelector('.intro-stream').innerText")
        assert not re.search(r"\d\.\d\d|\b0\d\b", text), f"score · 채널 번호 같은 debug 표시: {text!r}"
        page.wait_for_function("document.getElementById('splashCueText').textContent.startsWith('16-channel')",
                               timeout=5000)
    finally:
        ctx.close()


def test_the_logo_is_gone_before_the_first_scene_comes_in(browser, port):
    """logo 가 반투명하게 남아 교차로 위에 겹쳤다 (사용자 피드백 2026-09-30) — 장면이 들어올 때는 이미 없다."""
    ctx, page = _open(browser, port)
    try:
        page.wait_for_selector(".intro-stream", state="attached", timeout=15000)
        seen = page.evaluate("""() => ['splashMark', 'splashSubtitle'].map(id =>
          parseFloat(getComputedStyle(document.getElementById(id)).opacity))""")
        assert max(seen) < 0.05, f"장면이 들어오는 순간 logo · 부제가 남아 있다: {seen}"
    finally:
        ctx.close()


def test_the_pulled_back_channel_lands_on_its_own_tile(browser, port):
    ctx, page = _open(browser, port)
    try:
        page.wait_for_selector(".intro-stream.is-rippled", state="attached", timeout=18000)
        page.wait_for_timeout(300)
        got = page.evaluate("""() => {
          const r = e => { const b = document.querySelector(e).getBoundingClientRect();
                           return [b.left, b.top, b.width, b.height]; };
          return { hero: r('.ist-hero'), slot: r('.ist-slot') };
        }""")
        for a, b in zip(got["hero"], got["slot"]):
            assert abs(a - b) <= 2, got
        answer = page.evaluate("document.getElementById('splashCueAnswer').textContent")
        assert answer.startswith("Stream") and "16" in answer and "DX-M1" in answer, answer
    finally:
        ctx.close()


def test_without_its_pictures_the_beat_is_the_prompt_alone(browser, port):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(_FRESH)
    ctx.route("**/img/intro/stream/**", lambda route: route.abort())
    page = ctx.new_page()
    try:
        page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function("document.getElementById('splashCueText').textContent.startsWith('16-channel')",
                               timeout=15000)
        assert not page.evaluate("!!document.querySelector('.intro-stream.is-on')")
    finally:
        ctx.close()


def test_reduced_motion_never_plays_the_wall(browser, port):
    ctx, page = _open(browser, port, reduced_motion="reduce")
    try:
        page.wait_for_timeout(5000)
        assert not page.evaluate("!!document.querySelector('.intro-stream.is-on')")
    finally:
        ctx.close()
