"""home-router 테스트가 공유하는 소스 로더와 히어로 칩 목록.

계약이 두 파일로 갈렸다 — 소스만 읽는 정적 계약은 블로킹 게이트에, 실제 라우터를
브라우저에서 돌리는 계약은 advisory 인 --browser 스테이지에 있다. 양쪽이 같은
`source()` 와 `HERO_CHIPS` 를 봐야 하므로 여기 한 벌만 둔다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROUTER = ROOT / "launcher" / "static" / "home-router.js"

# The four chips the hero ships with. If one of these resolves to nothing, the
# chip is wrong — a suggestion the product cannot honour is worse than none.
HERO_CHIPS = (
    "compile yolo26n to DXNN",
    "pose estimation on webcam",
    "16-channel CCTV object detection",
    "segment a video file",
)


def source() -> str:
    assert ROUTER.is_file(), "launcher/static/home-router.js is missing"
    return ROUTER.read_text(encoding="utf-8")
