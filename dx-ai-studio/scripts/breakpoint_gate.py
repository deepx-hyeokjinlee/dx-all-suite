#!/usr/bin/env python3
"""breakpoint 파편화를 단조 감소로 묶는 ratchet.

한때 19개 폭에서 반응형이 갈렸다. 한 화면이 900 에서 접히고 옆 화면이 960 에서
접히는 데 이유는 없었다 — 어느 파일이 쓰던 값을 그대로 복사해 온 결과다.

이 게이트는 원래 값을 옮기지 않고 늘어나는 것만 막았다. 옮기면 그 폭 구간의
레이아웃이 실제로 바뀌는데 그걸 확인할 responsive 시각 baseline 이 없었기
때문이다. 지금은 있다 — tests/visual 이 650·860·1150·1320 을 찍는다. 그래서
이전이 시작됐고, 남은 값은 다섯이다:

    480   chat-widget    모바일 전체화면 채팅        (이전 불가 — 아래 참조)
    768   5개 파일       모바일→태블릿              (이전 안 함 — 아래 참조)
    1600  dx_planner     detailed workspace 2단     (baseline 밖 — 수동 확인 필요)
    1979  about-deepx    좌측 레일 vs 1680 컬럼     (이전 대상 아님)

480 은 "SCALE 600 으로 이전 가능" 이라고 적혀 있었는데 틀렸다. 이 문서가 요구하는
절차는 "그 값을 덮는 baseline 폭에서 렌더를 눈으로 확인" 인데, tests/visual 의 폭은
650·860·1150·1320 이라 480~600 구간을 덮는 것이 **없다**. 검증할 방법이 없는 이전은
이 게이트의 절차를 따르지 않는 것이므로, 먼저 그 구간의 baseline 을 만들어야 한다.

768 은 2026-09-18 에 실험했다: 다섯 파일을 900 으로 옮기고 시각 스위트를 돌리면
정확히 w860 에서 4건이 바뀐다(모바일 레이아웃이 768 대신 860 에서 적용). 깨지는 곳은
없었다. 그래도 넣지 않았다 — 768 이 빠지고 900 이 들어오므로 **고유값이 8 그대로**라
ratchet 이 얻는 것이 없고, 다섯 파일이 같은 의도(모바일→태블릿)로 쓰는 표준 경계는
이 게이트가 겨냥한다고 밝힌 "근거 없이 복제된 값" 이 아니라 공유 관례에 가깝다.
이득 없이 다섯 모듈의 동작을 바꾸는 거래는 하지 않는다.

그 실험에서 얻은 것은 따로 있다: launcher 의 모듈 그리드는 breakpoint 가 애초에
필요 없었다. `repeat(auto-fit, minmax(280px, 1fr))` 이면 스스로 접힌다 — 값을 어디로
옮길지 묻기 전에 그 질문이 필요한지부터 물어볼 일이다.

1979 는 복사된 값이 아니라 파생값이다. 1680 콘텐츠 컬럼 옆 거터에 레일이 들어갈
수 있는 최소 폭이고, 근거가 about-deepx.css 주석에 적혀 있다. 스케일로 몰면
1440~1979 구간에서 레일이 본문을 덮는다. 게이트가 겨냥하는 것은 근거 없이
복제된 값이지 계산된 값이 아니다.

이전 절차: 한 번에 한 값만 옮기고, 그 값을 덮는 baseline 폭에서 렌더를 눈으로
확인한 뒤, --write 로 baseline 을 조인다. (1100 → 1200 을 그렇게 옮겼다 — 6개
파일, 9개 모듈 전부 w1150 에서 움직였고 다른 63장은 그대로였다.)

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


def new_values(counts: dict[str, list[int]], baseline: dict[str, list[int]]) -> dict[str, list[int]]:
    """파일별로, 스케일에도 그 파일의 기준값에도 없는 breakpoint.

    스케일 값은 파편화를 늘리지 않으므로 어느 파일이든 기준값 없이 쓴다. 처음 판에서는
    메시지만 "스케일 중에서 고르라" 고 했고 판정은 스케일을 보지 않아, 새 파일이 스케일
    값을 써도 막혔다. 계약: tests/test_breakpoint_gate.py
    """
    out: dict[str, list[int]] = {}
    for rel, values in counts.items():
        allowed = set(baseline.get(rel, [])) | set(SCALE)
        new = [v for v in values if v not in allowed]
        if new:
            out[rel] = new
    return out


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
    problems = [
        f"  {rel}: 새 breakpoint {new} — {SCALE} 중에서 고르거나 "
        f"이 파일이 이미 쓰는 값 {sorted(baseline.get(rel, []))} 을 쓰세요"
        for rel, new in new_values(counts, baseline).items()
    ]
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
