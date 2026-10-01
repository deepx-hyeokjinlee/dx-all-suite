"""dx_app Run Demo — 공통 결과 무대 위에 (spec 2026-10-01 demo stage).

예전에는 card 마다 옵션 · Run · 결과가 들어 있어 결과를 그리면 card 가 858px 로 늘어났다
(``.rd-card`` · ``.rundemo-result`` · 결과를 좁은 card 안에 가두는 inline style). 이제 Run Demo 는
공통 component (``shared/static/dx-demo-stage.{js,css}``) 에 올라가고, 자기 옵션 · 실행 · 결과만 채운다.
화면에서의 약속은 test_rundemo_cards_browser.py.
"""
from __future__ import annotations

import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = (ROOT / "dx_app" / "static" / "js" / "rundemo.js").read_text(encoding="utf-8")
INF = (ROOT / "dx_app" / "static" / "js" / "inference.js").read_text(encoding="utf-8")
CSS = (ROOT / "dx_app" / "static" / "css" / "style.css").read_text(encoding="utf-8")
HTML = (ROOT / "dx_app" / "templates" / "index.html").read_text(encoding="utf-8")
gate = importlib.import_module("scripts.emoji_gate")


def test_run_demo_sits_on_the_shared_stage():
    assert "DXDemoStage.mount(" in JS
    assert HTML.index("/static/shared/dx-demo-stage.js") < HTML.index("/static/js/rundemo.js")
    assert "/static/shared/dx-demo-stage.css" in HTML


def test_the_old_in_card_result_is_gone():
    for old in (".rd-card", ".rundemo-result", ".rundemo-grid", ".rd-controls"):
        assert old not in CSS, old
    for old in ("rundemo-result-", "rundemo-block-", "_rundemoInjectStyle", "rundemoRunLive"):
        assert old not in JS, old


def test_the_postprocess_toggle_reaches_the_body():
    """sel.post 는 boolean 이고 rundemoBody 는 'on' 을 본다 — 예전에는 C++ 후처리가 늘 빠졌다."""
    run = JS[JS.index("function rundemoRun("):]
    run = run[:run.index("\n}\n")]
    assert "post: sel.post ? 'on' : 'off'" in run


def test_no_emoji_in_the_demo_page_or_the_result():
    assert gate.count(JS) == 0, sorted({c for c in JS if gate.count(c)})
    result = INF[INF.index("window.renderInferenceError="):INF.index("function previewImg(")]
    assert gate.count(result) == 0, sorted({c for c in result if gate.count(c)})
    page = HTML[HTML.index('<div id="page-rundemo"'):]
    page = page[:page.index("</div>")]
    assert gate.count(page) == 0
