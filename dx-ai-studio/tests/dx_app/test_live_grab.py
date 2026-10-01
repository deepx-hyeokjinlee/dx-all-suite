"""Live frames are grabbed from Xvfb with libX11 itself — no `mss` (2026-10-02 release audit).

`mss` was never declared anywhere (requirements.txt says the studio has no third-party runtime
dependencies); it only worked because it had been pip-installed into one .venv by hand. A fresh
install failed every camera / RTSP / Continuous / Run Demo video run with
"Live streaming requires: mss (pip install mss)". The grab now uses XGetImage through ctypes,
the same libX11 the window fitting already loads.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_the_live_path_does_not_need_mss():
    for rel in ("dx_app/core/camera.py", "dx_app/core/live.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "import mss" not in src, f"{rel} 가 mss 를 쓴다"
    live = (ROOT / "dx_app/core/live.py").read_text(encoding="utf-8")
    assert "pip install mss" not in live


def test_the_missing_dependency_message_is_translated():
    i18n = (ROOT / "dx_app/static/js/i18n.js").read_text(encoding="utf-8")
    assert "'live_deps_missing': {" in i18n


@pytest.fixture()
def xvfb():
    if not shutil.which("Xvfb"):
        pytest.skip("Xvfb not installed")
    from dx_app.core import camera
    if camera._xlib() is None:
        pytest.skip("libX11 not available")
    display = ":187"
    proc = subprocess.Popen(["Xvfb", display, "-screen", "0", "320x240x24", "-nolisten", "tcp"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            if os.path.exists("/tmp/.X11-unix/X187"):
                break
            time.sleep(0.1)
        else:
            pytest.skip("Xvfb did not come up")
        yield display
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def test_a_window_on_the_virtual_display_comes_back_as_its_pixels(xvfb):
    from dx_app.core import camera
    x = camera._xlib()
    d = x.XOpenDisplay(xvfb.encode())
    assert d
    try:
        root = x.XDefaultRootWindow(d)
        # 왼쪽 위 100x60 에 빨간 (0xff0000) 창 — 나머지는 Xvfb 기본 (검정)
        w = x.XCreateSimpleWindow(d, root, 0, 0, 100, 60, 0, 0, 0xFF0000)
        x.XMapWindow(d, w)
        x.XSync(d, 0)
        time.sleep(0.2)
        img = camera._grab_screen(xvfb)
        assert img is not None and img.size == (320, 240)
        assert img.getpixel((50, 30))[:3] == (255, 0, 0)
        assert img.getpixel((300, 200))[:3] != (255, 0, 0)
    finally:
        x.XCloseDisplay(d)


def test_a_virtual_display_that_dies_is_reported_not_fatal(tmp_path):
    """Xlib 은 X 연결이 끊기면 프로세스를 exit 시킨다 — 그래서 xcb. 죽은 display 는 None, 다시 뜨면 다시 찍는다."""
    if not shutil.which("Xvfb"):
        pytest.skip("Xvfb not installed")
    script = tmp_path / "probe.py"
    script.write_text(
        "import os, subprocess, sys, time\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from dx_app.core import camera\n"
        "def up():\n"
        "    p = subprocess.Popen(['Xvfb', ':188', '-screen', '0', '160x120x24', '-nolisten', 'tcp'],\n"
        "                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "    for _ in range(100):\n"
        "        if os.path.exists('/tmp/.X11-unix/X188'): break\n"
        "        time.sleep(0.1)\n"
        "    time.sleep(0.5)\n"
        "    return p\n"
        "p = up(); a = camera._grab_screen(':188'); p.terminate(); p.wait()\n"
        "time.sleep(0.3); b = camera._grab_screen(':188')\n"
        "p = up(); c = camera._grab_screen(':188'); p.terminate(); p.wait()\n"
        "print(a.size if a else None, b, c.size if c else None)\n",
        encoding="utf-8")
    out = subprocess.run([os.sys.executable, str(script)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-800:]
    assert out.stdout.strip().splitlines()[-1] == "(160, 120) None (160, 120)"


def test_an_x_server_already_on_the_display_is_reused_not_killed(monkeypatch):
    """`pkill -f 'Xvfb :99'` 는 ':990' 이나 다른 studio 의 Xvfb 까지 죽였다. 이미 있으면 쓰고, 멈출 때는 자기 것만 끈다
    (2026-10-02 release audit A-15)."""
    if not shutil.which("Xvfb"):
        pytest.skip("Xvfb not installed")
    from dx_app.core import camera
    code = [ln.split("#", 1)[0] for ln in (ROOT / "dx_app/core/camera.py").read_text(encoding="utf-8").splitlines()]
    assert not any("pkill" in ln for ln in code), "camera.py 가 pkill 을 부른다"
    monkeypatch.setattr(camera, "_XVFB_BASE", 180)
    slot, disp, sock = 6, ":186", "/tmp/.X11-unix/X186"

    def up():
        p = subprocess.Popen(["Xvfb", disp, "-screen", "0", "160x120x24", "-nolisten", "tcp"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if os.path.exists(sock):
                break
            time.sleep(0.1)
        time.sleep(0.5)
        return p

    other = up()
    try:
        camera._ensure_xvfb(slot)
        assert slot not in camera._xvfb_procs, "남의 display 는 우리 것으로 적지 않는다"
        camera.stop_xvfb(slot)
        assert other.poll() is None, "남의 Xvfb 를 죽였다"
    finally:
        other.terminate()
        other.wait(timeout=5)
    for _ in range(50):
        if not os.path.exists(sock):
            break
        time.sleep(0.1)
    camera._ensure_xvfb(slot)
    ours = camera._xvfb_procs.get(slot)
    try:
        assert ours is not None and ours.poll() is None
        camera.stop_xvfb(slot)
        assert ours.poll() is not None, "멈추면 우리가 띄운 Xvfb 는 끈다"
    finally:
        if ours is not None and ours.poll() is None:
            ours.kill()
