# ghes-sync — Quick Guide by Scenario

The tool never reads your working checkout. It works on its own **bare cache**
(`~/.cache/ghes-sync/<repo>.git`) and on the two remotes in `sync.conf`:
**src** = github.com mirror (`{DEEPX-MIRROR-ORG}/*`), **dst** = closed-network GHES (`gh.deepx.ai/deepx/*`).
"Closed network" below = a machine that reaches GHES and can *read* github.com but not push to it.
"Open network" = a machine that can push to github.com (usually your dev box). Reference: [README.md](README.md).

Always start with `--dry-run`; it fetches, classifies and prints every push/PR it *would* do.

## Remote naming convention (dev checkouts)

| remote | URL | role |
|---|---|---|
| `ghes` | `https://gh.deepx.ai/deepx/<repo>.git` | closed-network SCM (source of truth) |
| `mirror` | `https://github.com/{DEEPX-MIRROR-ORG}/<repo>.git` | private mirror the sync tool reads/writes |
| `ghcloud` | `https://github.com/DEEPX-AI/<repo>.git` | public channel — **only** for a repo that sets `ghcloud_url` (today: `dx_fw`) |

The public channel is normally produced by the GHES release export and is not a dev remote; see Scenario 5
for the one repo where it is the actual source.
Apply the convention to the suite and its four harness sub-repos in one go (idempotent; `--rename-origin` turns an
`origin` that equals one of the two into that name; `--dry-run` shows the plan):
```bash
bash internal/tools/ghes-sync/setup_remotes.sh --rename-origin
```
All commands below use these names. Never put a token in a remote URL — use a credential helper or
`GHES_SYNC_*_TOKEN`; a URL with a PAT ends up in `.git/config`, `git remote -v` output and pasted logs.

---

## Scenario 1 — Mirror → GHES (normal development flow)

| Step | Where | Command / action |
|---|---|---|
| 1 | dev box | Commit your work and push it to the mirror, nested repos first: `git push mirror feature/dx-agent-dev` in dx_app / dx_stream → dx-runtime → dx-compiler → dx-all-suite. Do **not** bump submodule pointers unless intended. |
| 2 | closed network | `bash internal/tools/ghes-sync/ghes-sync.sh --dry-run` — expect `CREATE` / `FAST-FORWARD` / `UP-TO-DATE` per repo and a PR plan. |
| 3 | closed network | `bash internal/tools/ghes-sync/ghes-sync.sh` — fetches the mirror branch, verifies submodule pointers, ff-pushes the same-name branch to GHES, opens or reuses the PR into `pr_base` (`main`; `dev` for dx_app/dx_stream). Title: `ci: sync <repo> <branch> -> <base> (N commits)`. |
| 4 | GHES UI | Review / merge the PRs. The suite gate (`harness-gate`) and sub-repo gates (`subrepo-gate`) run on them. |

Credentials: `GHES_SYNC_SRC_TOKEN` (github.com PAT, read) and `GHES_SYNC_DST_TOKEN` or `GH_ENTERPRISE_TOKEN` or `GHES_TOKEN`
(GHES PAT, repo scope) — or `gh auth login --hostname <host> --with-token` + `gh auth setup-git --hostname <host>`.
The tool never prompts: a host with neither fails before the first fetch, with the exact command to fix it.
Before the first run: `cp internal/tools/ghes-sync/sync.override.conf.example internal/tools/ghes-sync/sync.override.conf`
and set `src_host` (your mirror org) and `branch` (your feature branch) there — the file is gitignored and applied on top of
the shared `sync.conf`, whose two keys are intentionally empty (the tool refuses to start until they are set, or
`GHES_SYNC_SRC_HOST` / `GHES_SYNC_BRANCH` are exported).

**Variants**
- The PR base moved on GHES since you branched (other PRs merged) and you want the branch up to date:
  add `--update-branch`. A clean merge is pushed automatically (merge commit, never rebase/force).
  A **conflict aborts** — resolve it by hand in your checkout: `git fetch ghes <pr_base> && git merge ghes/<pr_base>`,
  resolve, commit, then on the closed network `git push ghes HEAD:refs/heads/<branch>` (ff), or on the dev box
  `git push mirror feature/dx-agent-dev` and rerun the forward sync (FAST-FORWARD). Never `--force-with-lease`/`--reset-to-base` for a conflict.
- Only some repos: `--repo dx_app --repo dx-runtime`. Push without PRs: `--no-pr`. Tags: `--tags`.
- Re-run the review bot after a push: `--reviewers dci` (or `reviewers = dci` in `sync.override.conf`). The bot reviews a PR when it opens, not on later pushes; re-requesting the reviewer wakes it. To act on its review items see `internal/tools/pr-review-apply/README.md`.
- `DST-AHEAD` in the summary = GHES has commits the mirror lacks (e.g. that merge-update) — nothing to push; bring the
  mirror up with Scenario 3.
- `DIVERGED` = both sides have commits the other lacks. Decide who is right: mirror → merge/rebase in the mirror checkout
  and rerun; GHES → Scenario 2/3 with `--reset-to-base` / `--force-with-lease`.

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
| Mirror afterwards | unchanged — the next forward run is `UP-TO-DATE` | GHES is ahead by the merge commit (`DST-AHEAD`) — run `--reverse` (Scenario 3) where github.com is pushable to bring it back |
| Use it when | almost always | (1) the PR page shows conflicts, (2) branch protection requires "branches up to date before merging", (3) you want the gate to run on branch + base before merging |

GHES's **Update branch** button does the same thing as `--update-branch` (a merge commit on the GHES branch); after
either one the mirror is behind, so finish with Scenario 3 (`--reverse`). Recommended order: run without the flag, look at
the PRs, and use `--update-branch --repo <name>` only for the repos that show a conflict.

---

## Scenario 2 — GHES → Mirror after the PRs were merged (`--reverse --reset-to-base`)

GHES squash-merges, so `main`/`dev` get one new commit per PR and **both** `feature/dx-agent-dev` branches — the
mirror's and the one left on GHES — are now diverged from the base. `--reset-to-base` moves both to the base tip
(GHES side where GHES is reachable, mirror side where github.com is pushable) and syncs `main`/`dev` themselves.

| Step | Where | Command / action |
|---|---|---|
| 2.1 | closed network | `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --pull-only --reset-to-base --dry-run`, then without `--dry-run` — fetches GHES `pr_base` (`main`/`dev`) and `main` of every repo into the cache (rows `FETCHED`) **and resets the GHES feature branch**: row `<repo>:feature/dx-agent-dev<=<pr_base>@GHES` — `RESET` when the stale pre-merge branch is still there (its tip is first saved to GHES `backup/feature/dx-agent-dev/<ts>`, the GHES-only commits are listed, and the tool checks for a merged PR with that head — REST with a dst token, or `gh`; without either it only reminds you to check), `CREATE` when GHES deleted the branch at merge (recreated at the base tip), `UP-TO-DATE` when already there. Internally `--force-with-lease`; nothing is pushed to the mirror in this step. |
| 2.2 | — | Carry the cache to the open network: same laptop, or copy `~/.cache/ghes-sync/` (bare repos; ~size of the repos). Nothing else needs to move — not your checkout. |
| 2.3 | open network | **Before this step make sure every mirror-only commit on `feature/dx-agent-dev` has already reached GHES** (cherry-picked/merged) — RESET drops them from the branch (they stay in `backup/…`). `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --push-only --reset-to-base --dry-run` — check the plan: per repo `main`/`dev` (ff) and the row `<repo>:feature/dx-agent-dev<=<pr_base>` marked `RESET` (or `FAST-FORWARD` if the base already contains the branch) with the list of mirror-only commits that will leave the branch. Then run it without `--dry-run`. RESET first pushes `backup/feature/dx-agent-dev/<YYYYmmdd-HHMMSS>` to the mirror (`--no-backup` to skip), then overwrites the branch (internally `--force-with-lease`; refused only if someone pushed to the mirror branch meanwhile — rerun). |
| 2.4 | open network (dev checkout) | `git fetch mirror && git checkout feature/dx-agent-dev && git reset --hard mirror/feature/dx-agent-dev` (stash/commit local changes first). Sub-repos: the same in each (nested first) — `git submodule update` also works since the suite's pointers now equal the sub-repo tips. Also `git pull --ff-only mirror main` (or `dev`) if you track them. |

Afterwards a forward `--dry-run` shows `UP-TO-DATE` everywhere: both feature branches sit on the base tip, so the next
real commits go up as `FAST-FORWARD`. (Before 2.1 also reset the GHES side, a leftover GHES branch showed
`DST-AHEAD`/`DIVERGED` here and had to be deleted by hand.) In the reverse summary the `@GHES` row's `ghes` column is the
base tip and `mirror-before/after` are the GHES branch before/after — the row is about GHES only.

`--reset-to-base` / `--force-with-lease` are accepted only with `--reverse`; the forward direction never forces.

---

**`main` / `dev` are synced in the same run.** `reverse_branches` defaults to *branch + pr_base + main*, so
every `--reverse` (with or without `--reset-to-base`) also fast-forwards the mirror's `main` and `dev` to
GHES — no extra step. A `TO-AHEAD` row on `main`/`dev` means the mirror has commits GHES lacks there;
the tool does not touch it (the forward run only syncs the feature branch). Find out why before acting
(`git log ghes/main..mirror/main` in that repo): if GHES was rewound and GHES is right, rerun with
`--force-with-lease`; if the mirror has real work, get it onto GHES first.

### What `--reverse` maps, per repo

`--reverse` pushes **same-name** branches GHES → mirror. Which branches: `reverse_branches` if set, else
**`branch` + `pr_base` + `main`** (deduplicated). `--reset-to-base` adds one more row — GHES `pr_base` →
mirror `branch` — and then *skips* the same-name sync of `branch` (it is about to be replaced anyway).
With `branch = feature/X`:

| repo | `pr_base` | `--reverse` alone (same name → same name) | `--reset-to-base` adds |
|---|---|---|---|
| dx_app, dx_stream | dev | `feature/X`, `dev`, `main` | mirror `feature/X` ← GHES `dev` (and `feature/X` is not synced by name) |
| dx-runtime, dx-compiler, dx-all-suite | main | `feature/X`, `main` | mirror `feature/X` ← GHES `main` |

The header line of each repo shows exactly this: `same-name sync: dev main | reset: mirror feature/X <= GHES dev`.
`reverse_branches` may be set under `[defaults]` (all repos) and/or under a `[repo NAME]` section (that repo only,
wins over defaults); leaving it unset gives the table above.

### No feature branch in flight — `branch = none`

`branch` is REQUIRED, so between feature branches there is nothing valid to put there. Do **not**
park `main` or `dev` in it: `--reset-to-base` would then force-rewrite that shared branch on the
mirror *and* GHES (the tool now refuses that combination outright, exit 2, before any network call).

Set `branch = none` instead — `reverse_branches` falls back to `pr_base` + `main`, which is exactly
"keep the integration branches in sync":

```bash
ghes-sync.sh --reverse --pull-only --branch none    # closed network
ghes-sync.sh --reverse --push-only --branch none    # open network
```

| repo | `pr_base` | `--reverse --branch none` syncs |
|---|---|---|
| dx_app, dx_stream | dev | `dev`, `main` |
| dx-runtime, dx-compiler, dx-all-suite | main | `main` |

`branch = none` is `--reverse`-only (forward would mean pushing the mirror's `main`/`dev` straight
into GHES, bypassing the PR review) and cannot be combined with `--reset-to-base`.

## Scenario 3 — GHES → Mirror, same-name branches only (`--reverse`)

Use when GHES gained commits on branches that also exist on the mirror and no history was rewritten: `dci` bot bumps
on `main`, a merge-update commit on the feature branch (`DST-AHEAD` in a forward run), release commits.

| Step | Where | Command |
|---|---|---|
| 3.1 | closed network | `ghes-sync.sh --reverse --pull-only` |
| 3.2 | — | carry `~/.cache/ghes-sync/` |
| 3.3 | open network | `ghes-sync.sh --reverse --push-only` — per branch `CREATE` / `FAST-FORWARD` / `UP-TO-DATE` / `TO-AHEAD` (mirror ahead: nothing to do, the forward run will push it) |
| 3.4 | dev checkout | `git pull --ff-only mirror <branch>` on the affected branches |

`DIVERGED` here means both sides moved. If GHES is right (e.g. you force-pushed a resolved branch on GHES), rerun 3.3 with
`--force-with-lease`: the mirror-only commits are listed, then the mirror branch is overwritten. If a **sub-repo** branch
was rewritten, bump the parent repos' submodule pointers to the new commits too, otherwise the forward gitlink check blocks
the parent.

---

## Scenario 4 — Something is red

Messages come out in the terminal's language (Korean locale → Korean, otherwise English; force one with
`--lang ko|en` or `GHES_SYNC_LANG`). The table below quotes the English wording; the Korean one is in
[QUICKGUIDE-KO.md](QUICKGUIDE-KO.md). Action words, env vars and git commands are the same in both.

| Symptom | Meaning / fix |
|---|---|
| `GnuTLS recv error (-110)` / `RPC failed` / `early EOF` on push | Transient TLS/network trouble between this machine and github.com (seen on an Orange Pi with Debian's GnuTLS git). The tool retries each push 3× (`GHES_SYNC_RETRIES`, `GHES_SYNC_RETRY_DELAY`) and prints git's own error; if it keeps failing, set `git config --global http.version HTTP/1.1` (and `http.postBuffer 524288000`) and simply **rerun the same command** — every step is idempotent: done rows become UP-TO-DATE, an existing backup is reused. |
| `cannot reach the mirror (to) / GHES (from) — git: Authentication failed … — the token in GH_TOKEN was REJECTED` | The token the tool used (named in the message) was refused: revoked/expired (e.g. after a leak), wrong org, or no `Contents` access on the mirror repos. Mint a new PAT; `GHES_SYNC_SRC_TOKEN` wins over `GH_TOKEN`, `GHES_SYNC_DST_TOKEN` over `GH_ENTERPRISE_TOKEN` — check which one is exported. |
| `cannot reach … — git: Could not resolve host / unable to access — NETWORK problem` | Network, not auth: the host is not reachable from this machine (wrong network, proxy, DNS). |
| `probe attempt N/3 failed — looks like a transient network/TLS error … retrying` | Transient TLS error (GnuTLS -110) on the `ls-remote` probe; the probe is retried (`GHES_SYNC_RETRIES`=3, `GHES_SYNC_RETRY_DELAY`=5 s) before the repo is failed with `still failing after N attempts — … NETWORK`. Not an auth problem. |
| `cannot fetch src […]` / `cannot reach dst (GHES)` | Missing or wrong PAT, or the host is not reachable from this machine. `--reverse --push-only` where github.com push is blocked simply fails like this — that is expected: run step 2.3/3.3 on the open network. |
| `probe timeout (30s, GHES_SYNC_PROBE_TIMEOUT exceeded)` | GHES not reachable from here (wrong network). `GHES_SYNC_PROBE_TIMEOUT` / `GHES_SYNC_NET_TIMEOUT` tune the limits. |
| `DIVERGED` on a sub-repo right after its PR was squash-merged, while the mirror carries a NEW feature branch | GHES still has the pre-merge `feature/<X>` (merge does not delete it); it shares nothing with the rebuilt mirror branch. Its content is already in `main`/`dev`, so delete it on GHES (`git push ghes --delete feature/<X>` in that repo, or the GHES UI) and rerun — the sync becomes CREATE. |
| `gitlink … NOT reachable` | A parent repo points at a sub-repo commit that is not on the synced sub-repo branch. Fix the pointer or sync the right sub-repo branch first (nested repos are always processed first). |
| `PR skipped (no gh CLI, no dst token)` | Branch pushed; the tool reads `GHES_SYNC_DST_TOKEN`, `GH_ENTERPRISE_TOKEN` or `GHES_TOKEN` — any other variable name is invisible to it. Export one of them (REST via curl) or install `gh`, rerun — the open PR is reused. |
| `cache cleanup: dropped stale copies of branches deleted on GHES — …` | Informational: the bare cache still had `refs/remotes/dst/<branch>` for a branch GHES no longer has (deleted after a squash-merge); it was dropped so it cannot be misread as DIVERGED. |
| `merge CONFLICT` (with `--update-branch`) | Resolve by hand (Scenario 1 variant); nothing was pushed or kept. |
| Sub-repo gate: `suite/.deepx/tools/scripts/subrepo_check.sh: No such file` | Old gate on that sub-repo's integration branch; the current gate waits 180 s for the suite branch and refuses an old suite explicitly. Merge the gate-workflow PR into that sub-repo's `main`/`dev`. |
| Suite gate red on `main` push while dx_app/dx_stream work sits on `dev` | Expected. The How-to-fix step dispatches (or tells you to run) the gate with `submodule_refs='dx_app=dev dx_stream=dev'`. |

Exit codes: `0` all OK · `1` at least one repo/branch failed · `2` usage/config/setup error.

---

## Scenario 5 — `dx_fw`: the content you need is only on the public channel

`dx_fw`'s source lives on GHES, but the `fw.bin` that gets flashed is published only on
`github.com/DEEPX-AI/dx_fw`. Mirroring either side would be wrong, so the repo is `sync = off` in
`sync.conf` and never appears in a sync run except as one `SKIPPED (sync=off)` row.

```bash
bash internal/tools/ghes-sync/setup_remotes.sh --checkout-ghcloud
git -C dx-runtime/dx_fw log --oneline -1           # the public channel's tip
```

(On a fresh clone the directory is still empty — `submodule update --init` skips it — and the same
command clones it there.)

What that does to `dx-runtime` (local config only — `.gitmodules` belongs to the GHES repo):

| setting | why |
|---|---|
| `submodule.dx_fw.url` → ghcloud | the mirror org has no `dx_fw` repo to clone from |
| `submodule.dx_fw.update = none` | the recorded gitlink is a GHES commit the public history never had, so `git submodule update --init` must skip it instead of failing the whole run |
| `submodule.dx_fw.ignore = all` | the checked-out content differs from the gitlink **by design** |

Going back to the GHES source: `git -C dx-runtime config --unset-all submodule.dx_fw.url` (and
`.update` / `.ignore`), then `git -C dx-runtime/dx_fw checkout ghes-main`. The `ghes` remote of that
checkout is left untouched, so both histories stay available side by side.

