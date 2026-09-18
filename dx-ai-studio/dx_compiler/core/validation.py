"""경계에서 사용자 입력을 확인하는 순수 함수들.

왜 이 파일이 있나 — 2026-09-18 전수조사에서 라우트 22 개 중 12 곳에 결함이 나왔다.
원인은 각각의 버그가 아니라 하나였다: **공용 검증 헬퍼가 없어서 28 개 호출부가
각자 손으로 짰다.** 손으로 짜면 어떤 날은 꼼꼼하고(`/compile/resume`) 어떤 날은
아니다(`/compile`). 같은 필드가 엔드포인트마다 다르게 처리됐다.

그래서 **타입별이 아니라 필드 이름별로** 만든다. `validate_enhanced_scheme` 은
어느 엔드포인트에 나타나든 같은 함수다. 그것이 불일치를 구조적으로 없애는
유일한 방법이다 — 규칙이 한 군데에만 적혀 있으면 갈라질 수가 없다.

이 모듈은 HTTP 를 모른다. 정상값을 돌려주거나 ValidationError 를 던진다.
400 으로 바꾸는 일은 server.py 가 한 곳에서 한다.

설계: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md
"""
from __future__ import annotations


class ValidationError(ValueError):
    """경계에서 거부된 사용자 입력. 호출부가 400 으로 바꾼다.

    ValueError 를 상속하는 이유: 이미 ValueError 를 잡아 400 을 내는 호출부
    (`_list_dir`, `_mkdir`) 가 있고, 그 동작을 그대로 물려받는 편이
    맞다 — 둘 다 "사용자가 보낸 값이 틀렸다" 는 같은 뜻이다.
    """


# opt_level 은 모델을 읽어야 아는 값이 아니다. 벤더 문서가 고정 열거형으로
# 못박았다: dx-compiler/source/docs/02_06_Execution_of_DX-COM.md:76
#   | `--opt_level` | `{0,1}` (Default: `1`) |
_OPT_LEVELS = (0, 1)


def validate_opt_level(raw) -> int:
    """멀티파트 필드로 오므로 문자열이다. 정수로 바꾸고 범위를 본다.

    예전에는 `int(fields.get("opt_level", "1"))` 한 줄이었다. `'abc'` 도 `''` 도
    ValueError 를 그대로 흘려 500 이 됐다 — 빈 폼 필드면 `''` 는 실제로 온다.
    """
    if raw is None:
        return 1
    if isinstance(raw, bool):
        # 파이썬에서 True 는 int 의 인스턴스다. 먼저 거른다.
        raise ValidationError(f"Invalid opt_level: {raw!r} — must be one of {list(_OPT_LEVELS)}")
    if isinstance(raw, int):
        value = raw
    else:
        text = str(raw).strip()
        if not text:
            raise ValidationError(
                "Invalid opt_level: empty — must be one of " + str(list(_OPT_LEVELS)))
        try:
            value = int(text)
        except (TypeError, ValueError):
            raise ValidationError(
                f"Invalid opt_level: {raw!r} — must be one of {list(_OPT_LEVELS)}") from None
    if value not in _OPT_LEVELS:
        raise ValidationError(
            f"Invalid opt_level: {value} — must be one of {list(_OPT_LEVELS)}")
    return value


def validate_fs_path(raw, field: str, *, required: bool = True) -> str:
    """경로 필드가 문자열인지 본다.

    경로가 **어디를 가리키는지** 는 보지 않는다. `is_safe_path` 는 파일 탐색기가
    루트 전체를 훑지 않게 하는 UX 가드레일이지 보안 경계가 아니며, 컴파일 경로에
    적용하면 `/media/usb/model.onnx` 같은 멀쩡한 모델이 막힌다. 근거와 전제는
    `config.is_safe_path` 의 주석에 적어 두었다.

    여기서 막는 것은 타입뿐이다. 문자열이 아니면 `.strip()` 이 AttributeError 로
    터져 500 이 됐다.
    """
    if raw is None or raw == "":
        if required:
            raise ValidationError(f"{field} is required")
        return ""
    if not isinstance(raw, str):
        raise ValidationError(
            f"Invalid {field}: expected a path string, got {type(raw).__name__}")
    text = raw.strip()
    if not text and required:
        raise ValidationError(f"{field} is required")
    return text


def validate_node_names(raw, field: str) -> list:
    """그래프 노드 이름 목록. **문자열을 거부한다.**

    거부하는 이유가 미묘하다. 파이썬에서 문자열은 순회 가능하므로
    ``set("ab")`` 이 ``{'a','b'}`` 가 된다. 노드 이름이 한 글자인 그래프에서는
    그 두 글자가 실재하는 노드로 보이고, 서버는 **200 과 함께 사용자가 말하지
    않은 노드 두 개를 선택한다.** 오류가 없다. 아무도 모른다.

    지금까지 동작은 정확히 반대였다:

        input_nodes="ab"    -> 200, 노드 a·b 로 해석     (틀린 형태가 성공)
        input_nodes=["ab"]  -> 500, "ab 가 없다"          (맞는 형태가 실패)

    그래서 편의를 봐주지 않는다. 문자열 하나를 받아 ``[raw]`` 로 감싸주면
    친절해 보이지만, 그 순간 "ab" 가 노드 하나인지 둘인지 서버가 추측하게 된다.
    추측하지 않고 거부한다.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        raise ValidationError(
            f"Invalid {field}: expected a list of node names, got a string. "
            f"A single node must still be a list — use [{raw!r}], not {raw!r}.")
    if not isinstance(raw, (list, tuple)):
        raise ValidationError(
            f"Invalid {field}: expected a list of node names, got {type(raw).__name__}")
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(
                f"Invalid {field}: {item!r} — node names must be non-empty strings")
    return list(raw)


def validate_enhanced_scheme_json(raw, field: str = "enhanced_scheme"):
    """멀티파트로 오는 enhanced_scheme 의 **JSON 파싱만** 본다.

    예전에는 파싱에 실패하면 조용히 ``None`` 이 됐다. 사용자가 DXQ 를 요청했는데
    아무 말 없이 평범한 컴파일이 돌았다 — 요청한 것과 실행된 것이 다르고
    아무도 모른다. 조용한 오답은 오류보다 나쁘다.

    키·값 검증은 여기서 하지 않는다. `/compile/resume` 이 이미 하고 있고,
    그것을 이 모듈로 옮기는 일은 따로 한다 (계획 S3).
    """
    import json as _json

    if raw is None or raw == "":
        return None
    if not isinstance(raw, str):
        return raw
    try:
        return _json.loads(raw)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"Invalid {field}: not valid JSON — {exc}") from None


# 이름이 비슷하지만 **같은 것이 아니다.** 합치지 말 것.
#
#   config.json 의 calibration_method   : {ema, minmax}
#       config-schema.md:76 이 표로 둘만 적어 두었다.
#   resume 의 recalibration_method      : {minmax, ema, iqr}
#       02_06_Execution_of_DX-COM.md:103 이 "(Resume-only)" 라고 명시했다.
#
# 하나로 합치면 iqr 이 config.json 에 들어간다. 이 주석이 그것을 막는 유일한
# 장치다 — 없으면 다음 사람이 "중복" 으로 보고 합친다.
_CALIBRATION_METHODS = ("ema", "minmax")
_RECALIBRATION_METHODS = ("ema", "iqr", "minmax")


def validate_calibration_method(raw):
    """config.json 의 calibration_method. `{ema, minmax}` 뿐이다."""
    if raw is None or raw == "":
        return None
    # 타입 검사를 따로 두지 않는다. 문자열이 아니면 아래 membership 에서
    # 어차피 걸리고, 그 메시지가 값과 허용 집합을 둘 다 보여주므로 더 낫다.
    # (변이 검사에서 타입 분기만 살아남았다 = 아무 테스트도 구분하지 못한다
    #  = 새로 알려주는 것이 없다. 살리려고 계약을 만드는 것은 지표 맞추기다.)
    if raw not in _CALIBRATION_METHODS:
        raise ValidationError(
            f"Invalid calibration_method: {raw!r} — "
            f"must be one of {list(_CALIBRATION_METHODS)}")
    return raw


def validate_recalibration_method(raw):
    """resume 전용. `{minmax, ema, iqr}`.

    빈 문자열은 "지정 안 함" 으로 친다 — 기존 동작이고 바꾸지 않는다.
    """
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    if raw not in _RECALIBRATION_METHODS:   # 위와 같은 이유로 타입 분기 없음
        raise ValidationError(
            f"recalibration_method must be one of {sorted(_RECALIBRATION_METHODS)}")
    return raw


# 02_06_Execution_of_DX-COM.md:490 — "Supported Schemes: DXQ-P0 through DXQ-P5"
_DXQ_KEYS = ("DXQ-P0", "DXQ-P1", "DXQ-P2", "DXQ-P3", "DXQ-P4", "DXQ-P5")


def validate_enhanced_scheme(raw):
    """DXQ 스킴 묶음. 키는 화이트리스트, 값은 객체여야 한다.

    **인자 이름은 막지 않는다.** 02_06:493 을 보면 스킴마다 다르다 —
    `alpha`, `beta`, `cosim_num`, `num_samples`. 이름을 화이트리스트하면
    preprocessing transform 이름과 같은 과잉 차단이 된다. 문서 목록이
    최신이라는 보장도 없다. 값이 객체인지까지만 본다.

    `/compile/resume` 이 이미 하던 검사를 여기로 옮긴 것이다. 새 규칙이 아니다 —
    `/compile` 이 부르지 않고 있었을 뿐이다.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return _bad_scheme("enhanced_scheme must be a JSON object")
    bad = [k for k in raw if k not in _DXQ_KEYS]
    if bad:
        return _bad_scheme(f"Unknown DXQ key(s): {bad}. Valid: {sorted(_DXQ_KEYS)}")
    for key, params in raw.items():
        if not isinstance(params, dict):
            return _bad_scheme(
                f"Invalid enhanced_scheme[{key!r}]: expected an object of scheme "
                f"parameters, got {type(params).__name__}")
    return raw


def _bad_scheme(message: str):
    raise ValidationError(message)
