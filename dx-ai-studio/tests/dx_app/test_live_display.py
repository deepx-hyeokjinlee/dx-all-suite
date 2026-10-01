"""실시간 연속 실행 (live) 의 화면 — 2026-10-01 Xvfb 를 깔고 처음 실제로 돌려 본 결과.

1. 창: dx_app 의 C++ runner 는 OpenCV 창을 Qt 기본 크기 (400x300) 로 띄운다 (per-model 8d0b748 의 DisplayPump 는
   setInitialWindowSize 를 아무도 부르지 않는다). studio 는 1280x720 Xvfb 화면 전체를 찍으므로 영상이 왼쪽 위
   구석에 작게, 나머지는 검게 나왔다 → 창을 화면 크기로 맞춘다 (libX11, 새 의존성 없음).
2. 테두리: Qt 창의 toolbar · status bar · 비율을 지키느라 남는 회색 여백을 잘라낸다.
3. 통계: runner 는 [DET] 같은 프레임별 줄을 --show-log 일 때만 찍는다 — 없으면 poll 이 frames 0 · FPS 0.
"""
import shutil
import subprocess
import time

import pytest
from PIL import Image, ImageDraw

from dx_app.core import camera

_CHROME = (239, 239, 239)


def _qt_window(w=1280, h=720, img=(43, 1237, 28, 700)):
    """x_fit.png 와 같은 모양: 회색 바탕 · 위 toolbar 글자 · 가운데 영상."""
    im = Image.new("RGB", (w, h), _CHROME)
    d = ImageDraw.Draw(im)
    # 실제 Qt toolbar 처럼 글자가 길다 — 그 줄의 회색은 절반 남짓 (실측 0.44–0.53)
    for y in range(10, 20):
        for x0 in range(8, w - 40, 14):
            d.line([x0, y, x0 + 6, y], fill=(20, 20, 20))
    x0, x1, y0, y1 = img
    d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=(12, 12, 16))
    d.rectangle([x0 + 100, y0 + 200, x0 + 300, y0 + 500], outline=(0, 0, 255), width=3)
    return im


def test_the_qt_chrome_is_cropped_away():
    box = camera._content_box(_qt_window())
    assert box is not None
    x0, y0, x1, y1 = box
    assert abs(x0 - 43) <= 6 and abs(x1 - 1237) <= 6, box
    assert abs(y0 - 28) <= 6 and abs(y1 - 700) <= 6, box


def test_a_portrait_video_keeps_its_wide_margins_out():
    """세로 영상 (480x640) 은 좌우 여백이 화면의 절반을 넘는다 — 줄만 보면 영상 줄도 회색이 많다."""
    box = camera._content_box(_qt_window(img=(371, 909, 28, 700)))
    assert box is not None
    x0, y0, x1, y1 = box
    assert abs(x0 - 371) <= 6 and abs(x1 - 909) <= 6, box
    assert abs(y0 - 28) <= 6 and abs(y1 - 700) <= 6, box


def test_a_frame_without_chrome_is_left_alone():
    im = Image.new("RGB", (1280, 720), (30, 60, 90))
    assert camera._content_box(im) in (None, (0, 0, 1280, 720))


def test_the_live_frame_keeps_its_aspect():
    out = camera._frame_jpeg(_qt_window())
    w, h = Image.open(__import__("io").BytesIO(out)).size
    assert w <= 960 and h <= 540
    assert abs(w / h - (1194 / 672)) < 0.03, (w, h)


@pytest.mark.skipif(not shutil.which("Xvfb"), reason="Xvfb 없음")
def test_the_window_is_fitted_to_the_virtual_screen():
    import ctypes
    display = ":131"
    xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", "1280x720x24", "-ac"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1)
        x = camera._xlib()
        if x is None:
            pytest.skip("libX11 없음")
        d = x.XOpenDisplay(display.encode())
        assert d
        win = x.XCreateSimpleWindow(d, x.XDefaultRootWindow(d), 0, 0, 400, 300, 0, 0, 0)
        x.XMapWindow(d, win)
        x.XSync(d, 0)
        assert camera._fit_windows(display, 1280, 720) >= 1
        x.XSync(d, 0)
        root, gx, gy = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_int()
        gw, gh, bw, depth = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
        x.XGetGeometry(d, win, ctypes.byref(root), ctypes.byref(gx), ctypes.byref(gy),
                       ctypes.byref(gw), ctypes.byref(gh), ctypes.byref(bw), ctypes.byref(depth))
        assert (gw.value, gh.value) == (1280, 720)
        x.XCloseDisplay(d)
    finally:
        xvfb.terminate()
        xvfb.wait(timeout=5)


def test_live_cpp_runs_print_per_frame_lines(tmp_path, monkeypatch):
    from dx_app.core import live

    model = tmp_path / "m.dxnn"
    model.write_bytes(b"DXNN")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"v")
    build = tmp_path / "build"
    build.mkdir()
    (build / "demo_async").write_text("")
    captured = {}

    class FakeProc:
        pid = 1

        def __init__(self, cmd, **kw):
            captured["cmd"] = cmd

        def poll(self):
            return None

    monkeypatch.setattr(live, "BUILD_DIR", build)
    monkeypatch.setattr(live, "resolve_model_path", lambda f, r: model)
    monkeypatch.setattr(live, "_ensure_xvfb", lambda s: None)
    monkeypatch.setattr(live.shutil if hasattr(live, "shutil") else shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(live.subprocess, "Popen", FakeProc)
    r = live.run_inference_live("demo", "object_detection", "m.dxnn", lang="cpp", variant="async",
                                input_type="video", video_path=str(video), slot_idx=7)
    live._live_procs.pop(7, None)
    assert r.get("status") == "started", r
    assert "--show-log" in captured["cmd"]


def test_det_frames_are_counted_as_frames_not_detections():
    """[DET] 는 검출 하나에 한 줄 — 프레임 번호가 없다. 줄 수를 프레임으로 세면 FPS 가 470 이 됐다 (yolov12-n, 실제
    ~60). 한 프레임의 검출은 신뢰도 내림차순으로 찍히므로 신뢰도가 다시 오르는 곳이 새 프레임이다 — 실제 로그에서
    yolov12-n 478/478 · RT-DETR r18 190/190 프레임이 맞았다. 검출이 없는 프레임은 세지 못한다 (하한)."""
    from dx_app.core import live
    log = "\n".join([
        "[DET] person 0.91 1 2 3 4 1920 1080", "[DET] person 0.72 1 2 3 4 1920 1080", "[DET] bag 0.30 1 2 3 4 1920 1080",
        "[DET] person 0.88 1 2 3 4 1920 1080", "[DET] person 0.40 1 2 3 4 1920 1080",
        "[DET] person 0.95 1 2 3 4 1920 1080",
    ])
    t = live._parse_task_tags(log)
    assert t["tag"] == "DET" and len(t["lines"]) == 6
    assert t["frame_count"] == 3
