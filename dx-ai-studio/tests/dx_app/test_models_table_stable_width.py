"""모델 표는 **로컬에 무엇이 설치돼 있든** 같은 자리에 그려져야 한다.

models.js 는 설치된 모델에만 `📊 Graph` 버튼을 붙이고, 다운로드 버튼 라벨을
Download → Re-download 로 늘린다. ACTIONS 가 마지막 열이라 폭이 변하면 왼쪽
열들이 좁아지며 표 전체가 리플로우된다.

두 가지가 걸렸다:

1. **UX** — 모델을 하나 받을 때마다 표가 들썩인다.
2. **게이트** — 비주얼 베이스라인이 "모델이 하나도 없는 상태" 로 찍혀 있어서,
   모델을 설치하는 순간(= 이 제품의 정상 사용) 8개 베이스라인이 22%까지 어긋났다.
   ACTIONS 열만 마스크해 봤지만 리플로우는 마스크 밖에서 일어나므로 소용없었다
   (22.58% → 22.17%). 원인을 없애는 편이 맞다.

실측(2026-09-21, chromium, 650/860/1150/1320 네 폭 전부):
    설치됨   maxWidth 246px
    미설치   maxWidth 175px
네 폭에서 값이 같으므로 미디어 쿼리 없이 한 값으로 고정할 수 있다 —
breakpoint ratchet 을 건드리지 않는다.

이 파일은 소스 계약이다. 실제 렌더 폭은 비주얼 스위트가 잡는다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "dx_app" / "static" / "css" / "style.css"
JS = ROOT / "dx_app" / "static" / "js" / "models.js"


def _actions_rule() -> str:
    css = CSS.read_text(encoding="utf-8")
    m = re.search(r"\.m-actions\{([^}]*)\}", css)
    assert m, ".m-actions 규칙을 찾을 수 없다"
    return m.group(1)


def test_the_actions_column_has_a_pinned_width():
    """폭이 고정돼 있지 않으면 내용에 따라 열이 커지고 표가 밀린다."""
    rule = _actions_rule()
    assert re.search(r"min-width:\s*\d+px", rule), (
        "ACTIONS 열에 고정 폭이 없다 — 설치된 모델 수에 따라 표가 리플로우된다. "
        f"현재 규칙: {rule!r}"
    )


def test_the_pinned_width_fits_the_widest_state():
    """가장 넓은 상태(설치됨, Graph + Re-download)가 246px 였다.

    이보다 좁게 잡으면 버튼이 잘리거나 줄바꿈되어 행 높이가 바뀐다 —
    리플로우를 세로로 옮길 뿐이다.
    """
    rule = _actions_rule()
    px = int(re.search(r"min-width:\s*(\d+)px", rule).group(1))
    assert px >= 246, f"min-width {px}px 는 가장 넓은 상태(246px)보다 좁다"


def test_the_buttons_still_cannot_wrap():
    """flex-wrap:nowrap 이 빠지면 고정 폭 안에서 버튼이 접히며 행 높이가 변한다."""
    assert "flex-wrap:nowrap" in _actions_rule()


def test_the_install_state_is_what_changes_the_content():
    """이 계약이 왜 필요한지를 코드에 묶어둔다.

    models.js 가 `model_exists` 로 버튼을 갈라 그리는 한 이 열의 폭은
    로컬 상태에 달려 있다. 그 분기가 사라지면 이 테스트도 의미를 잃으므로,
    분기가 아직 있다는 것을 확인한다.
    """
    js = JS.read_text(encoding="utf-8")
    assert "model_exists" in js, "설치 여부로 갈리는 렌더가 사라졌다 — 계약을 재검토할 것"
    assert "Re-download" in js, "Download/Re-download 라벨 분기가 사라졌다"
