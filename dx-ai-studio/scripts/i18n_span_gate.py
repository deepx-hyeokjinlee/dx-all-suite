#!/usr/bin/env python3
"""언어별 형제 span 뭉치 수를 단조 감소로 묶는 ratchet.

한 문구를 6개 언어 span 으로 늘어놓는 마크업은 사전과 번역이 두 곳에 살게
만든다. `scripts/migrate_i18n_spans.py` 가 대부분을 data-i18n 으로 옮겼고,
남은 것은 key 하나에 문구가 둘이라 사람이 정해야 하는 것들뿐이다. 새로
늘어나는 것만 막으면 된다.

    python -m scripts.i18n_span_gate            # 검사
    python -m scripts.i18n_span_gate --write    # baseline 조이기
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts.migrate_i18n_spans import _GROUP, _markup_files

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "config" / "i18n_span_baseline.json"

SCAN_ROOTS = (
    "dx_agent_dev",
    "dx_app",
    "dx_benchmark",
    "dx_compiler",
    "dx_modelzoo",
    "dx_monitor",
    "dx_planner",
    "dx_stream",
    "launcher",
    "shared",
)


def count_groups(text: str) -> int:
    return sum(1 for _ in _GROUP.finditer(text))


def scan(root: Path = ROOT) -> dict[str, int]:
    """lang-span 뭉치가 하나라도 있는 파일 → 개수."""
    out: dict[str, int] = {}
    for name in SCAN_ROOTS:
        for path in _markup_files(name):
            n = count_groups(path.read_text())
            if n:
                out[path.relative_to(root).as_posix()] = n
    return dict(sorted(out.items()))


def main() -> int:
    counts = scan()
    if "--write" in sys.argv:
        BASELINE_PATH.write_text(
            json.dumps(counts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"baseline 갱신: {sum(counts.values())} groups / {len(counts)} files")
        return 0

    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    over = {r: (n, baseline.get(r, 0)) for r, n in counts.items() if n > baseline.get(r, 0)}
    for rel, (now, allowed) in over.items():
        print(f"OVER  {rel}: {now} > {allowed}")
    print(f"total lang-span groups: {sum(counts.values())}")
    return 1 if over else 0


if __name__ == "__main__":
    raise SystemExit(main())
