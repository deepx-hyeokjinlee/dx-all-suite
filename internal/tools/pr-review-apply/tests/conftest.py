# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import sys
from pathlib import Path
import pytest

HERE = Path(__file__).resolve().parent
TOOL_DIR = HERE.parent
sys.path.insert(0, str(TOOL_DIR))          # import pr_review_apply without installing
FIXTURE = HERE / "fixtures" / "pr91.mhtml"
CLI = TOOL_DIR / "pr_review_apply.py"


@pytest.fixture
def fixture_mhtml() -> Path:
    assert FIXTURE.is_file(), "run tests/make_fixture.py <full.mhtml> first"
    return FIXTURE


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    d = tmp_path / ".dx-pr-review"
    d.mkdir()
    return d
