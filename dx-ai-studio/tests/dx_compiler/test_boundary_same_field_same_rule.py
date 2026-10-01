"""같은 필드는 어느 엔드포인트에서나 같게 처리돼야 한다.

전수조사에서 나온 가장 설명적인 증거다. `/compile/resume` 은 꼼꼼히 검증하는데
바로 옆 `/compile` 과 `/config/generate` 는 같은 개념을 그냥 받는다:

    enhanced_scheme 알 수 없는 DXQ 키   resume 400  /compile 200
    enhanced_scheme 이 dict 가 아님      resume 400  /compile 200
    calibration method                  resume 400  /config/generate 200 ("고양이" 저장)

즉 "검증이 없다" 가 아니라 **"있는데 고르지 않다"** 이다. 그래서 새 규칙을
만들지 않는다 — resume 이 이미 옳게 하는 것을 validation.py 로 옮기고 안 부르던
곳이 부르게 한다.

이 파일 앞부분(TestResumeContractIsUnchanged)은 **리팩터링 안전장치**다. 추출
전에 기존 400 동작을 못박아, 옮기는 과정에서 동작이 바뀌지 않았음을 보증한다.

계약: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

import pytest

from tests.server_helpers import start_module_server


@pytest.fixture()
def compiler():
    server, port = start_module_server("dx_compiler")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _compile(base, **extra):
    fields = {"model_path": "/tmp/a.onnx", "config_path": "/tmp/a.json",
              "output_dir": "/tmp/o", **extra}
    b = uuid.uuid4().hex
    body = "".join(
        f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
        for k, v in fields.items()) + f"--{b}--\r\n"
    req = urllib.request.Request(
        base + "/compile", data=body.encode(),
        headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


_RESUME = {"qxnn_path": "/tmp/a.qxnn", "output_dir": "/tmp/o"}


class TestResumeContractIsUnchanged:
    """추출 전후로 동작이 같아야 한다. 리팩터링 안전장치."""

    @pytest.mark.parametrize("method", ["minmax", "ema", "iqr"])
    def test_the_three_documented_resume_methods_pass(self, compiler, method):
        """02_06_Execution_of_DX-COM.md:103 — `{minmax,ema,iqr}` (Resume-only)."""
        code, body = _post(compiler, "/compile/resume",
                           {**_RESUME, "recalibration_method": method})
        assert code == 200, f"{method} 를 막았다 — {body}"

    @pytest.mark.parametrize("method", ["고양이", "EMA", "", "  "])
    def test_other_resume_methods_are_refused(self, compiler, method):
        code, _ = _post(compiler, "/compile/resume",
                        {**_RESUME, "recalibration_method": method})
        # "" 는 "지정 안 함" 으로 취급하는 기존 동작이다 — 바꾸지 않는다.
        expected = 200 if not method.strip() else 400
        assert code == expected

    def test_unknown_dxq_keys_are_still_refused(self, compiler):
        code, body = _post(compiler, "/compile/resume",
                           {**_RESUME, "enhanced_scheme": {"DXQ-P99": {}}})
        assert code == 400 and "DXQ-P99" in body

    def test_a_non_object_enhanced_scheme_is_still_refused(self, compiler):
        code, _ = _post(compiler, "/compile/resume",
                        {**_RESUME, "enhanced_scheme": [1, 2, 3]})
        assert code == 400

    def test_q_pro_and_enhanced_scheme_are_still_mutually_exclusive(self, compiler):
        code, _ = _post(compiler, "/compile/resume",
                        {**_RESUME, "use_q_pro": True,
                         "enhanced_scheme": {"DXQ-P3": {"num_samples": 8}}})
        assert code == 400


class TestCompileNowChecksWhatResumeAlreadyChecked:
    def test_an_unknown_dxq_key_is_refused(self, compiler):
        code, body = _compile(compiler, enhanced_scheme='{"DXQ-P99": {"num_samples": 8}}')
        assert code == 400, f"resume 은 막는 값을 /compile 이 통과시켰다 — {code} {body}"

    @pytest.mark.parametrize("raw", ['[1,2,3]', '"hello"', '42'])
    def test_a_non_object_enhanced_scheme_is_refused(self, compiler, raw):
        code, body = _compile(compiler, enhanced_scheme=raw)
        assert code == 400, f"enhanced_scheme={raw} 가 통과했다 — {code} {body}"

    def test_a_valid_scheme_still_compiles(self, compiler):
        """과잉 차단 방지 — 정상 DXQ 는 계속 통과해야 한다."""
        code, body = _compile(compiler, enhanced_scheme='{"DXQ-P3": {"num_samples": 8}}')
        assert code == 200, f"정상 DXQ 를 막았다 — {code} {body}"


class TestDxqValuesMustBeObjects:
    """키 화이트리스트는 있었지만 값은 아무도 안 봤다.

    인자 **이름** 은 막지 않는다 — 02_06:493 을 보면 스킴마다 다르다
    (alpha, beta, cosim_num, num_samples). 이름을 막는 것은 과잉 차단이다.
    값이 객체인지까지만 본다.
    """

    @pytest.mark.parametrize("value", ["많이", 5, [1, 2], None])
    def test_a_scheme_value_that_is_not_an_object_is_refused(self, compiler, value):
        code, body = _post(compiler, "/compile/resume",
                           {**_RESUME, "enhanced_scheme": {"DXQ-P3": value}})
        assert code == 400, f"DXQ-P3={value!r} 가 통과했다 — {code} {body}"

    @pytest.mark.parametrize("params", [
        {"num_samples": 1024},
        {"alpha": 0.5},
        {"alpha": 0.1, "beta": 1.0, "cosim_num": 2},
        {},
    ])
    def test_documented_scheme_parameters_pass(self, compiler, params):
        """02_06:493 에 나오는 인자 조합들. 이름을 화이트리스트하지 않으므로
        전부 통과해야 한다."""
        code, body = _post(compiler, "/compile/resume",
                           {**_RESUME, "enhanced_scheme": {"DXQ-P0": params}})
        assert code == 200, f"문서에 있는 인자를 막았다: {params} — {body}"


class TestConfigCalibrationMethodIsNotTheResumeOne:
    """이름은 비슷하지만 같은 것이 아니다.

    config.json 의 calibration_method 는 `{ema, minmax}` (config-schema.md:76).
    resume 의 recalibration_method 는 `{minmax, ema, iqr}` 이고 문서가
    **"(Resume-only)"** 라고 못박았다 (02_06:103).

    하나로 합치면 iqr 이 config.json 에 들어간다. 합치지 않는 이유를 이 테스트가
    기억한다 — 안 그러면 다음 사람이 "중복" 으로 보고 합친다.
    """

    @pytest.mark.parametrize("method", ["ema", "minmax"])
    def test_the_two_documented_methods_pass(self, compiler, method):
        code, body = _post(compiler, "/config/generate",
                           {"input_shapes": {"i": [1, 3, 8, 8]},
                            "calibration_method": method})
        assert code == 200, body
        assert json.loads(body)["config"]["calibration_method"] == method

    def test_iqr_is_resume_only_and_does_not_belong_in_config_json(self, compiler):
        code, body = _post(compiler, "/config/generate",
                           {"input_shapes": {"i": [1, 3, 8, 8]},
                            "calibration_method": "iqr"})
        assert code == 400, f"iqr 이 config.json 에 들어갔다 — {code} {body}"

    @pytest.mark.parametrize("method", ["고양이", "EMA", 5, {"a": 1}, []])
    def test_anything_else_is_refused(self, compiler, method):
        code, body = _post(compiler, "/config/generate",
                           {"input_shapes": {"i": [1, 3, 8, 8]},
                            "calibration_method": method})
        assert code == 400, f"calibration_method={method!r} 가 저장됐다 — {body}"
