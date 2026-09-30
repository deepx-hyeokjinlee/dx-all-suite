"""튜토리얼의 아이콘도 sprite 한 벌 (spec 2026-09-29 아이콘 체계 단계 5).

예전: 구역 icon 은 이모지 ('🎬'), 제목은 '⚙️ 설정 & 설치', 본문은 "✅이면 완료", "①번 카드". 이제
- 구역 icon 은 sprite 이름 (tutorial-engine.js _dxtSectionIcon 이 그린다),
- 제목 · 설명은 글자만,
- 본문이 화면의 표시를 가리킬 때는 {{i:name}} (엔진이 그 아이콘으로 바꾼다), ①–⑥ 은 숫자.
옮긴 모듈은 아래 MIGRATED 에 오른다 — 옮긴 뒤 이모지가 다시 들어오지 않게.
"""
from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = (ROOT / "shared" / "static" / "tutorial-engine.js").read_text(encoding="utf-8")
SPRITE = (ROOT / "shared" / "static" / "dx-icons.svg").read_text(encoding="utf-8")
gate = importlib.import_module("scripts.emoji_gate")
SYMBOLS = set(re.findall(r'<symbol id="([^"]+)"', SPRITE))

MIGRATED = [
    "dx_planner/static/js/tutorial.js",
    "dx_agent_dev/static/js/tutorial.js",
    "dx_benchmark/static/js/tutorial.js",
    "dx_compiler/static/js/tutorial.js",
    "dx_modelzoo/static/js/tutorial.js",
    "dx_monitor/static/js/tutorial.js",
]


def test_the_engine_turns_icon_tokens_into_sprite_icons():
    assert "function _dxtExpandIcons(" in ENGINE
    assert ENGINE.count("_dxtExpandIcons(this._t(step.content))") == 2
    assert "/^[a-z0-9_-]+$/" in ENGINE, "task-object_detection 같은 이름도 구역 아이콘이 되어야 한다"


@pytest.mark.parametrize("rel", MIGRATED)
def test_a_migrated_tutorial_has_no_emoji_left(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert gate.count(src) == 0, sorted({c for c in src if gate.count(c)})


@pytest.mark.parametrize("rel", MIGRATED)
def test_its_section_icons_and_tokens_are_real_symbols(rel):
    src = (ROOT / rel).read_text(encoding="utf-8")
    names = re.findall(r"\bicon\s*:\s*'([^']+)'", src) + re.findall(r"\{\{i:([a-z0-9_-]+)\}\}", src)
    missing = sorted({n for n in names if n not in SYMBOLS})
    assert not missing, missing
