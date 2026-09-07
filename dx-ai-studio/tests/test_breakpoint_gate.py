"""breakpoint 파편화가 다시 늘지 않도록 묶는 ratchet.

같은 제품 안에서 반응형이 19개 폭에서 갈린다 — 900 에서 접히는 화면 옆에
960 에서 접히는 화면이 있고, 그 차이에 이유는 없다. 값을 지금 스케일로 몰면
그 폭 구간 레이아웃이 실제로 바뀌는데 확인할 responsive baseline 이 아직
없다. 그래서 새 값이 들어오는 것만 막는다.
"""
from __future__ import annotations

import json

from scripts.breakpoint_gate import BASELINE_PATH, SCALE, distinct, scan


def test_scale_is_ordered_and_distinct():
    assert list(SCALE) == sorted(set(SCALE))


def test_no_file_introduces_a_new_breakpoint():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    counts = scan()
    new = {
        rel: [v for v in values if v not in set(baseline.get(rel, []))]
        for rel, values in counts.items()
    }
    new = {rel: vals for rel, vals in new.items() if vals}
    assert not new, (
        f"새 breakpoint 가 생겼다 — {SCALE} 중에서 고르거나 그 파일이 이미 "
        f"쓰는 값을 쓰세요: {new}"
    )


def test_breakpoint_baseline_has_no_stale_values():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    counts = scan()
    stale = {
        rel: [v for v in values if v not in set(counts.get(rel, []))]
        for rel, values in baseline.items()
    }
    stale = {rel: vals for rel, vals in stale.items() if vals}
    assert not stale, (
        "안 쓰는 breakpoint 가 baseline 에 남았다. "
        f"`python -m scripts.breakpoint_gate --write` 로 조인다: {stale}"
    )


def test_distinct_breakpoints_do_not_grow():
    assert len(distinct(scan())) <= 19
