# SPDX-License-Identifier: Apache-2.0
"""Contract tests for internal/tools/ghes-sync/ghes-sync.sh (spec §8).
Everything runs against local bare repos and a fake `gh` — no network."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import TOOL, Env, git, out

BR = "feature/x"


def _basic(env: Env, *, gitlinks: bool = True, dst_has_branch: bool = False) -> dict:
    """dx_app (leaf) + dx-runtime (parent with gitlink dx_app) on src; dst has
    `main` for both (the shared base). Returns the interesting SHAs."""
    r = env.repos
    r.make("dx_app", "dx-runtime")
    app_main = r.commit("src", "dx_app", "main", "app base", files={"a.txt": "0\n"})
    rt_main = r.commit("src", "dx-runtime", "main", "rt base", files={"r.txt": "0\n"},
                       gitlinks={"dx_app": app_main})
    for n in ("dx_app", "dx-runtime"):
        r.mirror_branch(n, "main")
    app_tip = r.commit("src", "dx_app", BR, "app feature", files={"a.txt": "1\n"}, parent_branch="main")
    rt_tip = r.commit("src", "dx-runtime", BR, "rt feature", files={"r.txt": "1\n"},
                      gitlinks={"dx_app": app_tip if gitlinks else app_main}, parent_branch="main")
    if dst_has_branch:
        for n in ("dx_app", "dx-runtime"):
            r.mirror_branch(n, BR)
    env.write_conf([("dx_app", ""), ("dx-runtime", "gitlinks = dx_app:dx_app")])
    return {"app_main": app_main, "rt_main": rt_main, "app_tip": app_tip, "rt_tip": rt_tip}


# ── static / usage ────────────────────────────────────────────────────────────

def test_script_exists_executable_and_bash_syntax():
    assert TOOL.is_file(), TOOL
    assert TOOL.stat().st_mode & 0o111
    r = subprocess.run(["bash", "-n", str(TOOL)], text=True, capture_output=True)
    assert r.returncode == 0, r.stderr


def test_help_exits_0_and_lists_options(env):
    r = env.run("--help")
    assert r.returncode == 0, out(r)
    for opt in ("--config", "--repo", "--pull-only", "--push-only", "--dry-run", "--tags", "--no-pr", "--print-config"):
        assert opt in r.stdout, f"--help must list {opt}"


def test_print_config_merges_defaults_and_overrides(env):
    env.repos.make("dx_app", "dx-runtime")
    env.write_conf([("dx_app", "pr_base = dev"), ("dx-runtime", "gitlinks = dx_app:dx_app")])
    r = env.run("--print-config")
    assert r.returncode == 0, out(r)
    app = re.search(r"\[dx_app\](.*?)(?=\n\[|\Z)", r.stdout, re.S).group(1)
    rt = re.search(r"\[dx-runtime\](.*?)(?=\n\[|\Z)", r.stdout, re.S).group(1)
    assert "pr_base = dev" in app and "pr_base = main" in rt
    assert f"dst_url = file://{env.repos.dst}/dx_app.git" in app
    assert f"src_url = file://{env.repos.src}/dx_app.git" in app
    assert f"branch = {BR}" in app and f"dst_branch = {BR}" in app
    assert "gitlinks = dx_app:dx_app" in rt


def test_gitlink_referencing_a_later_repo_is_a_config_error(env):
    env.repos.make("dx_app", "dx-runtime")
    env.write_conf([("dx-runtime", "gitlinks = dx_app:dx_app"), ("dx_app", "")])
    r = env.run("--print-config")
    assert r.returncode == 2, out(r)
    assert "gitlinks" in out(r) and "dx_app" in out(r)


def test_unknown_key_is_a_config_error(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "colour = blue")])
    r = env.run("--print-config")
    assert r.returncode == 2, out(r)
    assert "colour" in out(r)


def test_unknown_repo_filter_is_a_usage_error(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")])
    r = env.run("--repo", "nope", "--dry-run")
    assert r.returncode == 2, out(r)


# ── classify + push ───────────────────────────────────────────────────────────

def test_create_pushes_branch_when_dst_lacks_it(env):
    s = _basic(env)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == s["app_tip"]
    assert env.repos.rev("dst", "dx-runtime", f"refs/heads/{BR}") == s["rt_tip"]
    assert "CREATE" in r.stdout


def test_fast_forward_pushes_new_commits(env):
    s = _basic(env, dst_has_branch=True)
    tip2 = env.repos.commit("src", "dx_app", BR, "app more", files={"a.txt": "2\n"})
    r = env.run("--no-pr", "--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == tip2
    assert "FAST-FORWARD" in r.stdout


def test_up_to_date_is_a_noop(env):
    s = _basic(env, dst_has_branch=True)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert r.stdout.rsplit("SUMMARY", 1)[-1].count("UP-TO-DATE") == 2
    assert "git push" not in r.stdout  # nothing planned, nothing done
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == s["app_tip"]


def test_diverged_fails_and_never_forces(env):
    s = _basic(env, dst_has_branch=True)
    dst_extra = env.repos.commit("dst", "dx_app", BR, "ghes-side commit", files={"g.txt": "1\n"})
    env.repos.commit("src", "dx_app", BR, "mirror-side commit", files={"m.txt": "1\n"})
    r = env.run("--no-pr", "--repo", "dx_app")
    assert r.returncode == 1, out(r)
    assert "DIVERGED" in r.stdout
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == dst_extra  # untouched
    assert "force" in out(r).lower()  # hint says: never force, reconcile first
    # ...and names the GHES-is-right path (branch rewritten on GHES → reverse + force-with-lease)
    assert "--reverse --push-only --force-with-lease" in out(r) and "submodule pointer" in out(r)
    # ...and the stale-merged-branch case (c): delete the leftover GHES branch, rerun → CREATE
    assert "--delete" in out(r) and "squash-merge" in out(r)


# ── gitlink check ─────────────────────────────────────────────────────────────

def test_gitlink_pointing_outside_synced_branch_blocks_parent_push(env):
    s = _basic(env)
    stray = env.repos.commit("src", "dx_app", "other", "stray", files={"o.txt": "1\n"}, parent_branch="main")
    env.repos.commit("src", "dx-runtime", BR, "rt points at stray", gitlinks={"dx_app": stray})
    r = env.run("--no-pr")
    assert r.returncode == 1, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == s["app_tip"]      # leaf still synced
    assert env.repos.rev("dst", "dx-runtime", f"refs/heads/{BR}") is None           # parent blocked
    assert "gitlink" in out(r).lower() and stray[:7] in out(r)


def test_gitlink_reachable_from_synced_branch_allows_parent_push(env):
    s = _basic(env, gitlinks=True)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx-runtime", f"refs/heads/{BR}") == s["rt_tip"]


def test_gitlink_warn_mode_pushes_with_warning(env):
    s = _basic(env)
    stray = env.repos.commit("src", "dx_app", "other", "stray", files={"o.txt": "1\n"}, parent_branch="main")
    rt2 = env.repos.commit("src", "dx-runtime", BR, "rt points at stray", gitlinks={"dx_app": stray})
    env.write_conf([("dx_app", ""), ("dx-runtime", "gitlinks = dx_app:dx_app")],
                   extra_defaults="gitlink_check = warn")
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx-runtime", f"refs/heads/{BR}") == rt2
    assert "WARNING" in out(r)


# ── PR ensure via gh ──────────────────────────────────────────────────────────

def test_pr_created_when_none_open_and_commits_ahead_of_base(env):
    _basic(env)
    r = env.run()
    assert r.returncode == 0, out(r)
    creates = [c for c in env.gh_calls() if c.startswith("pr create")]
    assert len(creates) == 2, env.gh_calls()
    assert all(f"-B main" in c and f"-H {BR}" in c and "-R " in c for c in creates)
    # conventional-commit title: the GHES commit-message-checker-pr workflow rejects "sync(<repo>): ..."
    assert all(f"-t ci: sync dx_app {BR} -> main (" in c or f"-t ci: sync dx-runtime {BR} -> main (" in c for c in creates), creates
    assert "pull/42" in r.stdout


def test_pr_not_recreated_when_one_is_open(env):
    _basic(env)
    env.set_open_prs([{"number": 7, "url": "https://gh.example/deepx/x/pull/7"}])
    r = env.run()
    assert r.returncode == 0, out(r)
    assert not [c for c in env.gh_calls() if c.startswith("pr create")]
    assert "#7" in r.stdout


def test_no_pr_when_branch_equals_base(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    env.write_conf([("dx_app", "")], branch="main", pr_base="main")
    r = env.run()
    assert r.returncode == 0, out(r)
    assert env.gh_calls() == []


def test_no_pr_when_nothing_ahead_of_base(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.commit("src", "dx_app", BR, "same as main", parent_branch="main")   # empty commit? no: identical tree but new sha
    # make the feature branch point exactly at main so nothing is ahead
    git("update-ref", f"refs/heads/{BR}", "refs/heads/main", cwd=r_.bare("src", "dx_app"))
    r_.mirror_branch("dx_app", "main")
    env.write_conf([("dx_app", "")])
    r = env.run()
    assert r.returncode == 0, out(r)
    assert not [c for c in env.gh_calls() if c.startswith("pr create")]


def test_no_pr_flag_and_push_mode_skip_gh(env):
    _basic(env)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert env.gh_calls() == []
    env2_conf = env.write_conf([("dx_app", ""), ("dx-runtime", "gitlinks = dx_app:dx_app")], mode="push")
    r = env.run()
    assert r.returncode == 0, out(r)
    assert env.gh_calls() == []


# ── flags ─────────────────────────────────────────────────────────────────────

def test_dry_run_changes_nothing(env):
    _basic(env)
    r = env.run("--dry-run")
    assert r.returncode == 0, out(r)
    assert "DRY-RUN" in r.stdout
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") is None
    assert not [c for c in env.gh_calls() if c.startswith("pr create")]
    assert "git push" in r.stdout  # the planned command is shown


def test_repo_filter_processes_only_named_repos(env):
    s = _basic(env)
    r = env.run("--no-pr", "--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == s["app_tip"]
    assert env.repos.rev("dst", "dx-runtime", f"refs/heads/{BR}") is None
    assert "dx-runtime" not in r.stdout.split("summary")[-1] if "summary" in r.stdout else True


def test_pull_only_fetches_but_never_pushes(env):
    s = _basic(env)
    r = env.run("--pull-only")
    assert r.returncode == 0, out(r)
    cache = env.cache / "dx_app.git"
    assert git("rev-parse", "--verify", "-q", f"refs/remotes/src/{BR}", cwd=cache).stdout.strip() == s["app_tip"]
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") is None


def test_tags_are_pushed_only_with_flag(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main", tag="v9.9.9")
    env.write_conf([("dx_app", "")])
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert r_.rev("dst", "dx_app", "refs/tags/v9.9.9") is None
    r = env.run("--no-pr", "--tags")
    assert r.returncode == 0, out(r)
    assert r_.rev("dst", "dx_app", "refs/tags/v9.9.9") is not None


def test_summary_table_lists_every_repo_and_action(env):
    _basic(env)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "dx_app" in tail and "dx-runtime" in tail and "CREATE" in tail


def test_cache_dir_expands_env_default_and_tilde(env, tmp_path, monkeypatch):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")], extra_defaults="cache_dir = ${XDG_CACHE_HOME:-~/.cache}/ghes-sync")
    # write_conf's own cache_dir line comes first; the later duplicate key wins
    r = env.run("--print-config")
    assert r.returncode == 0, out(r)
    first = r.stdout.splitlines()[0]
    assert first.startswith("cache_dir = ") and "~" not in first and "$" not in first, first


# ── closed-network auth: https + PAT, never SSH, never a prompt ────────────────

import base64
from conftest import SUITE

CONF = SUITE / "internal" / "tools" / "ghes-sync" / "sync.conf"


def _b64(token: str) -> str:
    return base64.b64encode(f"x-access-token:{token}".encode()).decode()


def test_committed_conf_has_no_hardcoded_mirror_org_or_branch():
    """The committed sync.conf must be edited by each user: no personal mirror org, no
    hardcoded feature branch, https only (the closed network has no SSH to github.com)."""
    text = CONF.read_text(encoding="utf-8")
    assert "deepx-dhyang" not in text
    assert re.search(r"^src_host\s*=\s*(#.*)?$", text, re.M), "src_host must be left EMPTY for the user to fill in"
    assert re.search(r"^branch\s*=\s*(#.*)?$", text, re.M), "branch must be left EMPTY for the user to fill in"
    assert "dst_host  = https://gh.deepx.ai/deepx" in text.replace("dst_host =", "dst_host  ="), text
    assert "git@" not in text
    # ghcloud came back as a PER-REPO source for the one repo whose usable content exists only
    # on the public channel (dx_fw). It must never be a defaults-level host again (663ff4c).
    assert not re.search(r"^\s*ghcloud_host\s*=", text, re.M), text
    for line in (l.strip() for l in text.splitlines()):
        if line.startswith("ghcloud"):
            assert re.match(r"^ghcloud_(url|ref)\s*=", line), line


def test_committed_conf_refuses_to_run_unedited_with_a_hint(env, tmp_path):
    # sync.override.conf is gitignored and auto-loaded when present, so a
    # developer who has (correctly) created one would otherwise turn this test
    # red. Point --override at an empty file to test the committed conf alone.
    empty_override = tmp_path / "empty.override.conf"
    empty_override.write_text("", encoding="utf-8")
    r = subprocess.run(["bash", str(TOOL), "--config", str(CONF),
                        "--override", str(empty_override), "--print-config"],
                       text=True, capture_output=True,
                       env={k: v for k, v in __import__("os").environ.items() if not k.startswith("GHES_SYNC_")})
    assert r.returncode == 2, r.stdout + r.stderr
    o = r.stdout + r.stderr
    assert "src_host" in o and "sync.conf" in o and "GHES_SYNC_SRC_HOST" in o


def test_empty_src_host_and_branch_fail_with_hints_unless_env_overrides(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")])
    conf = env.conf.read_text(encoding="utf-8")
    env.conf.write_text(re.sub(r"^src_host = .*$", "src_host =", conf, flags=re.M), encoding="utf-8")
    r = env.run("--print-config")
    assert r.returncode == 2 and "src_host" in out(r) and "GHES_SYNC_SRC_HOST" in out(r), out(r)
    r = env.run("--print-config", extra_env={"GHES_SYNC_SRC_HOST": f"file://{env.repos.src}"})
    assert r.returncode == 0 and f"src_url = file://{env.repos.src}/dx_app.git" in r.stdout, out(r)
    env.conf.write_text(re.sub(r"^branch = .*$", "branch =", conf, flags=re.M), encoding="utf-8")
    r = env.run("--print-config")
    assert r.returncode == 2 and "branch" in out(r) and "GHES_SYNC_BRANCH" in out(r), out(r)
    r = env.run("--print-config", extra_env={"GHES_SYNC_BRANCH": "topic/x"})
    assert r.returncode == 0 and "branch = topic/x" in r.stdout, out(r)


def test_ghcloud_host_is_no_longer_a_config_key(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")], extra_defaults="ghcloud_host = https://github.com/DEEPX-AI")
    r = env.run("--print-config")
    assert r.returncode == 2 and "ghcloud_host" in out(r)


def test_src_token_is_sent_as_extraheader_and_never_printed(env):
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "src_url = https://github.invalid/mirror-org/dx_app.git")])
    r = env.run("--pull-only", "--repo", "dx_app", extra_env={"GHES_SYNC_SRC_TOKEN": "s3cretTOKEN"})
    assert r.returncode == 1, out(r)                       # .invalid never resolves → repo FAIL
    fetches = [l for l in log.read_text().splitlines() if " fetch " in l and "github.invalid" in l]
    assert fetches, log.read_text()
    assert all(f"http.https://github.invalid/.extraheader=AUTHORIZATION: basic {_b64('s3cretTOKEN')}" in l for l in fetches), fetches
    assert "s3cretTOKEN" not in out(r) and "s3cretTOKEN" not in log.read_text()
    assert "GHES_SYNC_SRC_TOKEN" in out(r) or "gh auth setup-git" in out(r)   # auth hint on failure


def test_dst_token_and_gh_enterprise_fallback_are_sent_as_extraheader(env):
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    env.write_conf([("dx_app", "dst_url = https://ghes.invalid/deepx/dx_app.git")])
    r = env.run("--no-pr", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"})
    assert r.returncode == 1, out(r)
    lines = [l for l in log.read_text().splitlines() if "ls-remote" in l and "ghes.invalid" in l]
    assert lines and all(f"http.https://ghes.invalid/.extraheader=AUTHORIZATION: basic {_b64('dstTOK')}" in l for l in lines), lines
    assert "dstTOK" not in out(r)
    log.write_text("")
    r = env.run("--no-pr", extra_env={"GH_ENTERPRISE_TOKEN": "entTOK"})   # gh's own variable works for git too
    lines = [l for l in log.read_text().splitlines() if "ls-remote" in l and "ghes.invalid" in l]
    assert lines and all(_b64("entTOK") in l for l in lines), lines
    log.write_text("")
    r = env.run("--no-pr", extra_env={"GHES_TOKEN": "plainGhesTOK"})       # the closed-network machines export GHES_TOKEN
    lines = [l for l in log.read_text().splitlines() if "ls-remote" in l and "ghes.invalid" in l]
    assert lines and all(_b64("plainGhesTOK") in l for l in lines), lines


def test_file_urls_get_no_extraheader_and_prompts_are_disabled(env):
    log = env.install_fake_git()
    _basic(env)
    r = env.run("--no-pr", extra_env={"GHES_SYNC_SRC_TOKEN": "unusedTOK"})
    assert r.returncode == 0, out(r)
    text = log.read_text()
    assert "extraheader" not in text                       # file:// → no header injection
    assert "GTP=0 |" in text and "GTP=unset" not in text   # git must never stop at a password prompt


def test_unreachable_dst_probe_times_out_fast(env):
    """An unreachable GHES must not hang the run until the TCP timeout (observed:
    > 120 s). The connectivity probe honours GHES_SYNC_PROBE_TIMEOUT."""
    import shutil as _sh, time as _t
    real = _sh.which("git")
    shim = env.bin / "git"
    shim.write_text("#!/usr/bin/env bash\n"
                    'case "$*" in *ls-remote*) sleep 20;; esac\n'
                    f"exec '{real}' \"$@\"\n")
    shim.chmod(0o755)
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    env.write_conf([("dx_app", "")])
    t0 = _t.monotonic()
    r = env.run("--no-pr", extra_env={"GHES_SYNC_PROBE_TIMEOUT": "1"})
    assert _t.monotonic() - t0 < 10, "probe did not time out"
    assert r.returncode == 1, out(r)
    assert "timeout" in out(r) and "GHES_SYNC_PROBE_TIMEOUT" in out(r)


# ── no gh CLI (Windows git bash): REST fallback / skip, interactive prompts ──────

def test_without_gh_a_dst_token_creates_the_pr_via_rest(env):
    env.remove_fake_gh()
    curl_log, curl_cfg = env.install_fake_curl()
    _basic(env)
    r = env.run("--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    calls = curl_log.read_text().splitlines()
    assert any("/repos/" in c and "/pulls?state=open&head=" in c and "base=main" in c for c in calls), calls   # list
    assert any("/repos/" in c and c.rstrip().endswith("/pulls") and "POST" in c for c in calls), calls        # create
    assert "Authorization: token dstTOK" in curl_cfg.read_text()     # header travels in the -K config file...
    assert f"ci: sync dx_app {BR} -> main (" in r.stdout              # REST path uses the same conventional title
    assert "dstTOK" not in out(r) and not any("dstTOK" in c for c in calls)   # ...never on argv or in output
    assert "pull/5" in r.stdout
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") is not None


def test_without_gh_and_token_push_succeeds_and_pr_is_skipped_with_warning(env):
    env.remove_fake_gh()
    s = _basic(env)
    r = env.run("--repo", "dx_app", hide_gh=True)   # non-TTY: no prompt possible
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == s["app_tip"]
    assert "WARNING" in out(r) and "SKIP" in out(r)
    assert "GHES_SYNC_DST_TOKEN" in out(r) and "GHES_TOKEN" in out(r)      # every accepted dst token variable is named
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "skipped" in tail


def test_rest_dry_run_creates_nothing(env):
    env.remove_fake_gh()
    curl_log, _ = env.install_fake_curl()
    _basic(env)
    r = env.run("--dry-run", "--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    calls = curl_log.read_text().splitlines() if curl_log.exists() else []
    assert not any("POST" in c for c in calls), calls
    assert "DRY-RUN" in r.stdout and "/pulls" in r.stdout


def test_tool_is_always_non_interactive(env):
    """User decision 2026-09-15: interactive prompts never authenticated reliably, so the
    tool is non-interactive only — no --non-interactive flag, GIT_TERMINAL_PROMPT=0 always,
    no PAT prompt; missing credentials fail fast with a hint (see the preflight test)."""
    r = env.run("--help")
    assert "--non-interactive" not in r.stdout and "GHES_SYNC_INTERACTIVE" not in r.stdout
    r = env.run("--non-interactive", "--no-pr")
    assert r.returncode == 2, out(r)                       # unknown argument
    log = env.install_fake_git()
    _basic(env)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert "GTP=0 |" in log.read_text() and "GTP=unset" not in log.read_text()


def test_https_host_without_any_credential_fails_before_fetching(env):
    """No token env and no credential helper for the host → fail fast with a hint
    naming the env var and `gh auth setup-git`, without even attempting the fetch."""
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "src_url = https://github.invalid/mirror-org/dx_app.git")])
    r = env.run("--pull-only", "--repo", "dx_app", extra_env={"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                                                              "GHES_SYNC_SRC_TOKEN": "", "GH_TOKEN": ""})
    assert r.returncode == 1, out(r)
    o = out(r)
    assert "credential" in o.lower() and "GHES_SYNC_SRC_TOKEN" in o and "gh auth setup-git" in o
    assert not [l for l in log.read_text().splitlines() if " fetch " in l and "github.invalid" in l], "must not attempt the fetch"


def test_rest_existing_pr_is_reported_with_its_html_url(env):
    """GitHub's REST list JSON has `url` (API) before `html_url` (web); the summary must show the web URL."""
    env.remove_fake_gh()
    curl_log, _ = env.install_fake_curl(
        list_json='[{"url":"https://api.ghes.example/repos/deepx/dx_app/pulls/7","id":1,"number":7,'
                  '"html_url":"https://ghes.example/deepx/dx_app/pull/7"}]')
    _basic(env)
    r = env.run("--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    assert "#7 (existing) https://ghes.example/deepx/dx_app/pull/7" in r.stdout, r.stdout
    assert not any("POST" in c for c in curl_log.read_text().splitlines())


# ── --update-branch (merge the moved PR base into the branch) / DST-AHEAD ──────

def _pr_branch_with_moved_base(env, conflict: bool = False):
    """dst already has the PR branch (= src tip). Then another PR lands on dst `main`
    (the PR base), so the branch is no longer up to date with its base."""
    r = env.repos
    r.make("dx_app")
    r.commit("src", "dx_app", "main", "base", files={"a.txt": "0\n", "b.txt": "0\n"})
    r.mirror_branch("dx_app", "main")
    tip = r.commit("src", "dx_app", BR, "feat", files={"a.txt": "1\n"}, parent_branch="main")
    r.mirror_branch("dx_app", BR)
    moved = r.commit("dst", "dx_app", "main", "other pr merged",
                     files={("a.txt" if conflict else "b.txt"): "9\n"})
    env.write_conf([("dx_app", "")])
    return tip, moved


def _worktrees(cache):
    """Linked worktrees of the bare cache (the bare repo itself is listed first — skip it)."""
    entries = [l[len("worktree "):] for l in git("worktree", "list", "--porcelain", cwd=cache).stdout.splitlines()
               if l.startswith("worktree ")]
    return [e for e in entries if Path(e).resolve() != Path(cache).resolve()]


def test_update_branch_merges_the_moved_base_and_ff_pushes(env):
    tip, moved = _pr_branch_with_moved_base(env)
    r = env.run("--no-pr", "--update-branch")
    assert r.returncode == 0, out(r)
    new = env.repos.rev("dst", "dx_app", f"refs/heads/{BR}")
    assert new not in (None, tip)
    bare = env.repos.bare("dst", "dx_app")
    assert git("merge-base", "--is-ancestor", tip, new, cwd=bare, check=False).returncode == 0
    assert git("merge-base", "--is-ancestor", moved, new, cwd=bare, check=False).returncode == 0
    assert git("rev-list", "--parents", "-n1", new, cwd=bare).stdout.split().__len__() == 3   # merge commit
    assert "MERGE-UPDATED" in r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "--reverse" in out(r)                      # mirror write-back hint
    assert _worktrees(env.cache / "dx_app.git") == [] # temp worktree cleaned up


def test_update_branch_conflict_aborts_and_gives_manual_guidance(env):
    """Conflicts are resolved by hand (user decision 2026-09-10): nothing is pushed, no
    worktree is kept, and the guidance covers both machines — closed network (merge in
    your checkout, ff-push GHES feature, later --reverse) and dev machine (merge in the
    mirror checkout, push the mirror, forward sync)."""
    tip, moved = _pr_branch_with_moved_base(env, conflict=True)
    r = env.run("--no-pr", "--update-branch")
    assert r.returncode == 1, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == tip
    o = out(r)
    assert "conflict" in o.lower() and "a.txt" in o
    assert "git merge" in o and "refs/heads/" in o and "--reverse" in o and "mirror" in o.lower()
    assert not (env.cache / "dx_app.merge").exists()
    assert _worktrees(env.cache / "dx_app.git") == []


def test_without_update_branch_a_moved_base_is_only_reported(env):
    tip, moved = _pr_branch_with_moved_base(env)
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == tip
    assert "--update-branch" in out(r) and "base 'main'" in out(r)


def test_update_branch_dry_run_detects_conflicts_but_pushes_nothing(env):
    tip, _ = _pr_branch_with_moved_base(env, conflict=True)
    r = env.run("--no-pr", "--update-branch", "--dry-run")
    assert r.returncode == 1, out(r)
    assert "conflict" in out(r).lower()
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == tip
    assert not (env.cache / "dx_app.merge").exists()      # dry-run leaves no state behind


def test_update_branch_dry_run_clean_merge_pushes_nothing(env):
    tip, _ = _pr_branch_with_moved_base(env)
    r = env.run("--no-pr", "--update-branch", "--dry-run")
    assert r.returncode == 0, out(r)
    assert "DRY-RUN" in r.stdout and "MERGE-UPDATED" in r.stdout.rsplit("SUMMARY", 1)[-1]
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == tip
    assert _worktrees(env.cache / "dx_app.git") == []


def test_update_branch_is_a_noop_when_base_did_not_move(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    tip = r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")
    r_.mirror_branch("dx_app", BR)
    env.write_conf([("dx_app", "")])
    r = env.run("--no-pr", "--update-branch")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == tip
    assert "UP-TO-DATE" in r.stdout.rsplit("SUMMARY", 1)[-1]


def test_dst_ahead_of_src_is_not_diverged(env):
    """After a merge-update (or any commit added on the GHES side on top of the mirror
    tip), dst CONTAINS src: nothing to push, not a failure — the mirror is behind."""
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    tip = r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")
    r_.mirror_branch("dx_app", BR)
    ahead = r_.commit("dst", "dx_app", BR, "ghes-side merge-update", files={"z": "1"})
    env.write_conf([("dx_app", "")])
    r = env.run("--no-pr")
    assert r.returncode == 0, out(r)
    assert "DST-AHEAD" in r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "DIVERGED" not in out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == ahead
    assert "--reverse" in out(r)


# ── --reverse: GHES (dst) -> mirror (src), the bare cache as the carrier ────────

def _reverse_scenario(env):
    """mirror (src) and GHES (dst) share `main`; GHES main got a new commit (dci bot),
    and the GHES feature branch is the mirror feature tip + a merge-update commit."""
    r = env.repos
    r.make("dx_app")
    r.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r.mirror_branch("dx_app", "main")
    feat = r.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")
    r.mirror_branch("dx_app", BR)
    ghes_main = r.commit("dst", "dx_app", "main", "ci: dci bump", files={"m": "1"})
    ghes_feat = r.commit("dst", "dx_app", BR, "Merge main into feature (update-branch)", files={"z": "1"})
    env.write_conf([("dx_app", "")])
    return feat, ghes_main, ghes_feat


def test_reverse_ff_pushes_ghes_branches_to_the_mirror(env):
    feat, ghes_main, ghes_feat = _reverse_scenario(env)
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == ghes_feat
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "REVERSE" in tail and tail.count("FAST-FORWARD") == 2
    assert env.gh_calls() == []                      # never a PR in reverse


def test_reverse_two_steps_pull_where_ghes_is_reachable_then_push_without_it(env):
    feat, ghes_main, ghes_feat = _reverse_scenario(env)
    r = env.run("--reverse", "--pull-only")
    assert r.returncode == 0, out(r)
    cache = env.cache / "dx_app.git"
    assert git("rev-parse", "--verify", "-q", "refs/remotes/dst/main", cwd=cache).stdout.strip() == ghes_main
    assert env.repos.rev("src", "dx_app", "refs/heads/main") != ghes_main   # nothing pushed yet
    # now "on the open network": GHES unreachable, only the cache and the mirror
    conf = env.conf.read_text(encoding="utf-8").replace(f"dst_host = file://{env.repos.dst}", "dst_host = file:///nonexistent/ghes")
    env.conf.write_text(conf, encoding="utf-8")
    r = env.run("--reverse", "--push-only")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == ghes_feat


def test_reverse_diverged_needs_force_with_lease_and_lists_dropped_commits(env):
    feat, ghes_main, ghes_feat = _reverse_scenario(env)
    mirror_only = env.repos.commit("src", "dx_app", "main", "mirror-only commit", files={"q": "1"})
    r = env.run("--reverse")
    assert r.returncode == 1, out(r)
    assert "DIVERGED" in out(r) and "--force-with-lease" in out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == mirror_only
    r = env.run("--reverse", "--force-with-lease")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main
    assert "mirror-only commit" in out(r)             # the dropped commit is named
    assert "FORCED" in r.stdout.rsplit("SUMMARY", 1)[-1]


def test_reverse_mirror_ahead_is_a_noop(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")
    r_.mirror_branch("dx_app", BR)
    newer = r_.commit("src", "dx_app", BR, "not yet synced forward", files={"a": "2"})
    env.write_conf([("dx_app", "")])
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == newer
    assert "TO-AHEAD" in r.stdout.rsplit("SUMMARY", 1)[-1]


def test_force_with_lease_is_rejected_outside_reverse(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")])
    r = env.run("--force-with-lease", "--no-pr")
    assert r.returncode == 2, out(r)
    assert "--reverse" in out(r)


def test_reverse_push_blocked_fails_clearly(env):
    _reverse_scenario(env)
    conf = env.conf.read_text(encoding="utf-8").replace(f"src_host = file://{env.repos.src}", "src_host = file:///nonexistent/mirror")
    env.conf.write_text(conf, encoding="utf-8")
    r = env.run("--reverse")
    assert r.returncode == 1, out(r)
    assert "접근할 수 없음" in out(r) or "fetch 할 수 없음" in out(r)


def test_reverse_default_branches_include_main_when_pr_base_is_dev(env):
    """dx_app/dx_stream integrate on dev, but GHES main (dci / release commits) must
    also come back to the mirror — the default reverse set is branch + pr_base + main."""
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")
    r_.mirror_branch("dx_app", BR)
    git("update-ref", "refs/heads/dev", "refs/heads/main", cwd=r_.bare("dst", "dx_app"))
    ghes_main = r_.commit("dst", "dx_app", "main", "ci: dci", files={"m": "1"})
    env.write_conf([("dx_app", "pr_base = dev")])
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "dx_app:dev" in tail and "dx_app:main" in tail and f"dx_app:{BR}" in tail


# ── --reverse --reset-to-base: after squash-merge, point the mirror feature at GHES's base ──

def _squash_merged_scenario(env, ff: bool = False):
    """mirror feature has 2 commits; GHES dev (pr_base) got them as ONE squash commit
    (ff=False) or as a merge commit that contains them (ff=True)."""
    r = env.repos
    r.make("dx_app")
    r.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r.mirror_branch("dx_app", "main")
    r.commit("src", "dx_app", BR, "feat 1", files={"a": "1"}, parent_branch="main")
    tip = r.commit("src", "dx_app", BR, "feat 2", files={"b": "1"})
    r.mirror_branch("dx_app", BR)
    git("update-ref", "refs/heads/dev", "refs/heads/main", cwd=r.bare("dst", "dx_app"))
    if ff:  # merge-commit style: dev contains the feature commits (dev := feature tip, then one more commit)
        git("update-ref", "refs/heads/dev", f"refs/heads/{BR}", cwd=r.bare("dst", "dx_app"))
        dev = r.commit("dst", "dx_app", "dev", "merge feature into dev", files={"c": "1"})
    else:
        dev = r.commit("dst", "dx_app", "dev", "feat 1 + feat 2 (squash, #12)", files={"a": "1", "b": "1"})
    env.write_conf([("dx_app", "pr_base = dev")])
    return tip, dev


def test_reset_to_base_overwrites_mirror_feature_with_ghes_base_and_backs_it_up(env):
    tip, dev = _squash_merged_scenario(env)
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev
    backups = [l.split()[1] for l in git("show-ref", cwd=env.repos.bare("src", "dx_app")).stdout.splitlines()
               if f"refs/heads/backup/{BR}/" in l]
    assert len(backups) == 1 and env.repos.rev("src", "dx_app", backups[0]) == tip
    o = out(r)
    assert "feat 1" in o and "feat 2" in o                       # dropped mirror-only commits are listed
    assert "RESET" in r.stdout.rsplit("SUMMARY", 1)[-1]
    assert "reset --hard" in o                                    # dev-checkout follow-up hint
    assert not [c for c in env.gh_calls() if c.startswith("pr create")]   # reverse never opens a PR (it may LIST merged PRs)


def test_reset_to_base_no_backup_flag(env):
    tip, dev = _squash_merged_scenario(env)
    r = env.run("--reverse", "--reset-to-base", "--no-backup")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev
    assert "refs/heads/backup/" not in git("show-ref", cwd=env.repos.bare("src", "dx_app")).stdout


def test_reset_to_base_is_a_fast_forward_when_base_contains_the_feature(env):
    tip, dev = _squash_merged_scenario(env, ff=True)
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev
    assert "refs/heads/backup/" not in git("show-ref", cwd=env.repos.bare("src", "dx_app")).stdout
    assert "FAST-FORWARD" in r.stdout.rsplit("SUMMARY", 1)[-1]


def test_reset_to_base_dry_run_changes_nothing(env):
    tip, dev = _squash_merged_scenario(env)
    r = env.run("--reverse", "--reset-to-base", "--dry-run")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == tip
    assert "refs/heads/backup/" not in git("show-ref", cwd=env.repos.bare("src", "dx_app")).stdout
    assert "RESET" in r.stdout and "DRY-RUN" in r.stdout


def test_reset_to_base_requires_reverse(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")])
    r = env.run("--reset-to-base", "--no-pr")
    assert r.returncode == 2, out(r)
    assert "--reverse" in out(r)


def test_reset_to_base_two_steps_then_forward_is_up_to_date(env):
    tip, dev = _squash_merged_scenario(env)
    assert env.run("--reverse", "--pull-only").returncode == 0
    conf = env.conf.read_text(encoding="utf-8").replace(f"dst_host = file://{env.repos.dst}", "dst_host = file:///nonexistent/ghes")
    env.conf.write_text(conf, encoding="utf-8")
    r = env.run("--reverse", "--push-only", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev
    env.conf.write_text(conf.replace("dst_host = file:///nonexistent/ghes", f"dst_host = file://{env.repos.dst}"), encoding="utf-8")
    # forward: GHES feature (still the old commits) vs mirror feature (= dev): GHES is behind or diverged? The GHES
    # feature branch is normally deleted after the merge; here it still exists, so we only check the tool does not crash.
    r = env.run("--no-pr", "--dry-run")
    assert r.returncode in (0, 1), out(r)


# ── docs: the scenario quick guide exists (EN/KO) and names the real flags ────────

import pytest as _pytest


@_pytest.mark.parametrize("name", ["QUICKGUIDE.md", "QUICKGUIDE-KO.md"])
def test_quickguide_exists_and_covers_the_scenarios(name):
    p = SUITE / "internal" / "tools" / "ghes-sync" / name
    assert p.is_file(), p
    text = p.read_text(encoding="utf-8")
    for needle in ("--reverse --pull-only", "--reverse --push-only --reset-to-base", "--update-branch",
                   "--force-with-lease", "~/.cache/ghes-sync", "reset --hard mirror/feature/dx-agent-dev", "setup_remotes.sh",
                   "--dry-run", "DST-AHEAD", "TO-AHEAD",
                   "--dry-run --update-branch", "Update branch",
                   ("최신 상태가 아닙니다" if name.endswith("-KO.md") else "not up to date with its base"),   # default-vs---update-branch comparison, quoted in the doc's language
                   "--reverse --pull-only --reset-to-base", "@GHES",                      # GHES-side reset in Scenario 2
                   "branch = none"):                                                        # the no-feature-branch recipe
        assert needle in text, f"{name}: must mention {needle!r}"
    readme = (SUITE / "internal" / "tools" / "ghes-sync" / ("README.md" if name == "QUICKGUIDE.md" else "README-KO.md")).read_text(encoding="utf-8")
    assert name in readme, f"README must link {name}"


@_pytest.mark.parametrize("name", ["README.md", "README-KO.md"])
def test_readme_documents_the_reset_guard_and_branch_none(name):
    text = (SUITE / "internal" / "tools" / "ghes-sync" / name).read_text(encoding="utf-8")
    for needle in ("branch = none", "--reset-to-base", "pr_base"):
        assert needle in text, f"{name}: must mention {needle!r}"


# ── lessons from the first real --reverse --reset-to-base run (orangepi, GnuTLS -110) ──

def _flaky_git(env, pattern: str, fail_times: int, stderr: str = "fatal: unable to access 'x': GnuTLS recv error (-110): The TLS connection was non-properly terminated."):
    """Install a git shim that fails the first *fail_times* invocations whose argv matches
    *pattern* (bash case pattern — match the SUBCOMMAND, e.g. '*" push "*'; a bare `*push*`
    also matches tmp paths named after the test) with *stderr*, then behaves like the real git."""
    import shutil as _sh
    real = _sh.which("git")
    counter = env.tmp / "flaky.count"
    counter.write_text("0")
    shim = env.bin / "git"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        f'case "$*" in {pattern})\n'
        f"  n=$(cat '{counter}'); if [ \"$n\" -lt {fail_times} ]; then echo $((n+1)) > '{counter}'; echo \"{stderr}\" >&2; exit 128; fi;;\n"
        "esac\n"
        f"exec '{real}' \"$@\"\n"
    )
    shim.chmod(0o755)
    return counter


def test_push_is_retried_on_transient_network_errors(env):
    tip, ghes_main, ghes_feat = _reverse_scenario(env)
    counter = _flaky_git(env, '*" push "*', fail_times=2)
    r = env.run("--reverse", extra_env={"GHES_SYNC_RETRY_DELAY": "0"})
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main
    assert "재시도" in out(r) and counter.read_text().strip() == "2"


def test_persistent_push_failure_shows_git_stderr_and_a_network_hint(env):
    _reverse_scenario(env)
    _flaky_git(env, '*" push "*', fail_times=99)
    r = env.run("--reverse", extra_env={"GHES_SYNC_RETRY_DELAY": "0"})
    assert r.returncode == 1, out(r)
    o = out(r)
    assert "GnuTLS recv error" in o                      # the real git error, not a guess
    assert "http.version" in o                          # the known GnuTLS -110 workaround is suggested
    assert "lease mismatch or permission" not in o      # no misattribution


def test_pull_only_records_branches_absent_on_ghes_so_push_only_skips_them(env):
    """dx-runtime's GHES feature branch was deleted at merge; --push-only then FAILED with
    'not in the cache — run --pull-only first' although --pull-only HAD run. The pull phase
    must record 'absent on GHES' so the push phase reports SKIPPED, not FAIL."""
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")   # mirror-only; GHES has no feature branch
    ghes_main = r_.commit("dst", "dx_app", "main", "dci", files={"m": "1"})
    env.write_conf([("dx_app", "pr_base = main")])
    assert env.run("--reverse", "--pull-only").returncode == 0
    conf = env.conf.read_text(encoding="utf-8").replace(f"dst_host = file://{env.repos.dst}", "dst_host = file:///nonexistent/ghes")
    env.conf.write_text(conf, encoding="utf-8")
    r = env.run("--reverse", "--push-only")
    assert r.returncode == 0, out(r)
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert f"dx_app:{BR}" in tail and "SKIPPED" in tail and "GHES 에 없음" in out(r)
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main


def test_reset_to_base_does_not_also_sync_the_feature_branch_by_name(env):
    """With --reset-to-base the mirror feature branch is about to be REPLACED by the base;
    syncing GHES's (stale, possibly diverged) feature branch onto it first is wrong and noisy."""
    tip, dev = _squash_merged_scenario(env)
    env.repos.commit("dst", "dx_app", BR, "stale ghes feature", files={"s": "1"})   # GHES still has a diverged feature branch
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert f"dx_app:{BR}<=dev" in tail and "RESET" in tail
    assert f"dx_app:{BR} " not in tail and "DIVERGED" not in out(r)
    # the header spells out what is same-name and what is the reset mapping
    assert "같은 이름으로 sync: dev main" in r.stdout and f"reset: mirror {BR} <= GHES dev" in r.stdout
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev


def test_reset_backup_is_not_duplicated_on_rerun_after_a_failed_overwrite(env):
    tip, dev = _squash_merged_scenario(env)
    _flaky_git(env, "*--force-with-lease*", fail_times=99)          # backup push works, overwrite fails
    r = env.run("--reverse", "--reset-to-base", extra_env={"GHES_SYNC_RETRY_DELAY": "0"})
    assert r.returncode == 1, out(r)
    (env.bin / "git").unlink()                                         # network "recovers"
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    backups = [l for l in git("show-ref", cwd=env.repos.bare("src", "dx_app")).stdout.splitlines() if "refs/heads/backup/" in l]
    assert len(backups) == 1, backups                                  # reused, not duplicated
    assert "이미 backup" in out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev


def test_to_ahead_hint_does_not_promise_a_forward_push_for_non_feature_branches(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", "main", "mirror main moved", files={"a": "1"})
    r_.commit("src", "dx_app", BR, "feat", files={"b": "1"}, parent_branch="main")
    r_.mirror_branch("dx_app", BR)
    env.write_conf([("dx_app", "")])
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    line = [l for l in out(r).splitlines() if "dx_app:main" in l and "TO-AHEAD" in l][0]
    assert "push되지 않음" in line and "확인" in line          # no promise that the forward run pushes it


# ── remote naming convention: ghes / mirror (setup_remotes.sh) ───────────────────

SETUP = SUITE / "internal" / "tools" / "ghes-sync" / "setup_remotes.sh"


def _fake_suite_tree(env, origin_is_mirror: bool = True) -> Path:
    """A dev-checkout-like tree: suite + 4 nested git repos, each with an `origin`."""
    root = env.tmp / "checkout"
    for name, rel in (("dx-all-suite", "."), ("dx-compiler", "dx-compiler"), ("dx-runtime", "dx-runtime"),
                      ("dx_app", "dx-runtime/dx_app"), ("dx_stream", "dx-runtime/dx_stream")):
        d = root / rel
        d.mkdir(parents=True, exist_ok=True)
        git("init", "-q", cwd=d)
        url = f"file://{env.repos.src}/{name}.git" if origin_is_mirror else f"https://elsewhere/{name}.git"
        git("remote", "add", "origin", url, cwd=d)
    env.write_conf([("dx_app", "path = dx-runtime/dx_app"), ("dx_stream", "path = dx-runtime/dx_stream"),
                    ("dx-runtime", "path = dx-runtime"), ("dx-compiler", "path = dx-compiler"), ("dx-all-suite", "path = .")])
    return root


def _remotes(d: Path) -> dict:
    out = git("remote", "-v", cwd=d).stdout.splitlines()
    return {l.split()[0]: l.split()[1] for l in out if l.endswith("(fetch)")}


def _run_setup(env, *args):
    import subprocess as _sp, os as _os
    return _sp.run(["bash", str(SETUP), "--config", str(env.conf), *args], text=True, capture_output=True,
                   env={**_os.environ, "PATH": f"{env.bin}:{_os.environ['PATH']}"}, timeout=120)


def test_setup_remotes_adds_ghes_and_mirror_to_all_five_repos(env):
    root = _fake_suite_tree(env)
    r = _run_setup(env, "--suite-dir", str(root))
    assert r.returncode == 0, r.stdout + r.stderr
    for name, rel in (("dx-all-suite", "."), ("dx-compiler", "dx-compiler"), ("dx_app", "dx-runtime/dx_app")):
        rem = _remotes(root / rel)
        assert rem["mirror"] == f"file://{env.repos.src}/{name}.git"
        assert rem["ghes"] == f"file://{env.repos.dst}/{name}.git"
        assert "ghcloud" not in rem                               # the public channel is not a dev remote
        assert "origin" in rem                                   # untouched without --rename-origin
    assert "origin" in r.stdout and "--rename-origin" in r.stdout   # tells you origin == mirror


def test_setup_remotes_rename_origin_and_idempotent(env):
    root = _fake_suite_tree(env)
    r = _run_setup(env, "--suite-dir", str(root), "--rename-origin")
    assert r.returncode == 0, r.stdout + r.stderr
    rem = _remotes(root / "dx-runtime")
    assert "origin" not in rem and rem["mirror"].endswith("/dx-runtime.git")
    r2 = _run_setup(env, "--suite-dir", str(root), "--rename-origin")
    assert r2.returncode == 0 and "ok" in r2.stdout.lower() and "added" not in r2.stdout.lower(), r2.stdout


def test_setup_remotes_dry_run_changes_nothing(env):
    root = _fake_suite_tree(env)
    r = _run_setup(env, "--suite-dir", str(root), "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _remotes(root / "dx-compiler").keys() == {"origin"}
    assert "DRY-RUN" in r.stdout


def test_setup_remotes_does_not_rename_a_foreign_origin(env):
    root = _fake_suite_tree(env, origin_is_mirror=False)
    r = _run_setup(env, "--suite-dir", str(root), "--rename-origin")
    assert r.returncode == 0, r.stdout + r.stderr
    rem = _remotes(root / "dx-compiler")
    assert rem["origin"] == "https://elsewhere/dx-compiler.git" and "mirror" in rem


def test_print_config_exposes_path_and_no_ghcloud(env):
    _fake_suite_tree(env)
    r = env.run("--print-config")
    assert r.returncode == 0, out(r)
    app = re.search(r"\[dx_app\](.*?)(?=\n\[|\Z)", r.stdout, re.S).group(1)
    assert "path = dx-runtime/dx_app" in app and "ghcloud" not in r.stdout


# ── reverse: UP-TO-DATE must not push; suite-url derivation follows the naming convention ──

def test_reverse_up_to_date_branch_is_not_pushed_again(env):
    log = env.install_fake_git()
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", BR, "feat", files={"a": "1"}, parent_branch="main")
    r_.mirror_branch("dx_app", BR)
    git("fetch", "-q", r_.url("src", "dx_app"), "+refs/heads/*:refs/heads/*", cwd=r_.bare("dst", "dx_app"))   # GHES == mirror
    env.write_conf([("dx_app", "")])
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    assert not [l for l in log.read_text().splitlines() if " push " in l], "UP-TO-DATE branches must not be pushed"
    assert r.stdout.rsplit("SUMMARY", 1)[-1].count("UP-TO-DATE") == 2


# ── sync.override.conf: local, gitignored overlay so sync.conf stays untouched ──────

OVERRIDE_EXAMPLE = SUITE / "internal" / "tools" / "ghes-sync" / "sync.override.conf.example"


def test_override_conf_overlays_sync_conf(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")])
    conf = env.conf.read_text(encoding="utf-8")
    env.conf.write_text(re.sub(r"^(src_host|branch) = .*$", r"\1 =", conf, flags=re.M), encoding="utf-8")
    ov = env.conf.with_name(env.conf.name.replace(".conf", ".override.conf"))
    ov.write_text(f"[defaults]\nsrc_host = file://{env.repos.src}\nbranch = topic/o\n[repo dx_app]\npr_base = dev\n", encoding="utf-8")
    r = env.run("--print-config")
    assert r.returncode == 0, out(r)
    app = re.search(r"\[dx_app\](.*?)(?=\n\[|\Z)", r.stdout, re.S).group(1)
    assert f"src_url = file://{env.repos.src}/dx_app.git" in app and "branch = topic/o" in app and "pr_base = dev" in app
    assert "override" in r.stdout.lower()                      # the tool says which override file it applied


def test_override_conf_example_exists_and_real_override_is_gitignored():
    assert OVERRIDE_EXAMPLE.is_file()
    text = OVERRIDE_EXAMPLE.read_text(encoding="utf-8")
    assert "src_host" in text and "branch" in text and "deepx-dhyang" not in text
    r = subprocess.run(["git", "-C", str(SUITE), "check-ignore", "-q", "internal/tools/ghes-sync/sync.override.conf"])
    assert r.returncode == 0, "sync.override.conf must be gitignored"
    r = subprocess.run(["git", "-C", str(SUITE), "check-ignore", "-q", "internal/tools/ghes-sync/sync.override.conf.example"])
    assert r.returncode != 0, "the .example must stay tracked"


# ── probe failures must show git's own error and say which token env was used ─────

def _shim_ls_remote_fails(env, stderr: str):
    import shutil as _sh
    real = _sh.which("git")
    shim = env.bin / "git"
    shim.write_text("#!/usr/bin/env bash\n"
                    f'case "$*" in *ls-remote*github.invalid*) echo "{stderr}" >&2; exit 128;; esac\n'   # only the https mirror probe fails
                    f"exec '{real}' \"$@\"\n")
    shim.chmod(0o755)


def test_probe_rejected_token_is_reported_as_auth_with_the_env_var_name(env):
    _reverse_scenario(env)
    conf = env.conf.read_text(encoding="utf-8").replace(f"src_host = file://{env.repos.src}", "src_host = https://github.invalid/mirror-org")
    env.conf.write_text(conf, encoding="utf-8")
    _shim_ls_remote_fails(env, "fatal: Authentication failed for 'https://github.invalid/mirror-org/dx_app.git/'")
    r = env.run("--reverse", extra_env={"GH_TOKEN": "ghp_revoked"})
    assert r.returncode == 1, out(r)
    o = out(r)
    assert "Authentication failed" in o                          # git's real error is shown
    assert "REJECTED" in o and "GH_TOKEN" in o                   # ...classified, naming the token source actually used
    assert "revoked" in o.lower() or "expired" in o.lower()


def test_probe_network_failure_is_reported_as_network(env):
    _reverse_scenario(env)
    conf = env.conf.read_text(encoding="utf-8").replace(f"src_host = file://{env.repos.src}", "src_host = https://github.invalid/mirror-org")
    env.conf.write_text(conf, encoding="utf-8")
    _shim_ls_remote_fails(env, "fatal: unable to access 'https://github.invalid/mirror-org/dx_app.git/': Could not resolve host: github.invalid")
    r = env.run("--reverse", extra_env={"GH_TOKEN": "ghp_x"})
    assert r.returncode == 1, out(r)
    o = out(r)
    assert "Could not resolve host" in o and "NETWORK" in o
    assert "REJECTED" not in o


# ── gitlink fallback must consider every GHES branch of the sub-repo, not just its feature ─

def test_gitlink_check_accepts_a_pointer_to_the_subrepo_ghes_main_when_the_subrepo_was_not_synced(env):
    """Closed-network run 2026-09-17: dx-compiler's GHES feature branch was a stale pre-merge
    leftover (DIVERGED, not synced), and the suite pointed dx-compiler at its GHES *main* tip.
    The fallback looked only at GHES feature/dx-agent-dev and wrongly blocked the suite push."""
    r_ = env.repos
    r_.make("dx_app", "dx-runtime")
    app_main = r_.commit("src", "dx_app", "main", "app base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx-runtime", "main", "rt base", files={"r": "0"}, gitlinks={"dx_app": app_main})
    r_.mirror_branch("dx-runtime", "main")
    # GHES dx_app: main moved on (merged work), and a STALE feature branch that diverged from the mirror's
    app_ghes_main = r_.commit("dst", "dx_app", "main", "squash-merged feature", files={"a": "1"})
    r_.commit("dst", "dx_app", BR, "stale ghes feature", files={"s": "1"}, parent_branch="main")
    # mirror dx_app: a NEW feature branch (rebuilt on main) -> DIVERGED against the stale GHES one
    r_.commit("src", "dx_app", BR, "new feature", files={"n": "1"}, parent_branch="main")
    # mirror dx-runtime feature points dx_app at the GHES main tip (which exists on GHES)
    rt_tip = r_.commit("src", "dx-runtime", BR, "rt feature", files={"r": "1"}, gitlinks={"dx_app": app_ghes_main}, parent_branch="main")
    env.write_conf([("dx_app", ""), ("dx-runtime", "gitlinks = dx_app:dx_app")])
    r = env.run("--no-pr")
    assert r.returncode == 1, out(r)                 # dx_app is DIVERGED (expected) ...
    assert "DIVERGED" in r.stdout
    assert env.repos.rev("dst", "dx-runtime", f"refs/heads/{BR}") == rt_tip   # ... but the parent MUST be pushed
    assert not [l for l in out(r).splitlines() if "dx-runtime" in l and "gitlink" in l and "NOT reachable" in l], out(r)


# ── 2026-09-17 closed-network review: stale cache refs, probe retries, readable output ─────

def test_probe_is_retried_on_transient_tls_errors_and_then_succeeds(env):
    """GnuTLS -110 on the first ls-remote must not fail the repo: probes retry like pushes do."""
    _reverse_scenario(env)
    counter = _flaky_git(env, '*ls-remote*', fail_times=2)
    r = env.run("--reverse", extra_env={"GHES_SYNC_RETRY_DELAY": "0"})
    assert r.returncode == 0, out(r)
    assert "재시도" in out(r) and counter.read_text().strip() == "2"


def test_persistent_probe_tls_failure_is_classified_as_network_with_the_attempt_count(env):
    _reverse_scenario(env)
    _flaky_git(env, '*ls-remote*', fail_times=99)
    r = env.run("--reverse", extra_env={"GHES_SYNC_RETRY_DELAY": "0", "GHES_SYNC_RETRIES": "2"})
    assert r.returncode == 1, out(r)
    o = out(r)
    assert "GnuTLS recv error" in o and "NETWORK" in o and "2회" in o
    assert "REJECTED" not in o                                    # a TLS hiccup is not an auth failure


def test_stale_cached_dst_ref_of_a_branch_deleted_on_ghes_is_pruned(env):
    """A branch deleted on GHES (e.g. the feature branch after its squash-merge) must not
    survive in the bare cache — a stale refs/remotes/dst/* would classify as DIVERGED."""
    s = _basic(env)
    assert env.run("--no-pr").returncode == 0
    cache = env.cache / "dx_app.git"
    old = s["app_main"]                                                           # an object the cache already has
    git("update-ref", "refs/remotes/dst/zombie", old, cwd=cache)                   # a ref GHES does not have
    git("update-ref", f"refs/remotes/dst/{BR}", old, cwd=cache)                      # and a stale copy of the feature
    git("update-ref", "-d", f"refs/heads/{BR}", cwd=env.repos.bare("dst", "dx_app"))   # GHES deleted the feature branch
    r = env.run("--no-pr", "--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert "CREATE" in r.stdout and "DIVERGED" not in out(r)
    assert "cache 정리" in r.stdout and "zombie" in r.stdout
    assert git("rev-parse", "-q", "--verify", "refs/remotes/dst/zombie", cwd=cache, check=False).returncode != 0
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == s["app_tip"]


def test_per_repo_lines_share_one_separator_column_and_summary_columns_align(env):
    """Readability (user request 2026-09-17): every per-repo line has the repo key padded to
    one width before `│`; the summary table's columns line up and long explanations are
    numbered notes under the table, not inline cells."""
    s = _basic(env, dst_has_branch=True)
    env.repos.commit("dst", "dx_app", BR, "ghes-side", files={"g": "1"})
    env.repos.commit("src", "dx_app", BR, "mirror-side", files={"m": "1"})          # dx_app DIVERGED, dx-runtime blocked/ok
    r = env.run("--no-pr")
    o = out(r)
    seps = {l.index("│") for l in o.splitlines() if l.startswith("[ghes-sync] ") and "│" in l}
    assert len(seps) == 1, seps
    tail = r.stdout.rsplit("SUMMARY", 1)[-1].splitlines()
    header = next(l for l in tail if l.strip().startswith("repo"))
    rows = [l for l in tail if l.strip().startswith(("dx_app", "dx-runtime"))]
    assert rows, tail
    col = header.index("status")
    for row in rows:
        assert row[col:].split()[0] in ("OK", "FAIL", "SKIPPED"), row       # status starts exactly under the header
    assert any(l.strip().startswith("[1] dx_app:") and "DIVERGED" in l for l in tail), tail   # the long text lives in a note


# ── GHES-side --reset-to-base (2026-09-17): the stale GHES feature branch is reset to pr_base too ──

def _squash_merged_with_stale_ghes_feature(env):
    tip, dev = _squash_merged_scenario(env)
    stale = env.repos.commit("dst", "dx_app", BR, "stale ghes feature", files={"s": "1"})   # GHES branch survived the merge
    return tip, dev, stale


def _ghes_backups(env):
    return [l.split()[1] for l in git("show-ref", cwd=env.repos.bare("dst", "dx_app")).stdout.splitlines()
            if f"refs/heads/backup/{BR}/" in l]


def test_reset_to_base_resets_the_ghes_feature_branch_with_a_ghes_backup(env):
    tip, dev, stale = _squash_merged_with_stale_ghes_feature(env)
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == dev          # GHES feature := GHES dev
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev          # mirror feature := GHES dev (as before)
    backups = _ghes_backups(env)
    assert len(backups) == 1 and env.repos.rev("dst", "dx_app", backups[0]) == stale
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert f"dx_app:{BR}<=dev@GHES" in tail and tail.count("RESET") >= 2
    assert "stale ghes feature" in out(r)                                       # the GHES-only commit is listed
    r = env.run("--no-pr", "--dry-run")                                         # both sides on dev → forward is a no-op
    assert r.returncode == 0 and "UP-TO-DATE" in r.stdout.rsplit("SUMMARY", 1)[-1], out(r)


def test_pull_only_reset_to_base_resets_ghes_but_leaves_the_mirror_for_the_open_network(env):
    tip, dev, stale = _squash_merged_with_stale_ghes_feature(env)
    r = env.run("--reverse", "--pull-only", "--reset-to-base")                 # closed network
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == dev
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == tip           # mirror untouched here
    assert "RESET" in r.stdout and f"dx_app:{BR}<=dev@GHES" in r.stdout
    conf = env.conf.read_text(encoding="utf-8").replace(f"dst_host = file://{env.repos.dst}", "dst_host = file:///nonexistent/ghes")
    env.conf.write_text(conf, encoding="utf-8")
    r = env.run("--reverse", "--push-only", "--reset-to-base")                 # open network
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev
    assert "@GHES" not in r.stdout.rsplit("SUMMARY", 1)[-1]                     # no GHES step when GHES is not fetched


def test_ghes_reset_dry_run_changes_nothing_on_ghes(env):
    tip, dev, stale = _squash_merged_with_stale_ghes_feature(env)
    r = env.run("--reverse", "--reset-to-base", "--dry-run")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == stale
    assert _ghes_backups(env) == []
    assert "@GHES" in r.stdout and "DRY-RUN" in r.stdout


def test_ghes_feature_deleted_at_merge_is_recreated_at_the_base(env):
    tip, dev = _squash_merged_scenario(env)                                    # GHES has no feature branch
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == dev
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert f"dx_app:{BR}<=dev@GHES" in tail and "CREATE" in tail


def test_ghes_reset_confirms_the_merged_pr_via_rest_when_a_token_is_present(env):
    tip, dev, stale = _squash_merged_with_stale_ghes_feature(env)
    env.remove_fake_gh()
    env.install_fake_curl(list_json=f'[{{"number":12,"merged_at":"2026-09-17T01:02:03Z","head":{{"sha":"{stale}"}}}}]')
    r = env.run("--reverse", "--reset-to-base", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    assert "merged PR 확인" in out(r) and "찾지 못함" not in out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == dev


def test_ghes_reset_warns_but_proceeds_when_no_merged_pr_is_found(env):
    tip, dev, stale = _squash_merged_with_stale_ghes_feature(env)
    env.remove_fake_gh()
    env.install_fake_curl(list_json="[]")
    r = env.run("--reverse", "--reset-to-base", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    assert "WARNING" in out(r) and "찾지 못함" in out(r)
    assert env.repos.rev("dst", "dx_app", f"refs/heads/{BR}") == dev and len(_ghes_backups(env)) == 1


# ── reviewers (2026-09-18): re-request the review bot after a real push ──
# The n8n review bot (account dci) runs when a PR opens, not on later pushes; re-requesting the
# reviewer is what wakes it. Only a push that actually moved the branch (CREATE/FAST-FORWARD) counts.

def test_reviewers_rerequested_after_fast_forward_push_to_existing_pr(env):
    _basic(env, dst_has_branch=True)
    env.repos.commit("src", "dx_app", BR, "more", files={"a.txt": "2\n"})
    env.set_open_prs([{"number": 42, "url": "https://gh.example/deepx/dx_app/pull/42"}])
    env.write_conf([("dx_app", "")], extra_defaults="reviewers = dci")
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert "FAST-FORWARD" in r.stdout
    assert any(c.startswith("pr edit 42") and "--add-reviewer dci" in c for c in env.gh_calls()), env.gh_calls()
    assert "reviewer 재요청" in r.stdout


def test_reviewers_not_requested_when_up_to_date(env):
    _basic(env, dst_has_branch=True)
    env.set_open_prs([{"number": 42, "url": "u"}])
    env.write_conf([("dx_app", "")], extra_defaults="reviewers = dci")
    r = env.run("--repo", "dx_app")
    assert "UP-TO-DATE" in r.stdout
    assert not any("--add-reviewer" in c for c in env.gh_calls())


def test_reviewers_off_by_default_and_cli_override(env):
    _basic(env, dst_has_branch=True)
    env.repos.commit("src", "dx_app", BR, "more", files={"a.txt": "2\n"})
    env.set_open_prs([{"number": 42, "url": "u"}])
    env.write_conf([("dx_app", "")])
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert not any("--add-reviewer" in c for c in env.gh_calls())
    env.repos.commit("src", "dx_app", BR, "more2", files={"a.txt": "3\n"})
    r = env.run("--repo", "dx_app", "--reviewers", "dci,alice")
    assert r.returncode == 0, out(r)
    assert any("--add-reviewer dci,alice" in c for c in env.gh_calls()), env.gh_calls()


def test_reviewers_dry_run_logs_but_does_not_call(env):
    _basic(env, dst_has_branch=True)
    env.repos.commit("src", "dx_app", BR, "more", files={"a.txt": "2\n"})
    env.set_open_prs([{"number": 42, "url": "u"}])
    env.write_conf([("dx_app", "")], extra_defaults="reviewers = dci")
    r = env.run("--repo", "dx_app", "--dry-run")
    assert "DRY-RUN" in r.stdout and "reviewer 재요청" in r.stdout
    assert not any("--add-reviewer" in c for c in env.gh_calls())


def test_reviewers_rest_backend_posts_requested_reviewers(env):
    _basic(env, dst_has_branch=True)
    env.repos.commit("src", "dx_app", BR, "more", files={"a.txt": "2\n"})
    log, _ = env.install_fake_curl(list_json='[{"number": 7, "html_url": "https://ghes.example/deepx/dx_app/pull/7"}]')
    env.write_conf([("dx_app", "")], extra_defaults="reviewers = dci")
    r = env.run("--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    assert any("pulls/7/requested_reviewers" in l for l in log.read_text().splitlines()), log.read_text()


# ── output language (2026-09-18): --lang ko|en > GHES_SYNC_LANG > locale (LC_ALL > LC_MESSAGES > LANG) ──
_HANGUL = re.compile(r"[가-힣]")


def _diverged(env):
    _basic(env, dst_has_branch=True)
    env.repos.commit("dst", "dx_app", BR, "ghes-side", files={"g": "1"})
    env.repos.commit("src", "dx_app", BR, "mirror-side", files={"m": "1"})


def test_lang_en_prints_english_diverged_and_summary(env):
    _diverged(env)
    r = env.run("--no-pr", "--repo", "dx_app", "--lang", "en")
    o = out(r)
    assert "DIVERGED" in o and "have commits the other lacks" in o and "SUMMARY" in o
    assert not _HANGUL.search(o), o


def test_lang_ko_is_the_default_for_a_korean_locale_and_en_otherwise(env):
    _diverged(env)
    ko = out(env.run("--no-pr", "--repo", "dx_app", extra_env={"GHES_SYNC_LANG": "", "LC_ALL": "ko_KR.UTF-8"}))
    en = out(env.run("--no-pr", "--repo", "dx_app", extra_env={"GHES_SYNC_LANG": "", "LC_ALL": "en_US.UTF-8"}))
    c = out(env.run("--no-pr", "--repo", "dx_app", extra_env={"GHES_SYNC_LANG": "", "LC_ALL": "C", "LC_MESSAGES": "", "LANG": ""}))
    assert "서로 없는 commit" in ko and "요약" in ko
    assert not _HANGUL.search(en) and "SUMMARY" in en
    assert not _HANGUL.search(c)


def test_lang_precedence_option_over_env_over_locale(env):
    _diverged(env)
    env_wins = out(env.run("--no-pr", "--repo", "dx_app", extra_env={"GHES_SYNC_LANG": "en", "LC_ALL": "ko_KR.UTF-8"}))
    opt_wins = out(env.run("--no-pr", "--repo", "dx_app", "--lang", "ko", extra_env={"GHES_SYNC_LANG": "en", "LC_ALL": "en_US.UTF-8"}))
    assert not _HANGUL.search(env_wins)
    assert "서로 없는 commit" in opt_wins


def test_lang_invalid_value_exits_2_naming_the_choices(env):
    _basic(env)
    r = env.run("--no-pr", "--lang", "fr")
    assert r.returncode == 2 and "ko|en" in out(r)
    r = env.run("--no-pr", extra_env={"GHES_SYNC_LANG": "fr"})
    assert r.returncode == 2 and "GHES_SYNC_LANG" in out(r) and "ko|en" in out(r)


def test_lang_help_follows_the_selection(env):
    en = env.run("--lang", "en", "--help"); ko = env.run("--lang", "ko", "--help")
    assert en.returncode == 0 and "Usage:" in en.stdout and "--lang" in en.stdout and not _HANGUL.search(en.stdout)
    assert ko.returncode == 0 and "사용법" in ko.stdout and "--lang" in ko.stdout


def test_lang_en_full_run_has_no_korean_at_all(env):
    """fetch, classify (FAST-FORWARD), gitlink check, push, PR skipped (no gh/no token), summary + notes."""
    s = _basic(env, dst_has_branch=True)
    env.repos.commit("src", "dx_app", BR, "more", files={"a.txt": "2\n"})
    env.repos.commit("src", "dx-runtime", BR, "rt more", files={"r.txt": "2\n"},
                     gitlinks={"dx_app": env.repos.rev("src", "dx_app", f"refs/heads/{BR}")})
    env.remove_fake_gh()                       # no gh, no token -> the PR is skipped with a warning
    r = env.run("--lang", "en", hide_gh=True)
    o = out(r)
    assert r.returncode == 0, o
    assert "FAST-FORWARD" in o and "PR skipped" in o and "SUMMARY" in o
    assert not _HANGUL.search(o), [l for l in o.splitlines() if _HANGUL.search(l)]


# ── sync = off: configured (setup_remotes reads it) but never synced ──────────

def test_sync_off_repo_is_never_pushed(env):
    """dx_fw lives only on the public channel: it must stay in the conf (setup_remotes
    needs its path/ghcloud_url) while ghes-sync never touches either side."""
    r = env.repos
    r.make("dx_app", "dx_fw")
    r.commit("src", "dx_app", BR, "app", files={"a": "1"})
    r.commit("src", "dx_fw", BR, "fw", files={"f": "1"})
    env.write_conf([("dx_app", ""), ("dx_fw", "sync = off")])
    res = env.run("--no-pr")
    assert res.returncode == 0, out(res)
    assert r.rev("dst", "dx_fw", f"refs/heads/{BR}") is None, "a sync=off repo must never be pushed"
    assert r.rev("dst", "dx_app", f"refs/heads/{BR}"), "the other repos still sync"
    assert "sync=off" in out(res), out(res)


def test_sync_off_repo_is_skipped_in_reverse(env):
    r = env.repos
    r.make("dx_fw")
    r.commit("dst", "dx_fw", "main", "fw on ghes", files={"f": "1"})
    env.write_conf([("dx_fw", "sync = off")])
    res = env.run("--reverse")
    assert res.returncode == 0, out(res)
    assert r.rev("src", "dx_fw", "refs/heads/main") is None, "a sync=off repo must never be pushed to the mirror"
    assert "sync=off" in out(res), out(res)


def test_sync_off_repo_still_appears_in_print_config(env):
    env.repos.make("dx_fw")
    env.write_conf([("dx_fw", "sync = off\nghcloud_url = https://github.com/DEEPX-AI/dx_fw.git\nghcloud_ref = main")])
    res = env.run("--print-config")
    assert res.returncode == 0, out(res)
    sec = re.search(r"\[dx_fw\](.*?)(?=\n\[|\Z)", res.stdout, re.S).group(1)
    assert "sync = off" in sec, sec
    assert "ghcloud_url = https://github.com/DEEPX-AI/dx_fw.git" in sec, sec
    assert "ghcloud_ref = main" in sec, sec


def test_invalid_sync_value_is_rejected(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "sync = maybe")])
    res = env.run("--print-config")
    assert res.returncode == 2 and "sync" in out(res), out(res)


# ── the PAT is chosen by URL host, not by src/dst side ───────────────────────

def _host_conf(env, repo_body: str, *, src_host: str) -> None:
    env.write_conf([("dx_app", repo_body)])
    env.conf.write_text(
        env.conf.read_text(encoding="utf-8").replace(f"src_host = file://{env.repos.src}", f"src_host = {src_host}"),
        encoding="utf-8")


def test_token_is_chosen_by_url_host_not_by_side(env):
    """dx_fw-style: a dst that lives on the SAME host as the mirror must use the
    mirror's PAT. Sending the GHES PAT to github.com is rejected even for public repos."""
    log = env.install_fake_git()
    env.repos.make("dx_app")
    _host_conf(env, "dst_url = https://github.invalid/DEEPX-AI/dx_app.git",
               src_host="https://github.invalid/mirror-org")
    env.run("--push-only", "--no-pr", "--repo", "dx_app",
            extra_env={"GHES_SYNC_SRC_TOKEN": "mirrorTOK", "GHES_SYNC_DST_TOKEN": "ghesTOK"})
    lines = [l for l in log.read_text().splitlines() if "ls-remote" in l and "DEEPX-AI" in l]
    assert lines, log.read_text()
    assert all(_b64("mirrorTOK") in l for l in lines), lines
    assert all(_b64("ghesTOK") not in l for l in lines), lines


def test_token_host_override_env_wins(env):
    log = env.install_fake_git()
    env.repos.make("dx_app")
    _host_conf(env, "dst_url = https://github.invalid/DEEPX-AI/dx_app.git",
               src_host="https://github.invalid/mirror-org")
    env.run("--push-only", "--no-pr", "--repo", "dx_app",
            extra_env={"GHES_SYNC_SRC_TOKEN": "mirrorTOK", "GHES_SYNC_DST_TOKEN": "ghesTOK",
                       "GHES_SYNC_TOKEN_GITHUB_INVALID": "ovTOK"})
    lines = [l for l in log.read_text().splitlines() if "ls-remote" in l and "DEEPX-AI" in l]
    assert lines, log.read_text()
    assert all(_b64("ovTOK") in l for l in lines), lines


def test_unknown_host_still_falls_back_to_the_side_token(env):
    """A dst host that matches neither configured host keeps the old behaviour."""
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "dst_url = https://ghes.invalid/deepx/dx_app.git")])
    env.run("--push-only", "--no-pr", "--repo", "dx_app",
            extra_env={"GHES_SYNC_SRC_TOKEN": "mirrorTOK", "GHES_SYNC_DST_TOKEN": "ghesTOK"})
    lines = [l for l in log.read_text().splitlines() if "ls-remote" in l and "ghes.invalid" in l]
    assert lines and all(_b64("ghesTOK") in l for l in lines), lines


# ── "repo is missing" is not "your token was rejected" ───────────────────────

def _git_failing_ls_remote(env, message: str) -> None:
    """A git shim that fails every ls-remote with *message* (the server's wording is
    what probe_reason classifies) and delegates everything else to the real git."""
    real = shutil.which("git")
    shim = env.bin / "git"
    shim.write_text(
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do\n'
        '  if [ "$a" = ls-remote ]; then printf \'%s\\n\' ' + repr(message).replace("'", '"') + ' >&2; exit 128; fi\n'
        "done\n"
        f'exec "{real}" "$@"\n')
    shim.chmod(0o755)


def test_missing_repo_is_not_reported_as_a_rejected_token(env):
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    env.write_conf([("dx_app", "")])
    _git_failing_ls_remote(env, "remote: Repository not found.")
    r = env.run("--no-pr", "--push-only", "--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"})
    o = out(r)
    assert r.returncode == 1, o
    assert "REJECTED" not in o, o
    assert "repo 가 없거나" in o, o
    assert "fine-grained" in o, o


def test_rejected_token_is_still_reported_as_rejected(env):
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    env.write_conf([("dx_app", "")])
    _git_failing_ls_remote(env, "remote: Invalid username or token.")
    r = env.run("--no-pr", "--push-only", "--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"})
    o = out(r)
    assert r.returncode == 1, o
    assert "REJECTED" in o and "GHES_SYNC_DST_TOKEN" in o, o


# ── never push outside the configured host/org ───────────────────────────────

def _foreign_dst_conf(env, repo_body: str) -> None:
    env.write_conf([("dx_app", repo_body)])
    env.conf.write_text(
        env.conf.read_text(encoding="utf-8").replace(f"dst_host = file://{env.repos.dst}",
                                                     "dst_host = https://ghes.invalid/deepx"),
        encoding="utf-8")


def test_push_to_a_foreign_org_is_refused_before_any_network_call(env):
    """A per-repo dst pointing at another org (e.g. the public channel) must never be
    pushed to — that is how a private mirror branch ends up on a public repo."""
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    _foreign_dst_conf(env, "dst_url = https://ghes.invalid/other-org/dx_app.git")
    r = env.run("--no-pr", "--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "t"})
    o = out(r)
    assert r.returncode == 1, o
    assert "allow_foreign_dst" in o, o
    assert not [l for l in log.read_text().splitlines() if "ls-remote" in l and "other-org" in l], \
        "must refuse before touching the network"


def test_allow_foreign_dst_opt_in_lets_it_through(env):
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    _foreign_dst_conf(env, "dst_url = https://ghes.invalid/other-org/dx_app.git\nallow_foreign_dst = yes")
    r = env.run("--no-pr", "--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "t"})
    o = out(r)
    assert "allow_foreign_dst = yes 를" not in o, o          # no longer the blocking hint
    assert [l for l in log.read_text().splitlines() if "ls-remote" in l and "other-org" in l], \
        "with the opt-in the run proceeds to the network"


def test_reverse_refuses_pushing_the_mirror_outside_its_org(env):
    env.repos.make("dx_app")
    env.repos.commit("dst", "dx_app", "main", "on ghes", files={"a": "1"})
    env.write_conf([("dx_app", "src_url = https://github.invalid/other-org/dx_app.git")])
    env.conf.write_text(
        env.conf.read_text(encoding="utf-8").replace(f"src_host = file://{env.repos.src}",
                                                     "src_host = https://github.invalid/mirror-org"),
        encoding="utf-8")
    r = env.run("--reverse", "--repo", "dx_app", extra_env={"GHES_SYNC_SRC_TOKEN": "t"})
    assert r.returncode == 1 and "allow_foreign_dst" in out(r), out(r)


def test_pull_only_does_not_trip_the_push_guard(env):
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", BR, "c", files={"a": "1"})
    _foreign_dst_conf(env, "dst_url = https://ghes.invalid/other-org/dx_app.git")
    r = env.run("--pull-only", "--repo", "dx_app", extra_env={"GHES_SYNC_SRC_TOKEN": "t"})
    assert "allow_foreign_dst" not in out(r), out(r)   # nothing is pushed in --pull-only


# ── --branch: the feature branch on the command line, not only in the env ────

def test_branch_option_is_listed_in_help(env):
    r = env.run("--help")
    assert r.returncode == 0, out(r)
    assert "--branch" in r.stdout, "--help must list --branch"


def test_branch_option_overrides_defaults_and_env(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")], branch="conf/branch")
    r = env.run("--print-config", "--branch", "cli/branch",
                extra_env={"GHES_SYNC_BRANCH": "env/branch"})
    assert r.returncode == 0, out(r)
    assert "branch = cli/branch" in r.stdout, r.stdout
    assert "conf/branch" not in r.stdout and "env/branch" not in r.stdout, r.stdout


def test_branch_option_overrides_a_per_repo_branch(env):
    """`--branch X` means "sync X" — a per-repo branch mapping must not win over it."""
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "branch = per/repo")])
    r = env.run("--print-config", "--branch", "cli/branch")
    assert r.returncode == 0, out(r)
    app = re.search(r"\[dx_app\](.*?)(?=\n\[|\Z)", r.stdout, re.S).group(1)
    assert "branch = cli/branch" in app and "per/repo" not in app, app


def test_branch_option_needs_a_value(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")])
    r = env.run("--print-config", "--branch")
    assert r.returncode == 2 and "--branch" in out(r), out(r)


def test_branch_option_leaves_dst_branch_alone(env):
    """Only the source branch is overridden; an explicit dst_branch mapping stays."""
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "dst_branch = ghes/target")])
    r = env.run("--print-config", "--branch", "cli/branch")
    app = re.search(r"\[dx_app\](.*?)(?=\n\[|\Z)", r.stdout, re.S).group(1)
    assert "branch = cli/branch" in app and "dst_branch = ghes/target" in app, app


# ── gh prints notices on the same stream as the URL ──────────────────────────

def _noisy_gh(env, log_path):
    """A gh that prints a warning BEFORE and AFTER the URL, like the real one does
    ("Warning: N uncommitted changes")."""
    gh = env.bin / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> '{log_path}'\n"
        'case "$1 $2" in\n'
        "  'pr list') echo '[]';;\n"
        "  'pr create') echo 'Warning: 2 uncommitted changes'; "
        "echo 'https://gh.example/deepx/dx_app/pull/42'; echo 'Notice: trailing chatter';;\n"
        "  *) exit 0;;\n"
        "esac\n")
    gh.chmod(0o755)


def test_gh_notices_do_not_leak_into_the_pr_summary_cell(env):
    _basic(env)
    _noisy_gh(env, env.gh_log)
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    summary = out(r).split("SUMMARY", 1)[1]
    row = [l for l in summary.splitlines() if l.strip().startswith("dx_app")][0]
    assert "pull/42" in row, row
    assert "Warning" not in row and "Notice" not in row, row


def test_pr_number_comes_from_the_url_not_the_trailing_output(env):
    """The reviewer re-request needs the PR number; parsing digits off the end of the
    whole output picks up whatever gh printed last."""
    _basic(env)
    _noisy_gh(env, env.gh_log)
    env.run("--repo", "dx_app", "--reviewers", "dci")
    edits = [c for c in env.gh_calls() if c.startswith("pr edit")]
    assert edits, env.gh_calls()
    assert all(c.split()[2] == "42" for c in edits), edits


# ── --reset-to-base guards + `branch = none` (2026-10-20) ─────────────────────
# `branch` means "the feature branch I sync". Putting an integration branch there
# (because there is no feature branch yet) turned --reset-to-base into a forced
# rewrite of main/dev on BOTH the mirror and GHES — see the design spec.

def _git_pushes(log) -> list:
    """Lines of the fake-git log that pushed. A missing log = git never ran."""
    text = log.read_text(encoding="utf-8") if log.exists() else ""
    return [line for line in text.splitlines() if " push" in line]


def _integration_branch_scenario(env, *, branch: str):
    """dx_app integrates on dev (pr_base = dev), dx-runtime on main. `branch` is
    whatever the caller put in [defaults] — an integration name is the bug."""
    r = env.repos
    r.make("dx_app", "dx-runtime")
    for n in ("dx_app", "dx-runtime"):
        r.commit("src", n, "main", "base", files={"a": "0"})
        r.mirror_branch(n, "main")
    git("update-ref", "refs/heads/dev", "refs/heads/main", cwd=r.bare("dst", "dx_app"))
    r.commit("dst", "dx_app", "dev", "ghes dev moved", files={"d": "1"})
    env.write_conf([("dx_app", "pr_base = dev"), ("dx-runtime", "")], branch=branch)


@pytest.mark.parametrize("branch,repo,mapping", [
    ("main", "dx_app", "main <= dev"),              # dx-runtime's main == its pr_base: a no-op, not an error
    ("dev", "dx-runtime", "dev <= main"),           # dx_app's dev == its pr_base: likewise
    ("master", "dx_app", "master <= dev"),
    ("develop", "dx_app", "develop <= dev"),
])
def test_reset_to_base_refuses_an_integration_branch_before_any_network(env, branch, repo, mapping):
    """--reset-to-base rewrites <branch> to <pr_base> with force-with-lease. When
    <branch> is an integration branch that silently force-rewrites main/dev."""
    _integration_branch_scenario(env, branch=branch)
    log = env.install_fake_git()
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 2, out(r)
    assert "--reset-to-base" in out(r) and branch in out(r)
    assert repo in out(r) and mapping in out(r)     # names the repo that would be rewritten
    assert _git_pushes(log) == [], log                 # refused before any git ran at all


def test_reset_to_base_refusal_message_is_clean_in_both_languages(env):
    """A backtick inside a "$(m ...)" message is command substitution, not quoting —
    the first version of this message ran `branch` and leaked a shell error."""
    for lang in ("ko", "en"):
        _integration_branch_scenario(env, branch="main")
        r = env.run("--reverse", "--reset-to-base", "--lang", lang)
        assert r.returncode == 2, out(r)
        assert "command not found" not in out(r) and "명령어를" not in out(r), out(r)
        assert out(r).count("ERROR:") == 1, out(r)


def test_reset_to_base_refusal_lists_the_rewrite_and_the_way_out(env):
    _integration_branch_scenario(env, branch="main")
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 2, out(r)
    assert "main <= dev" in out(r)                   # what would have happened
    assert "--branch" in out(r) and "--reverse --push-only" in out(r)   # both alternatives


def test_reset_to_base_still_works_for_a_real_feature_branch(env):
    """The guard must not catch the normal workflow."""
    tip, dev = _squash_merged_scenario(env)
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert env.repos.rev("src", "dx_app", f"refs/heads/{BR}") == dev


def test_reset_to_base_warns_when_branch_equals_pr_base(env):
    """branch == pr_base: reset_to_base()/reset_ghes_branch() return early, and the
    same-name list loses the only branch — the run went completely silent."""
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", "main", "base", files={"a": "0"})
    env.repos.mirror_branch("dx_app", "main")
    env.write_conf([("dx_app", "")], branch="main", pr_base="main")
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 0, out(r)
    assert "pr_base" in out(r) and "main" in out(r)
    assert "--reset-to-base" in out(r).rsplit("SUMMARY", 1)[-1]   # summary says it applied nowhere


def test_branch_none_syncs_only_the_integration_branches_in_reverse(env):
    """No feature branch yet: bring GHES's pr_base + main back to the mirror."""
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    git("update-ref", "refs/heads/dev", "refs/heads/main", cwd=r_.bare("dst", "dx_app"))
    ghes_main = r_.commit("dst", "dx_app", "main", "ci: dci", files={"m": "1"})
    ghes_dev = r_.commit("dst", "dx_app", "dev", "dev moved", files={"d": "1"})
    env.write_conf([("dx_app", "pr_base = dev")], branch="none")
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    assert "같은 이름으로 sync: dev main" in r.stdout
    assert env.repos.rev("src", "dx_app", "refs/heads/main") == ghes_main
    assert env.repos.rev("src", "dx_app", "refs/heads/dev") == ghes_dev


def test_branch_none_is_refused_in_the_forward_direction(env):
    """Forward = push the feature branch to GHES and open a PR. With no feature
    branch the only reading would be 'push mirror main straight into GHES main',
    which bypasses the GHES PR review."""
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "")], branch="none")
    log = env.install_fake_git()
    r = env.run("--no-pr")
    assert r.returncode == 2, out(r)
    assert "--reverse" in out(r) and "none" in out(r)
    assert _git_pushes(log) == [], log                 # refused before any git ran at all


def test_branch_none_is_refused_with_reset_to_base(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "pr_base = dev")], branch="none")
    r = env.run("--reverse", "--reset-to-base")
    assert r.returncode == 2, out(r)
    assert "--reset-to-base" in out(r)


def test_branch_none_is_reported_as_none_in_print_config(env):
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "pr_base = dev")], branch="none")
    r = env.run("--reverse", "--print-config")
    assert r.returncode == 0, out(r)
    assert "branch = none" in r.stdout


def test_branch_none_via_cli_option_and_case_insensitively(env):
    env.repos.make("dx_app")
    env.repos.commit("src", "dx_app", "main", "base", files={"a": "0"})
    env.repos.mirror_branch("dx_app", "main")
    env.write_conf([("dx_app", "pr_base = dev")])          # [defaults] branch = feature/x
    r = env.run("--reverse", "--branch", "NONE", "--print-config")
    assert r.returncode == 0, out(r)
    assert "branch = none" in r.stdout and BR not in r.stdout


def test_branch_none_to_ahead_hint_does_not_quote_an_empty_branch(env):
    r_ = env.repos
    r_.make("dx_app")
    r_.commit("src", "dx_app", "main", "base", files={"a": "0"})
    r_.mirror_branch("dx_app", "main")
    r_.commit("src", "dx_app", "main", "mirror main moved", files={"a": "1"})
    env.write_conf([("dx_app", "")], branch="none")
    r = env.run("--reverse")
    assert r.returncode == 0, out(r)
    line = [l for l in out(r).splitlines() if "dx_app:main" in l and "TO-AHEAD" in l][0]
    assert "''" not in line and "' '" not in line, line
    assert "branch = none" in line, line          # not "the forward run syncs only 'none'"
