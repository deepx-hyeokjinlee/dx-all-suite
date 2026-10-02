"""SR-758 이 원래 지목한 필드. `/config/generate` 의 preprocessings.

티켓은 `preprocessing.resize.width = -640` 을 들었다. 최상위 `preprocessing` 키는
없어서 그 payload 는 `{"inputs": {}}` 를 만들지만, **필드를 잘못 짚은 것은
아니었다** — `resize.width` 는 `preprocessings[]` 안에 실재하고, 재보니 거기도
검증이 없었다. 틀린 것은 JSON 중첩이지 지목한 필드가 아니다.

input_shapes 보다 나쁘다. input_shapes 는 프론트가 잘못된 값을 조용히 버려서
API 를 직접 불러야 재현됐다. 여기는 **GUI 로 그냥 된다** — 파라미터 입력칸이
`type="text"` 자유 입력이고 수집 코드가 `isNaN(num) ? raw : num` 이라 타이핑한
값이 그대로 실린다.

무엇을 막지 않는지가 더 중요하다. 저장소의 실제 config 8 개를 읽어 보면:

    {"resize": {"mode": "pad", "size": 640,
                "pad_location": "edge",          # UI 는 'EDGE' 대문자를 준다
                "pad_value": [114, 114, 114]}}   # UI 기본값은 스칼라 0
    {"transpose": {"axis": [2, 0, 1]}}           # 리스트
    {"expandDim": {"axis": 0}}                   # 스칼라

같은 파라미터가 스칼라도 되고 리스트도 되며 대소문자도 다르다. 이런 것에
규칙을 세우면 지금 도는 config 가 막힌다. 뜻이 분명한 것만 본다.

계약: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest
from tests.dx_compiler._compile_paths import compile_paths_not_under_test, compile_jobs_outside_var  # noqa: F401  (경로 정책은 이 시험의 대상이 아니다 · 작업은 tmp 에)

from tests.server_helpers import start_module_server

OK = {"loader_mode": "default", "dataset_path": "/tmp/calib",
      "input_shapes": {"images": [1, 3, 640, 640]}}

# 저장소의 실제 config 에서 그대로 가져온 전처리 사슬.
# 새 규칙이 이것을 막으면 규칙이 틀린 것이다.
REAL_CHAIN = [
    {"resize": {"mode": "pad", "size": 640, "pad_location": "edge",
                "pad_value": [114, 114, 114]}},
    {"div": {"x": 255.0}},
    {"convertColor": {"form": "BGR2RGB"}},
    {"transpose": {"axis": [2, 0, 1]}},
    {"expandDim": {"axis": 0}},
]


@pytest.fixture()
def compiler():
    server, port = start_module_server("dx_compiler")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _generate(base, preps):
    payload = {**OK, "preprocessings": preps}
    req = urllib.request.Request(
        base + "/config/generate", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


class TestRealConfigsMustKeepWorking:
    """과잉 차단 방지. 이 클래스가 실패하면 규칙이 틀린 것이다."""

    def test_the_chain_from_the_repositorys_own_configs_passes(self, compiler):
        code, body = _generate(compiler, REAL_CHAIN)
        assert code == 200, f"저장소의 실제 config 를 막았다 — {body}"
        assert body["config"]["default_loader"]["preprocessings"] == REAL_CHAIN

    @pytest.mark.parametrize("entry", [
        {"transpose": {"axis": [2, 0, 1]}},
        {"expandDim": {"axis": 0}},
        {"squeeze": {"axis": -1}},
        {"div": {"x": 255.0}},
        {"div": {"x": [255.0, 255.0, 255.0]}},
        {"subtract": {"x": -1.0}},
        {"resize": {"mode": "pad", "size": 640, "pad_value": [114, 114, 114]}},
        {"resize": {"mode": "pad", "size": 640, "pad_value": 0}},
        {"convertColor": {"form": "BGR2RGB"}},
        {"dtype": {"t": "float32"}},
        {"pil_2_cv": None},
        {"slice": {"channel": 3}},
    ])
    def test_shapes_that_vary_legitimately_are_left_alone(self, compiler, entry):
        """axis 는 음수도 리스트도 되고, x 와 pad_value 는 스칼라도 리스트도 된다.

        여기에 규칙을 세우면 정당한 config 가 막힌다. 건드리지 않는다.
        """
        code, body = _generate(compiler, [entry])
        assert code == 200, f"정당한 값을 막았다: {entry} — {body}"

    @pytest.mark.parametrize("name", ["resize2", "resize3", "resize_tv", "그런거"])
    def test_transform_names_are_not_whitelisted(self, compiler, name):
        """벤더 레지스트리(02_06:394)에 resize2·resize3·resize_tv 가 있는데 UI 는
        내보내지 않는다. UI 목록으로 막으면 정당한 config 가 거부된다. 문서
        목록이 최신이라는 보장도 없다. 이름은 컴파일 단계가 판단한다."""
        code, body = _generate(compiler, [{name: {"size": 640}}])
        assert code == 200, f"transform 이름을 막았다: {name} — {body}"


class TestUnusableSizesAreRefused:
    @pytest.mark.parametrize("width, why", [
        (-640, "음수 — 티켓이 지목한 바로 그 값"),
        (0, "0 — 크기가 될 수 없다"),
        ("abc", "문자열"),
        ("640", "숫자처럼 보이는 문자열 — GUI 자유 입력이 이것을 만든다"),
        (True, "bool — 파이썬에서 True 는 int 다"),
        (None, "없음"),
    ])
    def test_a_resize_width_that_cannot_be_a_size_is_refused(self, compiler, width, why):
        code, body = _generate(compiler, [{"resize": {"mode": "default",
                                                      "width": width, "height": 640}}])
        assert code == 400, f"{why}: width={width!r} 가 통과했다 — {body}"

    @pytest.mark.parametrize("key", ["width", "height", "size", "scale"])
    def test_every_size_like_parameter_is_checked(self, compiler, key):
        code, body = _generate(compiler, [{"resize": {"mode": "default", key: -1}}])
        assert code == 400, f"{key}=-1 이 통과했다 — {body}"

    def test_centercrop_sizes_are_checked_too(self, compiler):
        """크기 규칙은 transform 이름이 아니라 **파라미터 이름** 에 붙는다.
        resize 만 보면 centercrop 이 빠진다."""
        code, body = _generate(compiler, [{"centercrop": {"width": 0, "height": 224}}])
        assert code == 400, f"centercrop.width=0 이 통과했다 — {body}"


class TestNormalizeMustBeUsable:
    def test_a_zero_in_std_is_a_division_by_zero(self, compiler):
        code, body = _generate(compiler, [{"normalize": {"mean": [0, 0, 0],
                                                         "std": [1, 0, 1]}}])
        assert code == 400, f"std 의 0 이 통과했다 — 0 으로 나눈다. {body}"

    @pytest.mark.parametrize("std", ["많이", [1, "a", 1], 5.0, {"a": 1}])
    def test_std_must_be_a_list_of_numbers(self, compiler, std):
        code, body = _generate(compiler, [{"normalize": {"mean": [0, 0, 0], "std": std}}])
        assert code == 400, f"std={std!r} 가 통과했다 — {body}"

    def test_mean_and_std_must_describe_the_same_channels(self, compiler):
        code, body = _generate(compiler, [{"normalize": {"mean": [0, 0], "std": [1, 1, 1]}}])
        assert code == 400, f"길이가 다른 mean/std 가 통과했다 — {body}"

    @pytest.mark.parametrize("pair", [
        ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ([0.0, 0.0, 0.0], [1.0, 1.0, 1.0]),
        ([0.0], [255.0]),
        ([0, 0, 0], [255, 255, 255]),
    ])
    def test_documented_normalizations_pass(self, compiler, pair):
        """config-schema.md:140 의 표에 있는 조합들. 전부 통과해야 한다."""
        mean, std = pair
        code, body = _generate(compiler, [{"normalize": {"mean": mean, "std": std}}])
        assert code == 200, f"문서에 있는 정규화를 막았다: {pair} — {body}"


class TestTheContainerItselfMustBeUsable:
    @pytest.mark.parametrize("value, why", [
        ({"resize": {"width": 640}}, "배열이 아니라 dict"),
        ("resize 640x640", "배열이 아니라 문자열"),
        (5, "배열이 아니라 숫자"),
        (["resize"], "원소가 dict 가 아님"),
        # 길이가 1 인 것들이 중요하다. 원소 타입 가드가 없으면 len(entry) != 1 을
        # 통과해 .items() 에서 AttributeError 가 나고 400 이 아니라 500 이 된다.
        # 변이 검사에서 그 가드만 살아남아 드러났다 — "resize" 는 길이 6 이라
        # 다음 검사에 걸려서 가드의 값어치를 가리고 있었다.
        (["a"], "원소가 길이 1짜리 문자열"),
        ([["x"]], "원소가 길이 1짜리 리스트"),
        ([5], "원소가 숫자"),
        ([None], "원소가 None"),
        ([{"a": {}, "b": {}}], "원소에 transform 이 둘 — 순서를 알 수 없다"),
        ([{}], "빈 원소"),
        ([{"resize": 640}], "인자가 객체가 아님"),
    ])
    def test_a_malformed_container_is_refused(self, compiler, value, why):
        code, body = _generate(compiler, value)
        assert code == 400, f"{why}: 통과했다 — {body}"

    def test_an_absent_preprocessings_is_fine(self, compiler):
        """전처리 없이 컴파일하는 것은 정상이다."""
        payload = dict(OK)
        req = urllib.request.Request(
            compiler + "/config/generate", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            assert r.status == 200


class TestTheOtherLoaderFields:
    """preprocessings 옆에서 같이 새던 것들."""

    @pytest.mark.parametrize("value, why", [
        ("jpg", "문자열 — dx_com 이 'j','p','g' 로 순회한다"),
        ([1, 2], "숫자 원소"),
        ([""], "빈 문자열"),
        (5, "배열이 아님"),
    ])
    def test_unusable_file_extensions_are_refused(self, compiler, value, why):
        code, body = _generate_field(compiler, {"file_extensions": value})
        assert code == 400, f"{why}: 통과했다 — {body}"

    def test_the_string_message_shows_the_exact_fix(self, compiler):
        code, body = _generate_field(compiler, {"file_extensions": "jpg"})
        assert "['jpg']" in body.get("error", ""), \
            f"무엇으로 고쳐야 하는지 보여주지 않는다 — {body}"

    def test_documented_file_extensions_pass(self, compiler):
        """config-schema.md:126 의 예시."""
        code, body = _generate_field(
            compiler, {"file_extensions": ["jpeg", "png", "jpg", "bmp"]})
        assert code == 200, body
        assert body["config"]["default_loader"]["file_extensions"] == \
            ["jpeg", "png", "jpg", "bmp"]

    @pytest.mark.parametrize("value", [5, ["/tmp"], {"p": "/tmp"}, True])
    def test_a_non_string_dataset_path_is_refused(self, compiler, value):
        code, body = _generate_field(compiler, {"dataset_path": value})
        assert code == 400, f"dataset_path={value!r} 가 저장됐다 — {body}"

    def test_a_boolean_calibration_num_is_refused(self, compiler):
        """input_shapes 의 차원에서는 bool 을 막아 놓고 여기서는 안 막았다.
        int(True) 가 1 이라 `true` 가 표본 수 1 로 조용히 저장된다."""
        code, body = _generate_field(compiler, {"calibration_num": True})
        assert code == 400, f"calibration_num=True 가 1 로 저장됐다 — {body}"


def _generate_field(base, extra):
    payload = {**OK, **extra}
    req = urllib.request.Request(
        base + "/config/generate", data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())
