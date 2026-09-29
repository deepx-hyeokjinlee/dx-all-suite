"""dx_stream 데모 카드가 DX App Run Demo 와 같은 틀인지 (spec 2026-09-29 아이콘 체계 단계 4, 사용자 확정).

예전: 머리에 #0 과 ✓/⚠ 알약, 📦 모델, 끝에 카테고리 글자, 왼쪽 색 띠, 준비 안 된 카드에도 잠긴 Start.
이제: task 한 조각 (sprite task-<key>) + 상태 (Setup 단계 목록 모양), 제목은 데모, 준비 안 된 카드는
이유 한 줄 + Setup 링크 하나.
"""
from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
JS = (ROOT / "dx_stream" / "static" / "js" / "stream-demo.js").read_text(encoding="utf-8")
CSS = (ROOT / "dx_stream" / "static" / "css" / "stream.css").read_text(encoding="utf-8")
gate = importlib.import_module("scripts.emoji_gate")


def _render_src() -> str:
    body = JS[JS.index("function _renderDemoCards("):]
    return body[:body.index("\n}\n")]


def test_the_card_head_is_task_and_state():
    src = _render_src()
    assert "demo-task" in src and "_demoTaskIco(d.category)" in src and "_demoStateHtml(" in src
    assert "dx-step-state" in JS
    for gone in ("demo-card-num", "pill-ok", "pill-warn", "demo-card-cat"):
        assert gone not in src, gone
    assert gate.count(JS) == 0, sorted({c for c in JS if gate.count(c)})


def test_not_ready_cards_have_one_link_and_no_locked_start():
    src = _render_src()
    assert "demo-setup-link demo-card-go" in src and "DXStream.nav('setup')" in src
    assert "${ready ? `<button class=\"btn btn-primary btn-sm demo-card-go\"" in src


def test_no_colour_stripe_and_short_cards_stay_short():
    card = CSS[CSS.index(".demo-card{"):]
    card = card[:card.index("}")]
    assert "border-left:4px" not in card
    assert "#demo-grid{align-items:start}" in CSS
