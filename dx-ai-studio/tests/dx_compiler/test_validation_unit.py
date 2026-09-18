"""validation.py 의 순수 함수 단위 계약.

HTTP 를 거치는 테스트(test_boundary_no_500.py)와 별개로 필요하다. 멀티파트
필드는 **항상 문자열**이라 `/compile` 로는 bool·int·None 이 도달할 수 없다.
그 분기들을 여기서 덮지 않으면 테스트 없는 코드가 된다 — 나중에 JSON 엔드포인트가
같은 검증자를 부르면 그때 처음 실행된다.

계약: docs/superpowers/specs/2026-09-18-compiler-input-validation-design.md
"""
from __future__ import annotations

import pytest

from dx_compiler.core.validation import (
    ValidationError, validate_fs_path, validate_opt_level,
)


class TestOptLevel:
    @pytest.mark.parametrize("raw, expected", [("0", 0), ("1", 1), (0, 0), (1, 1), (" 1 ", 1)])
    def test_documented_values_pass(self, raw, expected):
        assert validate_opt_level(raw) == expected

    def test_absent_means_the_documented_default(self):
        """문서 기본값은 1. 예전 코드의 `fields.get("opt_level", "1")` 과 같다."""
        assert validate_opt_level(None) == 1

    @pytest.mark.parametrize("raw", ["abc", "1.5", "", "   ", [], {}])
    def test_unparseable_is_refused(self, raw):
        with pytest.raises(ValidationError):
            validate_opt_level(raw)

    @pytest.mark.parametrize("raw", [-1, 2, 3, 999, "-5"])
    def test_outside_the_documented_range_is_refused(self, raw):
        with pytest.raises(ValidationError):
            validate_opt_level(raw)

    @pytest.mark.parametrize("raw", [True, False])
    def test_bool_is_refused(self, raw):
        """파이썬에서 True 는 int 의 인스턴스다. 먼저 거르지 않으면
        True 가 opt_level 1 로, False 가 0 으로 조용히 통과한다."""
        with pytest.raises(ValidationError):
            validate_opt_level(raw)

    @pytest.mark.parametrize("raw", ["", "   "])
    def test_an_empty_value_says_empty_not_quote_quote(self, raw):
        """빈 폼 필드는 가장 흔한 실수다. 그 메시지가 `Invalid opt_level: ''` 이면
        사용자는 자기가 뭘 안 넣었는지 알기 어렵다.

        이 계약이 없으면 빈값 분기는 죽은 코드다 — `int("")` 도 ValueError 라
        아래 except 가 어차피 잡는다. 변이 검사에서 그 분기만 살아남았고,
        그래서 분기가 실제로 하는 일(메시지)을 여기서 못박는다.
        """
        with pytest.raises(ValidationError, match="empty"):
            validate_opt_level(raw)

    def test_the_message_says_what_is_allowed(self):
        """400 은 무엇이 틀렸는지 말해야 한다. 그러지 않으면 500 과 다를 바 없다."""
        with pytest.raises(ValidationError, match=r"\[0, 1\]"):
            validate_opt_level("7")


class TestFsPath:
    def test_a_normal_path_passes_through_stripped(self):
        assert validate_fs_path("  /tmp/a.onnx ", "model_path") == "/tmp/a.onnx"

    @pytest.mark.parametrize("raw", [5, ["/tmp/a"], {"p": 1}, True, 1.5])
    def test_non_string_is_refused(self, raw):
        with pytest.raises(ValidationError, match="expected a path string"):
            validate_fs_path(raw, "model_path")

    @pytest.mark.parametrize("raw", [None, "", "   "])
    def test_empty_is_refused_when_required(self, raw):
        with pytest.raises(ValidationError, match="required"):
            validate_fs_path(raw, "model_path")

    @pytest.mark.parametrize("raw", [None, ""])
    def test_empty_is_allowed_when_optional(self, raw):
        assert validate_fs_path(raw, "dataset_path", required=False) == ""

    def test_the_message_names_the_field(self):
        """어느 필드가 틀렸는지 말하지 않으면 사용자가 고칠 수 없다."""
        with pytest.raises(ValidationError, match="qxnn_path"):
            validate_fs_path(5, "qxnn_path")

    def test_the_path_target_is_not_inspected(self):
        """이 함수는 경로가 **어디를 가리키는지** 보지 않는다 — 타입만 본다.

        `is_safe_path` 는 파일 탐색기용 UX 가드레일이지 보안 경계가 아니며,
        컴파일 경로에 적용하면 /media/usb 의 멀쩡한 모델이 막힌다.
        (스펙 R1, 2026-09-18 결정)
        """
        assert validate_fs_path("/etc/passwd", "model_path") == "/etc/passwd"
        assert validate_fs_path("/media/usb/m.onnx", "model_path") == "/media/usb/m.onnx"
