"""GstShark 성능 측정 관리 — 설치/트레이싱/파싱.

GStreamer 파이프라인의 요소별 CPU, FPS, 처리시간을 측정한다.
"""
import os
import re
import subprocess
import threading
from pathlib import Path
from dx_stream.core.config import DX_STREAM_ROOT

TRACE_DIR = DX_STREAM_ROOT / "shark_traces"

_install_log = ""
_install_done = True
_install_ok = False
_install_lock = threading.Lock()


def is_installed() -> bool:
    """GstShark tracer 플러그인 설치 여부."""
    try:
        result = subprocess.run(
            ["gst-inspect-1.0", "sharkcpuusage"],
            capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_tracer_env(trace_subdir: str = "latest") -> dict:
    """파이프라인 실행 시 추가할 환경변수 반환."""
    trace_path = TRACE_DIR / trace_subdir
    trace_path.mkdir(parents=True, exist_ok=True)
    return {
        "GST_TRACERS": "cpuusage;framerate;proctime",
        "GST_SHARK_LOCATION": str(trace_path),
    }


def install(sudo_password: str = None):
    """GstShark 설치 — 직접 명령 실행 (install_gstshark.sh 버그 우회)."""
    global _install_log, _install_done, _install_ok

    with _install_lock:
        if not _install_done:
            raise RuntimeError("Installation already in progress")
        _install_log = ""
        _install_done = False
        _install_ok = False

    def _run():
        global _install_log, _install_done, _install_ok
        import platform
        arch = platform.machine()
        util_dir = DX_STREAM_ROOT / "util"
        shark_dir = util_dir / "gst-shark"
        try:
            cmds = [
                ["sudo", "-S", "apt-get", "install", "-y",
                 "graphviz", "libgraphviz-dev", "octave",
                 "epstool", "babeltrace"],
                ["mkdir", "-p", str(util_dir)],
            ]
            if not shark_dir.exists():
                cmds.append(
                    ["git", "clone",
                     "https://github.com/RidgeRun/gst-shark.git",
                     str(shark_dir)]
                )
            cmds.extend([
                ["bash", "-c",
                 f"cd {shark_dir} && ./autogen.sh "
                 f"--prefix /usr --libdir /usr/lib/{arch}-linux-gnu"],
                ["bash", "-c", f"cd {shark_dir} && make"],
                ["sudo", "-S", "bash", "-c",
                 f"cd {shark_dir} && make install"],
                ["sudo", "-S", "ldconfig"],
            ])

            for cmd in cmds:
                with _install_lock:
                    _install_log += f"$ {' '.join(cmd)}\n"
                needs_sudo = cmd[0] == "sudo"
                proc = subprocess.Popen(
                    cmd, cwd=str(DX_STREAM_ROOT),
                    stdin=subprocess.PIPE if needs_sudo else None,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                if needs_sudo and sudo_password and proc.stdin:
                    proc.stdin.write(sudo_password + "\n")
                    proc.stdin.flush()
                    try:
                        proc.stdin.close()
                    except Exception:
                        pass
                for line in proc.stdout:
                    with _install_lock:
                        _install_log += line
                proc.wait()
                if proc.returncode != 0:
                    with _install_lock:
                        _install_log += (
                            f"\n[ERROR] 명령 실패 (exit {proc.returncode})\n"
                        )
                        _install_done = True
                        _install_ok = False
                    return

            with _install_lock:
                _install_log += "\n[OK] GstShark 설치 완료\n"
                _install_done = True
                _install_ok = True
        except Exception as e:
            with _install_lock:
                _install_log += f"\n[ERROR] {e}\n"
                _install_done = True
                _install_ok = False

    threading.Thread(target=_run, daemon=True).start()


def get_install_log() -> dict:
    with _install_lock:
        return {"log": _install_log, "done": _install_done, "ok": _install_ok}


def parse_trace(trace_dir: str) -> dict:
    """babeltrace로 CTF 로그 파싱 → {element: {tracer: avg_value}} 반환."""
    try:
        result = subprocess.run(
            ["babeltrace", str(trace_dir)],
            capture_output=True, text=True, timeout=30
        )
    except Exception:
        return {}

    metrics = {}
    # babeltrace CTF 출력 형식:
    # [...] gst_shark:cpuusage: { cpu_name = "elem0", cpu_load = 12.5 }
    # [...] gst_shark:proctime: { element_name = "elem0", time = 0.001 }
    # [...] gst_shark:framerate: { element_name = "elem0", fps = 30.0 }
    pattern = re.compile(
        r"gst_shark:(cpuusage|framerate|proctime):\s*\{[^}]*?"
        r"(?:cpu_name|element_name)\s*=\s*\"(\w+)\"[^}]*?"
        r"(?:cpu_load|fps|time)\s*=\s*([\d.]+)"
    )
    for line in result.stdout.splitlines():
        m = pattern.search(line)
        if m:
            tracer, elem, val = m.groups()
            metrics.setdefault(elem, {}).setdefault(tracer, []).append(float(val))

    summary = {}
    for elem, tracers in metrics.items():
        summary[elem] = {
            t: round(sum(vals) / len(vals), 2) for t, vals in tracers.items()
        }
    return summary


def get_latest_trace() -> dict:
    """최신 트레이스 결과 반환."""
    latest = TRACE_DIR / "latest"
    if not latest.exists():
        return {"error": "No trace data available"}
    return parse_trace(str(latest))
