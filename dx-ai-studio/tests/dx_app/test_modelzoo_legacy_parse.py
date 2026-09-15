"""legacy 테이블 분기가 자체 HTML 파서의 문법을 지켜야 한다.

`_parse_models()` 는 20칼럼(Q-Lite/Q-Pro 그룹 헤더) 레이아웃을 먼저 찾고, 아니면
"`.dxnn` 링크가 든 표" 라는 느슨한 legacy 분기로 떨어진다. 그 분기가
`find_all("a", href=True)` 로 쓰여 있었다 — BeautifulSoup 문법이다.

`dx_app/core/_html_dom.py` 의 Node.find_all 은 `find_all(self, names)` 다.
같은 파일의 `find(name, href=False)` 는 href 를 받으므로 호출부가 find_all 도
그럴 것이라 가정했고, 그래서 이 분기에 닿는 순간 TypeError 로 500 이 났다.
공개 페이지가 인라인 JSON 으로 리팩토링되면서 20칼럼 판정이 실패하게 되자
실제로 닿았다.
"""
from __future__ import annotations

import pytest

LEGACY_HTML = """
<html><body>
<h2>Object Detection</h2>
<table>
  <tr><th>Model</th><th>Download</th></tr>
  <tr>
    <td>yolov5s</td>
    <td>
      <a href="https://sdk.deepx.ai/modelzoo/yolov5s_512.dxnn">dxnn</a>
      <a href="https://sdk.deepx.ai/modelzoo/yolov5s_512.json">json</a>
    </td>
  </tr>
</table>
</body></html>
"""


def _parse():
    from dx_app.core.modelzoo import _parse_models

    return _parse_models(LEGACY_HTML)


def test_legacy_table_parses_without_raising():
    """이 호출이 TypeError 를 내면 SETUP 페이지가 500 을 돌려준다."""
    try:
        models = _parse()
    except TypeError as exc:  # pragma: no cover - 회귀했을 때만 도달
        pytest.fail(f"legacy 분기가 자체 파서 문법을 어겼다: {exc}")
    assert models, "legacy 레이아웃에서 한 건도 못 읽었다"


def test_legacy_table_picks_up_both_urls():
    models = _parse()
    assert len(models) == 1
    model = models[0]
    assert model["name"] == "yolov5s"
    qlite = model.get("qlite", {})
    assert qlite.get("dxnn_url", "").endswith("yolov5s_512.dxnn")
    assert qlite.get("json_url", "").endswith("yolov5s_512.json")


def test_anchors_without_href_are_skipped():
    """href 없는 <a> 가 섞여도 죽지 않아야 한다 — 그게 href=True 가 하던 일이다."""
    from dx_app.core.modelzoo import _parse_models

    html = LEGACY_HTML.replace(
        "<td>\n      <a href=",
        "<td>\n      <a name=\"anchor\">pin</a>\n      <a href=",
    )
    models = _parse_models(html)
    assert len(models) == 1
    assert models[0]["qlite"]["dxnn_url"].endswith("yolov5s_512.dxnn")
