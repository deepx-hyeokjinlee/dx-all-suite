"""dx_app Run Demo 카드 (spec 2026-09-29 아이콘 체계 단계 4, 사용자 확정 2026-09-29).

예전 카드는 같은 말을 세 번 했다 — 섹션 제목 DETECTION, 썸네일 위 DETECTION 태그, 제목
"Object Detection (YOLOv7)", 그리고 고정폭 글씨의 yolov7. 모델이 없는 카드도 돌아가는 카드와 같은
높이로 가운데가 비어 있었다. 이제:
- 썸네일 위에 task 아이콘 + task 이름 한 조각, 제목은 모델 이름 (YOLOv7), 왼쪽 색 띠 없음.
- 준비 안 된 카드는 짧게: 흐린 썸네일 · "Needs setup" 표시 (Setup 단계 목록과 같은 모양) · 링크 하나.
- 결과의 ✅ ❌ ⚠️ 📊 📋 → 아이콘.
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


def _fn(src: str, head: str) -> str:
    body = src[src.index(head):]
    return body[:body.index("\n}\n")]


def test_the_head_says_the_task_once_and_titles_the_model():
    shell = _fn(JS, "function _rundemoShell(")
    assert "rd-task" in shell and "_rundemoTaskIco(d)" in shell
    assert "rd-tag" not in shell and "rd-model" not in shell
    assert "_rundemoTitle(d)" in shell


def test_not_ready_cards_are_short_with_one_link():
    body = _fn(JS, "function _rundemoNotRunnableHtml(")
    assert "dx-step-state is-todo" in body
    assert "rd-setup-link" in body and "nav('setup')" in body.replace("\\'", "'")
    assert "rd-run-ghost" not in body
    assert "is-unready" in JS
    assert ".rd-card.is-unready" in CSS


def test_cards_no_longer_carry_a_colour_stripe_or_equal_height():
    card = CSS[CSS.index(".rd-card{"):]
    card = card[:card.index("}")]
    assert "border-left:3px" not in card
    grid = CSS[CSS.index(".rundemo-grid{"):]
    assert "align-items:start" in grid[:grid.index("}")]


def test_no_emoji_in_the_cards_or_the_result():
    assert gate.count(JS) == 0, sorted({c for c in JS if gate.count(c)})
    result = INF[INF.index("window.renderInferenceError="):INF.index("function previewImg(")]
    assert gate.count(result) == 0, sorted({c for c in result if gate.count(c)})
    page = HTML[HTML.index('<div id="page-rundemo"'):]
    page = page[:page.index("</div>")]
    assert gate.count(page) == 0
