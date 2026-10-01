"""home 의 모듈 목록은 각 모듈이 스스로 내놓는 숫자를 든다.

여덟 행이 이름 + 산문 한 줄로만 되어 있으면 서로 구별되지 않아 목록이 한 덩어리로
읽힌다. Model Zoo 한 행만 `347 models · 22 tasks` 를 들고 있었고, 그 방식
(`/zoo/api/catalog` 를 프록시로 불러 `.card-desc` 에 쓰기)이 이미 검증돼 있으므로
나머지에도 같은 수를 둔다.

**표 하나로 모은다.** 모듈마다 함수를 한 벌씩 쓰면 다음 모듈이 생길 때 또 한 벌이
늘고, 그건 이 저장소에서 이미 두 번 고친 패턴이다 (`_CHIP_DIRS`, `MZ_CHIPS`).

Compiler 와 EdgeGuide 는 일부러 제외한다 — 셀 것이 없다. 각각 `/api/listdir`
`/api/mkdir` 과 `/api/hb` 뿐이고, 숫자를 붙이자고 새 엔드포인트를 만드는 것은
이 작업의 목적이 아니다. 비대칭을 그대로 두는 편이 정직하다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "launcher" / "static" / "home-sections.js"


def source() -> str:
    assert SRC.is_file(), "launcher/static/home-sections.js is missing"
    return SRC.read_text(encoding="utf-8")


def _facts_block() -> str:
    src = source()
    m = re.search(r"MODULE_FACTS\s*=\s*\[(.*?)\n\s*\];", src, re.S)
    assert m, "MODULE_FACTS 표가 없다 — 모듈마다 함수를 따로 두면 안 된다"
    return m.group(1)


def test_every_module_with_a_number_is_in_the_table():
    block = _facts_block()
    for app in ("zoo", "app", "stream", "agent", "benchmark", "dx_monitor"):
        assert f"'{app}'" in block, f"MODULE_FACTS 에 {app} 이 없다"


def test_modules_with_nothing_to_count_are_left_out():
    """Compiler 와 EdgeGuide 는 셀 것이 없다. 억지로 넣으면 빈 숫자가 생긴다."""
    block = _facts_block()
    for app in ("compiler", "planner"):
        assert f"'{app}'" not in block, (
            f"{app} 은 셀 API 가 없는데 MODULE_FACTS 에 있다"
        )


def test_each_entry_fetches_through_the_launcher_proxy():
    """모듈은 각자 포트에 있고, home 은 런처 프록시(/zoo/, /app/ …)로만 닿는다."""
    block = _facts_block()
    urls = re.findall(r"url:\s*'([^']+)'", block)
    assert len(urls) >= 6, f"url 이 {len(urls)}개뿐이다"
    for u in urls:
        assert u.startswith("/"), f"프록시 경로가 아니다: {u}"
        assert "://" not in u, f"절대 URL 은 프록시를 우회한다: {u}"


def test_counts_are_written_to_the_description_not_the_state_slot():
    """`card-state` 는 Running 이 쓴다. 숫자가 그 자리를 뺏으면 상태가 사라진다."""
    src = source()
    paint = src[src.index("function _paintFacts") :] if "function _paintFacts" in src else ""
    assert paint, "_paintFacts 가 없다"
    body = paint[: paint.index("\n  }")]
    assert "card-desc" in body, "숫자는 설명 줄에 써야 한다"
    assert "card-state" not in body, "숫자가 Running 상태 슬롯을 덮어쓴다"
    assert "data-role=\"state\"" not in body
