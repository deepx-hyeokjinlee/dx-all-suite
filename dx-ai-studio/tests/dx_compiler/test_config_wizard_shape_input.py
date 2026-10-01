"""SR-758 (프론트) — 마법사가 쓸 수 없는 차원을 조용히 넘기면 안 된다.

백엔드가 400 으로 막게 됐지만, 그것만으로는 사용자가 "왜 안 되는지" 를 생성 버튼을
누른 뒤에야 안다. `validateCalibNum` 은 이미 입력 즉시 경고를 띄운다 — 차원도 같은
자리에서 같은 방식으로 말해야 한다.

그리고 지금 파서에는 별개의 문제가 있다:

    .split(',').map(d => parseInt(d.trim())).filter(d => !isNaN(d))

`1,3,abc,224` 를 넣으면 `abc` 가 **조용히 사라져** `[1,3,224]` 가 된다. 4차원을
넣었는데 3차원이 전송되고, 아무도 그 사실을 말해주지 않는다. 음수는 그대로 통과한다.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "dx_compiler" / "static" / "js" / "config_wizard.js"


def source() -> str:
    return SRC.read_text(encoding="utf-8")


def test_the_wizard_warns_about_unusable_dimensions():
    src = source()
    assert "validateInputShapes" in src, (
        "차원에 대한 즉시 피드백이 없다 — calibration_num 은 이미 그렇게 한다"
    )


def test_bad_dimensions_are_not_silently_dropped():
    """`filter(d => !isNaN(d))` 는 잘못 쓴 값을 없애고 차원 수를 바꿔버린다."""
    src = source()
    m = re.search(r"\.split\(','\)[^;]*", src, re.S)
    assert m, "차원 파싱 부분을 찾을 수 없다"
    body = m.group(0)
    assert "filter(d => !isNaN(d))" not in body, (
        "잘못된 값을 조용히 버린다 — 4차원을 넣었는데 3차원이 전송된다"
    )


def test_the_warning_uses_the_same_mechanism_as_calibration():
    """경고를 보여주는 방식이 둘로 갈리면 하나는 반드시 낡는다."""
    src = source()
    assert src.count("style.display = msg ? '' : 'none'") >= 2, (
        "차원 경고가 기존 경고와 다른 방식으로 그려진다"
    )
