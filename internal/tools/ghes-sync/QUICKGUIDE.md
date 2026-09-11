# ghes-sync — Quick Guide by Scenario

The tool never reads your working checkout. It works on its own **bare cache**
(`~/.cache/ghes-sync/<repo>.git`) and on the two remotes in `sync.conf`:
**src** = github.com mirror (`deepx-dhyang/*`), **dst** = closed-network GHES (`gh.deepx.ai/deepx/*`).
"Closed network" below = a machine that reaches GHES and can *read* github.com but not push to it.
"Open network" = a machine that can push to github.com (usually your dev box). Reference: [README.md](README.md).

Always start with `--dry-run`; it fetches, classifies and prints every push/PR it *would* do.

---

## Scenario 1 — Mirror → GHES (normal development flow)

| Step | Where | Command / action |
|---|---|---|
| 1 | dev box | Commit your work and push it to the mirror, nested repos first: `git push origin feature/dx-agent-dev` in dx_app / dx_stream → dx-runtime → dx-compiler → dx-all-suite. Do **not** bump submodule pointers unless intended. |
| 2 | closed network | `bash internal/tools/ghes-sync/ghes-sync.sh --dry-run` — expect `CREATE` / `FAST-FORWARD` / `UP-TO-DATE` per repo and a PR plan. |
| 3 | closed network | `bash internal/tools/ghes-sync/ghes-sync.sh` — fetches the mirror branch, verifies submodule pointers, ff-pushes the same-name branch to GHES, opens or reuses the PR into `pr_base` (`main`; `dev` for dx_app/dx_stream). Title: `ci: sync <repo> <branch> -> <base> (N commits)`. |
| 4 | GHES UI | Review / merge the PRs. The suite gate (`harness-gate`) and sub-repo gates (`subrepo-gate`) run on them. |

Credentials: `GHES_SYNC_SRC_TOKEN` (github.com PAT, read) and `GHES_SYNC_DST_TOKEN` or `GH_ENTERPRISE_TOKEN`
(GHES PAT, repo scope) — or `gh auth login --hostname <host> --with-token` + `gh auth setup-git`. On an
interactive terminal without tokens, git / Git Credential Manager prompts are allowed; `--non-interactive` for CI.

**Variants**
- The PR base moved on GHES since you branched (other PRs merged) and you want the branch up to date:
  add `--update-branch`. A clean merge is pushed automatically (merge commit, never rebase/force).
  A **conflict aborts** — resolve it by hand in your checkout: `git fetch <dst_url> <pr_base> && git merge FETCH_HEAD`,
  resolve, commit, then on the closed network `git push <dst_url> HEAD:refs/heads/<branch>` (ff), or on the dev box push the
  mirror and rerun the forward sync (FAST-FORWARD). Never `--force-with-lease`/`--reset-to-base` for a conflict.
- Only some repos: `--repo dx_app --repo dx-runtime`. Push without PRs: `--no-pr`. Tags: `--tags`.
- `DST-AHEAD` in the summary = GHES has commits the mirror lacks (e.g. that merge-update) — nothing to push; bring the
  mirror up with Scenario 3.
- `DIVERGED` = both sides have commits the other lacks. Decide who is right: mirror → merge/rebase in the mirror checkout
  and rerun; GHES → Scenario 2/3 with `--reset-to-base` / `--force-with-lease`.

---

## Scenario 2 — GHES → Mirror after the PRs were merged (`--reverse --reset-to-base`)

GHES squash-merges, so `main`/`dev` get one new commit per PR and the mirror's `feature/dx-agent-dev` can never
fast-forward to it. This resets the mirror branch to GHES's integration branch and syncs `main`/`dev` themselves.

| Step | Where | Command / action |
|---|---|---|
| 2.1 | closed network | `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --pull-only` — fetches GHES `feature/dx-agent-dev`, `pr_base` (`main`/`dev`) and `main` of every repo into the cache. Pushes nothing. Summary rows show `FETCHED`. |
| 2.2 | — | Carry the cache to the open network: same laptop, or copy `~/.cache/ghes-sync/` (bare repos; ~size of the repos). Nothing else needs to move — not your checkout. |
| 2.3 | open network | `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --push-only --reset-to-base --dry-run` — check the plan: per repo `main`/`dev` (ff) and the row `<repo>:feature/dx-agent-dev<=<pr_base>` marked `RESET` (or `FAST-FORWARD` if the base already contains the branch) with the list of mirror-only commits that will leave the branch. Then run it without `--dry-run`. RESET first pushes `backup/feature/dx-agent-dev/<YYYYmmdd-HHMMSS>` to the mirror (`--no-backup` to skip), then overwrites the branch (internally `--force-with-lease`; refused only if someone pushed to the mirror branch meanwhile — rerun). |
| 2.4 | open network (dev checkout) | `git fetch origin && git checkout feature/dx-agent-dev && git reset --hard origin/feature/dx-agent-dev` (stash/commit local changes first). Sub-repos: the same in each, nested first, or `git submodule update --init` if the suite pointers moved. Also `git pull --ff-only` on `main`/`dev` if you track them. |

Afterwards a forward `--dry-run` shows `UP-TO-DATE` everywhere (the GHES feature branch is usually deleted at merge; if it
still exists it may show `DST-AHEAD`/`DIVERGED` — harmless until you push new work).

`--reset-to-base` / `--force-with-lease` are accepted only with `--reverse`; the forward direction never forces.

---

## Scenario 3 — GHES → Mirror, same-name branches only (`--reverse`)

Use when GHES gained commits on branches that also exist on the mirror and no history was rewritten: `dci` bot bumps
on `main`, a merge-update commit on the feature branch (`DST-AHEAD` in a forward run), release commits.

| Step | Where | Command |
|---|---|---|
| 3.1 | closed network | `ghes-sync.sh --reverse --pull-only` |
| 3.2 | — | carry `~/.cache/ghes-sync/` |
| 3.3 | open network | `ghes-sync.sh --reverse --push-only` — per branch `CREATE` / `FAST-FORWARD` / `UP-TO-DATE` / `TO-AHEAD` (mirror ahead: nothing to do, the forward run will push it) |
| 3.4 | dev checkout | `git pull --ff-only` on the affected branches |

`DIVERGED` here means both sides moved. If GHES is right (e.g. you force-pushed a resolved branch on GHES), rerun 3.3 with
`--force-with-lease`: the mirror-only commits are listed, then the mirror branch is overwritten. If a **sub-repo** branch
was rewritten, bump the parent repos' submodule pointers to the new commits too, otherwise the forward gitlink check blocks
the parent.

---

## Scenario 4 — Something is red

| Symptom | Meaning / fix |
|---|---|
| `GnuTLS recv error (-110)` / `RPC failed` / `early EOF` on push | Transient TLS/network trouble between this machine and github.com (seen on an Orange Pi with Debian's GnuTLS git). The tool retries each push 3× (`GHES_SYNC_RETRIES`, `GHES_SYNC_RETRY_DELAY`) and prints git's own error; if it keeps failing, set `git config --global http.version HTTP/1.1` (and `http.postBuffer 524288000`) and simply **rerun the same command** — every step is idempotent: done rows become UP-TO-DATE, an existing backup is reused. |
| `cannot fetch src … auth/network?` / `cannot reach dst` | Missing or wrong PAT, or the host is not reachable from this machine. `--reverse --push-only` where github.com push is blocked simply fails like this — that is expected: run step 2.3/3.3 on the open network. |
| `dst probe timed out after 30s` | GHES not reachable from here (wrong network). `GHES_SYNC_PROBE_TIMEOUT` / `GHES_SYNC_NET_TIMEOUT` tune the limits. |
| `gitlink … is NOT reachable` | A parent repo points at a sub-repo commit that is not on the synced sub-repo branch. Fix the pointer or sync the right sub-repo branch first (nested repos are always processed first). |
| `PR skipped (no gh CLI and no dst token)` | Branch pushed; set `GHES_SYNC_DST_TOKEN` (REST via curl) or install `gh`, rerun — the open PR is reused. |
| `merge CONFLICT` (with `--update-branch`) | Resolve by hand (Scenario 1 variant); nothing was pushed or kept. |
| Sub-repo gate: `suite/.deepx/tools/scripts/subrepo_check.sh: No such file` | Old gate on that sub-repo's integration branch; the current gate waits 180 s for the suite branch and refuses an old suite explicitly. Merge the gate-workflow PR into that sub-repo's `main`/`dev`. |
| Suite gate red on `main` push while dx_app/dx_stream work sits on `dev` | Expected. The How-to-fix step dispatches (or tells you to run) the gate with `submodule_refs='dx_app=dev dx_stream=dev'`. |

Exit codes: `0` all OK · `1` at least one repo/branch failed · `2` usage/config/setup error.
