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
