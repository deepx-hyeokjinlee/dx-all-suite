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
