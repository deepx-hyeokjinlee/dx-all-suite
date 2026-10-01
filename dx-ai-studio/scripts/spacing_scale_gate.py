#!/usr/bin/env python3
"""간격이 4px 스케일을 벗어나는 것을 단조 감소로 묶는 ratchet.

토큰은 일곱 단계를 정해 두었다 — `--sp-1..7` = 4·8·12·16·24·32·48px.
그런데 실측하면(2026-09-22) padding/margin/gap 에 쓰인 생 px 값이 **33종** 이고,
1,576개 중 **788개(50%)가 스케일 밖** 이다. 가장 흔한 값이 6px(210회)로 토큰에
아예 없다. 10px 192회, 14px 116회가 뒤를 잇는다.

한 자리만 보면 2px 차이는 눈에 띄지 않는다. 문제는 **쌓일 때** 생긴다 — 카드에
6px, 그 안 목록에 10px, 배지에 14px 이 섞이면 어느 것도 서로 정렬되지 않는다.
그리고 뒤늦게 고치면 비주얼 baseline 이 통째로 흔들린다.

색상(css_token_gate)·breakpoint(breakpoint_gate)와 같은 방식을 쓴다: **지금
값을 파일별 상한으로 박고 늘어나는 것만 막는다.** 줄이는 것은 자유이고,
`--update` 로 내린다.

스케일은 여기 적지 않고 `shared/static/dx-tokens.css` 에서 읽는다. 따로 적으면
토큰이 바뀔 때 조용히 어긋난다.

세지 않는 것:
  - `var(--sp-*)` 를 쓴 선언 — 목적을 이미 달성했다
  - 0, 1px, 2px — 테두리·헤어라인급이라 스케일의 대상이 아니다
  - `auto`, `%`, `em`, `rem`, `calc()` 안의 값 — px 스케일이 적용되지 않는다

계약: tests/shared/test_spacing_scale_gate.py
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "shared" / "static" / "dx-tokens.css"
BASELINE_PATH = ROOT / "config" / "spacing_scale_baseline.json"

_PROPS = ("padding", "margin", "gap")
# 테두리·헤어라인은 스케일의 대상이 아니다.
_IGNORE_BELOW = 3
_SKIP_DIRS = (".venv", "node_modules", "/data/", "docs/.venv-docs", "/outputs/")


def scale() -> set[int]:
    """`--sp-N: Xpx` 선언에서 스케일을 읽는다."""
    text = TOKENS.read_text(encoding="utf-8")
    return {int(v) for v in re.findall(r"--sp-\d+\s*:\s*(\d+)px", text)}


def _iter_css():
    for path in sorted(ROOT.rglob("*.css")):
        rel = str(path.relative_to(ROOT))
        if any(s.strip("/") in rel for s in _SKIP_DIRS):
            continue
        yield rel, path


def count_off_scale(allowed: set[int]) -> dict[str, int]:
    """파일별로 스케일 밖 간격 값이 몇 번 쓰였는지 센다."""
    counts: dict[str, int] = {}
    for rel, path in _iter_css():
        n = 0
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            for prop in _PROPS:
                for m in re.finditer(rf"\b{prop}[^:]*:\s*([^;}}]+)", line):
                    value = m.group(1)
                    if "var(--" in value or "calc(" in value:
                        continue
                    for raw in re.findall(r"(\d+)px", value):
                        px = int(raw)
                        if px < _IGNORE_BELOW or px in allowed:
                            continue
                        n += 1
        if n:
            counts[rel] = n
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true",
                    help="현재 값으로 baseline 을 다시 쓴다 (줄었을 때만 의미가 있다)")
    args = ap.parse_args(argv)

    allowed = scale()
    if not allowed:
        print(f"스케일을 읽지 못했다: {TOKENS}")
        return 1
    counts = count_off_scale(allowed)
    total = sum(counts.values())

    if args.update:
        BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_PATH.write_text(
            json.dumps(dict(sorted(counts.items())), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"baseline 갱신: {len(counts)}개 파일 · 스케일 밖 {total}개")
        return 0

    if not BASELINE_PATH.is_file():
        print(f"baseline 이 없다: {BASELINE_PATH} (--update 로 만든다)")
        return 1

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    problems = []
    for rel, n in sorted(counts.items()):
        cap = baseline.get(rel, 0)
        if n > cap:
            problems.append(
                f"  {rel}: 스케일 밖 간격이 {cap} → {n} 로 늘었다. "
                f"{sorted(allowed)} 중에서 고르거나 var(--sp-*) 를 쓰세요")

    print(f"간격 스케일 밖 {total}개 · 파일 {len(counts)}개 "
          f"(스케일 {sorted(allowed)})")
    if problems:
        print("\n".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
