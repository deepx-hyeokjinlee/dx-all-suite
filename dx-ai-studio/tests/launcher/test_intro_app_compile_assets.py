"""intro 의 App · Compiler 장면 소재 (spec 2026-09-30 intro app/compiler).

App 은 공식 sample 주행 영상의 모든 frame 에 공식 segformer 를 DX-M1 에서 돌려 구운 clip 이고
(`scripts/intro/bake_app.py`), Compiler 는 Ultralytics 공식 YOLO26n 의 실제 ONNX graph 다
(`scripts/intro/bake_compile.py`). 여기서는 굽힌 산출물이 화면이 기대는 모양과 무게를 지키는지 본다.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTRO = ROOT / "launcher" / "static" / "img" / "intro"
APP = INTRO / "app"
COMPILE = INTRO / "compile"


def test_the_app_scene_has_its_frames_and_a_light_clip():
    assert (APP / "first.webp").stat().st_size <= 250_000
    assert (APP / "seg-first.webp").stat().st_size <= 250_000
    clip = (APP / "seg.mp4").read_bytes()
    assert clip[4:8] == b"ftyp", "seg.mp4 는 MP4 여야 한다"
    assert clip.find(b"moov") < clip.find(b"mdat"), "faststart — moov 가 앞에 와야 받는 중에 재생된다"
    assert len(clip) <= 900_000
    assert not (APP / "seg.webm").exists()


def test_the_app_source_names_the_video_the_model_and_the_speed():
    src = (APP / "SOURCE.md").read_text(encoding="utf-8")
    for needle in ("blackbox-city-road.mp4", "segformer_mit-b0_512x1024.dxnn", "sample_videos.tar.gz", "FPS"):
        assert needle in src, needle


def test_the_compile_graph_is_the_real_yolo26n():
    g = json.loads((COMPILE / "graph.json").read_text(encoding="utf-8"))
    assert (COMPILE / "graph.json").stat().st_size <= 40_000
    nodes, edges = g["nodes"], g["edges"]
    assert len(nodes) == 384, "Ultralytics YOLO26n 의 ONNX node 수"
    assert sum(1 for n in nodes if n[2] == "conv") == 102
    w, h = g["stage"]
    for x, y, kind in nodes:
        assert 0 <= x <= w and 0 <= y <= h and kind in {"conv", "act", "other"}
    assert edges and all(0 <= a < len(nodes) and 0 <= b < len(nodes) and a != b for a, b in edges)


def test_the_compile_source_names_the_onnx_and_the_compiled_model():
    src = (COMPILE / "SOURCE.md").read_text(encoding="utf-8")
    for needle in ("yolo26n.onnx", "yolo26-n_640x640.dxnn", "384", "FPS"):
        assert needle in src, needle


def test_only_the_splash_timeline_owns_the_scene_flag():
    """`is-scene` (prompt 를 화면 아래로 · logo 를 비킨다) 를 장면이 각자 끄면, 앞 장면이 늦게 시작한
    날에는 그 timer 가 다음 장면이 켠 뒤에 돌아 Compiler 도중 prompt 가 가운데로 튀어 칩과 겹쳤다
    (간헐, 실측 여유 9–15ms). 박자마다 splash 한 곳이 "이번 장면이 떴는가" 로 켜고 끈다."""
    static = ROOT / "launcher" / "static"
    for js in ("intro-stream.js", "intro-app.js", "intro-compile.js"):
        assert "is-scene" not in (static / js).read_text(encoding="utf-8"), js
    splash = (static / "launcher-splash.js").read_text(encoding="utf-8")
    assert "classList.toggle('is-scene'" in splash
