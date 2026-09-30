"""dx_stream Demo Launcher — 공통 결과 무대 위에 (spec 2026-10-01 demo stage).

예전: page 위의 Playback 막대 · 고정된 filter 막대 · card grid · 그 **아래** 영상 영역 (Start 를 누르면
scroll 해야 보였다). 이제 App Run Demo 와 같은 ``shared/static/dx-demo-stage.{js,css}`` 에 올라가고,
Playback · RTSP · Start 는 무대 옵션, 영상은 무대 media, filter 는 demo 의 category 에서.
화면에서의 약속은 test_demo_cards_browser.py.
"""
from __future__ import annotations

import importlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
JS = (ROOT / "dx_stream" / "static" / "js" / "stream-demo.js").read_text(encoding="utf-8")
CSS = (ROOT / "dx_stream" / "static" / "css" / "stream.css").read_text(encoding="utf-8")
HTML = (ROOT / "dx_stream" / "templates" / "index.html").read_text(encoding="utf-8")
gate = importlib.import_module("scripts.emoji_gate")


def _demo_page() -> str:
    page = HTML[HTML.index('<div class="page" id="page-demo">'):]
    return page[:page.index("<!-- ═══ PAGE: Pipeline Builder ═══ -->")]


def test_the_demo_page_sits_on_the_shared_stage():
    assert "DXDemoStage.mount(" in JS
    assert HTML.index("/static/shared/dx-demo-stage.js") < HTML.index("/static/js/stream-demo.js")
    assert "/static/shared/dx-demo-stage.css" in HTML
    page = _demo_page()
    assert 'id="demo-root"' in page
    for gone in ('id="playback-mode-bar"', 'id="demo-filter-bar"', 'id="demo-grid"', 'class="video-info-bar"'):
        assert gone not in page, gone


def test_one_video_box_is_parked_in_the_document():
    page = _demo_page()
    park = page[page.index('id="demo-video-park"'):]
    for hook in ('id="demo-video-section"', 'id="webrtc-video"', 'id="webrtc-stats-overlay"', 'id="btn-demo-fullscreen"'):
        assert hook in park, hook
    assert "_demoVideoBoxEl" in JS, "the stage detaches the box with innerHTML — keep a handle to re-attach it"


def test_the_old_card_markup_is_gone():
    for gone in ("function _renderDemoCards(", "demo-setup-link", "stop-demo-", "demo-video-title"):
        assert gone not in JS, gone
    assert "#demo-grid" not in CSS
    assert gate.count(JS) == 0, sorted({c for c in JS if gate.count(c)})
