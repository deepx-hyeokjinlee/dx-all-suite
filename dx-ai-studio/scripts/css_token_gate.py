#!/usr/bin/env python3
"""모듈 CSS의 raw hex 사용량을 세고 baseline과 비교한다.

primitive 팔레트는 shared/static/dx-tokens.css 한 곳에만 있어야 한다.
모듈 CSS의 리터럴 hex는 테마 전환을 조용히 깨뜨리므로 여기서 묶는다.
baseline은 오를 수 없다 — 새 raw hex는 즉시 실패한다.
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
    "dx_*/static/css/*.css",
    "shared/chat/static/*.css",
)

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# custom property 정의(--x: #fff)는 토큰 선언이므로 세지 않는다.
_VAR_DEF = re.compile(r"--[\w-]+\s*:[^;}]*")


def count_raw_hex(css: str) -> int:
    return len(_HEX.findall(_VAR_DEF.sub("", css)))


def scan_modules(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pattern in SCAN_GLOBS:
        for path in sorted(root.glob(pattern)):
            counts[path.relative_to(root).as_posix()] = count_raw_hex(
                path.read_text(encoding="utf-8")
            )
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
