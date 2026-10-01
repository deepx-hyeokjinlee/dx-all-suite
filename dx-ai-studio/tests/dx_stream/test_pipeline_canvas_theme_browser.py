"""Pipeline Builder 캔버스 — 밝은 테마에서도 노드 이름 · 격자 · 연결선이 보인다 (release audit S-6).

예전에는 노드 이름을 흰 글자 (#f5f5f7) 로, 격자 · 연결선을 흰색 반투명으로 그렸고, 테마 색은 처음 읽은 것을 끝까지
썼다 — 밝은 테마로 바꿔도 캔버스는 어두운 색 그대로였고, 밝은 배경 위의 흰 글자는 읽을 수 없었다.
"""
from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")

from tests.server_helpers import start_module_server  # noqa: E402


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright

    srv, port = start_module_server("dx_stream")
    pw = sync_playwright().start()
    br = pw.chromium.launch(headless=True)
    ctx = br.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script("localStorage.setItem('dx-tutorial-mode','off'); localStorage.setItem('dx-theme','dark');")
    pg = ctx.new_page()
    pg.goto(f"http://127.0.0.1:{port}/", wait_until="load")
    pg.evaluate("() => DXStream.nav('pipeline')")
    pg.wait_for_function("() => DXStream._pipeState && DXStream._pipeState.elementFlat && DXStream._pipeState.elementFlat.length",
                         timeout=15000)
    yield pg
    ctx.close()
    br.close()
    pw.stop()
    srv.shutdown()


def _luma(page):
    """[캔버스 바탕의 밝기, 노드 이름 글자의 평균 밝기] (0–255). 글자 = 이름 자리에서 바탕과 40 넘게 다른 픽셀."""
    return page.evaluate("""() => {
      const st = DXStream._pipeState;
      if (!st.nodes.length) _addNode(st.elementFlat[0].name, 300, 200);
      _refreshCanvas();
      const c = document.getElementById('pipeline-canvas'), g = c.getContext('2d');
      const L = (d, i) => 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
      const bg = L(g.getImageData(3, 3, 1, 1).data, 0);
      const n = st.nodes[0];
      const x = Math.round(st.offsetX + (n.x + 26) * st.zoom), y = Math.round(st.offsetY + (n.y + 56 / 2 - 14) * st.zoom);
      const d = g.getImageData(x, y, Math.round(90 * st.zoom), Math.round(12 * st.zoom)).data;
      let sum = 0, cnt = 0;
      for (let i = 0; i < d.length; i += 4) { const l = L(d, i); if (Math.abs(l - bg) > 40) { sum += l; cnt++; } }
      return [bg, cnt ? sum / cnt : bg];
    }""")


def test_node_names_are_readable_in_both_themes(page):
    bg, text = _luma(page)
    assert bg < 80 and text > bg + 100, f"어두운 테마: 어두운 바탕 · 밝은 글자 (바탕 {bg:.0f}, 글자 {text:.0f})"
    page.evaluate("() => DXTheme.setTheme('light')")
    try:
        page.wait_for_timeout(300)
        bg, text = _luma(page)
        assert bg > 200, f"밝은 테마로 바꾸면 캔버스 바탕도 밝다 — 테마 색을 다시 읽는다 (바탕 {bg:.0f})"
        assert text < bg - 100, f"밝은 바탕 위의 이름은 어두운 글자 (바탕 {bg:.0f}, 글자 {text:.0f})"
    finally:
        page.evaluate("() => DXTheme.setTheme('dark')")
