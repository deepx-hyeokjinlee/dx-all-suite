"""internal 소스의 20칼럼 테이블이 우리가 가정한 모양인지.

`docs/testing.md` 에 "사내망 호스트라 게이트가 닿지 못한다" 고 적었는데, 확인해보니
닿는다. 확인하지 않고 단정한 것이었다. 실측 응답에서 대표 구간(20칼럼 헤더 3행 +
데이터 3행)을 잘라 픽스처로 두고, 여기서 그 모양을 고정한다.

왜 필요한가: 공개 페이지가 정확히 이렇게 조용히 깨졌다. 테이블이 사라지고 인라인
JSON 으로 바뀌었는데 스크래퍼는 따라가지 않았고, 그 경로는 500 을 내면서도 아무
게이트도 울리지 않았다. internal 은 같은 위험을 안고 있었고, 다른 점은 아무도 그것을
보고 있지 않았다는 것뿐이다.
"""
from __future__ import annotations

from pathlib import Path

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "internal_modelzoo_table.html"


def _models():
    from dx_app.core.modelzoo import _parse_models

    return _parse_models(FIXTURE.read_text(encoding="utf-8"))


def test_the_twenty_column_table_still_parses():
    models = _models()
    assert models, "internal 레이아웃에서 한 건도 못 읽었다"


def test_a_row_carries_the_fields_the_screen_uses():
    m = _models()[0]
    for key in ("name", "task", "qlite", "qpro"):
        assert key in m, f"{key} 가 없다: {sorted(m)}"
    assert m["qlite"].get("dxnn_url", "").endswith(".dxnn"), m["qlite"]


def test_internal_rows_carry_only_two_tiers():
    """공개 소스는 Q-Master 를 주지만 이쪽은 주지 않는다 — 그 비대칭을 적어 둔다.

    `_CHIP_DIRS` 와 프론트의 `MZ_CHIPS` 는 세 티어를 순회하는데, 이 경로가 만드는
    행에는 `qmaster` 키 자체가 없다. 지금은 조용히 넘어간다(`m.get(chip)` → None,
    `m[chip.key]` → undefined → '–'). 우연이 아니라 계약이 되도록 고정한다.
    실측: internal 496 모델 중 Q-Master 0 건.
    """
    m = _models()[0]
    assert "qmaster" not in m, (
        "internal 이 qmaster 를 내기 시작했다 — 화면과 설치 경로를 다시 확인할 것"
    )


def test_missing_numbers_are_dashes_here_not_nulls():
    """public 은 숫자나 None 을 주고 internal 은 '-' 문자열을 준다.

    같은 화면이 두 소스를 쓰므로 이 차이를 알고 있어야 한다 — 정렬이나 계산에
    들어가면 조용히 어긋난다.
    """
    m = _models()[0]
    for key in ("fps", "fps_per_watt"):
        assert isinstance(m.get(key), str), f"{key} 가 문자열이 아니다: {m.get(key)!r}"
