# SPDX-License-Identifier: Apache-2.0
"""Contract tests for `.deepx/tools/scripts/gate_mode.sh` — decides how the suite
harness gate checks out the sub-repos:

  branch-tip  (default) same-name branch tip, default branch if absent
  pointer     the commits recorded by the suite commit (integration truth)

pointer is chosen automatically when the pushed / PR'd range changed a submodule
gitlink (e.g. update-submodule.yml's `ci(...): Update dx-runtime` commit), or on
workflow_dispatch with --input-mode pointer."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _suite_root(start: Path) -> Path:
    cur = start.resolve()
    marker = Path(".deepx") / "tools" / "src" / "dx_agent_dev_gen" / "cli.py"
    for _ in range(10):
        if (cur / marker).is_file():
            return cur
        cur = cur.parent
    raise RuntimeError("suite root not found")


SCRIPT = _suite_root(Path(__file__)) / ".deepx" / "tools" / "scripts" / "gate_mode.sh"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True, capture_output=True).stdout.strip()


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> dict:
    """A: file → B: gitlink `sub` added (pointer change) → C: file edited (no gitlink change)."""
    r = tmp_path_factory.mktemp("gate-mode-repo")
    _git(r, "init", "-q"); _git(r, "symbolic-ref", "HEAD", "refs/heads/main")   # `init -b` needs git >= 2.28; GHES runners have 2.25
    _git(r, "config", "user.email", "t@example.com"); _git(r, "config", "user.name", "t")
    (r / "README.md").write_text("a\n"); _git(r, "add", "README.md"); _git(r, "commit", "-q", "-m", "A")
    a = _git(r, "rev-parse", "HEAD")
    fake_sha = "1" * 40
    _git(r, "update-index", "--add", "--cacheinfo", f"160000,{fake_sha},sub")
    _git(r, "commit", "-q", "-m", "B: bump sub")
    b = _git(r, "rev-parse", "HEAD")
    (r / "README.md").write_text("c\n"); _git(r, "add", "README.md"); _git(r, "commit", "-q", "-m", "C")
    c = _git(r, "rev-parse", "HEAD")
    return {"path": r, "a": a, "b": b, "c": c}


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd, text=True, capture_output=True, timeout=60)


def _kv(out: str) -> dict:
    return dict(l.split("=", 1) for l in out.splitlines() if "=" in l)


def test_script_exists_and_bash_syntax():
    assert SCRIPT.is_file()
    assert subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True).returncode == 0


def test_help():
    r = _run("--help")
    assert r.returncode == 0 and "branch-tip" in r.stdout and "pointer" in r.stdout


def test_gitlink_change_selects_pointer(repo):
    r = _run("--event", "push", "--from", repo["a"], "--to", repo["b"], "--repo", str(repo["path"]))
    assert r.returncode == 0, r.stderr
    kv = _kv(r.stdout)
    assert kv["mode"] == "pointer" and "sub" in kv["reason"]


def test_no_gitlink_change_selects_branch_tip(repo):
    kv = _kv(_run("--event", "pull_request", "--from", repo["b"], "--to", repo["c"], "--repo", str(repo["path"])).stdout)
    assert kv["mode"] == "branch-tip"


def test_range_spanning_a_gitlink_change_selects_pointer(repo):
    kv = _kv(_run("--event", "push", "--from", repo["a"], "--to", repo["c"], "--repo", str(repo["path"])).stdout)
    assert kv["mode"] == "pointer"


@pytest.mark.parametrize("base", ["", "0" * 40])
def test_missing_or_zero_base_defaults_to_branch_tip(repo, base):
    kv = _kv(_run("--event", "push", "--from", base, "--to", repo["c"], "--repo", str(repo["path"])).stdout)
    assert kv["mode"] == "branch-tip" and "no base" in kv["reason"]


def test_unknown_base_defaults_to_branch_tip_with_reason(repo):
    kv = _kv(_run("--event", "push", "--from", "f" * 40, "--to", repo["c"], "--repo", str(repo["path"])).stdout)
    assert kv["mode"] == "branch-tip" and "not available" in kv["reason"]


@pytest.mark.parametrize("m", ["pointer", "branch-tip"])
def test_dispatch_passes_input_through(repo, m):
    kv = _kv(_run("--event", "workflow_dispatch", "--input-mode", m, "--repo", str(repo["path"])).stdout)
    assert kv["mode"] == m and "workflow_dispatch" in kv["reason"]


def test_dispatch_without_input_defaults_to_branch_tip(repo):
    kv = _kv(_run("--event", "workflow_dispatch", "--repo", str(repo["path"])).stdout)
    assert kv["mode"] == "branch-tip"


def test_bad_input_mode_exits_2(repo):
    assert _run("--event", "workflow_dispatch", "--input-mode", "bogus", "--repo", str(repo["path"])).returncode == 2


def test_unknown_flag_exits_2():
    assert _run("--nope").returncode == 2
