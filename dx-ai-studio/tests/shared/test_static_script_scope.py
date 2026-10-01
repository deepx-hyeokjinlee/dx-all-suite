"""한 페이지가 불러오는 스크립트들은 전역 스코프 하나를 나눠 쓴다.

이 프로젝트에는 번들러가 없다. 모듈 페이지는 `<script src>` 를 순서대로 나열하고,
그 파일들의 최상위 선언은 전부 같은 전역 렉시컬 스코프에 들어간다. 그래서:

* `const` / `let` / `class` 를 두 파일이 같은 이름으로 선언하면 **나중에 로드되는
  파일이 통째로 파싱에 실패한다** (SyntaxError: has already been declared).
  화면은 조용히 빈 채로 남고, 파이썬 테스트는 전부 통과한다 — 실제로
  METRIC_HIGHER_IS_BETTER 를 catalog.js 와 detail.js 가 각자 선언해서
  ModelZoo 상세 화면이 통째로 렌더되지 않은 적이 있다.
* `function` / `var` 는 재선언이 허용되는 대신 **나중 것이 조용히 이긴다**.
  catalog.js 의 `_localLabel` 에 있던 ja/zh/es 폴백이 detail.js 의 같은 이름
  함수에 덮여 죽어 있었다.

둘 다 브라우저를 켜지 않으면 드러나지 않는데, 기본 CI 에는 브라우저 스테이지가
없다. 그래서 소스만 읽어서 막는다.

최상위 판정은 들여쓰기로 한다 — 이 코드베이스의 모든 파일이 2칸 들여쓰기를
쓰므로 컬럼 0 의 선언은 최상위다.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

_SCRIPT_SRC = re.compile(r"""<script[^>]*\bsrc=["']([^"']+)["']""", re.I)
_TOP_LEVEL_DECL = re.compile(
    r"^(?:export\s+)?(?:async\s+)?(?P<kind>const|let|var|class|function)\s*\*?\s*"
    r"(?P<name>[A-Za-z_$][\w$]*)"
)
# 재선언이 SyntaxError 인 것들. var/function 은 허용되지만 조용히 덮인다.
_FATAL_KINDS = {"const", "let", "class"}


def _documents():
    """(문서 경로, [스크립트 파일…]) — 로드 순서 그대로."""
    htmls = sorted(ROOT.glob("*/templates/index.html"))
    htmls += [p for p in [ROOT / "launcher" / "static" / "index.html"] if p.exists()]
    for html in htmls:
        module_dir = html.parent.parent if html.name == "index.html" and html.parent.name == "templates" else html.parent
        scripts = []
        for src in _SCRIPT_SRC.findall(html.read_text(encoding="utf-8")):
            path = _resolve(src, module_dir)
            if path is not None and path.exists():
                scripts.append(path)
        yield html, scripts


def _resolve(src: str, module_dir: Path) -> Path | None:
    path = src.split("?")[0]
    if path.startswith(("http://", "https://", "//")):
        return None
    if path.startswith("/static/shared/"):
        return ROOT / "shared" / "static" / path[len("/static/shared/"):]
    if path.startswith("/static/"):
        return module_dir / "static" / path[len("/static/"):]
    return None


def _top_level_declarations(path: Path):
    """{이름: 종류} — 컬럼 0 에서 시작하는 선언만."""
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _TOP_LEVEL_DECL.match(line)
        if match:
            out.setdefault(match.group("name"), match.group("kind"))
    return out


def _collisions(scripts):
    owners = defaultdict(list)
    kinds = {}
    for path in scripts:
        for name, kind in _top_level_declarations(path).items():
            owners[name].append(path)
            kinds.setdefault(name, kind)
            if kind in _FATAL_KINDS:
                kinds[name] = kind
    return {n: (kinds[n], p) for n, p in owners.items() if len(p) > 1}


@pytest.mark.parametrize(
    "html,scripts", list(_documents()), ids=lambda v: v.parts[-3] if isinstance(v, Path) else ""
)
def test_no_fatal_redeclaration_across_scripts(html, scripts):
    """const/let/class 충돌 — 나중 파일이 통째로 파싱에 실패한다."""
    fatal = {n: (k, p) for n, (k, p) in _collisions(scripts).items() if k in _FATAL_KINDS}
    assert not fatal, "\n".join(
        f"{html.relative_to(ROOT)}: `{k} {n}` 이(가) "
        + ", ".join(x.name for x in paths)
        + " 에 중복 선언됐다 — 나중 파일이 SyntaxError 로 통째로 죽는다"
        for n, (k, paths) in sorted(fatal.items())
    )


@pytest.mark.parametrize(
    "html,scripts", list(_documents()), ids=lambda v: v.parts[-3] if isinstance(v, Path) else ""
)
def test_no_silent_override_across_scripts(html, scripts):
    """function/var 충돌 — 파싱은 되지만 나중 것이 조용히 이긴다."""
    silent = {n: (k, p) for n, (k, p) in _collisions(scripts).items() if k not in _FATAL_KINDS}
    assert not silent, "\n".join(
        f"{html.relative_to(ROOT)}: `{k} {n}` 이(가) "
        + ", ".join(x.name for x in paths)
        + " 에 중복 선언됐다 — 나중 파일 정의가 앞 파일 호출까지 덮는다"
        for n, (k, paths) in sorted(silent.items())
    )
