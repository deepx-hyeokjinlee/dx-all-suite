"""Fixtures for the pixel visual-regression suite.

Every screenshot gets a FRESH browser context. That is not hygiene — it is what
makes the suite deterministic: reusing a context makes the second page render a
"return visit" (splash already seen, panels remembered), which on the launcher hub
alone moved 48.8% of the pixels between two captures of the same commit.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from tests.browser_support import launch_browser, selected_engines

# dx_app 의 모델 표는 **로컬에 무엇이 설치돼 있는지** 에 따라 다르게 그려진다:
# models.js 의 `dl = !!runnable` 이 설치된 모델에만 C++/PYTHON/MODE 열을 켜고
# ACTIONS 에 Graph 버튼을 더한다. 다섯 열의 폭이 달라지며 표가 통째로 리플로우돼
# 베이스라인이 최대 22% 어긋났다 — 개발자 파일시스템을 그대로 찍고 있었던 것이다.
#
# 빈 디렉터리를 가리켜 "아무것도 설치되지 않음" 으로 고정한다. dx_monitor 에
# DX_MONITOR_SKIP_HARDWARE_INIT 을 세워 실제 하드웨어 읽기를 끄는 것과 같은 이유다.
# 이 스위트는 `pytest tests/visual/` 로 **별도 프로세스** 에서 돌므로(run_ci.sh:230)
# 여기서 환경을 세워도 다른 스위트에 새지 않는다.
# 계약: tests/dx_app/test_models_dir_is_configurable.py
_EMPTY_MODELS_DIR = tempfile.mkdtemp(prefix="dx-visual-empty-models-")
os.environ.setdefault("DX_APP_MODELS_DIR", _EMPTY_MODELS_DIR)

# Applied before any page script runs, so neither the splash nor the tutorial
# walkthrough enters the capture.
STABILISE_INIT = """
() => {
  try {
    sessionStorage.setItem('dx-splash-seen', '1');
    localStorage.setItem('dx-splash-seen', '1');
    // The launcher — and only the launcher — auto-RUNS the walkthrough on a first
    // visit (tutorial-init.js), which scrolls the page to the toggle step and
    // opens a popover over a dimmed backdrop. hideTOC() closes the table of
    // contents, not a running tour, so eight launcher baselines were photographs
    // of a dimmed footer: the hub's actual landing layout was never in frame.
    // Marking the walkthrough as already run drops the launcher onto the same
    // showTOC() path as every module, which hideTOC() does handle.
    localStorage.setItem('dx-tutorial-launcher-autostarted', '1');
  } catch (e) { /* private mode — the settle wait still covers it */ }
}
"""


@pytest.fixture(scope="session", params=selected_engines())
def visual_browser(request):
    sync_api = pytest.importorskip("playwright.sync_api")

    pw = sync_api.sync_playwright().start()
    try:
        browser = launch_browser(pw, request.param)
    except Exception as exc:  # engine not installed on this host
        pw.stop()
        pytest.skip(f"{request.param} unavailable: {type(exc).__name__}: {exc}")
    try:
        yield request.param, browser
    finally:
        browser.close()
        pw.stop()
