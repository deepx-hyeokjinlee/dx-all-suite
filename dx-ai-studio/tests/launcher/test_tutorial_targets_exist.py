"""런처 튜토리얼이 가리키는 것은 실제로 만들어져야 한다.

왜 이 파일이 생겼는가 — 홈을 다시 자르면서 상단 바의 모듈 상태 점 묶음
(`.status-dots`)을 없앴는데, 그걸 가리키던 튜토리얼 4번 스텝은 그대로 남았다.
타깃이 없으면 엔진이 2초쯤 폴링한 뒤에야 floating tooltip 으로 떨어지므로,
사용자에게는 "다음을 눌러도 4번이 안 뜨고 한 번 더 누르면 5번이 뜬다"로 보였다.

아무 게이트도 이걸 잡지 못했다:

  · test_tutorial_e2e_journey.py 는 7개 모듈을 돌지만 launcher 가 없다
  · test_tutorial_spotlight_spot_check.py 의 11개 스텝은 전부 dx_app/dx_stream
  · 런처 스텝 타깃과 마크업을 잇는 계약이 없었다 (있던 건 순서 단언 하나)

CSS 만 보는 검사로는 부족하다. 마크업이 사라진 뒤에도 `.status-dots` 의 스타일
규칙은 파일에 남아 있었으므로, "어딘가 언급되면 통과"였다면 그대로 통과했다.
그래서 요소를 실제로 **만드는** 곳 — 마크업이나 JS — 을 요구한다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TUTORIAL = ROOT / "launcher" / "static" / "tutorial.js"

# 엔진이 직접 주입하는 것들(튜토리얼 카드, 미리보기 목업)은 마크업에 없다.
ENGINE_OWNED = ("dxt-",)

# 요소를 만들 수 있는 곳: 런처의 마크업과 스크립트, 그리고 공유 위젯들.
# CSS 는 일부러 뺀다 — 스타일은 요소를 만들지 않는다.
# tutorial.js 자신은 반드시 빠져야 한다. 스텝이 자기 타깃을 적어 둔 것은 그것이
# 존재한다는 증거가 아니다 — 처음 이 파일을 쓸 때 주석으로만 제외하고 목록에서
# 빼지 않아, mutation 을 두 번 다 통과했다. 계약이 자기 자신을 근거로 삼고 있었다.
CREATORS = [
    ROOT / "launcher" / "static" / "index.html",
    *sorted(p for p in (ROOT / "launcher" / "static").glob("*.js") if p.name != "tutorial.js"),
    *sorted((ROOT / "shared" / "static").glob("*.js")),
    *sorted((ROOT / "shared" / "chat" / "static").glob("*.js")),
]


def _targets() -> list[str]:
    return re.findall(r"target:\s*'([^']+)'", TUTORIAL.read_text(encoding="utf-8"))


def _tokens(selector: str) -> list[str]:
    """선택자에서 찾아볼 id/class 이름만 뽑는다."""
    return re.findall(r"[#.]([A-Za-z0-9_-]+)", selector)


def test_every_launcher_tutorial_target_is_created_somewhere():
    haystack = "\n".join(
        p.read_text(encoding="utf-8") for p in CREATORS if p.is_file()
    )
    # tutorial.js 자신은 제외한다. 스텝이 자기 타깃을 언급하는 것은 증거가 아니다.
    orphans = []
    for selector in _targets():
        names = [n for n in _tokens(selector) if not n.startswith(ENGINE_OWNED)]
        if not names:
            continue
        if not any(n in haystack for n in names):
            orphans.append(selector)
    assert not orphans, (
        "튜토리얼이 만들어지지 않는 것을 가리킨다 — 스텝이 아무것도 비추지 못하고, "
        f"사용자에게는 건너뛴 것처럼 보인다: {orphans}"
    )
