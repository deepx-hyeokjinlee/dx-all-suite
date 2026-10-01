"""Demo thumbnails resolve under the module prefix inside the launcher (2026-10-02 release audit S-2).

The server returns /static/img/demo/<id>.webp; inside the launcher (/stream/) that resolved to the launcher's own
/static and every Demo Launcher card and stage preview was a broken image (404 for ids 0–11)."""
from __future__ import annotations

from pathlib import Path

JS = (Path(__file__).resolve().parents[2] / "dx_stream/static/js/stream-demo.js").read_text(encoding="utf-8")


def test_every_thumbnail_goes_through_the_module_prefix():
    assert "function _thumbUrl(u)" in JS and "DXStream._base" in JS
    assert "thumb: _thumbUrl(d.thumbnail)" in JS
    assert "_escHtml(_thumbUrl(d.thumbnail))" in JS
    assert "_escHtml(d.thumbnail)" not in JS


def test_the_pipeline_run_button_and_the_diagnostics_button_say_different_things():
    """'Run' 한 key 를 Pipeline Builder 의 실행과 Deep Diagnostics 가 같이 써서 한국어 Run 버튼이 '진단 실행' 이었다 (S-4)."""
    root = Path(__file__).resolve().parents[2]
    i18n = (root / "dx_stream/static/js/stream-i18n.js").read_text(encoding="utf-8")
    html = (root / "dx_stream/templates/index.html").read_text(encoding="utf-8")
    run = i18n[i18n.index("\n  'Run': {"):]
    assert run[:120].count("ko: '실행'") == 1
    assert "'Run diagnostics': {" in i18n
    diag_line = next(l for l in html.splitlines() if 'id="stream-diag-run-btn"' in l)
    assert 'data-i18n="Run diagnostics"' in diag_line
