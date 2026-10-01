"""줌 감사가 **무엇을 보고 무엇을 안 보는지** 를 적어 둔다.

여섯 언어 감사가 "findings 0건" 이라 문제 없다고 읽혔지만, 그것은 칸이
채워졌는지만 보는 검사였다. 같은 착시가 줌 감사에도 있는지 재봤다
(2026-09-21).

**결과: 줌 감사는 딱 한 가지를 본다** — 문서 전체의 가로 넘침
(`documentElement.scrollWidth - clientWidth`). 5개 줌 × 3개 뷰포트로 돌지만
축이 많을 뿐 보는 것은 하나다.

그래서 아래는 통과해도 잡히지 않는다:

  - 요소가 `overflow:hidden` 조상에 **잘려서** 안 보이는 것
  - 글자가 너무 작아져 읽기 어려운 것
  - **세로** 넘침
  - 버튼이 화면 밖으로 밀려 **누를 수 없게** 되는 것

이 파일은 게이트가 아니다. 감사의 **범위를 사실대로 적어** 다음 사람이
"줌은 이미 촘촘하다" 고 잘못 읽지 않게 하는 것이 목적이다. 범위가 늘어나면
이 테스트가 실패하므로, 그때 이 설명을 같이 고치면 된다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FULL = ROOT / "test_zoom_full_audit.py"
AUDIT = ROOT / "tests" / "test_zoom_full_audit.py"


def _src() -> str:
    return AUDIT.read_text(encoding="utf-8")


def test_the_audit_measures_document_level_overflow_only():
    """측정식이 무엇인지 코드에서 확인한다."""
    src = _src()
    assert "scrollWidth - el.clientWidth" in src, (
        "측정식이 바뀌었다 — 이 파일의 설명을 다시 써야 한다")


def test_it_asserts_nothing_else():
    """단언이 하나뿐인지 — 늘어났다면 사각지대 설명이 낡은 것이다."""
    src = _src()
    asserts = [ln.strip() for ln in src.splitlines() if ln.strip().startswith("assert ")]
    assert len(asserts) == 1, f"단언이 {len(asserts)}개로 늘었다: {asserts}"
    assert "overflow == 0" in asserts[0]


def test_the_axes_are_wide_but_the_check_is_narrow():
    """축(줌 5 × 뷰포트 3)이 많아 촘촘해 보이지만, 재는 것은 한 가지다.
    이 대비가 착시의 원인이므로 수치를 고정해 둔다."""
    src = _src()
    zooms = re.search(r"ZOOMS = \((.*?)\)", src).group(1)
    viewports = re.search(r"VIEWPORTS = \((.*?)\)\n", src, re.S).group(1)
    assert len(zooms.split(",")) == 5
    assert viewports.count("(") == 3


def test_element_level_clipping_is_not_checked():
    """요소 단위 잘림을 보지 않는다는 사실 자체를 계약으로 둔다.

    실측(2026-09-21, dx_app, 1024x768): zoom 1.5 와 2.0 에서 문서 가로 넘침은
    0 이지만 `.dx-tab` 과 `.dx-tab-overflow` 가 `overflow:hidden` 인 부모
    (scrollWidth 945 / clientWidth 456) 밖에 놓여 있었다.

    **이것을 결함이라고 단정하지는 않았다.** `body.style.zoom` 은 resize
    이벤트를 일으키지 않으므로, 탭 오버플로 계산이 갱신되지 않은 **측정 착시**
    일 수 있다. 확인하려면 실제 브라우저 줌(CDP `Emulation.setPageScaleFactor`
    또는 deviceScaleFactor)으로 다시 재야 한다. 그 전까지는 "안 보는 영역" 으로만
    기록한다.
    """
    src = _src()
    for token in ("getComputedStyle", "overflow:hidden", "clientWidth + 2"):
        assert token not in src, f"요소 단위 검사가 들어왔다({token}) — 설명을 갱신할 것"
