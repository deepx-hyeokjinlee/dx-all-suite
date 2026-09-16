"""Agent Dev 콘솔이 자기가 시작하지 않은 실행에도 붙는지.

home 에서 시작한 실행을 여기서 이어받는 것이 `Open in DX Agent Dev` 가 원래
약속하던 일이다. 예전에는 그 버튼이 `#ask=<문장>` 만 넘겼고, 콘솔은 돌던 실행을
전혀 몰라서 "아무 일도 일어나지 않았다".

서버는 이제 실행을 들고 있다(`/api/agent/status` 의 run_id, `/api/agent/run/events`).
여기서 지키는 것은 콘솔이 그것을 **쓰는가** 이다.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "dx_agent_dev" / "static" / "js" / "console.js"


def source() -> str:
    assert SRC.is_file(), "console.js가 없습니다"
    return SRC.read_text(encoding="utf-8")


def test_the_console_knows_how_to_attach():
    src = source()
    assert "/api/agent/run/events" in src, (
        "콘솔이 붙는 경로를 모른다 — 시작한 실행만 볼 수 있다"
    )


def test_it_attaches_on_load_not_only_on_submit():
    """열릴 때 확인하지 않으면 이동해 온 사용자는 아무것도 못 본다."""
    src = source()
    m = re.search(r"async function checkStatus\(\)\s*\{(.*?)\n  \}", src, re.S)
    assert m, "checkStatus를 찾을 수 없다"
    assert "run_id" in m.group(1) or "attachIfRunning" in m.group(1), (
        "열릴 때 진행 중인 실행을 확인하지 않는다"
    )


def test_the_stream_reader_is_shared_between_start_and_attach():
    """붙는 쪽이 따로 그리면 '이어받았다'가 거짓말이 된다."""
    src = source()
    assert src.count("getReader()") <= 1, (
        "스트림 소비가 두 벌이다 — 시작과 붙기가 갈라진다"
    )
