#!/usr/bin/env python3
"""breakpoint 파편화를 단조 감소로 묶는 ratchet.

지금 19개 폭에서 반응형이 갈린다 — 399, 480, 600, 640, 700, 720, 768, 769,
900, 960, 980, 1024, 1100, 1200, 1280, 1360, 1440, 1600, 1979. 한 화면이
900 에서 접히고 옆 화면이 960 에서 접히는 데 이유는 없다. 어느 파일이 쓰던
값을 그대로 복사해 온 결과다.

값을 지금 한꺼번에 스케일로 몰면 그 폭 구간의 레이아웃이 실제로 바뀌는데,
그걸 확인할 responsive 시각 baseline 이 아직 없다 (tests/visual 은 뷰포트가
하나다). 그래서 이 게이트는 값을 옮기지 않는다 — 새 값이 늘어나는 것만
막는다. 뷰포트 축이 생기면 그때 SCALE 로 하나씩 옮기고 baseline 을 조인다.

    python -m scripts.breakpoint_gate            # 검사
    python -m scripts.breakpoint_gate --write    # baseline 조이기
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "config" / "breakpoint_baseline.json"

# 목표 스케일. 새 반응형 규칙은 이 중에서 고른다.
SCALE = (600, 900, 1200, 1440)

_MEDIA = re.compile(r"@media([^{]*)\{")
_WIDTH = re.compile(r"(?:max|min)-width:\s*(\d+)px")


def _css_files(root: Path) -> list[Path]:
    return sorted(
        p
        for p in root.rglob("*.css")
        if ".venv" not in p.parts
        and "node_modules" not in p.parts
        and "docs" not in p.parts
    )


def scan(root: Path = ROOT) -> dict[str, list[int]]:
    """파일 → 그 파일이 쓰는 breakpoint 값들 (정렬, 중복 제거)."""
    out: dict[str, list[int]] = {}
    for path in _css_files(root):
        found: set[int] = set()
        for query in _MEDIA.findall(path.read_text(encoding="utf-8")):
            found.update(int(v) for v in _WIDTH.findall(query))
        if found:
            out[path.relative_to(root).as_posix()] = sorted(found)
    return dict(sorted(out.items()))


def distinct(counts: dict[str, list[int]]) -> list[int]:
    return sorted({v for vals in counts.values() for v in vals})


def main() -> int:
    counts = scan()
    if "--write" in sys.argv:
        BASELINE_PATH.write_text(
            json.dumps(counts, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"baseline 갱신: 고유 {len(distinct(counts))}개 / {len(counts)} 파일"
        )
        return 0

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    problems = []
    for rel, values in counts.items():
        allowed = set(baseline.get(rel, []))
        new = [v for v in values if v not in allowed]
        if new:
            problems.append(
                f"  {rel}: 새 breakpoint {new} — {SCALE} 중에서 고르거나 "
                f"이 파일이 이미 쓰는 값 {sorted(allowed)} 을 쓰세요"
            )
    per_file = collections.Counter(len(v) for v in counts.values())
    print(
        f"breakpoint 고유값 {len(distinct(counts))}개 · "
        f"파일당 분포 {dict(sorted(per_file.items()))}"
    )
    if problems:
        print("\n".join(problems))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
