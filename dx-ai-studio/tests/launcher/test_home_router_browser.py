"""home-router 의 행동 계약 — 실제 라우터를 브라우저에서 돌린다.

빈 페이지에 스크립트만 주입해 순수 함수를 호출한다(서버도 페이지도 없다). 그래도
sync Playwright 는 프로세스당 이벤트 루프를 하나 소유하므로 --browser 스테이지에서
격리해 돌린다. 소스만 읽는 계약은 test_home_router.py 에 남아 블로킹 게이트를 지킨다.
"""
from __future__ import annotations

import json

import pytest

from tests.launcher.home_router_support import HERO_CHIPS, ROUTER, source  # noqa: F401

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
