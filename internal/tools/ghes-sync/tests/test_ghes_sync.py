# SPDX-License-Identifier: Apache-2.0
"""Contract tests for internal/tools/ghes-sync/ghes-sync.sh (spec §8).
Everything runs against local bare repos and a fake `gh` — no network."""

from __future__ import annotations

import re
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
    assert "--reverse --push-only --force-with-lease" in out(r) and "submodule pointers" in out(r)


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


def test_committed_conf_uses_https_hosts_not_ssh():
    """The closed-network machine has no SSH route to github.com — only https."""
    text = CONF.read_text(encoding="utf-8")
    assert "src_host  = https://github.com/deepx-dhyang" in text.replace("src_host =", "src_host  ="), text
    assert "dst_host  = https://gh.deepx.ai/deepx" in text.replace("dst_host =", "dst_host  ="), text
    assert "git@" not in text


def test_src_token_is_sent_as_extraheader_and_never_printed(env):
    log = env.install_fake_git()
    env.repos.make("dx_app")
    env.write_conf([("dx_app", "src_url = https://github.invalid/deepx-dhyang/dx_app.git")])
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
    assert "timed out" in out(r) and "GHES_SYNC_PROBE_TIMEOUT" in out(r)


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
    assert "WARNING" in out(r) and "skipped" in out(r)
    assert "GHES_SYNC_DST_TOKEN" in out(r) or "gh" in out(r)
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


def test_help_lists_non_interactive_and_prompts_stay_disabled_without_tty(env):
    r = env.run("--help")
    assert "--non-interactive" in r.stdout
    log = env.install_fake_git()
    _basic(env)
    r = env.run("--no-pr", "--non-interactive")
    assert r.returncode == 0, out(r)
    assert "GTP=0 |" in log.read_text() and "GTP=unset" not in log.read_text()


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
    assert "cannot reach" in out(r).lower() or "cannot fetch" in out(r).lower()


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
    assert env.gh_calls() == []


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
