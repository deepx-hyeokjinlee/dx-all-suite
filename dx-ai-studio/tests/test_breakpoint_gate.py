"""breakpoint 파편화가 다시 늘지 않도록 묶는 ratchet.

같은 제품 안에서 반응형이 19개 폭에서 갈린다 — 900 에서 접히는 화면 옆에
960 에서 접히는 화면이 있고, 그 차이에 이유는 없다. 값을 지금 스케일로 몰면
그 폭 구간 레이아웃이 실제로 바뀌는데 확인할 responsive baseline 이 아직
없다. 그래서 새 값이 들어오는 것만 막는다.
"""
from __future__ import annotations

import json

from scripts.breakpoint_gate import BASELINE_PATH, SCALE, distinct, new_values, scan


def test_scale_is_ordered_and_distinct():
    assert list(SCALE) == sorted(set(SCALE))


def test_no_file_introduces_a_new_breakpoint():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    new = new_values(scan(), baseline)
    assert not new, (
        f"새 breakpoint 가 생겼다 — {SCALE} 중에서 고르거나 그 파일이 이미 "
        f"쓰는 값을 쓰세요: {new}"
    )


def test_scale_values_need_no_baseline_entry():
    """메시지는 "스케일 중에서 고르라" 고 하는데 판정은 스케일을 보지 않았다 — 새 파일
    (launcher/static/home-stage.css) 이 600 · 900 · 1200 을 쓰자 전부 '새 값' 으로 막혔다.
    스케일 값은 파편화를 늘리지 않으므로 기준값 없이 허용한다."""
    assert new_values({"new.css": list(SCALE)}, {}) == {}


def test_values_off_the_scale_are_still_new():
    assert new_values({"new.css": [900, 1100]}, {}) == {"new.css": [1100]}
    # 이미 그 파일이 쓰던 값은 스케일 밖이어도 그대로 둔다 (옮기는 것은 별도 절차)
    assert new_values({"old.css": [768, 1100]}, {"old.css": [768]}) == {"old.css": [1100]}


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
