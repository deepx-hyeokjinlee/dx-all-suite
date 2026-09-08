"""The hero prompt is a router, not a generator.

An agent run takes minutes. A spinner on a front door is the wrong first
impression, so the input never starts one directly: it reads the sentence with
keyword matching over material the studio already serves — the model catalogue
and the twelve stream demos — and answers within a frame.

These are pure-function contracts. `home-router.js` takes a string and returns
routes; no DOM and no fetch at parse time, so it runs in a blank page with no
server behind it.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "launcher" / "static" / "home-router.js"

# The four chips the hero ships with. If one of these resolves to nothing, the
# chip is wrong — a suggestion the product cannot honour is worse than none.
HERO_CHIPS = (
    "compile yolo26n to DXNN",
    "pose estimation on webcam",
    "4-channel CCTV object detection",
    "segment a video file",
)


def source() -> str:
    assert ROUTER.is_file(), "launcher/static/home-router.js is missing"
    return ROUTER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def route():
    """Run the real router in a browser, with no server and no page.

    The studio ships no bundler and no JS test runner, and adding an embedded
    engine just for this would be a dependency the product does not otherwise
    need. Playwright is already here, and a pure function needs nothing but a
    blank page to run in — about two seconds for the whole module.
    """
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright

    from tests.browser_support import launch_browser

    pw = sync_playwright().start()
    try:
        browser = launch_browser(pw, "chromium")
    except Exception as exc:  # engine not installed on this host
        pw.stop()
        pytest.skip(f"chromium unavailable: {type(exc).__name__}: {exc}")
    page = browser.new_page()
    page.add_script_tag(content=source())

    def _call(text, catalog=None, demos=None):
        return page.evaluate(
            "([t, c, d]) => JSON.stringify(window.DXHomeRouter.resolve(t, c, d))",
            [text, catalog or [], demos or []],
        )

    yield _call
    page.close()
    browser.close()
    pw.stop()


# ── static contracts (always run) ───────────────────────────────


def test_router_exposes_one_pure_entry_point():
    src = source()
    assert "DXHomeRouter" in src, "the router must be reachable as window.DXHomeRouter"
    assert "function resolve" in src, "resolve(text, catalog, demos) is the entry point"


def test_router_does_not_fetch_while_parsing():
    """Parsing must cost nothing. Data is passed in, not fetched per keystroke."""
    src = source()
    body = src[src.index("function resolve") :]
    body = body[: body.index("\n  }")] if "\n  }" in body else body
    assert "fetch(" not in body, "resolve() must not reach the network"


def test_every_hero_chip_has_a_term_the_router_knows():
    """The chips are the router's published vocabulary.

    Checked against the term tables in the source so this holds with or without
    a JS engine on the host.
    """
    src = source()
    missing = []
    for chip in HERO_CHIPS:
        words = re.findall(r"[a-z0-9]+", chip.lower())
        if not any(f"'{w}'" in src or f'"{w}"' in src for w in words):
            missing.append(chip)
    assert not missing, f"hero chips the router has no term for: {missing}"


def test_router_knows_the_studio_vocabulary():
    src = source().lower()
    for term in ("detection", "pose", "segment", "compile", "face"):
        assert f"'{term}" in src or f'"{term}' in src, f"router has no term for {term!r}"


# ── behavioural contracts (run the real router in a browser) ────

CATALOG = [
    {"id": "yolo26n", "name": "YOLOv26n", "task": "object_detection"},
    {"id": "yolo26n_pose", "name": "YOLOv26n_Pose", "task": "pose_estimation"},
]
DEMOS = [
    {"id": 0, "name_en": "Object Detection", "category": "object_detection"},
    {"id": 4, "name_en": "Pose Estimation", "category": "pose_estimation"},
    {"id": 6, "name_en": "Semantic Segmentation", "category": "segmentation"},
]


def test_it_reads_task_channels_and_target(route):
    got = json.loads(route("4-channel CCTV, detect people, 30 FPS", CATALOG, DEMOS))
    assert got["parsed"]["task"] == "object_detection"
    assert got["parsed"]["channels"] == 4
    assert got["parsed"]["fps"] == 30
    assert got["routes"], "a matched sentence must offer somewhere to go"


def test_a_model_name_resolves_that_model(route):
    got = json.loads(route("run yolo26n_pose", CATALOG, DEMOS))
    assert any(r.get("model") == "YOLOv26n_Pose" for r in got["routes"])


def test_compile_routes_to_the_compiler(route):
    got = json.loads(route("compile yolo26n to DXNN", CATALOG, DEMOS))
    assert any(r.get("module") == "compiler" for r in got["routes"])


def test_a_sentence_about_nothing_we_ship_returns_no_routes(route):
    """An unmatched sentence is the agent's cue, not a bad guess."""
    got = json.loads(route("write me a haiku about the weather", CATALOG, DEMOS))
    assert got["routes"] == []
    assert got["parsed"]["task"] is None


def test_understanding_the_task_is_not_the_same_as_having_a_preset(route):
    """"Count push-ups" is pose estimation — we should say so.

    What we do not have is something to run. Reading the task and offering a
    route are separate answers, and conflating them is how a router starts
    guessing: the agent is the escalation, and it earns that by there being no
    preset, not by us failing to understand the sentence.
    """
    no_pose_demo = [d for d in DEMOS if d["category"] != "pose_estimation"]
    got = json.loads(
        route("count push-ups from a webcam and shout the number", CATALOG, no_pose_demo)
    )
    assert got["parsed"]["task"] == "pose_estimation", "we do understand it"
    assert got["parsed"]["source"] == "webcam"
    assert not [r for r in got["routes"] if r["kind"] == "run"], (
        "nothing to run means no run route — that is the agent's opening"
    )


@pytest.mark.parametrize("chip", HERO_CHIPS)
def test_each_hero_chip_resolves(route, chip):
    got = json.loads(route(chip, CATALOG, DEMOS))
    assert got["routes"], f"the hero offers {chip!r} and the router cannot honour it"
