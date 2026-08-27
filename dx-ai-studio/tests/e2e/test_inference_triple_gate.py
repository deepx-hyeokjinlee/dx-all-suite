"""Inference E2E triple gate — SR-586 / SR-678.

One real browser journey (nav -> pick model -> pick image -> click Run) asserted
on three independent layers, so a regression in any one of them fails the gate:

  1. NETWORK  the POST /api/run response is HTTP 200 and carries no ``error``
  2. RENDER   the annotated result actually paints — ``img.res-img`` is visible
              and has decoded pixels (``naturalWidth > 0``), not a broken <img>
  3. METRICS  the FPS / Latency perf cards show finite, in-range numbers

Two tiers share this body:

  ``e2e_mock``  fixture DX_APP_ROOT + shell fake runner. Deterministic, no NPU,
                seconds. This is the tier that blocks a PR.
  ``e2e_npu``   the real dx-runtime tree and a real ``.dxnn`` on the DX-M1.
                Opt-in (``DX_E2E_NPU_MODEL``), for nightly / the ``run-npu`` label.

Only the NPU binary differs between tiers — the studio server, the perf parser,
the result-image pipeline and the browser assertions are identical, so the mock
tier genuinely exercises the production path rather than a stub of it.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from playwright.sync_api import expect  # noqa: E402

from tests.e2e import fake_app_root as F  # noqa: E402

# Guards against a fake runner that reports a nonsense rate (e.g. a parser that
# silently returns 0, or a units slip that turns 92.6 FPS into 92600).
FPS_MIN, FPS_MAX = 0.1, 100_000.0

# renderInferenceResult() emits either a comparison slider or a plain result <img>.
RESULT_IMG_SELECTOR = "#r-result .cmp-after-clip img, #r-result img.res-img"

# The fake runner returns in ~1s, so the happy path finishes in ~5s. Keep the
# mock budget tight: it is what a BROKEN render costs the PR gate, and 180s of
# waiting to be told the image never painted is 175s of wasted CI.
MOCK_RUN_TIMEOUT_MS = 60_000
# Real NPU inference (and video input) legitimately takes far longer.
NPU_RUN_TIMEOUT_MS = 300_000


def _dismiss_tutorial(page):
    """Close Tutorial Mode, which blocks every click until dismissed.

    On a fresh profile the shared tutorial engine opens its table of contents
    ASYNCHRONOUSLY, roughly 1-3s after load. Its backdrop is a full-viewport
    layer at z-index 99997, so Playwright reports "<div class=dxt-toc-backdrop
    open> intercepts pointer events" on any click.

    Dismissing immediately after `load` is a race we lose (nothing is open yet,
    the assertion passes, and the TOC opens a moment later). So: wait for it to
    open, then close it through the engine's own hideTOC(). If it never opens
    (Tutorial Mode off in this profile) there is simply nothing to dismiss.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    try:
        page.wait_for_selector(".dxt-toc-backdrop.open", timeout=15_000)
    except PWTimeout:
        return
    page.evaluate(
        "() => { const t = window._dxTutorial;"
        " if (t && t.hideTOC) { try { t.hideTOC(); } catch (e) {} } }"
    )
    expect(page.locator(".dxt-toc-backdrop.open")).to_have_count(0, timeout=15_000)


def _open_run_tab(page, base_url):
    page.goto(base_url, wait_until="load", timeout=60_000)
    _dismiss_tutorial(page)
    page.click('.nav-item[data-page="run"]')
    expect(page.locator("#r-run-btn")).to_be_visible(timeout=30_000)


def _first_option(page, select_id: str) -> str:
    page.wait_for_function(
        "id => { const s = document.getElementById(id);"
        " return s && [...s.options].some(o => o.value); }",
        arg=select_id,
        timeout=30_000,
    )
    return page.evaluate(
        "id => [...document.getElementById(id).options].map(o => o.value).find(v => v)",
        select_id,
    )


def _select_model(page) -> str:
    """Walk the real dependency chain: #r-cat drives onRCat(), which populates
    #r-model AND loads the sample-image grid. Selecting #r-model directly would
    find an empty <select>."""
    category = _first_option(page, "r-cat")
    page.select_option("#r-cat", category)

    value = _first_option(page, "r-model")
    page.select_option("#r-model", value)
    return value


def _select_image(page):
    """Click a sample-image tile so doRun() has an input path."""
    tiles = page.locator("#r-imgs .img-item, .img-item")
    expect(tiles.first).to_be_visible(timeout=30_000)
    tiles.first.click()


def _to_number(text: str) -> float:
    """Pull the numeric part out of a perf-card value (e.g. '6.35ms' -> 6.35)."""
    import re

    m = re.search(r"[-+]?\d*\.?\d+", (text or "").replace(",", ""))
    assert m, f"no number in perf card value: {text!r}"
    return float(m.group())


def _run_triple_gate(page, base_url, *, run_timeout_ms: int):
    _open_run_tab(page, base_url)
    model = _select_model(page)
    _select_image(page)

    # ---- layer 1: network ------------------------------------------------
    # The UI prefers the non-blocking POST /api/run_async (-> {job_id}) and then
    # polls /api/run_result, falling back to the blocking POST /api/run. Collect
    # every /api/run* response so the gate covers whichever path the UI took.
    seen: list[tuple[str, int, dict]] = []

    def _capture(response):
        if "/api/run" not in response.url:
            return
        try:
            seen.append((response.url, response.status, response.json()))
        except Exception:  # non-JSON (e.g. a streamed frame) — not a result carrier
            pass

    page.on("response", _capture)
    try:
        with page.expect_response(
            lambda r: r.request.method == "POST" and "/api/run" in r.url,
            timeout=run_timeout_ms,
        ) as caught:
            page.click("#r-run-btn")
        start_response = caught.value
        assert start_response.status == 200, (
            f"{start_response.url} returned HTTP {start_response.status} for model {model!r}"
        )

        # The terminal payload is whichever response carries exit_code — the
        # blocking /api/run body, or the polled /api/run_result body.
        page.wait_for_function(
            "sel => { const i = document.querySelector(sel);"
            " return i && i.complete && i.naturalWidth > 0; }",
            arg=RESULT_IMG_SELECTOR,
            timeout=run_timeout_ms,
        )
    finally:
        page.remove_listener("response", _capture)

    bad_status = [(u, st) for u, st, _ in seen if st != 200]
    assert not bad_status, f"non-200 responses on the run path: {bad_status}"

    finals = [body for _, _, body in seen if "exit_code" in body]
    assert finals, (
        "no /api/run* response carried a final result payload; saw: "
        + str([(u, sorted(b)[:6]) for u, _, b in seen])
    )
    payload = finals[-1]
    assert not payload.get("error"), f"run reported an error: {payload.get('error')}"
    assert payload.get("exit_code") == 0, f"runner exit_code={payload.get('exit_code')}"

    # ---- layer 2: render --------------------------------------------------
    # renderInferenceResult() has two shapes: with a "before" image (a sample was
    # picked) it draws a comparison slider and the result lives in
    # .cmp-after-clip img; otherwise it emits a plain img.res-img. Accept either,
    # so the gate does not silently pass just because the layout changed.
    result_img = page.locator(RESULT_IMG_SELECTOR).first
    expect(result_img).to_be_visible(timeout=run_timeout_ms)
    # Visibility only proves layout. naturalWidth proves the browser actually
    # DECODED the base64 payload — a corrupt src stays "visible" but is 0 wide.
    dims = page.evaluate(
        "sel => { const i = document.querySelector(sel);"
        " return [i.naturalWidth, i.naturalHeight]; }",
        RESULT_IMG_SELECTOR,
    )
    assert dims[0] > 0 and dims[1] > 0, f"result image has no decoded pixels: {dims}"
    assert page.evaluate(
        "sel => document.querySelector(sel).src.startsWith('data:image/jpeg;base64,')",
        RESULT_IMG_SELECTOR,
    ), "result image is not an inline base64 JPEG"

    # ---- layer 3: metrics -------------------------------------------------
    def _card_value(label: str):
        return page.evaluate(
            "lbl => { const c = [...document.querySelectorAll('#r-result .pcard')]"
            ".find(e => (e.querySelector('.pk')?.textContent || '').includes(lbl));"
            " return c ? c.querySelector('.pv').textContent : null; }",
            label,
        )

    fps_text = _card_value("FPS")
    assert fps_text, "no FPS perf card rendered"
    fps = _to_number(fps_text)
    assert FPS_MIN < fps < FPS_MAX, f"FPS out of range: {fps} (raw {fps_text!r})"

    latency_text = _card_value("Latency")
    assert latency_text, "no Latency perf card rendered"
    latency = _to_number(latency_text)
    assert latency > 0, f"latency must be positive, got {latency} (raw {latency_text!r})"

    return {"model": model, "fps": fps, "latency": latency, "payload": payload}


@pytest.mark.e2e
@pytest.mark.e2e_mock
def test_inference_triple_gate_mock(page, dx_app_server):
    """Blocking PR gate: full UI -> API -> render -> metrics against the fake runner."""
    got = _run_triple_gate(page, dx_app_server, run_timeout_ms=MOCK_RUN_TIMEOUT_MS)

    # The mock tier is deterministic, so pin the exact numbers the fake runner
    # emitted. This is what proves the real _parse_perf ran instead of the test
    # reading back its own fixture constants.
    assert got["fps"] == pytest.approx(F.EXPECTED_FPS), got["fps"]
    assert got["latency"] == pytest.approx(F.EXPECTED_LATENCY_MS), got["latency"]
    assert got["model"] == F.MODEL_NAME


@pytest.mark.e2e
@pytest.mark.e2e_npu
@pytest.mark.requires_dx_runtime
def test_inference_triple_gate_npu(page, dx_app_server):
    """Nightly / run-npu tier: identical assertions against real NPU inference.

    Opt-in: set DX_E2E_NPU_MODEL to a model name present in the REAL dx_app tree
    and run with DX_APP_ROOT unset (or pointed at dx-runtime/dx_app).
    """
    import os

    if not os.environ.get("DX_E2E_NPU_MODEL"):
        pytest.skip("DX_E2E_NPU_MODEL not set — real-NPU tier is opt-in")
    if not os.path.exists("/dev/dxrt0"):
        pytest.skip("no NPU device node (/dev/dxrt0)")

    got = _run_triple_gate(page, dx_app_server, run_timeout_ms=NPU_RUN_TIMEOUT_MS)
    # No exact pinning here — real throughput varies per host and thermal state.
    assert got["fps"] > FPS_MIN
    assert got["latency"] > 0
