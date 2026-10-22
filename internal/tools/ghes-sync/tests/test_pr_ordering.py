# SPDX-License-Identifier: Apache-2.0
"""Ordering contract of a forward run: every repo is pushed before any PR is opened.
Runs against local bare repos and fake git/gh shims — no network."""

from __future__ import annotations

import shutil

from conftest import _basic, out


# ── push everything first, open the PRs after (GHES #124 race, 2026-10-22) ──────
# The sub-repo drift gates fire on `pull_request` and clone the same-name
# dx-all-suite branch. ghes-sync pushed the suite LAST, so a PR opened for the
# first sub-repo started a gate while the suite branch did not exist yet; the gate
# fell back to suite main and failed on fragments main does not have.

def _ordered_shims(env):
    """A fake git and a fake gh that append to ONE log, so the relative order of
    pushes and `pr create` calls is observable."""
    order = env.tmp / "order.log"
    real_git = shutil.which("git")
    (env.bin / "git").write_text(
        "#!/usr/bin/env bash\n"
        'for a in "$@"; do [ "$a" = push ] && { ' + f"printf 'push %s\\n' \"$*\" >> '{order}'" + '; break; }; done\n'
        f"exec '{real_git}' \"$@\"\n")
    (env.bin / "git").chmod(0o755)
    (env.bin / "gh").write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> '{env.gh_log}'\n"
        f"case \"$1 $2\" in\n"
        f"  'pr list') cat '{env.gh_prs}';;\n"
        f"  'pr create') printf 'pr-create %s\\n' \"$*\" >> '{order}'; echo 'https://gh.example/deepx/x/pull/42';;\n"
        "  *) exit 0;;\n"
        "esac\n")
    (env.bin / "gh").chmod(0o755)
    return order


def test_every_branch_is_pushed_before_the_first_pr_is_opened(env):
    """A PR starts the other side's CI, and that CI wants the branches this run is
    still about to push. So: push all repos, then open all PRs."""
    _basic(env)
    order = _ordered_shims(env)
    r = env.run()
    assert r.returncode == 0, out(r)
    lines = [l.split()[0] for l in order.read_text(encoding="utf-8").splitlines()]
    assert "push" in lines and "pr-create" in lines, lines
    assert lines.index("pr-create") > len(lines) - 1 - lines[::-1].index("push"), (
        "a PR was opened before the last push:\n  " + "\n  ".join(lines))


def test_deferred_prs_are_still_one_per_repo_in_config_order(env):
    _basic(env)
    _ordered_shims(env)
    r = env.run()
    assert r.returncode == 0, out(r)
    creates = [c for c in env.gh_calls() if c.startswith("pr create")]
    assert len(creates) == 2, creates
    assert " dx_app " in f" {creates[0]} " or "/dx_app" in creates[0], creates[0]
    assert "dx-runtime" in creates[1], creates[1]
    tail = r.stdout.rsplit("SUMMARY", 1)[-1]
    assert tail.index("dx_app") < tail.index("dx-runtime")        # summary order unchanged
