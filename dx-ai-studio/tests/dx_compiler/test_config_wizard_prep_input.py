"""전처리 값에 대한 프론트엔드 즉시 피드백.

서버가 400 으로 막게 됐지만 그것만으로는 사용자가 생성 버튼을 누른 뒤에야
안다. `validateCalibNum` 과 `validateInputShapes` 가 이미 입력 즉시 말한다 —
전처리도 같은 자리에서 같은 방식이어야 한다.

여기서 더 중요한 것은 **프론트와 서버의 규칙이 같아야** 한다는 점이다.
프론트가 더 빡빡하면 서버가 받아줄 값을 막고, 더 헐거우면 경고 없이 400 을
맞는다. 둘 다 사용자를 혼란스럽게 한다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JS = ROOT / "dx_compiler" / "static" / "js" / "config_wizard.js"
HTML = ROOT / "dx_compiler" / "templates" / "partials" / "config_wizard.html"


def js() -> str:
    return JS.read_text(encoding="utf-8")


def test_the_wizard_warns_about_unusable_preprocessing_values():
    assert "validatePreprocessings" in js(), (
        "전처리에 대한 즉시 피드백이 없다 — 차원과 calibration_num 은 이미 그렇게 한다")


def test_the_warning_element_exists_and_is_announced():
    """경고가 화면에만 뜨고 스크린리더에 안 알려지면 절반만 된 것이다."""
    html = HTML.read_text(encoding="utf-8")
    assert 'id="wiz-prep-warning"' in html, "경고를 띄울 자리가 없다"
    block = html[html.index('id="wiz-prep-warning"') - 200:
                 html.index('id="wiz-prep-warning"') + 200]
    assert 'aria-live' in block, "wiz-shape-warning 과 달리 aria-live 가 없다"


def test_the_listener_is_delegated_to_the_pipeline_container():
    """전처리 항목은 추가·삭제로 계속 바뀐다. 개별 입력칸에 붙이면 나중에
    추가된 항목이 조용히 검사에서 빠진다 — input-shapes-list 와 같은 이유."""
    src = js()
    assert re.search(r"prepPipeline\.addEventListener\('input', validatePreprocessings\)", src), \
        "컨테이너 위임이 아니다 — 나중에 추가한 전처리가 검사에서 빠진다"


def test_the_front_end_checks_the_same_size_parameters_as_the_server():
    """서버는 width·height·size·scale 을 양수로 본다. 프론트도 같아야 한다."""
    from dx_compiler.core.validation import _POSITIVE_PARAMS
    src = js()
    m = re.search(r"var PREP_POSITIVE = \[([^\]]*)\]", src)
    assert m, "프론트에 크기 파라미터 목록이 없다"
    front = {t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()}
    assert front == set(_POSITIVE_PARAMS), (
        f"프론트와 서버의 규칙이 다르다 — 프론트 {sorted(front)} / "
        f"서버 {sorted(_POSITIVE_PARAMS)}")


def test_the_front_end_also_catches_a_zero_std():
    """0 으로 나누는 것은 생성 버튼을 누르기 전에 말해줄 수 있다."""
    src = js()
    assert "'std'" in src and "n === 0" in src, "std 의 0 을 프론트가 잡지 않는다"


def test_the_front_end_does_not_police_what_the_server_leaves_alone():
    """axis·x·pad_value 는 스칼라도 리스트도 되고 부호도 자유롭다.

    프론트가 이것을 막으면 서버가 받아줄 정당한 값에 경고가 뜬다 — 서버보다
    빡빡한 프론트는 그 자체로 결함이다.
    """
    src = js()
    m = re.search(r"var PREP_POSITIVE = \[([^\]]*)\]", src)
    front = {t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()}
    for loose in ("axis", "x", "pad_value", "channel"):
        assert loose not in front, (
            f"{loose} 는 스칼라도 리스트도 되는데 프론트가 양수로 제한한다")
