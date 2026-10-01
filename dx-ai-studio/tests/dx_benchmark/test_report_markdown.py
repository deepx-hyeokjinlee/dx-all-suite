"""Run reports render with the shared Markdown renderer, tables included (2026-10-02 release audit B-1).

dx_benchmark shipped a 748-byte "minimal fallback" under the name vendor/marked.min.js; it turned a GFM table into
bare <tr> rows inside a <p>, so every REPORT.md table read as run-on text in Results.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_results_use_the_shared_renderer():
    html = (ROOT / "dx_benchmark/templates/index.html").read_text(encoding="utf-8")
    js = (ROOT / "dx_benchmark/static/js/results.js").read_text(encoding="utf-8")
    assert '<script src="/static/shared/markdown_render.js"></script>' in html
    assert "marked.min.js" not in html and "marked.parse" not in js
    assert "DXMarkdownRender.render(report.markdown)" in js
    assert not (ROOT / "dx_benchmark/static/js/vendor/marked.min.js").exists()
