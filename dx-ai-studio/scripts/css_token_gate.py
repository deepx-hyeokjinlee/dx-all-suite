#!/usr/bin/env python3
"""리터럴 색 사용량을 세고 baseline과 비교한다.

팔레트는 shared/static 의 세 파일(dx-tokens / dx-semantic / dx-theme-light)에만
있어야 한다. 그 밖의 리터럴 색은 테마 전환을 조용히 깨뜨린다.
baseline은 오를 수 없다 — 새 리터럴은 즉시 실패한다.

이 게이트에는 사각지대가 셋 있었고, 그래서 은퇴한 팔레트가 207곳에 살아남아
있었다. 팔레트를 애플 톤으로 옮겼을 때 토큰을 쓰는 자리는 전부 따라왔지만,
리터럴은 정의상 토큰을 쓰지 않으므로 하나도 움직이지 않았다:

  1. hex 만 셌다. `rgba(99,140,255,.1)` 은 같은 색인데 정규식에 안 걸렸다.
     은퇴 팔레트 207건 중 150건이 이 형태였다.
  2. shared/static/ 을 통째로 제외했다. "파운데이션은 팔레트를 정의하는
     자리"라는 이유였는데, dx-tokens/dx-semantic/dx-theme-light 만 그렇고
     tutorial.css(hex 43개) · toolbar.css(15개) · dx-base · dx-components ·
     dx-utilities 는 컴포넌트다.
  3. .js / .html 을 아예 안 봤다. 차트와 위젯이 색을 인라인으로 들고 있다.

무채색 rgb (검정·흰색 알파)는 scrim·hairline 으로 정당하므로 세지 않는다.
유채색만 센다 — 유채색을 인라인으로 박는 것이 테마를 깨는 행위다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "config" / "css_token_baseline.json"

# 모듈이 소유한 CSS만 스캔한다. shared/static/ 파운데이션은 팔레트를 정의하는
# 자리이므로 제외한다 (dx-tokens.css가 곧 원본).
SCAN_GLOBS = (
    "launcher/static/*.css",
    "launcher/static/*.js",
    "dx_*/static/css/*.css",
    "dx_*/static/js/*.js",
    "shared/static/*.css",
    "shared/static/*.js",
    "shared/chat/static/*.css",
    "shared/hw_widget/*.html",
)

# 팔레트를 정의하는 자리. 여기에는 리터럴이 있어야 한다.
PALETTE_FILES = frozenset({
    "shared/static/dx-tokens.css",
    "shared/static/dx-semantic.css",
    "shared/static/dx-theme-light.css",
})

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_RGB = re.compile(r"\brgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")
# custom property 정의(--x: #fff)는 토큰 선언이므로 세지 않는다.
_VAR_DEF = re.compile(r"--[\w-]+\s*:[^;}]*")


def count_raw_hex(css: str) -> int:
    """리터럴 색의 수. hex 전부 + 유채색 rgb()/rgba().

    무채색(r==g==b)은 scrim·hairline 이라 정당하다. 유채색을 인라인으로 박는
    것만이 테마를 깨므로 그것만 센다.
    """
    body = _VAR_DEF.sub("", css)
    n = len(_HEX.findall(body))
    for m in _RGB.finditer(body):
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        if not (r == g == b):
            n += 1
    return n


def scan_modules(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pattern in SCAN_GLOBS:
        for path in sorted(root.glob(pattern)):
            rel = path.relative_to(root).as_posix()
            if rel in PALETTE_FILES:
                continue
            counts[rel] = count_raw_hex(path.read_text(encoding="utf-8"))
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="현재 값으로 baseline을 다시 쓴다")
    args = ap.parse_args(argv)

    counts = scan_modules(ROOT)
    if args.write:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"wrote {BASELINE_PATH.relative_to(ROOT)} ({sum(counts.values())} raw hex)")
        return 0

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    failed = False
    for rel, n in sorted(counts.items()):
        allowed = baseline.get(rel, 0)
        if n > allowed:
            print(f"FAIL {rel}: {n} raw hex > baseline {allowed}")
            failed = True
    print(f"total raw hex: {sum(counts.values())}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
