"""compile 경로 정책 (QA COM-A2) 을 대상으로 하지 않는 시험용 — 가짜 경로를 그대로 통과시킨다.

opt_level · enhanced_scheme · preprocessings 같은 다른 검증을 보는 시험들은 '/tmp/a.onnx' 같은 존재하지 않는
경로를 넣는다. 경로 정책 자체는 test_path_policy.py 가 실제 함수로 본다. (모듈 conftest 는 경로 설정만 하는
규칙이라 — tests/test_pytest_infra_contract.py — fixture 를 여기에 둔다.)
"""
import importlib
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def compile_jobs_outside_var(monkeypatch, tmp_path):
    """이 시험들이 띄우는 compiler 는 작업 폴더를 tmp 에 — 진짜 var/compiler/jobs 에 빈 폴더를 남기지 않는다."""
    monkeypatch.setenv("DX_COMPILER_JOB_ROOT", str(tmp_path / "compiler-jobs"))


@pytest.fixture(autouse=True)
def compile_paths_not_under_test(monkeypatch):
    pp = importlib.import_module("dx_compiler.core.path_policy")
    monkeypatch.setattr(pp, "check_input_file", lambda raw, field: Path(raw))
    monkeypatch.setattr(pp, "check_input_dir", lambda raw, field: Path(raw))
    monkeypatch.setattr(pp, "check_output_dir", lambda raw, field="output_dir": Path(raw))
