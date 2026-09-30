"""Stream demo card 이미지 — 공식 sample 영상에 그 demo 의 model 을 DX-M1 에서 돌린 결과 (spec 2026-10-01
demo stage 결정 3). App Run Demo card 는 이미 실제 결과 이미지가 있고, Stream 만 비어 있었다.

bake: scripts/demo/bake_stream_thumbs.py → dx_stream/static/img/demo/<id>.webp + SOURCE.md
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dx_stream" / "static" / "img" / "demo"
BAKE = ROOT / "scripts" / "demo" / "bake_stream_thumbs.py"


def _bake():
    spec = importlib.util.spec_from_file_location("bake_stream_thumbs", BAKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_bake_table_follows_the_stream_demos():
    from dx_stream.core.demos import DEMOS

    table = _bake().PLAN
    assert sorted(table) == sorted(d["id"] for d in DEMOS)
    for d in DEMOS:
        assert table[d["id"]]["model"] == d["model"], d["id"]


def test_every_demo_has_a_small_16_9_image_or_a_recorded_reason():
    source = (OUT / "SOURCE.md").read_text(encoding="utf-8")
    for demo_id in _bake().PLAN:
        img = OUT / f"{demo_id}.webp"
        if img.exists():
            data = img.read_bytes()
            assert len(data) <= 60 * 1024, (demo_id, len(data))
            assert data[:4] == b"RIFF" and data[8:12] == b"WEBP"
            w, h = _webp_size(data)
            assert abs(w / h - 16 / 9) < 0.01, (demo_id, w, h)
        assert re.search(rf"^\| {demo_id} \|", source, re.M), f"SOURCE.md 에 demo {demo_id} 줄이 없다"


def test_the_payload_points_cards_at_the_baked_images():
    from dx_stream.core.demos import list_demo_entries

    for e in list_demo_entries():
        img = OUT / f"{e['id']}.webp"
        if img.exists():
            assert e["thumbnail"].startswith(f"/static/img/demo/{e['id']}.webp"), e["thumbnail"]
        else:
            assert not e.get("thumbnail")


def _webp_size(data: bytes) -> tuple[int, int]:
    chunk = data[12:16]
    if chunk == b"VP8 ":
        return (int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF)
    if chunk == b"VP8L":
        b = int.from_bytes(data[21:25], "little")
        return ((b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1)
    if chunk == b"VP8X":
        return (int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1)
    raise AssertionError(chunk)
