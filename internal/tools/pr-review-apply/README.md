# pr-review-apply — act on a bot's code review of a GHES PR

> Korean: [README-KO.md](README-KO.md) · driven by the skill `dx-internal-pr-review-apply`
> (`.deepx/skills/dx-internal-pr-review-apply/`). Local-only by design: the developer runs it on their own
> machine with their own agent; there is no CI variant (a workflow run cannot ask per-item questions and
> would need an agent CLI + model access on the runner).

When a PR opens on the closed-network GHES (`gh.deepx.ai/deepx/*`) an n8n automation reviews it and
the bot account **`dci`** leaves a summary comment plus inline review threads. This tool turns that
review into a per-thread decision record and closes the loop:

```
fetch ──> show ──> decide (per thread, by a human) ──> [fix + ONE commit] ──> commit-ref
      ──> replies (preview) ──> publish (thread replies + re-request reviewer dci)
```

The **judgement** — is a thread a change request or praise, apply it or not — is made by the agent
running the skill together with the developer, from the thread text and the current code. The tool
never classifies by emoji or headings (the bot's markers are not stable).

## Two ways in

| Source | Command | When |
|---|---|---|
| Saved PR page (`.mhtml`, Chrome "Save as → Webpage, Single File") | `fetch --mhtml <file>` | the developer PC cannot reach GHES (the usual case) |
| GHES REST API | `fetch --pr https://gh.deepx.ai/deepx/<repo>/pull/<n>` | a token or a logged-in `gh` is available |

Token chain (same as ghes-sync): `GHES_SYNC_DST_TOKEN` > `GH_ENTERPRISE_TOKEN` > `GHES_TOKEN` > `GH_TOKEN`;
with none set, `gh api` is used when `gh` is on PATH.

## Commands

```bash
T=internal/tools/pr-review-apply/pr_review_apply.py
python3 $T fetch  --mhtml ~/Downloads/pr91.mhtml          # or: fetch --pr <url>
python3 $T show   [--pending]                             # every thread + its decision state
python3 $T decide --id r18833 --apply     --note "log the failed url derivation, then exit 3"
python3 $T decide --id r18829 --skip      --note "output is Korean by design; added a one-line note"
python3 $T decide --id r18845 --defer     --note "follow-up cleanup"
python3 $T decide --id r18847 --no-action --note "praise"          # no reply is ever sent for these
python3 $T commit-ref --sha "$(git rev-parse HEAD)"        # the single fix commit, recorded on every apply
python3 $T replies                                         # preview the reply bodies
python3 $T publish --pr <url> [--retrigger rerequest|comment|both|none] [--dry-run]
python3 $T publish --queue                                 # offline: publish-queue.json + replies.md
python3 $T publish --queue-file .dx-pr-review/<owner>-<repo>-<n>/publish-queue.json   # on a GHES-reachable machine
python3 $T probe-bot --pr <url>                            # which re-trigger can reach the bot (needs repo admin)
```

State lives in `.dx-pr-review/<owner>-<repo>-<n>/` (gitignored): `review.json` (parsed review),
`decisions.json` (`apply|skip|defer|no-action`, note, commit, `published_at`), `publish-queue.json`,
`replies.md`. Every reply starts with `<!-- dx-pr-review-apply r<id> -->`, so a re-run never posts twice.

## Re-triggering the review bot

The bot runs when the PR is opened; a later push does **not** re-run it. What does:

| `--retrigger` | What is sent | Note |
|---|---|---|
| `rerequest` (default) | `POST …/pulls/<n>/requested_reviewers {"reviewers":["dci"]}` | same webhook (`pull_request.review_requested`) as the UI button "Re-request review" |
| `comment` | `POST …/issues/<n>/comments` with `--comment-text` | only if n8n subscribes to `issue_comment` |
| `both` | both | |

`probe-bot` reads the repo's webhooks (admin token) and reports which of the two the n8n hook can
receive. Without admin access keep `rerequest`. `ghes-sync.sh` can do the re-request for you on every
real push (`reviewers = dci` in `sync.override.conf`, or `--reviewers dci`).

## Closed-network flow

```
developer PC (no GHES)            mirror (github.com)        closed-network PC              GHES
fetch --mhtml  ─ decide ─ fix ─ commit ─ push ──────────────> ghes-sync.sh ───────────────> PR updated,
publish --queue  ──(copy .dx-pr-review/<dir>/)──────────────> publish --queue-file ────────> replies + dci re-requested
```

Fallback with no tooling on the far side: paste `replies.md` into the threads and click "Re-request review".

## Tests

```bash
cd internal/tools/pr-review-apply && python3 -m pytest tests -q
# fixture: tests/fixtures/pr91.mhtml (reduced real page, 10 threads) — rebuild with tests/make_fixture.py <full.mhtml> <out>
```
