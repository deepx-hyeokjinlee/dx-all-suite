"""dx_app Run Demo 카드가 화면에서 약속대로 보이는지 (spec 2026-09-29 아이콘 체계 단계 4).

/api/demos 는 fixture 로 고정한다 — 이 PC 에 모델이 설치됐는지와 무관하게.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402

READY = {"cpp_sync": True, "cpp_async": True, "py_sync": True, "py_async": True,
         "py_sync_cpp_postprocess": False, "py_async_cpp_postprocess": False, "model_exists": True}
MISSING = {k: False for k in READY}


def _demo(idx, label, group, cat, name, avail):
    return {"idx": idx, "label": label, "group": group, "model": f"{name}.dxnn", "category": cat,
            "model_name": name, "py_base": name, "cpp_base": name, "default_video": "assets/videos/boat.mp4",
            "default_image": "sample/img/sample_street.jpg", "async_full": True, "image_only": False,
            "avail": dict(avail), "run_ref": {"model_name": name, "category": cat, "model_file": f"{name}.dxnn"},
            "thumbnail": f"/api/demo-thumb?f={name}.jpg"}


DEMOS = [
    _demo(0, "Object Detection         (YOLOv7)", "Detection", "object_detection", "yolov7", READY),
    _demo(1, "Face Detection           (SCRFD500M)", "Detection", "face_detection", "scrfd500m", MISSING),
    _demo(2, "Object Detection + Semantic Segmentation (YOLOv7 + BiSeNet)", "Segmentation",
          "object_detection_x_semantic_segmentation", "yolov7_bisenet", MISSING),
]


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright

    srv, port = start_module_server("dx_app")
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script("localStorage.setItem('dx-tutorial-mode','off');")
    pg = ctx.new_page()
    pg.route("**/api/demos", lambda route, *_: route.fulfill(
        status=200, content_type="application/json",
        body=json.dumps({"ok": True, "demos": DEMOS, "groups": ["Detection", "Segmentation"]})))
    pg.goto(f"http://127.0.0.1:{port}/", wait_until="load")
    pg.evaluate("() => nav('rundemo')")
    pg.wait_for_selector("#rundemo-block-2", timeout=10000)
    yield pg
    ctx.close()
    br.close()
    pw.stop()
    srv.shutdown()


def _task(page, idx):
    return page.evaluate(f"""() => {{ const t = document.querySelector('#rundemo-block-{idx} .rd-task');
      return [t.querySelector('use').getAttribute('href').split('#')[1], t.textContent.trim()]; }}""")


def test_the_head_names_the_task_once_and_titles_the_model(page):
    assert _task(page, 0) == ["task-object_detection", "Object Detection"]
    assert page.inner_text("#rundemo-block-0 .rd-title").strip() == "YOLOv7"
    assert page.query_selector("#rundemo-block-0 .rd-model") is None
    assert page.query_selector("#rundemo-block-0 .rd-tag") is None


def test_a_combined_task_uses_its_first_task_icon(page):
    assert _task(page, 2)[0] == "task-object_detection"
    assert page.inner_text("#rundemo-block-2 .rd-title").strip() == "YOLOv7 + BiSeNet"


def test_a_ready_card_keeps_its_controls_and_run(page):
    assert page.is_visible('#rundemo-block-0 button[onclick*="rundemoRun"]')
    assert page.is_visible('#rundemo-block-0 [data-axis-row="code"]')


def test_a_not_ready_card_is_short_with_one_link(page):
    assert "is-unready" in page.get_attribute("#rundemo-block-1", "class")
    assert page.inner_text("#rundemo-block-1 .dx-step-state").strip() == "Needs setup"
    assert page.inner_text("#rundemo-block-1 .rd-setup-link").strip() == "Demo Quick Start"
    ready, unready = page.evaluate("""() => [0, 1].map(i => document.getElementById('rundemo-block-' + i).getBoundingClientRect().height)""")
    assert unready < ready * 0.75, (ready, unready)
    page.click("#rundemo-block-1 .rd-setup-link")
    page.wait_for_function("() => document.getElementById('page-setup').classList.contains('active')", timeout=5000)
    page.evaluate("() => nav('rundemo')")


def test_the_result_marks_are_icons(page):
    out = page.evaluate("""() => { const el = document.createElement('div'); document.body.appendChild(el);
      window.renderInferenceResult(el, { _cat: 'object_detection', exit_code: 1, fps: 30, output: 'log' });
      return [...el.querySelectorAll('svg.res-mark use')].map(u => u.getAttribute('href').split('#')[1]); }""")
    assert out == ["x", "alert", "file"], out


def test_the_task_name_follows_the_language_without_redrawing(page):
    page.evaluate("() => { document.getElementById('rundemo-block-0').dataset.probe = '1'; DXI18n.setLang('ko'); }")
    page.wait_for_timeout(300)
    try:
        assert page.inner_text("#rundemo-block-0 .rd-task").strip() == "객체 탐지"
        assert page.get_attribute("#rundemo-block-0", "data-probe") == "1", "카드를 다시 그렸다 (고른 설정 · 결과가 사라진다)"
    finally:
        page.evaluate("() => DXI18n.setLang('en')")
