"""사용자가 보낸 값 때문에 나는 500 은 전부 결함이다.

500 은 "우리 잘못" 을 뜻한다. 사용자가 이상한 값을 보냈으면 400 으로 "그 값은
못 쓴다" 고 말해야 한다. 500 은 아무것도 알려주지 않으면서 서버 로그에 스택
트레이스만 남긴다.

여기 네 건은 전부 실측으로 재현했다 (2026-09-18 전수조사):

    POST /compile          opt_level='abc'    -> 500  int() 가 맨몸
    POST /api/mkdir        300자 이름          -> 500  OSError(ENAMETOOLONG) 누출
    POST /viewer/parse     path=12345         -> 500  숫자에 .strip()
    POST /compile/resume   qxnn_path=5        -> 500  같은 원인

계약: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

import pytest
from tests.dx_compiler._compile_paths import compile_paths_not_under_test  # noqa: F401  (경로 정책은 이 시험의 대상이 아니다)

from tests.server_helpers import start_module_server


@pytest.fixture()
def compiler():
    server, port = start_module_server("dx_compiler")
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()


def _post_json(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post_form(base, path, fields):
    boundary = uuid.uuid4().hex
    body = "".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
        for k, v in fields.items()) + f"--{boundary}--\r\n"
    req = urllib.request.Request(
        base + path, data=body.encode(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


_COMPILE_BASE = {
    "model_path": "/tmp/dx-probe.onnx",
    "config_path": "/tmp/dx-probe.json",
    "output_dir": "/tmp/dx-probe-out",
}


@pytest.mark.parametrize(
    "value, why",
    [
        ("abc", "숫자가 아닌 문자열"),
        ("1.5", "정수가 아닌 실수"),
        ("", "빈 값 — 빈 폼 필드로 실제 발생한다"),
    ],
)
def test_unparseable_opt_level_is_refused_not_a_crash(compiler, value, why):
    code, body = _post_form(compiler, "/compile", {**_COMPILE_BASE, "opt_level": value})
    assert code != 500, f"{why}: 사용자 입력이 서버를 터뜨렸다 — {body}"
    assert code == 400, f"{why}: 400 이어야 한다 — {code} {body}"


@pytest.mark.parametrize("value", ["-5", "999", "2"])
def test_opt_level_outside_the_documented_range_is_refused(compiler, value):
    """문서가 {0, 1} 로 못박았다 (02_06_Execution_of_DX-COM.md).

    모델을 읽어야 아는 값이 아니라 고정 열거형이므로 이 계층이 판단할 수 있다.
    """
    code, body = _post_form(compiler, "/compile", {**_COMPILE_BASE, "opt_level": value})
    assert code == 400, f"opt_level={value} 가 통과했다 — {code} {body}"


@pytest.mark.parametrize("value", ["0", "1"])
def test_the_documented_opt_levels_still_pass(compiler, value):
    """과잉 차단 방지 — 정상 값은 계속 통과해야 한다."""
    code, _ = _post_form(compiler, "/compile", {**_COMPILE_BASE, "opt_level": value})
    assert code == 200, f"정상 opt_level={value} 를 막았다"


def test_an_unusable_directory_name_is_refused_not_a_crash(compiler):
    """fs_browse.make_directory 의 docstring 은 ValueError 만 던진다고 약속한다.

    실제로는 mkdir() 이 OSError(ENAMETOOLONG) 를 던지고, server.py 는 ValueError
    만 잡으므로 그대로 새어 500 이 된다. 약속을 지키게 한다.
    """
    code, body = _post_json(compiler, "/api/mkdir", {"path": "/tmp", "name": "x" * 300})
    assert code != 500, f"긴 이름이 서버를 터뜨렸다 — {body}"
    assert code == 400, f"400 이어야 한다 — {code} {body}"


@pytest.mark.parametrize("value", [12345, ["/tmp/a"], {"p": "/tmp/a"}, True])
def test_a_non_string_viewer_path_is_refused_not_a_crash(compiler, value):
    code, body = _post_json(compiler, "/viewer/parse", {"path": value})
    assert code != 500, f"path={value!r} 가 서버를 터뜨렸다 — {body}"
    assert code == 400, f"400 이어야 한다 — {code} {body}"


@pytest.mark.parametrize("value", [5, ["/tmp/a.qxnn"], {"p": 1}])
def test_a_non_string_qxnn_path_is_refused_not_a_crash(compiler, value):
    code, body = _post_json(
        compiler, "/compile/resume", {"qxnn_path": value, "output_dir": "/tmp/o"})
    assert code != 500, f"qxnn_path={value!r} 가 서버를 터뜨렸다 — {body}"
    assert code == 400, f"400 이어야 한다 — {code} {body}"
