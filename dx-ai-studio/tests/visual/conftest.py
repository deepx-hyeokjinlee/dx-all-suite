"""Fixtures for the pixel visual-regression suite.

Every screenshot gets a FRESH browser context. That is not hygiene — it is what
makes the suite deterministic: reusing a context makes the second page render a
"return visit" (splash already seen, panels remembered), which on the launcher hub
alone moved 48.8% of the pixels between two captures of the same commit.
"""
from __future__ import annotations

import pytest

from tests.browser_support import launch_browser, selected_engines

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
