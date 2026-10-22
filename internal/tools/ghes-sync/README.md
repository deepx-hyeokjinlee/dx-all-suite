# ghes-sync — mirror → GHES branch sync

> Scenario-by-scenario walkthrough: [QUICKGUIDE.md](QUICKGUIDE.md) · [QUICKGUIDE-KO.md](QUICKGUIDE-KO.md)

`ghes-sync.sh` moves work from the private github.com mirror (`github.com/{DEEPX-MIRROR-ORG}/*`)
to the closed-network GHES (`gh.deepx.ai/deepx/*`): it fetches each configured source branch,
verifies the submodule pointers it carries, **fast-forward pushes** the same-name branch to
GHES (never force) and opens — or finds — a PR from that branch into the configured base
(`main`, or `dev` for dx_app / dx_stream). Merging the PR stays a human step.

Run it on a machine that can reach GHES and *read* github.com (push to github.com may be
blocked there — that is fine). The two SCMs share git history (the mirror was cloned from GHES),
so plain `git push` works; the tool only guards the ordering and the pointers.

This directory lives under `internal/`, which is release-excluded — nothing here reaches the
public `github.com/DEEPX-AI` export.

## Prerequisites

- bash ≥ 4 and git — that is all (Git for Windows' **git bash** qualifies: bash 4.4+, git, curl, base64).
  `gh` is **optional**: PRs are created through `gh` when it is installed, otherwise through the GHES REST API
  with `curl` and the dst token; with neither, the branch is still pushed and the PR is *skipped with a warning*
  (exit 0 — open it by hand or rerun with a token).
- **https only.** The closed-network machine has no SSH route to github.com, so `sync.conf` uses
  `https://github.com/{DEEPX-MIRROR-ORG}` and `https://gh.deepx.ai/deepx`. Never put `git@…` there.
- **Credentials (both sides are private).** Two equivalent options:

  | | src = github.com mirror (read) | dst = GHES (push + PR) |
  |---|---|---|
  | env var (per run, nothing stored) | `GHES_SYNC_SRC_TOKEN` (fallback `GH_TOKEN`) — fine-grained PAT, *Contents: Read-only* on the 5 `{DEEPX-MIRROR-ORG}/*` repos | `GHES_SYNC_DST_TOKEN` (fallback `GH_ENTERPRISE_TOKEN`, then `GHES_TOKEN`; which `gh` also uses for the PR) — PAT with `repo` (contents write + pull requests) |
  | credential helper (once per machine) | `gh auth login --hostname github.com --with-token < pat.txt && gh auth setup-git --hostname github.com` | `gh auth login --hostname gh.deepx.ai [--with-token < pat.txt] && gh auth setup-git --hostname gh.deepx.ai` |

  With an env var the tool passes the token per call as `git -c http.https://<host>/.extraheader=AUTHORIZATION: basic <base64>` —
  it never lands in a URL, a `.git/config`, or the output (the same technique the CI workflows use). Without any
  credential git would normally stop at a password prompt; the tool sets `GIT_TERMINAL_PROMPT=0`, so it fails fast with an
  auth hint instead. `gh auth login` on the closed-network machine works with `--with-token` (no browser needed); the
  device/web flow also works if the machine can open `https://github.com/login/device`.
- If both an env token and a credential helper exist, the header (env token) wins for that call.
- **The token is chosen by the URL's host, not by the src/dst side.** Both configured hosts are known,
  so a repo whose dst sits on `github.com` (the public channel) is handed the *mirror* PAT — sending the
  GHES PAT to github.com is rejected even for a public repo. `GHES_SYNC_TOKEN_<HOST>` (e.g.
  `GHES_SYNC_TOKEN_GITHUB_COM`) overrides both; a host matching neither keeps using that side's token.
- **Non-interactive only.** The tool never prompts (`GIT_TERMINAL_PROMPT=0`, no PAT prompt) — interactive logins
  proved unreliable. Before touching a host it runs a **credential preflight**: with no token env for that side it asks
  git's credential helpers (`git credential fill`, no prompt) and, if nothing answers, fails fast with a hint naming the
  env var and `gh auth login --hostname <host> --with-token && gh auth setup-git --hostname <host>`. In CI inject the
  PATs as secrets.

## Quick start

```bash
cd <dx-all-suite>                                   # any checkout that has internal/
bash internal/tools/ghes-sync/ghes-sync.sh --print-config      # what would be synced where
bash internal/tools/ghes-sync/ghes-sync.sh --dry-run           # fetch + classify, print push/gh commands
bash internal/tools/ghes-sync/ghes-sync.sh                     # push + ensure PRs
bash internal/tools/ghes-sync/ghes-sync.sh --repo dx_app --no-pr   # one repo, push only
bash internal/tools/ghes-sync/ghes-sync.sh --reviewers dci          # + re-request the review bot on every PR that received a push
```

## Configuration — `sync.conf` + `sync.override.conf`

`sync.conf` is committed and shared; **do not edit it for your own values** (it would sit in `git status`
forever). Put them in `sync.override.conf` next to it — gitignored, same INI format, applied on top:

```bash
cp internal/tools/ghes-sync/sync.override.conf.example internal/tools/ghes-sync/sync.override.conf
# then set src_host (your mirror org) and branch (your feature branch) in that file
```
`--branch NAME` passes the feature branch on the command line instead: it beats the config, the
override file and `GHES_SYNC_BRANCH`, and overrides a per-repo `branch` too (a `dst_branch`
mapping is left alone).

The two keys are intentionally empty in `sync.conf`; until they are set (override file, `--override FILE`,
or `GHES_SYNC_SRC_HOST` / `GHES_SYNC_BRANCH` env) the tool exits 2 with a hint. `--print-config` shows which
override file was applied.


```ini
[defaults]
src_host  =                                 # REQUIRED — your private mirror org, e.g. https://github.com/{DEEPX-MIRROR-ORG}
                                            # (https only; or export GHES_SYNC_SRC_HOST). Empty → exit 2 with a hint.
dst_host  = https://gh.deepx.ai/deepx
branch    =                                 # REQUIRED — your feature branch, e.g. feature/my-topic
                                            # (or export GHES_SYNC_BRANCH); dst_branch defaults to the same name
pr_base   = main                            # PR target on dst; "" = no PR for that repo
mode      = pr                              # pr = push + ensure PR · push = push only
cache_dir = ${XDG_CACHE_HOME:-~/.cache}/ghes-sync
gitlink_check = strict                      # strict | warn | off

[repo dx_rt_npu_linux_driver]   ; section order = processing order (nested repos first)
[repo dx_rt]
[repo dx_fw]                                         # the public-channel exception — see below
sync = off                                           # ghes-sync never fetches/pushes this repo
ghcloud_url = https://github.com/DEEPX-AI/dx_fw.git  # setup_remotes.sh only: the `ghcloud` remote
ghcloud_ref = main
[repo dx_app]
pr_base = dev
[repo dx_stream]
pr_base = dev
[repo dx-runtime]
gitlinks = dx_rt:dx_rt dx_app:dx_app dx_stream:dx_stream   # <repo-name>:<path in this repo>
[repo dx-compiler]
[repo dx-all-suite]
gitlinks = dx-runtime:dx-runtime dx-compiler:dx-compiler
```

Per-repo keys: `src_url`, `dst_url` (full URLs override host+name), `src_host`, `dst_host`,
`branch`, `dst_branch`, `pr_base`, `mode`, `sync`, `ghcloud_url`, `ghcloud_ref`,
`allow_foreign_dst`, `gitlinks`. Adding a repo = adding a `[repo NAME]` section (before any parent
that lists it in `gitlinks`). Adding a branch mapping = `branch =` / `dst_branch =` in that
section, or a second config file (`--config other.conf`).

`sync = off` keeps a repo in the config for `setup_remotes.sh` while ghes-sync never touches it.
`allow_foreign_dst = yes` is the explicit opt-in for a push target outside the configured host/org;
without it such a push is **refused before any network call**, so a per-repo `dst_host` cannot
quietly put a private branch on someone else's (e.g. public) repo.

### `dx_fw` — the public-channel exception

`dx_fw`'s source lives only on GHES, while the `fw.bin` that actually gets used is published only on
`github.com/DEEPX-AI/dx_fw`, which GHES never carries. Neither side of the mirror sync is the right
source, so the repo is `sync = off` and the dev checkout is configured instead:

```bash
bash internal/tools/ghes-sync/setup_remotes.sh                      # `ghcloud` remote + submodule policy
bash internal/tools/ghes-sync/setup_remotes.sh --checkout-ghcloud   # …and check out ghcloud/main
```

That writes three **local** overrides in `dx-runtime` — never `.gitmodules`, which belongs to the GHES
repo: `submodule.dx_fw.url` = the ghcloud URL, `update = none` so `git submodule update --init` does
not die on a gitlink the public history has never contained, and `ignore = all` so the deliberately
different content is not reported as dirty. Back to the GHES source:
`git -C dx-runtime config --unset-all submodule.dx_fw.url` (same for `.update` / `.ignore`).

On a fresh clone `git submodule update --init` skips `dx_fw` (that is what `update = none` means),
so the directory stays empty until `--checkout-ghcloud` clones it there — that one command covers
both the empty-directory and the existing-checkout case.

`dx_fw` is deliberately **not** one of `dx-runtime`'s `gitlinks`: that pointer is a GHES commit the
ghcloud history does not contain, and the strict gitlink check would block every dx-runtime push.

## What happens per repo

| Step | Detail |
|------|--------|
| fetch | into a bare cache `<cache_dir>/<name>.git`: `src/<branch>`, `dst/<dst_branch>`, `dst/<pr_base>` (URLs are passed explicitly — no remotes, no stored credentials) |
| classify | **CREATE** (dst branch absent) · **FAST-FORWARD** · **UP-TO-DATE** (no-op) · **DST-AHEAD** (dst contains the mirror tip plus more, e.g. a merge-update — nothing to push, the mirror is behind: bring it back with `--reverse`) · **DIVERGED** (both sides have commits the other lacks → repo fails, nothing pushed) |
| gitlink check | every new commit's `160000` entries listed in `gitlinks` must be reachable from the sub-repo's synced tip (or, if that sub-repo was not processed this run, from what dst already has). `strict` blocks the parent push; `warn` pushes with a warning |
| push | `git push <dst> refs/remotes/src/<branch>:refs/heads/<dst_branch>` — ff-only, never `--force`; `--tags` adds `refs/tags/*` |
| update branch (`--update-branch`) | when the PR base (`pr_base`) moved on dst since the branch was cut: merge the base INTO the branch in a temporary worktree (GitHub's "Update branch", never a rebase — no force push, submodule pointers stay valid) and ff-push the merge commit; **conflict** → nothing pushed; the merge is aborted and nothing is kept — resolve it by hand (see *Resolving an update-branch conflict* below). `--dry-run` performs the local merge, so it detects conflicts without pushing (and keeps nothing). Without the flag a moved base is only reported. Merge identity: `GHES_SYNC_GIT_NAME` / `GHES_SYNC_GIT_EMAIL`, else your git config. The mirror is then behind by that merge commit — see `--reverse` |
| PR | `mode = pr` and `dst_branch != pr_base`: reuse the open PR (`gh pr list --head --base`) or `gh pr create` with the commit list as body; nothing when 0 commits ahead of the base |
| reviewers (`reviewers = dci` / `--reviewers dci`) | after a push that actually moved the branch (CREATE / FAST-FORWARD) and a PR exists or was created: (re)request those reviewers (`gh pr edit --add-reviewer`, or REST `POST …/requested_reviewers`). The GHES review bot (`dci`, n8n) runs when a PR opens but **not** on later pushes — re-requesting the reviewer is what wakes it again (same webhook as the UI button "Re-request review"). Off when unset; a failure is a warning, the sync itself succeeded. Pairs with `internal/tools/pr-review-apply` for acting on the review |
| summary | table `repo · action · src · dst-before · dst-after · pr · status` — cells are ASCII so the columns stay aligned; `status` is `OK` / `FAIL`, with `[n]` pointing at a numbered note under the table that carries the full explanation; exit 0 / 1 (a repo failed) / 2 (config or setup error) |
| output format | messages follow the output language (see *Output language*: Korean on a Korean locale, English otherwise; technical tokens — action names, env vars, git commands — are the same in both). Per-repo lines are `[ghes-sync] <repo(:branch)>  │ message` with the repo key padded to one width per run, so the `│` column lines up; `▶` starts a repo, `WARNING:` / `FAIL:` prefix problems |


### The PR title

The GHES PR carries the **mirror PR's title verbatim**, so a reviewer on GHES reads the same
sentence the author wrote on the mirror. Without a mirror PR the generated
`ci: sync <repo> <branch> -> <base> (N commits)` is used, as before. The mirror PR *number*
is deliberately not in the title — on GHES a bare `#7` links to GHES's own 7, not the
mirror's; the body's `Mirror PR: <url>` line is the accurate link.

The title must stay conventional-commit shaped, because GHES's `commit-message-checker-pr`
workflow rejects other forms — a mirror title like `feat(internal): …` already satisfies it.

`--pr-prefix-ci-skip` replaces that type prefix with `ci-skip:`:

| title on the mirror | with `--pr-prefix-ci-skip` |
|---|---|
| `feat(internal): ghes-sync — build the GHES PR body` | `ci-skip: ghes-sync — build the GHES PR body` |
| `Update the sync tool` (no prefix) | `ci-skip: Update the sync tool` |
| `ci-skip: already skipped` | unchanged (idempotent) |

It applies to the generated title as well, so "this sync must not run CI" does not depend on
whether a mirror PR happened to be found.

### The PR description

The GHES PR body is assembled from up to three parts; separators appear only between
parts that exist, so with none of them the body is exactly what this tool always wrote.

| Part | Where it comes from | When |
|---|---|---|
| the mirror PR's description | the mirror PR whose head is `branch` (OPEN preferred, else the most recently updated) | whenever one is found |
| the generated summary | `Mirror PR:` link, source branch + sha, commits ahead of `pr_base`, and the first 50 subjects | always |
| `pull_request_template.md` | the repo itself — `refs/remotes/dst/<pr_base>` first (what GitHub resolves against), then the branch being proposed | when the file exists and the body does not already contain it |

The template is looked up at `.github/pull_request_template.md`,
`.github/PULL_REQUEST_TEMPLATE.md`, the same two names at the repo root, and under `docs/`
— first hit wins. Both refs are already in the bare cache, so this costs no network call.

**Why it is sometimes not appended.** A mirror PR opened through github.com's web UI already
contains the template. Re-appending it would duplicate every section, so the template is added
only when the body is missing it, judged on *anchor* lines — markdown headings and task-list
items, with `- [x]` normalised to `- [ ]` so a ticked box does not count as different text.
Prose you typed into the template changes; its structure does not.

Reading the mirror PR needs a JSON client: the `gh` CLI (preferred — it is used regardless of
which backend opens the GHES PR) or `jq` for the REST path. Without either, or on any lookup
failure, the run prints one WARNING and continues with the generated summary; the template is
unaffected because it only needs git. `--dry-run` reports what it found and creates nothing.

An already-open GHES PR is left exactly as it is — neither its title nor its body is rewritten;
the run only re-requests reviewers. So a PR opened before this feature keeps the generated
`ci: sync …` title, and one opened after keeps whatever the mirror PR was called at the time,
even if the mirror PR has since been renamed. Everything described above applies when the PR
is **created**.

### When the base moved: default run vs `--update-branch`

You will see this line whenever `pr_base` (`main` / `dev`) on GHES received commits after your branch was cut —
typically other PRs were merged in the meantime (dci bumps, someone else's feature):

```
[ghes-sync] dx_stream    │ base 'dev' has 2 new commit(s) that feature/dx-agent-dev lacks — the PR is not up to date with its base; rerun with --update-branch to merge the base into the branch
```

It is a **notice, not a failure**: the push and the PR still happen. `--update-branch` is optional.

| | default (no flag) | `--update-branch` |
|---|---|---|
| What lands on GHES | the mirror branch **as is** (mirror == GHES branch) | the mirror branch **plus one merge commit** (`Merge <base> into <branch> (ghes-sync --update-branch)`) — base merged INTO the branch; never a rebase, never a force push |
| Base moved | notice only; the PR is created and GHES merges against the current base at merge time (its test-merge) — mergeable as long as there is no conflict | the tool merges first, so the PR branch itself contains the base; a **conflict pushes nothing** and prints the manual recipe |
| When a conflict shows up | in the PR page ("This branch has conflicts") | immediately — `--dry-run --update-branch` checks without pushing |
| PR CI | `pull_request` CI runs on GHES's test-merge, so base changes are included | the branch tip itself contains the base, so `push` CI sees it too |
| Mirror afterwards | unchanged — the next forward run is `UP-TO-DATE` | GHES is ahead by the merge commit (`DST-AHEAD`) — run `--reverse` (see *Reverse direction* below) where github.com is pushable to bring it back |
| Use it when | almost always | (1) the PR page shows conflicts, (2) branch protection requires "branches up to date before merging", (3) you want the gate to run on branch + base before merging |

GHES's **Update branch** button does the same thing as `--update-branch` (a merge commit on the GHES branch); after
either one the mirror is behind, so finish with `--reverse`. Recommended order: run without the flag, look at
the PRs, and use `--update-branch --repo <name>` only for the repos that show a conflict.

### Resolving an update-branch conflict (by hand)

Only a clean merge is automated. On a conflict the tool aborts, keeps nothing and pushes nothing;
resolve it in your own checkout and let the tool continue from there:

| where you are | do | then |
|---|---|---|
| closed network (GHES pushable) | in your checkout: `git fetch <dst_url> <pr_base> && git merge FETCH_HEAD`, resolve, commit, `git push <dst_url> HEAD:refs/heads/<branch>` (ff onto the GHES branch) | forward sync shows DST-AHEAD; bring the mirror up with `--reverse` |
| dev machine (github.com pushable) | in the mirror checkout: same merge, then `git push mirror <branch>` | forward sync pushes it as FAST-FORWARD |

Never use `--force-with-lease` / `--reset-to-base` to "fix" a conflict — it drops the resolution.

## Run-book

1. Push your work to the mirror (`feature/dx-agent-dev` in all 5 repos, nested repos first, no submodule pointer bumps unless intended).
2. On the GHES-side machine: `--dry-run`, read the summary, then run for real.
3. Review/merge the PRs on GHES (`feature/dx-agent-dev → main`, `→ dev` for dx_app/dx_stream). The suite gate
   (`harness-gate`) and the sub-repo gates (`subrepo-gate`) run on those PRs.
4. GHES → public export follows the existing release procedure (rsync + `release-excluded`).

### Push everything, then open the PRs

A forward run has two phases: **all repos are pushed first, in config order (nested first,
dx-all-suite last), and only then are the PRs opened** — again in config order.

The reason is the other side's CI. Each sub-repo carries a drift gate that fires on
`pull_request` and clones the dx-all-suite branch with the same name. When the PR for the
first sub-repo was opened before dx-all-suite had been pushed, that gate could not find the
suite branch, fell back to the suite's default branch and failed on fragments the default
branch does not have (GHES, 2026-10-22: dx-runtime and dx-compiler both red while the change
itself was fine). Opening every PR after every push removes the race rather than widening the
gate's retry window.

A side effect worth having: if a later repo fails to push, the earlier repos' PRs were never
opened, so a half-finished sync does not leave review requests behind.

## Reverse direction — `--reverse` (GHES → mirror)

Brings GHES-side changes back to the mirror: `dci` bot / merged commits on `main`/`dev`, and the
merge commit a `--update-branch` run added to the PR branch (the mirror is then **DST-AHEAD** in a
normal run). Per repo it syncs the branches in `reverse_branches` (default: `branch` + `pr_base` + `main`),
GHES → mirror, **fast-forward only**, no PRs. Same conf, same tokens (`GHES_SYNC_DST_TOKEN` still means
GHES, `GHES_SYNC_SRC_TOKEN` the mirror — which now needs *write*).

Because the closed network cannot push to github.com, the **bare cache is the carrier** and the run
is two steps (same laptop moved between networks, or copy `cache_dir` to a machine that can push):

```bash
# 1) closed network — GHES reachable: fetch GHES branches into the cache, push nothing
bash internal/tools/ghes-sync/ghes-sync.sh --reverse --pull-only
# 2) open network — github.com pushable: push the cached GHES branches to the mirror (no GHES access needed)
bash internal/tools/ghes-sync/ghes-sync.sh --reverse --push-only
```
A single `--reverse` (no `--pull-only`/`--push-only`) does both and is fine wherever both hosts are
reachable; where github.com push is blocked it simply fails with `cannot reach …` / `… push failed`.

Classification per branch: CREATE · FAST-FORWARD · UP-TO-DATE · **TO-AHEAD** (the mirror has commits GHES
lacks — the normal forward run will push them; nothing to do) · **DIVERGED** (both sides moved) → fails
unless `--force-with-lease` is given, which then overwrites the mirror branch with the GHES branch
(`--force-with-lease=<branch>:<mirror tip just fetched>`) after listing every mirror-only commit that is
dropped. `--force-with-lease` is only accepted together with `--reverse`; the forward direction never forces.

### After the PRs are merged — `--reverse --reset-to-base`

GHES squash-merges the PRs, so `main`/`dev` end up with ONE new commit per PR and the mirror's
`feature/dx-agent-dev` (the original commits) can never fast-forward to it again. `--reset-to-base`
points the mirror branch at GHES's `pr_base` (`main`, or `dev` for dx_app/dx_stream), per repo,
nested repos first:

```bash
# closed network                                    # open network (same cache)
ghes-sync.sh --reverse --pull-only --reset-to-base  ghes-sync.sh --reverse --push-only --reset-to-base
```
Per repo: if the mirror branch is already contained in the base (merge-commit style merge) it is a
plain FAST-FORWARD; otherwise **RESET**: the current mirror tip is first saved to
`backup/<branch>/<YYYYmmdd-HHMMSS>` on the mirror (skip with `--no-backup`), the mirror-only commits
that disappear are listed, and the base tip is pushed with `--force-with-lease=<branch>:<mirror tip
just fetched>` — for you that is an unconditional overwrite; it only refuses when someone pushed to
the mirror branch between the fetch and the push (rerun). `reverse_branches` (`main`/`dev`
themselves) are synced ff in the same run. Afterwards update your dev checkout:
`git fetch mirror && git reset --hard mirror/feature/dx-agent-dev` (the tool prints this; remotes follow the
`ghes` / `mirror` convention — `setup_remotes.sh --rename-origin` applies it).
**GHES side too.** Whenever GHES is reachable in the run (`--pull-only` included), `--reset-to-base` also resets the
GHES feature branch, which the squash-merge left diverged: the stale tip is saved to GHES `backup/<branch>/<ts>`, a merged
PR with that head is looked up (REST with a dst token, else `gh`; warning only when none is found or no client exists),
then GHES `<branch>` := `<pr_base>` tip with `--force-with-lease` — row `<repo>:<branch><=<pr_base>@GHES` (`CREATE` when
GHES had deleted the branch at merge). So the closed-network step is `--reverse --pull-only --reset-to-base`, the
open-network step `--reverse --push-only --reset-to-base`, and the next forward run is `UP-TO-DATE` on both sides.

`--reset-to-base` is only accepted together with `--reverse`.

**It is refused when `branch` is an integration branch.** `--reset-to-base` rewrites `branch` to
`pr_base` with `--force-with-lease` on *both* the mirror and GHES, so a `branch` of `main`, `master`,
`dev`, `develop` — or any repo's own `pr_base` — would force-rewrite that shared branch (with
`branch = main` and dx_app's `pr_base = dev`, `main` would be reset to `dev`). The run stops with
exit 2 *before any network call*, naming each repo and the rewrite it would have done. Name a real
feature branch (`--branch <feature>`), or, to only bring the integration branches down from GHES,
drop `--reset-to-base` and run `--reverse --push-only`.

A repo whose `branch` equals its own `pr_base` has nothing to reset: both reset halves return early,
the same-name list loses that branch, and the repo would vanish from the summary without a word. It
is now skipped with a `WARNING`, and when that is true for *every* target the summary says
`--reset-to-base` was applied nowhere.

### No feature branch yet — `branch = none`

`branch` is REQUIRED, so with no feature branch in flight there was nothing valid to put there —
and putting `main` there is exactly the trap above. Set `branch = none` instead (in
`sync.override.conf`, `--branch none`, or `GHES_SYNC_BRANCH=none`; case-insensitive):

```bash
# bring GHES's integration branches (pr_base + main) back to the mirror
bash internal/tools/ghes-sync/ghes-sync.sh --reverse --branch none
```

`reverse_branches` then defaults to `pr_base` + `main` per repo (the feature entry simply drops out),
so dx_app/dx_stream sync `dev` + `main` and everything else syncs `main`.

Two things are refused with exit 2:

| Combination | Why |
|---|---|
| `branch = none` without `--reverse` | Forward means "push my feature branch to GHES and open a PR". With no branch the only reading left is "push the mirror's `main`/`dev` straight into GHES", which bypasses the GHES PR review (`dci`). |
| `branch = none` with `--reset-to-base` | There is no feature branch to put back on `pr_base`. |

A real branch literally named `none` cannot be synced this way — rename it or use a different branch.

## Output language

Messages are printed in Korean or English. Selection order: `--lang ko|en` > `GHES_SYNC_LANG` > the terminal
locale (`LC_ALL` > `LC_MESSAGES` > `LANG`; a value starting with `ko` selects Korean, anything else — including `C`
or unset — English). Any other value exits 2. Action words (`CREATE`, `FAST-FORWARD`, `DST-AHEAD`, `DIVERGED`,
`DRY-RUN`, `FAIL`, `WARNING`, `SKIPPED`), env-var / option names and git commands are identical in both languages, so
scripts that grep for them keep working; `--help` follows the same selection. The examples in this file quote the
English messages; [README-KO.md](README-KO.md) quotes the Korean ones.

```bash
bash internal/tools/ghes-sync/ghes-sync.sh --lang en --dry-run     # English regardless of the locale
GHES_SYNC_LANG=ko bash internal/tools/ghes-sync/ghes-sync.sh       # Korean regardless of the locale
```

## Troubleshooting

| Symptom | Meaning / fix |
|---------|---------------|
| `DIVERGED` | GHES branch has commits the mirror lacks. Fetch that branch into the mirror, merge or rebase, push the mirror, rerun. The tool never force-pushes. |
| `gitlink … NOT reachable` | The parent repo points at a sub-repo commit that is not on the synced sub-repo branch (wrong branch, or the sub-repo failed earlier in the run). Fix the pointer or sync the right sub-repo branch first. |
| `PR base 'dev' does not exist on dst` | The configured `pr_base` is missing on GHES — fix `sync.conf`. |
| `gh pr list failed` / auth errors | `gh auth status --hostname gh.deepx.ai`; the branch itself was already pushed. |
| `PR skipped (no gh CLI, no dst token)` | Push succeeded; set `GHES_SYNC_DST_TOKEN` / `GH_ENTERPRISE_TOKEN` / `GHES_TOKEN` (REST via curl) or install `gh`, then rerun — the existing branch is reused. |
| `REST ... HTTP 401/404` | Token lacks `repo` scope or the wrong host: the API base is `https://<host>/api/v3` (GHES) / `https://api.github.com`. |
| `cannot fetch src […]` / `cannot reach dst (GHES) — git: … — … REJECTED / NETWORK` | No or wrong credential for a private repo (see Prerequisites), or the host is unreachable from this machine. An env token overrides the credential helper for that call. |
| `GnuTLS recv error (-110)` / `RPC failed` on push | Transient TLS/network error; pushes are retried (`GHES_SYNC_RETRIES`=3, `GHES_SYNC_RETRY_DELAY`=5 s) and git's stderr is shown. Persistent: `git config --global http.version HTTP/1.1`, then rerun (idempotent). |
| `probe attempt N/3 failed — looks like a transient network/TLS error` | Transient TLS error on the `ls-remote` probe (GnuTLS -110 etc.); probes retry like pushes (`GHES_SYNC_RETRIES`). Only after the last attempt is the repo failed, and the message says `still failing after N attempts`. |
| `cache cleanup: dropped stale copies of branches deleted on … — <branches>` | Informational: branches deleted on the remote (e.g. a feature branch after its squash-merge) were dropped from the bare cache so they cannot be mistaken for a DIVERGED branch. |
| `probe timeout (30s, GHES_SYNC_PROBE_TIMEOUT exceeded)` | GHES not reachable from here (wrong network). Tune `GHES_SYNC_PROBE_TIMEOUT` (probe, default 30 s) / `GHES_SYNC_NET_TIMEOUT` (fetch/push, default 1800 s). |
| exit 2 with `unknown key` / `must be listed as an EARLIER [repo]` | Config error — the message names the section and key. |

## Tests

```bash
python3 -m pytest --rootdir=. internal/tools/ghes-sync/tests -q     # network-free: local bare repos + fake gh
```
The GHES suite gate workflow (`.github/workflows/dx-agent-dev-gate-ghes.yml`, release-excluded) runs these tests
as its own step; the public `harness_gate.sh` / `.deepx/` docs deliberately do not mention this directory.
