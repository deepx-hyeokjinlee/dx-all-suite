"""글꼴이 선언만이 아니라 실제로 그렇게 그려지는지.

950.9px — Inter 를 400 · 600 · 900 으로 재도 폭이 같았다. Regular 한 벌뿐인 파일을
`font-weight:100 900` 으로 선언해서, 브라우저는 굵기가 다 있다고 믿고 가짜 굵기조차
만들지 않았다. 스튜디오의 굵은 영문은 전부 Regular 로 그려지고 있었다.
진짜 굵기라면 글자 폭이 달라진다.
"""
from __future__ import annotations

import re

import pytest

pytest.importorskip("playwright.sync_api")

from tests.browser_support import launch_browser  # noqa: E402
from tests.server_helpers import start_module_server  # noqa: E402

PROBE = """async ([lang, text]) => {
  document.documentElement.lang = lang;
  await document.fonts.ready;
  const el = document.createElement('span');
  el.textContent = text; el.style.fontSize = '56px';
  el.style.fontFamily = getComputedStyle(document.body).fontFamily;
  document.body.appendChild(el);
  const widths = {};
  for (const w of [400, 700]) {
    el.style.fontWeight = String(w);
    await document.fonts.load(`${w} 56px ${el.style.fontFamily}`, text);
    widths[w] = el.getBoundingClientRect().width;
  }
  el.remove();
  return widths;
}"""


@pytest.fixture(scope="module")
def page():
    from playwright.sync_api import sync_playwright

    server, port = start_module_server("dx_app")
    try:
        with sync_playwright() as p:
            browser = launch_browser(p, "chromium")
            pg = browser.new_page()
            pg.goto(f"http://127.0.0.1:{port}/", wait_until="load")
            yield pg
            browser.close()
    finally:
        server.shutdown()


@pytest.mark.parametrize("lang,text", [
    ("en", "Describe anything. Run it on DX-M1."),
    ("es", "Describe cualquier cosa. Ejecútalo en DX-M1."),
])
def test_latin_bold_is_a_real_weight(page, lang, text):
    """폭으로 가려지는 것은 라틴뿐이다. 한중일은 굵기와 무관하게 한 글자가 1em 이라
    진짜 굵기여도 폭이 같다 (처음 이 테스트를 다섯 언어에 걸었을 때 ja·zh 가 336 = 336)."""
    w = page.evaluate(PROBE, [lang, text])
    assert w["700"] > w["400"] * 1.02, w


@pytest.mark.parametrize("family", ["DX CJK KR", "DX CJK JP", "DX CJK SC", "DX CJK TC"])
def test_cjk_faces_cover_400_to_700_so_the_browser_never_synthesises_bold(page, family):
    """face 의 font-weight 범위가 400–700 을 실제로 덮어야, 그 사이 굵기가 그대로 나온다.
    옛 'Noto Sans CJK' 는 400 · 700 두 벌이라 600 을 요청하면 700 이 나왔다."""
    weight = page.evaluate(
        "(fam) => [...document.fonts].filter(f => f.family.replace(/\"/g, '') === fam)"
        ".map(f => f.weight)", family)
    assert len(weight) == 1, weight
    lo, hi = (float(x) for x in weight[0].split())
    assert lo <= 400 and hi >= 700, weight


# 정확히 맞춘다: "Pretendard" 로 앞부분만 보면 ja 용 "Pretendard JP" 가 ko 에 쓰여도 통과한다.
# Noto 의 " Thin" 은 가변 글꼴 기본 인스턴스의 이름일 뿐, 그려지는 굵기와 무관하다.
@pytest.mark.parametrize("lang,text,family", [
    ("ko", "무엇이든", r"Pretendard Variable"),
    ("ja", "説明", r"Pretendard JP Variable"),
    ("zh-CN", "描述", r"Noto Sans SC( Thin)?"),
    ("zh-TW", "描述", r"Noto Sans TC( Thin)?"),
])
def test_each_language_renders_with_its_own_cjk_font(page, lang, text, family):
    page.evaluate("""async ([lang, text]) => {
      document.documentElement.lang = lang;
      const el = document.createElement('div'); el.id = 'fp'; el.textContent = text;
      el.style.fontFamily = getComputedStyle(document.body).fontFamily;
      document.body.appendChild(el);
      await document.fonts.load(`400 16px ${el.style.fontFamily}`, text);
    }""", [lang, text])
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    root = cdp.send("DOM.getDocument")["root"]["nodeId"]
    node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": "#fp"})["nodeId"]
    fonts = [f["familyName"] for f in cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]]
    page.evaluate("() => document.getElementById('fp').remove()")
    assert fonts and re.fullmatch(family, fonts[0]), fonts
