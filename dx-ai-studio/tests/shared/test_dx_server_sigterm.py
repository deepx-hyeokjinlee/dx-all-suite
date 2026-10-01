"""모듈 서버가 SIGTERM 에 곧 끝나는지.

shared/dx_server.py 의 신호 처리기는 serve_forever() 가 도는 바로 그 main thread 에서 shutdown() 을
불렀다 — shutdown() 은 serve_forever() 가 끝나기를 기다리므로 서로를 기다리며 멈췄다. 테스트가 띄운
--port 0 서버들이 SIGTERM 을 받고도 살아남아 고아로 쌓였다 (2026-09-30, 7개). dx_monitor 는 이미
shutdown 을 다른 thread 에서 불러 피하고 있었다.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_a_module_server_exits_promptly_on_sigterm(tmp_path):
    port_file = tmp_path / "port"
    # launcher 처럼 repo 루트를 PYTHONPATH 에 (launcher/launcher.py 의 서버 띄우기와 같게)
    env = dict(os.environ, DX_PORT_FILE=str(port_file), PYTHONUNBUFFERED="1",
               PYTHONPATH=str(ROOT) + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else ""))
    proc = subprocess.Popen([sys.executable, str(ROOT / "dx_planner" / "server.py"), "--port", "0", "--no-browser"],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 20
        while not port_file.exists() and time.monotonic() < deadline:
            time.sleep(0.1)
        assert port_file.exists(), "서버가 뜨지 않았다"
        time.sleep(0.3)
        proc.send_signal(signal.SIGTERM)
        assert proc.wait(timeout=5) is not None
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_the_handler_does_not_call_shutdown_on_the_serving_thread():
    src = (ROOT / "shared" / "dx_server.py").read_text(encoding="utf-8")
    body = src[src.index("    def _register_signals(self):"):]
    body = body[:body.index("\n    def ", 10)]
    assert "threading.Thread(" in body and "target=self._server.shutdown" in body
