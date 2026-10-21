# SPDX-License-Identifier: Apache-2.0
"""The GHES PR description ghes-sync.sh assembles: the mirror PR's body, the
generated sync summary, and the repo's pull_request_template.md.
Everything runs against local bare repos and a fake `gh` — no network."""

from __future__ import annotations

import re

import pytest

from conftest import BR, TOOL, _basic, git, out

PR_BODY_MAX = int(re.search(r"^(?:readonly )?PR_BODY_MAX=(\d+)", TOOL.read_text(encoding="utf-8"), re.M).group(1))


# ── PR description: mirror PR body + .github/pull_request_template.md (2026-10-20) ──

TEMPLATE = "## Summary\n\n<!-- what and why -->\n\n## Checklist\n\n- [ ] tests\n- [ ] docs\n"
MIRROR_PRS = "7\tOPEN\thttps://github.com/o/r/pull/7\n"   # what `gh pr list --template` prints


def _gh_with_mirror(env, *, mirror_prs: str = "[]", mirror_body: str = "", mirror_title: str = "",
                    fail_list: bool = False):
    """Fake gh that answers the dst existing-PR check, the mirror-side `pr list`
    (slug contains /src/) and `pr view`, and saves the body file of `pr create -F`."""
    body_out = env.tmp / "pr_body.txt"
    mb = env.tmp / "mirror_body.txt"; mb.write_text(mirror_body, encoding="utf-8")
    mt = env.tmp / "mirror_title.txt"; mt.write_text(mirror_title, encoding="utf-8")
    mp = env.tmp / "mirror_prs.json"; mp.write_text(mirror_prs, encoding="utf-8")
    mirror_list = "echo 'gh: boom' >&2; exit 1" if fail_list else f"cat '{mp}'"
    gh = env.bin / "gh"
    gh.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' \"$*\" >> '{env.gh_log}'\n"
        'prev=""; for a in "$@"; do\n'
        f"  [ \"$prev\" = -F ] && cp \"$a\" '{body_out}'\n"
        '  prev="$a"\n'
        "done\n"
        'case "$1 $2" in\n'
        '  "pr list") case "$*" in\n'
        f"       */src/*) {mirror_list};;\n"
        f"       *) cat '{env.gh_prs}';;\n"
        "     esac;;\n"
        '  "pr view") case "$*" in\n'
        f"       *title*) cat '{mt}';;\n"
        f"       *) cat '{mb}';;\n"
        "     esac;;\n"
        "  \"pr create\") echo 'https://gh.example/deepx/x/pull/42';;\n"
        "  *) exit 0;;\n"
        "esac\n")
    gh.chmod(0o755)
    return body_out


def test_pr_body_appends_the_template_from_the_dst_base(env):
    """GitHub resolves the template against the BASE repo — so do we, first."""
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    body = _gh_with_mirror(env)
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    text = body.read_text(encoding="utf-8")
    assert "Automated sync by ghes-sync.sh" in text
    assert "## Checklist" in text and "- [ ] tests" in text
    assert text.index("Automated sync") < text.index("## Checklist")   # template goes last


def test_pr_body_template_falls_back_to_the_source_branch(env):
    _basic(env)
    env.repos.commit("src", "dx_app", BR, "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    body = _gh_with_mirror(env)
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert "## Checklist" in body.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [".github/PULL_REQUEST_TEMPLATE.md", "PULL_REQUEST_TEMPLATE.md",
                                  "docs/pull_request_template.md"])
def test_pr_body_finds_the_other_standard_template_paths(env, path):
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template", files={path: TEMPLATE})
    body = _gh_with_mirror(env)
    assert env.run("--repo", "dx_app").returncode == 0
    assert "## Checklist" in body.read_text(encoding="utf-8")


def test_pr_body_without_a_template_or_mirror_pr_is_unchanged(env):
    """No template, no mirror PR → byte-identical to the body this tool always wrote."""
    _basic(env)
    body = _gh_with_mirror(env)
    assert env.run("--repo", "dx_app").returncode == 0
    text = body.read_text(encoding="utf-8")
    assert text.startswith("Automated sync by ghes-sync.sh from the github.com mirror.")
    assert "\n---\n" not in text and "Mirror PR:" not in text


def test_pr_body_takes_the_mirror_pr_body_and_puts_it_first(env):
    _basic(env)
    body = _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="Why: the base moved.\n")
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    text = body.read_text(encoding="utf-8")
    assert text.startswith("Why: the base moved.")
    assert "Mirror PR: https://github.com/o/r/pull/7 (#7, OPEN)" in text
    assert text.index("Why: the base moved.") < text.index("Automated sync")


def test_pr_body_does_not_duplicate_a_template_the_mirror_body_already_has(env):
    """A mirror PR opened on github.com already contains the template; ticked
    checkboxes must not make it look like a different text."""
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    filled = "## Summary\n\nThis fixes X.\n\n## Checklist\n\n- [x] tests\n- [x] docs\n"
    body = _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body=filled)
    assert env.run("--repo", "dx_app").returncode == 0
    text = body.read_text(encoding="utf-8")
    assert text.count("## Checklist") == 1 and text.count("## Summary") == 1
    assert "This fixes X." in text


def test_pr_body_appends_the_template_to_a_free_form_mirror_body(env):
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    body = _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="Just some prose, no sections.\n")
    assert env.run("--repo", "dx_app").returncode == 0
    text = body.read_text(encoding="utf-8")
    assert "Just some prose" in text and "## Checklist" in text


def test_pr_body_appends_the_template_when_only_some_anchors_are_present(env):
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    body = _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="## Summary\n\nhalf a template.\n")
    assert env.run("--repo", "dx_app").returncode == 0
    assert "## Checklist" in body.read_text(encoding="utf-8")


def test_pr_body_mirror_lookup_failure_is_a_warning_not_a_failure(env):
    _basic(env)
    body = _gh_with_mirror(env, fail_list=True)
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert "WARNING" in out(r)
    assert body.read_text(encoding="utf-8").startswith("Automated sync by ghes-sync.sh")
    assert "pull/42" in out(r)                      # the PR was still created


def test_pr_body_truncates_an_oversized_mirror_body_but_keeps_the_template(env):
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    body = _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="x" * 70000)
    assert env.run("--repo", "dx_app").returncode == 0
    text = body.read_text(encoding="utf-8")
    # the script's own budget, not a hand-copied number — it moves with PR_BODY_MAX
    assert len(text.encode("utf-8")) <= PR_BODY_MAX, len(text.encode("utf-8"))
    assert "truncated" in text
    assert "Automated sync by ghes-sync.sh" in text and "## Checklist" in text


def test_pr_body_dry_run_reports_both_findings_and_creates_nothing(env):
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="Why: the base moved.\n")
    r = env.run("--repo", "dx_app", "--dry-run")
    assert r.returncode == 0, out(r)
    o = out(r)
    assert "pull_request_template.md" in o
    assert "#7" in o
    assert not [c for c in env.gh_calls() if c.startswith("pr create")]


def test_pr_body_without_gh_or_jq_skips_the_mirror_body_but_keeps_the_template(env):
    """REST backend on a machine without gh: the mirror body needs a JSON parser,
    the template only needs git."""
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": TEMPLATE})
    env.install_fake_curl()
    env.remove_fake_gh()
    r = env.run("--repo", "dx_app", extra_env={"GHES_SYNC_DST_TOKEN": "dstTOK"}, hide_gh=True)
    assert r.returncode == 0, out(r)
    assert "WARNING" in out(r) and "jq" in out(r)
    payload = (env.tmp / "curl_payload.json").read_text(encoding="utf-8")
    assert "## Checklist" in payload and "Automated sync" in payload


# ── PR title: from the mirror PR, and --pr-prefix-ci-skip (2026-10-20) ───────

def _pr_create_call(env) -> str:
    calls = [c for c in env.gh_calls() if c.startswith("pr create")]
    assert calls, env.gh_calls()
    return calls[0]


def _mirror_prs() -> str:
    """The list carries no title — the title comes from `pr view --json title`."""
    return MIRROR_PRS


def test_pr_title_comes_from_the_mirror_pr(env):
    _basic(env)
    _gh_with_mirror(env, mirror_prs=_mirror_prs(), mirror_body="why\n",
                    mirror_title="feat(internal): ghes-sync — build the GHES PR body")
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    call = _pr_create_call(env)
    assert "feat(internal): ghes-sync — build the GHES PR body" in call, call
    assert "#7" not in call, call                      # the number stays in the body, not the title


def test_pr_title_falls_back_to_the_generated_one_without_a_mirror_pr(env):
    _basic(env)
    _gh_with_mirror(env)
    assert env.run("--repo", "dx_app").returncode == 0
    assert "ci: sync dx_app" in _pr_create_call(env)


def test_pr_prefix_ci_skip_replaces_the_conventional_prefix(env):
    _basic(env)
    t = "feat(internal): ghes-sync — build the GHES PR body"
    _gh_with_mirror(env, mirror_prs=_mirror_prs(), mirror_title=t)
    r = env.run("--repo", "dx_app", "--pr-prefix-ci-skip")
    assert r.returncode == 0, out(r)
    call = _pr_create_call(env)
    assert "ci-skip: ghes-sync — build the GHES PR body" in call, call
    assert "feat(internal)" not in call, call


def test_pr_prefix_ci_skip_prepends_when_there_is_no_conventional_prefix(env):
    _basic(env)
    t = "Update the sync tool"
    _gh_with_mirror(env, mirror_prs=_mirror_prs(), mirror_title=t)
    assert env.run("--repo", "dx_app", "--pr-prefix-ci-skip").returncode == 0
    assert "ci-skip: Update the sync tool" in _pr_create_call(env)


def test_pr_prefix_ci_skip_is_idempotent(env):
    _basic(env)
    t = "ci-skip: already skipped"
    _gh_with_mirror(env, mirror_prs=_mirror_prs(), mirror_title=t)
    assert env.run("--repo", "dx_app", "--pr-prefix-ci-skip").returncode == 0
    call = _pr_create_call(env)
    assert "ci-skip: already skipped" in call and "ci-skip: ci-skip:" not in call, call


def test_pr_prefix_ci_skip_also_applies_to_the_generated_title(env):
    """The flag means 'this sync must not run CI' — that does not depend on a mirror PR."""
    _basic(env)
    _gh_with_mirror(env)
    assert env.run("--repo", "dx_app", "--pr-prefix-ci-skip").returncode == 0
    call = _pr_create_call(env)
    assert "ci-skip: sync dx_app" in call and "ci: sync" not in call, call


def test_pr_prefix_ci_skip_is_listed_in_help(env):
    r = env.run("--help")
    assert r.returncode == 0
    assert "--pr-prefix-ci-skip" in r.stdout


def test_a_template_without_anchors_is_not_swallowed_by_a_separator(env):
    """r21147: the no-anchor fallback used to compare only the template's FIRST
    meaningful line. A template starting with `---` matched the separator the body
    already contains, so it was judged 'already present' and silently dropped."""
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "add PR template",
                     files={".github/pull_request_template.md": "---\nDescribe the change.\n"})
    body = _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="prose only\n")
    assert env.run("--repo", "dx_app").returncode == 0
    assert "Describe the change." in body.read_text(encoding="utf-8")


def test_an_oversized_summary_says_so_instead_of_claiming_a_truncation(env):
    """r21148: when the summary alone blows the budget the mirror body is dropped
    whole — 'truncated' understates it and points at the wrong cause."""
    _basic(env)
    env.repos.commit("dst", "dx_app", "main", "huge template",
                     files={".github/pull_request_template.md": "## T\n" + "x" * 70000})
    _gh_with_mirror(env, mirror_prs=MIRROR_PRS, mirror_body="why\n")
    r = env.run("--repo", "dx_app")
    assert r.returncode == 0, out(r)
    assert "생성 요약" in out(r) or "generated summary" in out(r), out(r)
