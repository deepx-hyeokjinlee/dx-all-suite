"""Run Demo 카드의 썸네일은 새로 clone 한 곳에서도 나온다 (2026-10-01).

카드는 dx_modelzoo/data/thumbnails/*.jpg 만 읽었는데 그 폴더는 .gitignore 다 (원본은 NPU 로 다시 만든다).
그래서 이 PC 밖에서는 27 장 모두 빈 카드였다. Model Zoo 화면이 쓰는 것과 같은, 저장소에 들어 있는
data/optimized/thumbnails/<stem>-jpg.webp 로도 찾는다.
"""
import pytest

from dx_app.core import demos


@pytest.fixture
def no_raw_thumbs(tmp_path, monkeypatch):
    monkeypatch.setattr(demos, "_THUMBS_DIR", tmp_path / "thumbnails")   # clone 한 직후 — 원본 폴더 없음
    monkeypatch.setattr(demos, "_THUMB_INDEX", None)
    yield
    demos._THUMB_INDEX = None


def test_every_demo_card_finds_a_committed_thumbnail(no_raw_thumbs):
    payload = demos.build_demos_payload()
    if not payload.get("demos"):
        pytest.skip("run_demo.sh 를 읽지 못했다")
    missing = [d["model_name"] for d in payload["demos"] if not d.get("thumbnail")]
    assert not missing, missing
    for d in payload["demos"]:
        name = d["thumbnail"].split("f=", 1)[1]
        fp = demos.thumbnail_path(name)
        assert fp is not None and fp.is_file(), name
        assert demos._OPT_THUMBS_DIR in fp.parents


def test_a_raw_thumbnail_still_wins_when_present(tmp_path, monkeypatch):
    raw = tmp_path / "thumbnails"
    raw.mkdir()
    (raw / "yolov7.jpg").write_bytes(b"\xff\xd8raw")
    monkeypatch.setattr(demos, "_THUMBS_DIR", raw)
    monkeypatch.setattr(demos, "_THUMB_INDEX", None)
    try:
        assert demos._resolve_thumb("yolov7") == "yolov7.jpg"
        assert demos.thumbnail_path("yolov7.jpg") == (raw / "yolov7.jpg").resolve()
    finally:
        demos._THUMB_INDEX = None


@pytest.mark.parametrize("bad", ["../../server.py", "/etc/passwd", "..%2f..%2fserver.py", "x.py"])
def test_the_route_stays_inside_the_thumbnail_dirs(no_raw_thumbs, bad):
    assert demos.thumbnail_path(bad) is None
