"""pyproject 는 requires-python >= 3.8 — 런타임 코드는 3.9+ 문자열 API 를 쓰지 않는다 (2026-10-02 release audit).

vermin (stdlib · 문법 검사) 은 3.8 을 통과하지만 변수에 대한 `str.removesuffix` 는 타입을 몰라 놓친다.
그 둘만 따로 막는다. Ubuntu 20.04 는 Python 3.8 이다."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKIP = {".venv", "var", "tests", "scripts", "tools", "node_modules"}


def test_runtime_code_runs_on_the_declared_python_floor():
    assert 'requires-python = ">=3.8"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    offenders = []
    for p in ROOT.rglob("*.py"):
        if SKIP & set(p.relative_to(ROOT).parts):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.remove(suffix|prefix)\(", line):
                offenders.append(f"{p.relative_to(ROOT)}:{i}")
    assert offenders == [], "Python 3.9+ API: " + ", ".join(offenders)
