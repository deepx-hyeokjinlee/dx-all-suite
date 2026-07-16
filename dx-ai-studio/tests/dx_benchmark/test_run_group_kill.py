"""F-25: run_model must be killed by targeted process-group kill, not broad `pkill -f run_model`."""
import inspect
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_BENCHMARK_ROOT = str(Path(__file__).resolve().parents[2] / "dx_benchmark")


def _ensure_benchmark_path():
    # Match test_runner_contracts: drop any stale `core*` (other modules also ship a
    # `core` package) and force dx_benchmark to the front before importing.
    for mod_name in list(sys.modules):
        if mod_name == "core" or mod_name.startswith("core."):
            del sys.modules[mod_name]
    if _BENCHMARK_ROOT not in sys.path:
        sys.path.insert(0, _BENCHMARK_ROOT)
    elif sys.path[0] != _BENCHMARK_ROOT:
        sys.path.remove(_BENCHMARK_ROOT)
        sys.path.insert(0, _BENCHMARK_ROOT)


def _alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def test_run_capture_kills_whole_process_group_on_timeout(tmp_path):
    """On timeout the entire spawned process group (parent + grandchildren) must die."""
    _ensure_benchmark_path()
    from core import runner_model as rm

    pidfile = tmp_path / "child.pid"
    # bash spawns a child sleep; a parent-only kill would leave the grandchild alive.
    cmd = ["bash", "-c", f"sleep 30 & echo $! > {pidfile}; wait"]
    with pytest.raises(subprocess.TimeoutExpired):
        rm._run_capture(cmd, timeout=1)
    time.sleep(0.5)
    child_pid = int(pidfile.read_text().strip())
    assert not _alive(child_pid), "grandchild sleep survived — group kill failed"


def test_cleanup_run_model_has_no_broad_pkill():
    """F-25: the broad `pkill -9 -f run_model` (kills unrelated procs) must be gone."""
    _ensure_benchmark_path()
    from core import runner_model as rm

    src = inspect.getsource(rm._cleanup_run_model)
    # the removed broad call was subprocess.run(["pkill", "-9", "-f", "run_model"], ...)
    assert '"pkill"' not in src and "'pkill'" not in src, \
        "broad pkill call still present in _cleanup_run_model"
