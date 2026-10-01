"""_cleanup_old_pids() 는 자기가 띄운 하위 서버만 죽여야 한다.

pidfile 의 번호는 이전 launcher 가 남긴 것이지만, 그 사이 재부팅되거나 서버가 먼저
죽으면 같은 번호를 무관한 프로세스가 다시 받는다. 예전 구현은 번호만 보고 process
group 째 SIGTERM/SIGKILL 했다(60d900d 는 커밋된 pidfile 경로만 막았다).

하위 서버는 `python <studio>/<module>/server.py --port 0 --no-browser` 를 setsid 로
띄운다(start_sub_server). 그 모양일 때만 종료한다.
"""
import json
import os
import signal
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="/proc 기반")


def _spawn(argv, setsid=True):
    return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            preexec_fn=os.setsid if setsid else None)


def _alive(proc):
    return proc.poll() is None


@pytest.fixture
def launcher_mod(tmp_path, monkeypatch):
    from launcher import launcher as L
    studio = tmp_path / "studio"
    (studio / "dx_fake").mkdir(parents=True)
    (studio / "dx_fake" / "server.py").write_text("import time\ntime.sleep(60)\n")
    monkeypatch.setattr(L, "STUDIO_DIR", studio)
    monkeypatch.setattr(L, "_PIDFILE", tmp_path / ".launcher_pids")
    return L


@pytest.fixture
def procs():
    started = []
    yield started
    for p in started:
        if _alive(p):
            p.kill()
        p.wait(timeout=5)


def _write_pids(L, mapping):
    L._PIDFILE.write_text(json.dumps({k: p.pid for k, p in mapping.items()}))


def test_unrelated_process_with_a_recorded_pid_survives(launcher_mod, procs):
    L = launcher_mod
    stranger = _spawn([sys.executable, "-c", "import time; time.sleep(60)"])
    procs.append(stranger)
    _write_pids(L, {"DX Stream": stranger})
    L._cleanup_old_pids()
    time.sleep(0.2)
    assert _alive(stranger), "번호만 같은 무관한 프로세스를 죽였다"
    assert not L._PIDFILE.exists()


def test_server_py_outside_the_studio_survives(launcher_mod, procs, tmp_path):
    L = launcher_mod
    other = tmp_path / "elsewhere" / "server.py"
    other.parent.mkdir()
    other.write_text("import time\ntime.sleep(60)\n")
    p = _spawn([sys.executable, str(other), "--port", "0", "--no-browser"])
    procs.append(p)
    _write_pids(L, {"DX Stream": p})
    L._cleanup_old_pids()
    time.sleep(0.2)
    assert _alive(p), "studio 밖의 server.py 까지 죽였다"


def test_our_orphaned_sub_server_is_killed(launcher_mod, procs):
    L = launcher_mod
    server_py = L.STUDIO_DIR / "dx_fake" / "server.py"
    ours = _spawn([sys.executable, str(server_py), "--port", "0", "--no-browser"])
    procs.append(ours)
    _write_pids(L, {"DX Fake": ours})
    L._cleanup_old_pids()
    ours.wait(timeout=5)
    assert not _alive(ours)


def test_group_kill_only_when_the_pid_leads_its_own_group(launcher_mod, procs):
    """우리 서버라도 group leader 가 아니면(setsid 없이 떴으면) group 째 보내지 않는다 —
    그 group 은 launcher 를 띄운 셸의 것이다."""
    L = launcher_mod
    server_py = L.STUDIO_DIR / "dx_fake" / "server.py"
    # 같은 세션 안의 별도 group — setsid 로 띄우면 다른 세션이라 setpgid 로 합류할 수 없다
    leader = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, process_group=0)
    procs.append(leader)
    # leader 의 group 안에 우리 server.py 를 setsid 없이 넣는다
    member = subprocess.Popen([sys.executable, str(server_py), "--port", "0", "--no-browser"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              preexec_fn=lambda: os.setpgid(0, leader.pid))
    procs.append(member)
    assert os.getpgid(member.pid) == leader.pid
    _write_pids(L, {"DX Fake": member})
    L._cleanup_old_pids()
    member.wait(timeout=5)
    time.sleep(0.2)
    assert not _alive(member)
    assert _alive(leader), "group 째 보내 같은 group 의 다른 프로세스까지 죽였다"


def test_unreadable_pidfile_is_removed_without_killing(launcher_mod):
    L = launcher_mod
    L._PIDFILE.write_text("{not json")
    L._cleanup_old_pids()
    assert not L._PIDFILE.exists()


@pytest.mark.parametrize("payload", ["[1, 2]", '"x"', "null", '{"DX Stream": "123"}'])
def test_wrong_shape_pidfile_does_not_crash_startup(launcher_mod, payload):
    L = launcher_mod
    L._PIDFILE.write_text(payload)
    L._cleanup_old_pids()
    assert not L._PIDFILE.exists()


def test_sigkill_rechecks_identity(launcher_mod, monkeypatch):
    """SIGTERM 뒤 0.3초 사이 번호가 재사용될 수 있다 — SIGKILL 전에 다시 확인한다."""
    L = launcher_mod
    L._PIDFILE.write_text(json.dumps({"DX Fake": 424242}))
    answers = iter([True, False])
    monkeypatch.setattr(L, "_is_our_sub_server", lambda pid: next(answers))
    sent = []
    monkeypatch.setattr(L.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(L.os, "killpg", lambda pid, sig: sent.append(("pg", sig)))
    monkeypatch.setattr(L.os, "kill", lambda pid, sig: sent.append(("p", sig)))
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    L._cleanup_old_pids()
    assert ("pg", signal.SIGTERM) in sent
    assert all(sig != signal.SIGKILL for _, sig in sent), sent
