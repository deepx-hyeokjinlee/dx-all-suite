# ghes-sync — mirror → GHES branch sync

> Scenario-by-scenario walkthrough: [QUICKGUIDE.md](QUICKGUIDE.md) · [QUICKGUIDE-KO.md](QUICKGUIDE-KO.md)

`ghes-sync.sh` moves work from the private github.com mirror (`github.com/deepx-dhyang/*`)
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
  `https://github.com/deepx-dhyang` and `https://gh.deepx.ai/deepx`. Never put `git@…` there.
- **Credentials (both sides are private).** Two equivalent options:

  | | src = github.com mirror (read) | dst = GHES (push + PR) |
  |---|---|---|
  | env var (per run, nothing stored) | `GHES_SYNC_SRC_TOKEN` (fallback `GH_TOKEN`) — fine-grained PAT, *Contents: Read-only* on the 5 `deepx-dhyang/*` repos | `GHES_SYNC_DST_TOKEN` (fallback `GH_ENTERPRISE_TOKEN`, which `gh` also uses for the PR) — PAT with `repo` (contents write + pull requests) |
  | credential helper (once per machine) | `gh auth login --hostname github.com --with-token < pat.txt && gh auth setup-git --hostname github.com` | `gh auth login --hostname gh.deepx.ai [--with-token < pat.txt] && gh auth setup-git --hostname gh.deepx.ai` |

  With an env var the tool passes the token per call as `git -c http.https://<host>/.extraheader=AUTHORIZATION: basic <base64>` —
  it never lands in a URL, a `.git/config`, or the output (the same technique the CI workflows use). Without any
  credential git would normally stop at a password prompt; the tool sets `GIT_TERMINAL_PROMPT=0`, so it fails fast with an
  auth hint instead. `gh auth login` on the closed-network machine works with `--with-token` (no browser needed); the
  device/web flow also works if the machine can open `https://github.com/login/device`.
- If both an env token and a credential helper exist, the header (env token) wins for that call.
- **Interactive vs non-interactive.** On a terminal (git bash, ssh session) with no token, git is allowed to ask:
  Git Credential Manager on Windows opens the browser/device login, plain git asks for user + PAT on the terminal
  (type anything as user, the PAT as password; `git config --global credential.helper manager|store` remembers it).
  If no token and no `gh` are available for the PR step, the tool asks once for a GHES PAT (not stored). Without a TTY,
  with `--non-interactive`, or `GHES_SYNC_INTERACTIVE=0` (CI), prompts are disabled (`GIT_TERMINAL_PROMPT=0`) and a
  missing credential fails fast — inject the PATs as secrets there.

## Quick start

```bash
cd <dx-all-suite>                                   # any checkout that has internal/
bash internal/tools/ghes-sync/ghes-sync.sh --print-config      # what would be synced where
bash internal/tools/ghes-sync/ghes-sync.sh --dry-run           # fetch + classify, print push/gh commands
bash internal/tools/ghes-sync/ghes-sync.sh                     # push + ensure PRs
bash internal/tools/ghes-sync/ghes-sync.sh --repo dx_app --no-pr   # one repo, push only
```

## Configuration — `sync.conf`

```ini
[defaults]
src_host  = https://github.com/deepx-dhyang  # url = <host>/<name>.git — https only
dst_host  = https://gh.deepx.ai/deepx
branch    = feature/dx-agent-dev            # source branch; dst_branch defaults to the same name
pr_base   = main                            # PR target on dst; "" = no PR for that repo
mode      = pr                              # pr = push + ensure PR · push = push only
cache_dir = ${XDG_CACHE_HOME:-~/.cache}/ghes-sync
gitlink_check = strict                      # strict | warn | off

[repo dx_app]           ; section order = processing order (nested repos first)
pr_base = dev
[repo dx_stream]
pr_base = dev
[repo dx-runtime]
gitlinks = dx_app:dx_app dx_stream:dx_stream         # <repo-name>:<path in this repo>
[repo dx-compiler]
[repo dx-all-suite]
gitlinks = dx-runtime:dx-runtime dx-compiler:dx-compiler
```

Per-repo keys: `src_url`, `dst_url` (full URLs override host+name), `src_host`, `dst_host`,
`branch`, `dst_branch`, `pr_base`, `mode`, `gitlinks`. Adding a repo = adding a `[repo NAME]`
section (before any parent that lists it in `gitlinks`). Adding a branch mapping = `branch =` /
`dst_branch =` in that section, or a second config file (`--config other.conf`).

## What happens per repo

| Step | Detail |
|------|--------|
| fetch | into a bare cache `<cache_dir>/<name>.git`: `src/<branch>`, `dst/<dst_branch>`, `dst/<pr_base>` (URLs are passed explicitly — no remotes, no stored credentials) |
| classify | **CREATE** (dst branch absent) · **FAST-FORWARD** · **UP-TO-DATE** (no-op) · **DST-AHEAD** (dst contains the mirror tip plus more, e.g. a merge-update — nothing to push, the mirror is behind: bring it back with `--reverse`) · **DIVERGED** (both sides have commits the other lacks → repo fails, nothing pushed) |
| gitlink check | every new commit's `160000` entries listed in `gitlinks` must be reachable from the sub-repo's synced tip (or, if that sub-repo was not processed this run, from what dst already has). `strict` blocks the parent push; `warn` pushes with a warning |
| push | `git push <dst> refs/remotes/src/<branch>:refs/heads/<dst_branch>` — ff-only, never `--force`; `--tags` adds `refs/tags/*` |
| update branch (`--update-branch`) | when the PR base (`pr_base`) moved on dst since the branch was cut: merge the base INTO the branch in a temporary worktree (GitHub's "Update branch", never a rebase — no force push, submodule pointers stay valid) and ff-push the merge commit; **conflict** → nothing pushed; the merge is aborted and nothing is kept — resolve it by hand (see *Resolving an update-branch conflict* below). `--dry-run` performs the local merge, so it detects conflicts without pushing (and keeps nothing). Without the flag a moved base is only reported. Merge identity: `GHES_SYNC_GIT_NAME` / `GHES_SYNC_GIT_EMAIL`, else your git config. The mirror is then behind by that merge commit — see `--reverse` |
| PR | `mode = pr` and `dst_branch != pr_base`: reuse the open PR (`gh pr list --head --base`) or `gh pr create` with the commit list as body; nothing when 0 commits ahead of the base |
| summary | table `repo · action · src · dst-before · dst-after · pr · status`; exit 0 / 1 (a repo failed) / 2 (config or setup error) |

### Resolving an update-branch conflict (by hand)

Only a clean merge is automated. On a conflict the tool aborts, keeps nothing and pushes nothing;
resolve it in your own checkout and let the tool continue from there:

| where you are | do | then |
|---|---|---|
| closed network (GHES pushable) | in your checkout: `git fetch <dst_url> <pr_base> && git merge FETCH_HEAD`, resolve, commit, `git push <dst_url> HEAD:refs/heads/<branch>` (ff onto the GHES branch) | forward sync shows DST-AHEAD; bring the mirror up with `--reverse` |
| dev machine (github.com pushable) | in the mirror checkout: same merge, then `git push origin <branch>` | forward sync pushes it as FAST-FORWARD |

Never use `--force-with-lease` / `--reset-to-base` to "fix" a conflict — it drops the resolution.

## Run-book

1. Push your work to the mirror (`feature/dx-agent-dev` in all 5 repos, nested repos first, no submodule pointer bumps unless intended).
2. On the GHES-side machine: `--dry-run`, read the summary, then run for real.
3. Review/merge the PRs on GHES (`feature/dx-agent-dev → main`, `→ dev` for dx_app/dx_stream). The suite gate
   (`harness-gate`) and the sub-repo gates (`subrepo-gate`) run on those PRs.
4. GHES → public export follows the existing release procedure (rsync + `release-excluded`).

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
reachable; where github.com push is blocked it simply fails with `cannot reach/push`.

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
ghes-sync.sh --reverse --pull-only                  ghes-sync.sh --reverse --push-only --reset-to-base
```
Per repo: if the mirror branch is already contained in the base (merge-commit style merge) it is a
plain FAST-FORWARD; otherwise **RESET**: the current mirror tip is first saved to
`backup/<branch>/<YYYYmmdd-HHMMSS>` on the mirror (skip with `--no-backup`), the mirror-only commits
that disappear are listed, and the base tip is pushed with `--force-with-lease=<branch>:<mirror tip
just fetched>` — for you that is an unconditional overwrite; it only refuses when someone pushed to
the mirror branch between the fetch and the push (rerun). `reverse_branches` (`main`/`dev`
themselves) are synced ff in the same run. Afterwards update your dev checkout:
`git fetch origin && git reset --hard origin/feature/dx-agent-dev` (the tool prints this).
`--reset-to-base` is only accepted together with `--reverse`.

## Troubleshooting

| Symptom | Meaning / fix |
|---------|---------------|
| `DIVERGED` | GHES branch has commits the mirror lacks. Fetch that branch into the mirror, merge or rebase, push the mirror, rerun. The tool never force-pushes. |
| `gitlink … is NOT reachable` | The parent repo points at a sub-repo commit that is not on the synced sub-repo branch (wrong branch, or the sub-repo failed earlier in the run). Fix the pointer or sync the right sub-repo branch first. |
| `PR base 'dev' does not exist on dst` | The configured `pr_base` is missing on GHES — fix `sync.conf`. |
| `gh pr list failed` / auth errors | `gh auth status --hostname gh.deepx.ai`; the branch itself was already pushed. |
| `PR skipped (no gh CLI and no dst token)` | Push succeeded; set `GHES_SYNC_DST_TOKEN` (REST via curl) or install `gh`, then rerun — the existing branch is reused. |
| `REST ... HTTP 401/404` | Token lacks `repo` scope or the wrong host: the API base is `https://<host>/api/v3` (GHES) / `https://api.github.com`. |
| `cannot fetch src … auth/network?` / `cannot reach dst …` | No or wrong credential for a private repo (see Prerequisites), or the host is unreachable from this machine. An env token overrides the credential helper for that call. |
| `GnuTLS recv error (-110)` / `RPC failed` on push | Transient TLS/network error; pushes are retried (`GHES_SYNC_RETRIES`=3, `GHES_SYNC_RETRY_DELAY`=5 s) and git's stderr is shown. Persistent: `git config --global http.version HTTP/1.1`, then rerun (idempotent). |
| `dst probe timed out after 30s` | GHES not reachable from here (wrong network). Tune `GHES_SYNC_PROBE_TIMEOUT` (probe, default 30 s) / `GHES_SYNC_NET_TIMEOUT` (fetch/push, default 1800 s). |
| exit 2 with `unknown key` / `must be listed as an EARLIER [repo]` | Config error — the message names the section and key. |

## Tests

```bash
python3 -m pytest --rootdir=. internal/tools/ghes-sync/tests -q     # network-free: local bare repos + fake gh
```
The GHES suite gate workflow (`.github/workflows/dx-agent-dev-gate-ghes.yml`, release-excluded) runs these tests
as its own step; the public `harness_gate.sh` / `.deepx/` docs deliberately do not mention this directory.
