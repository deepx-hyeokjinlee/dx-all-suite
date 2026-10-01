"""SR-758 — `/config/generate` 가 쓸 수 없는 input_shapes 를 그대로 저장하면 안 된다.

QA 보고: 음수 차원이나 잘못된 타입이 4xx 없이 200 으로 통과해 config.json 에
기록되고, 오류는 한참 뒤 컴파일 단계에서야 드러난다. 실측으로 재현됐다.

다만 티켓의 원인 분석("어느 계층에도 검증이 없다")은 사실이 아니다. 같은 함수가
`calibration_num` 은 `int()` 로 감싸고 400 을 낸다. 빠진 것은 `input_shapes` 하나이고,
그 한 줄이 무엇이 들어오든 그대로 복사한다:

    config = {"inputs": config_data.get("input_shapes", {})}

유효 범위는 추측하지 않는다. `dx-compiler/.deepx/toolsets/config-schema.md` 가
"Dimensions: All must be positive integers (no -1, no 0)" 라고 정해 두었다.

여기서 막지 않는 것도 있다 — 배치가 1인지, 키가 ONNX 노드 이름과 맞는지. 이 API 는
모델을 보지 않으므로 알 수 없고, 알 수 없는 것을 막으면 마법사 단계에서 정당한
입력까지 거부한다. 이 계층이 아는 것만 이 계층에서 막는다.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from tests.server_helpers import start_module_server

OK_BASE = {"calibration_num": 3, "calibration_method": "ema", "loader_mode": "default"}


@pytest.fixture()
def compiler():
    server, port = start_module_server("dx_compiler")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _generate(base, payload):
    req = urllib.request.Request(
        base + "/config/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


@pytest.mark.parametrize(
    "shape, why",
    [
        ([1, 3, -224, 224], "음수 차원"),
        ([1, 3, 0, 224], "0 차원"),
        ([1, 3, "not-a-number", 224], "문자열 차원"),
        ([1, 3, 224.5, 224], "실수 차원"),
        ([1, 3, True, 224], "bool 차원 — 파이썬에서 True 는 int 다"),
        ("1,3,224,224", "list 가 아닌 shape"),
        # 스칼라는 문자열과 다르다. 문자열은 순회되어 글자마다 걸리지만 정수는
        # 순회 자체가 TypeError 라 — 타입 가드가 없으면 400 이 아니라 500 이 된다.
        (224, "list 가 아닌 스칼라 shape"),
    ],
)
def test_unusable_shapes_are_refused(compiler, shape, why):
    code, body = _generate(compiler, {**OK_BASE, "input_shapes": {"input.1": shape}})
    assert code == 400, f"{why}: {code} 로 통과했다 — {body}"
    assert body.get("error"), f"{why}: 이유를 말하지 않는다"


def test_input_shapes_must_be_a_mapping(compiler):
    code, body = _generate(compiler, {**OK_BASE, "input_shapes": [1, 3, 224, 224]})
    assert code == 400, body


def test_a_usable_shape_still_passes(compiler):
    code, body = _generate(compiler, {**OK_BASE, "input_shapes": {"input.1": [1, 3, 224, 224]}})
    assert code == 200, body
    assert body["config"]["inputs"] == {"input.1": [1, 3, 224, 224]}


def test_batch_and_node_names_are_left_to_the_compiler(compiler):
    """문서는 batch=1 만 지원한다고 하지만, 이 API 는 ONNX 를 보지 않는다.

    여기서 막으면 모델을 아직 고르지 않은 마법사 단계의 정당한 입력까지 거부한다.
    아는 것만 막는다.
    """
    code, _ = _generate(compiler, {**OK_BASE, "input_shapes": {"whatever": [4, 3, 224, 224]}})
    assert code == 200, "이 계층이 알 수 없는 것을 막고 있다"


def test_the_calibration_num_behaviour_is_unchanged(compiler):
    """이미 있던 검증을 새 검증이 덮어쓰면 안 된다."""
    code, body = _generate(
        compiler, {**OK_BASE, "calibration_num": "many", "input_shapes": {"i": [1, 3, 224, 224]}})
    assert code == 400 and "calibration_num" in body.get("error", ""), body


def test_a_negative_calibration_num_is_refused_too(compiler):
    """티켓 범위 밖이지만 같은 구멍이다.

    프론트의 `validateCalibNum` 은 `n <= 0` 을 막는데 서버는 `int()` 만 한다 —
    타입은 보고 범위는 보지 않았다. GUI 를 거치지 않으면 -5 가 그대로 저장된다.
    input_shapes 를 고치면서 이것만 남겨두면 다음 사람이 같은 티켓을 또 쓴다.
    """
    code, body = _generate(
        compiler, {**OK_BASE, "calibration_num": -5, "input_shapes": {"i": [1, 3, 224, 224]}})
    assert code == 400, f"음수 calibration_num 이 통과했다: {body}"
