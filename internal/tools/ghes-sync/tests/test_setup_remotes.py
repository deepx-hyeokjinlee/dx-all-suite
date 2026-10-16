# SPDX-License-Identifier: Apache-2.0
"""setup_remotes.sh — the dev-checkout side of sync.conf.

Besides the two mirror/GHES remotes it now applies a third role: a repo whose
content comes from the public channel (dx_fw: the fw.bin lives only there) gets
a `ghcloud` remote plus the parent's submodule policy, so `git submodule update
--init` neither reaches for a mirror repo that does not exist nor dies on a
gitlink that the public history has never contained.

Everything runs against throwaway local checkouts — no network.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import GIT_ID, git

SETUP = Path(__file__).resolve().parents[1] / "setup_remotes.sh"
GHCLOUD = "https://github.invalid/DEEPX-AI/dx_fw.git"


@pytest.fixture
def suite(tmp_path: Path) -> Path:
    """A parent checkout (dx-runtime) with a sub checkout (dx_fw) inside it."""
    parent = tmp_path / "dx-runtime"
    sub = parent / "dx_fw"
    for d in (parent, sub):
        d.mkdir(parents=True)
        git("init", "-q", str(d))
        (d / "f").write_text("1", encoding="utf-8")
        git("add", "-A", cwd=d)
        git("commit", "-q", "-m", "c", cwd=d)
    # A real superproject registers the submodule; the policy is only written when it does.
    (parent / ".gitmodules").write_text(
        '[submodule "dx_fw"]\n\tpath = dx_fw\n\turl = ../dx_fw.git\n', encoding="utf-8")
    git("add", "-A", cwd=parent)
    git("commit", "-q", "-m", "gitmodules", cwd=parent)
    return tmp_path


def _conf(tmp_path: Path, body: str) -> Path:
    conf = tmp_path / "sync.conf"
    conf.write_text(
        "[defaults]\n"
        "src_host = https://github.invalid/mirror-org\n"
        "dst_host = https://ghes.invalid/deepx\n"
        "branch = feature/x\n"
        f"{body}",
        encoding="utf-8")
    return conf


def _run(tmp_path: Path, conf: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SETUP), "--config", str(conf), "--suite-dir", str(tmp_path), *args],
        text=True, capture_output=True, timeout=120)


def _remote(repo: Path, name: str) -> str:
    r = git("config", "--get", f"remote.{name}.url", cwd=repo, check=False)
    return r.stdout.strip()


def test_ghcloud_remote_is_added(suite):
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\nghcloud_ref = main\n")
    r = _run(suite, conf)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remote(suite / "dx-runtime" / "dx_fw", "ghcloud") == GHCLOUD, r.stdout


def test_sync_off_repo_gets_no_ghes_or_mirror_remote(suite):
    """A sync = off repo has no mirror/GHES counterpart to point at."""
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\n")
    _run(suite, conf)
    sub = suite / "dx-runtime" / "dx_fw"
    assert _remote(sub, "mirror") == "", "nothing to mirror"
    assert _remote(sub, "ghes") == "", "the code is not fetched from GHES either"


def test_parent_submodule_policy_is_set(suite):
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\n")
    _run(suite, conf)
    parent = suite / "dx-runtime"
    assert git("config", "--get", "submodule.dx_fw.url", cwd=parent).stdout.strip() == GHCLOUD
    assert git("config", "--get", "submodule.dx_fw.update", cwd=parent).stdout.strip() == "none"
    assert git("config", "--get", "submodule.dx_fw.ignore", cwd=parent).stdout.strip() == "all"


def test_dry_run_changes_nothing(suite):
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\n")
    r = _run(suite, conf, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ghcloud" in r.stdout, r.stdout
    assert _remote(suite / "dx-runtime" / "dx_fw", "ghcloud") == ""
    assert git("config", "--get", "submodule.dx_fw.url", cwd=suite / "dx-runtime", check=False).stdout.strip() == ""


def test_checkout_is_opt_in(suite):
    """Without --checkout-ghcloud the worktree is left exactly as it was; the
    command to run is printed instead."""
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\nghcloud_ref = main\n")
    sub = suite / "dx-runtime" / "dx_fw"
    before = git("rev-parse", "HEAD", cwd=sub).stdout.strip()
    r = _run(suite, conf)
    assert git("rev-parse", "HEAD", cwd=sub).stdout.strip() == before
    assert "--checkout-ghcloud" in r.stdout, r.stdout


# ── fresh clone: the ghcloud repo may not be a checkout yet ──────────────────

def _bare_ghcloud(tmp_path: Path) -> str:
    """A local stand-in for github.com/DEEPX-AI/dx_fw.git."""
    bare = tmp_path / "ghcloud" / "dx_fw.git"
    bare.parent.mkdir(parents=True, exist_ok=True)
    # `git init -b` needs git >= 2.28; the GHES runner image ships 2.25.  # py38-ok
    git("init", "-q", "--bare", str(bare))
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=bare)
    wt = tmp_path / "seed"
    wt.mkdir()
    git("init", "-q", str(wt))
    git("symbolic-ref", "HEAD", "refs/heads/main", cwd=wt)
    (wt / "release.ver").write_text("2.7.4\n", encoding="utf-8")
    git("add", "-A", cwd=wt)
    git("commit", "-q", "-m", "fw", cwd=wt)
    git("push", "-q", f"file://{bare}", "main:main", cwd=wt)
    return f"file://{bare}"


def test_missing_checkout_is_cloned_with_the_opt_in(suite, tmp_path):
    """`submodule update --init` leaves dx_fw empty (update = none), so a fresh clone
    of the parent has no checkout there — setup_remotes must be able to create it."""
    url = _bare_ghcloud(tmp_path)
    sub = suite / "dx-runtime" / "dx_fw"
    shutil.rmtree(sub)
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {url}\nghcloud_ref = main\n")
    r = _run(suite, conf, "--checkout-ghcloud")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (sub / "release.ver").is_file(), r.stdout
    assert _remote(sub, "ghcloud") == url, r.stdout
    assert git("config", "--get", "submodule.dx_fw.url", cwd=suite / "dx-runtime").stdout.strip() == url


def test_missing_checkout_without_the_opt_in_prints_the_clone_command(suite, tmp_path):
    url = _bare_ghcloud(tmp_path)
    sub = suite / "dx-runtime" / "dx_fw"
    shutil.rmtree(sub)
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {url}\n")
    r = _run(suite, conf)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "git clone" in r.stdout and "--checkout-ghcloud" in r.stdout, r.stdout
    assert not sub.exists(), "without the opt-in nothing is created"


def test_policy_is_skipped_when_the_parent_does_not_register_it(suite):
    """Writing submodule.<name>.* into a parent that has no such submodule is a no-op
    that looks like success. The parent must actually register it at this path."""
    parent = suite / "dx-runtime"
    (parent / ".gitmodules").write_text(
        '[submodule "something_else"]\n\tpath = something_else\n\turl = ../something_else.git\n',
        encoding="utf-8")
    git("add", "-A", cwd=parent)
    git("commit", "-q", "-m", "gitmodules", cwd=parent)
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\n")
    r = _run(suite, conf)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git("config", "--get", "submodule.dx_fw.url", cwd=parent, check=False).stdout.strip() == "", \
        "must not configure a submodule the parent does not have"
    assert "not registered" in r.stdout, r.stdout


def test_policy_is_applied_when_the_parent_registers_it(suite):
    """The fixture registers dx_fw in .gitmodules, so the policy is written."""
    parent = suite / "dx-runtime"
    conf = _conf(suite, f"[repo dx_fw]\npath = dx-runtime/dx_fw\nsync = off\nghcloud_url = {GHCLOUD}\n")
    r = _run(suite, conf)
    assert r.returncode == 0, r.stdout + r.stderr
    assert git("config", "--get", "submodule.dx_fw.url", cwd=parent).stdout.strip() == GHCLOUD
    assert "not registered" not in r.stdout, r.stdout
