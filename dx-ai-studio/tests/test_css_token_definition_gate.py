"""var(--x) 는 어딘가에서 정의돼야 한다.

정의가 없으면 CSS 는 조용히 실패하지 않는다 — 계산 단계에서 선언 전체가 무효가
되고, 그 속성은 상속값이나 초기값으로 떨어진다. 실제로 이 저장소에서 벌어지던 일:

    border: 1px solid var(--bdr)   →  테두리가 통째로 사라짐 (initial: none)
    background: var(--bg2)         →  투명
    color: var(--dim)              →  부모 색을 상속

34곳이 이렇게 있었고 15개 이름은 이 저장소에서 한 번도 정의된 적이 없었다 — 다른
스타일시트에서 마크업과 함께 옮겨온 흔적이다. 분기점에도 그대로 있었으니 오래
살아남았다는 뜻이고, 오래 살아남은 이유는 아무 게이트도 이걸 보지 않았기 때문이다.
눈으로는 "테두리가 원래 없는 디자인" 과 구분되지 않는다.

fallback 이 있는 var(--x, 기본값) 은 검사하지 않는다. 그건 없을 수 있음을 작성자가
이미 다루고 있다는 뜻이다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {".venv", "node_modules", "var", ".git", "dx-agent-dev"}
EXTS = (".css", ".js", ".html")

_DEFINE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
_SET_PROP = re.compile(r"setProperty\(\s*['\"](--[A-Za-z0-9_-]+)")
# 닫는 괄호가 바로 오는 것만 — 쉼표가 오면 fallback 이 있다.
_USE = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)")


def _files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in EXTS and not (SKIP_PARTS & set(p.parts)):
            yield p


def test_every_custom_property_reference_resolves():
    defined: set[str] = set()
    texts: list[tuple[Path, str]] = []
    for p in _files():
        t = p.read_text(encoding="utf-8", errors="ignore")
        texts.append((p, t))
        defined |= set(_DEFINE.findall(t))
        defined |= set(_SET_PROP.findall(t))

    missing: dict[str, list[str]] = {}
    for p, t in texts:
        for i, line in enumerate(t.splitlines(), 1):
            for name in _USE.findall(line):
                if name not in defined:
                    missing.setdefault(name, []).append(f"{p.relative_to(ROOT)}:{i}")

    assert not missing, (
        "정의 없는 커스텀 속성 참조 — 해당 선언이 통째로 무효가 된다 "
        "(테두리 사라짐 / 배경 투명 / 글자색 상속): "
        + "; ".join(f"{k} @ {v[0]} (x{len(v)})" for k, v in sorted(missing.items()))
    )
