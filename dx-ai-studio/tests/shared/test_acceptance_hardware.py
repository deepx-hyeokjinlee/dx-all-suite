"""tests/acceptance/hardware.py — what the acceptance runner detects before it runs anything."""
from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("acceptance_hardware", ROOT / "tests" / "acceptance" / "hardware.py")
hw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hw)


def _fake_v4l2(monkeypatch, device_caps: int):
    """os.open/os.close and fcntl.ioctl as Linux and CPython behave for VIDIOC_QUERYCAP: a mutable buffer is
    filled in place and the call returns the ioctl's int result (0); only an immutable argument comes back as bytes."""
    monkeypatch.setattr(hw.os, "open", lambda path, flags: 7)
    monkeypatch.setattr(hw.os, "close", lambda fd: None)

    def ioctl(fd, request, arg, mutate_flag=True):
        assert request == hw._VIDIOC_QUERYCAP
        filled = bytearray(len(arg))
        filled[0:9] = b"uvcvideo\0"
        struct.pack_into("<II", filled, 84, hw._V4L2_CAP_DEVICE_CAPS | device_caps, device_caps)
        if isinstance(arg, bytearray) and mutate_flag:
            arg[:] = filled
            return 0
        return bytes(filled)

    monkeypatch.setattr(hw.fcntl, "ioctl", ioctl)


def test_a_uvc_capture_camera_is_detected(monkeypatch):
    _fake_v4l2(monkeypatch, hw._V4L2_CAP_VIDEO_CAPTURE)
    assert hw._is_capture_device("/dev/video0") is True


def test_a_metadata_node_of_the_same_camera_is_not_a_capture_device(monkeypatch):
    _fake_v4l2(monkeypatch, 0x00800000)            # V4L2_CAP_META_CAPTURE only (uvcvideo's second node)
    assert hw._is_capture_device("/dev/video1") is False


def test_probe_camera_reports_the_capture_nodes(monkeypatch):
    _fake_v4l2(monkeypatch, hw._V4L2_CAP_VIDEO_CAPTURE)
    monkeypatch.setattr(hw.glob, "glob", lambda pattern: ["/dev/video0"])
    assert hw.probe_camera() == (True, "/dev/video0")


def test_one_failing_probe_is_reported_and_never_stops_the_others(monkeypatch):
    def broken():
        raise TypeError("a bytes-like object is required, not 'int'")

    monkeypatch.delenv("DX_ACCEPT_HW", raising=False)
    monkeypatch.setattr(hw, "_PROBES", {k: (broken if k == "camera" else (lambda k=k: (True, k))) for k in hw.KINDS})
    got = hw.probe_all()
    assert set(got) == set(hw.KINDS)
    assert got["camera"][0] is False and "camera probe failed" in got["camera"][1] and "TypeError" in got["camera"][1]
    assert all(got[k] == (True, k) for k in hw.KINDS if k != "camera")


def test_an_unreadable_camera_is_reported_as_permission_denied_not_as_no_capture_device(monkeypatch):
    import errno

    def denied(path, flags):
        raise PermissionError(errno.EACCES, "Permission denied", path)

    monkeypatch.setattr(hw.os, "open", denied)
    monkeypatch.setattr(hw.glob, "glob", lambda pattern: ["/dev/video0", "/dev/video1"])
    ok, detail = hw.probe_camera()
    assert ok is False
    assert detail == "no usable camera: permission denied (/dev/video0, /dev/video1)"
    assert "not V4L2" not in detail
