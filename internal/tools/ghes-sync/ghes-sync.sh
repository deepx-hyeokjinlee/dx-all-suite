#!/usr/bin/env bash
# ghes-sync.sh — github.com mirror(src)의 설정된 브랜치를 폐쇄망 GHES(dst)로 sync:
# fetch → submodule pointer 검증 → fast-forward push(절대 force 없음) → 설정된 base 브랜치로 PR 생성/갱신.
#
# 사용법:
#   ghes-sync.sh [--config FILE] [--override FILE] [--branch NAME] [--repo NAME ...] [--pull-only | --push-only]
#                [--dry-run] [--tags] [--no-pr] [--reviewers A,B] [--update-branch]
#                [--reverse [--force-with-lease] [--reset-to-base [--no-backup]]]
#                [--cache-dir DIR] [--print-config] [--lang ko|en] [--help]
#
#   --config FILE     INI 설정 파일 (기본: 이 스크립트 옆의 sync.conf)
#   --override FILE   --config 위에 덧씌우는 로컬 overlay (기본: 같은 위치의 <config>.override.conf,
#                     즉 sync.override.conf — gitignored; sync.override.conf.example 을 복사해서 만든다).
#                     개인 값(src_host = 내 mirror org, branch = 내 feature 브랜치)은 여기에 두어
#                     sync.conf 가 `git status` 에 나타나지 않게 한다.
#   --branch NAME     sync 할 source 브랜치 (설정/override/GHES_SYNC_BRANCH 를 모두 이기고,
#                     repo별 `branch` 도 덮어쓴다; `dst_branch` 매핑은 건드리지 않는다)
#   --repo NAME       이 repo만 처리 (반복 가능; 설정 파일의 순서 유지)
#   --pull-only       src/dst를 로컬 cache로 fetch만 하고 push하지 않음
#   --push-only       src fetch 생략(cache 사용), dst는 fetch, push 수행
#   --dry-run         fetch·분류까지만 수행; push / gh 명령은 출력만 하고 실행하지 않음
#   --tags            refs/tags/* 도 push (절대 force 없음)
#   --no-pr           PR을 만들지 않음 (push만)
#   --reviewers A,B   push 가 실제 일어난(CREATE/FAST-FORWARD) PR 에 reviewer 를 (재)요청 — sync.conf 의 `reviewers` 를 덮어씀
#   --update-branch   dst의 PR base(pr_base)가 앞서갔을 때 base를 브랜치에 merge(merge commit —
#                     rebase/force push 없음)하고 ff-push. conflict면 중단(아무것도 남기지 않음)하고
#                     수동 절차를 안내. --dry-run 에서도 로컬 merge는 수행하므로 push 없이 conflict를 감지.
#   --reverse         GHES -> mirror: repo마다 `reverse_branches`(기본: branch + pr_base + main)를
#                     dst에서 src로 ff-only push, PR 없음. bare cache가 운반체: GHES 접근 가능한 곳에서
#                     `--reverse --pull-only`, github.com push 가능한 곳에서 `--reverse --push-only`.
#   --force-with-lease (--reverse 전용) DIVERGED일 때 mirror 브랜치를 GHES 브랜치로 덮어씀
#                     (lease = 방금 fetch한 mirror tip). drop되는 mirror-only commit을 먼저 나열.
#                     forward 방향은 절대 force하지 않음.
#   --reset-to-base   (--reverse 전용) PR이 (squash-)merge된 뒤, 양쪽의 `branch`를 GHES `pr_base` tip으로 맞춤.
#                     · GHES 쪽 (GHES 접근 가능할 때 = --push-only 아님; --pull-only 에서도 수행): 옛 GHES
#                       feature 브랜치를 GHES의 backup/<branch>/<timestamp> 로 저장하고, 그 tip이 head인
#                       merged PR이 있는지 확인(dst token+curl 또는 gh; 없으면 경고만)한 뒤 --force-with-lease
#                       로 GHES `branch` := `pr_base` tip (삭제+재생성을 한 번에; merge 시 삭제되어 없으면 CREATE).
#                       요약 행: <repo>:<branch><=<pr_base>@GHES
#                     · mirror 쪽 (--pull-only 아님): mirror `branch` := GHES `pr_base` tip — 가능하면 ff, 아니면
#                       RESET: mirror tip을 mirror의 backup/<branch>/<timestamp> 로 저장, drop되는 mirror-only
#                       commit 나열, --force-with-lease 로 push(fetch와 push 사이에 mirror 브랜치가 움직였을 때만 거부).
#                     --no-backup 은 양쪽 backup 브랜치 생략. 흐름: 폐쇄망 `--reverse --pull-only --reset-to-base`
#                     → 일반망 `--reverse --push-only --reset-to-base` → 다음 forward 는 UP-TO-DATE.
#   --cache-dir DIR   bare-repo cache (기본: 설정의 cache_dir, 없으면 $XDG_CACHE_HOME/ghes-sync)
#   --print-config    repo별 유효 설정을 출력하고 종료
#   --lang ko|en      출력 언어. 기본: GHES_SYNC_LANG, 없으면 터미널 locale(LC_ALL > LC_MESSAGES > LANG 이
#                     ko* 이면 ko, 그 외 en). 액션 단어·env/옵션 이름·git 명령은 두 언어에서 같다.
#
# 설정(INI): [defaults] src_host dst_host branch dst_branch pr_base mode cache_dir
#            gitlink_check(strict|warn|off) reverse_branches; [repo NAME] src_url dst_url
#            branch dst_branch pr_base mode gitlinks("<repo>:<path> ...") reverse_branches
#            path(suite 기준 checkout 경로, setup_remotes.sh 용).
#            필수이며 committed sync.conf 에서는 의도적으로 비워 둔 값: src_host, branch
#            (dst_host 도 비우면 필수) — sync.override.conf 에 설정하거나
#            GHES_SYNC_SRC_HOST / GHES_SYNC_DST_HOST / GHES_SYNC_BRANCH 를 export; 없으면 exit 2 + 힌트.
# dev checkout의 remote 이름 규칙(setup_remotes.sh): ghes = dst_host, mirror = src_host.
#            섹션 순서 = 처리 순서 (nested repo를 그것을 가리키는 parent보다 먼저).
#
# repo별 판정: CREATE(dst 브랜치 없음) · FAST-FORWARD · UP-TO-DATE · DST-AHEAD(dst가 mirror tip을
# 포함하고 더 앞섬, 예: merge-update — push할 것 없음, mirror가 뒤처짐: --reverse 사용) ·
# DIVERGED(양쪽에 서로 없는 commit → repo 실패, push 없음 — mirror에서 정리 후 재실행).
# gitlink 검사: 새 commit의 submodule pointer가 sub-repo의 sync된 tip에서 도달 가능해야 함.
# 아니면 parent를 push하지 않음(strict) / 경고만(warn).
#
# exit code: 0 모든 repo OK · 1 repo 1개 이상 실패 · 2 사용법/설정/환경 오류
#
# 요구 사항: bash >= 4, git. 선택: gh(PR), curl(gh가 없을 때 REST로 PR — Git for Windows의
#   git bash에는 curl이 있음). 둘 다 없으면 브랜치는 push되고 PR은 경고와 함께 생략.
#
# 인증(폐쇄망: https 전용, github.com SSH 불가, private repo):
#   token은 호출마다 `git -c http.<scheme://host>/.extraheader=AUTHORIZATION: basic <b64>` 로 전달
#   — git config, URL, 로그 어디에도 기록하지 않음. 이 도구는 비대화형 전용: 절대 입력을 요구하지
#   않음(GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=Never, PAT prompt 없음). host에 접근하기 전에
#   credential preflight: token env 있음 → ok; 아니면 `git credential fill`(helper, prompt 없음)이
#   답해야 함; 아니면 repo는 즉시 실패하고 정확한 해결책을 출력.
#   GHES_SYNC_SRC_TOKEN  src host용 PAT(github.com fine-grained PAT, mirror-org repo에 Contents: read).
#                        fallback: GH_TOKEN.
#   GHES_SYNC_DST_TOKEN  dst host용 PAT(GHES: repo write + pull-request). fallback:
#                        GH_ENTERPRISE_TOKEN(gh가 PR 생성에 쓰는 변수), 그 다음 GHES_TOKEN.
#   env 없이 쓰려면: `gh auth login --hostname <host> --with-token < pat.txt` 후
#   `gh auth setup-git --hostname <host>` (gh가 그 host의 git credential helper가 됨).
# timeout: GHES_SYNC_PROBE_TIMEOUT(ls-remote probe, 기본 30초), GHES_SYNC_NET_TIMEOUT(fetch/push, 기본 1800초)
#   — 접근 불가한 host는 hang 대신 빨리 실패. 일시적 network/TLS 오류(GnuTLS -110 등)는 probe/push 모두
#   GHES_SYNC_RETRIES(기본 3)회, GHES_SYNC_RETRY_DELAY(기본 5초) 간격으로 재시도.
set -euo pipefail

PROG="ghes-sync"
# ── 출력 언어 (output language): --lang > GHES_SYNC_LANG > locale (LC_ALL > LC_MESSAGES > LANG) ──
LANG_SEL=en
resolve_lang() {  # resolve_lang VALUE SOURCE — VALUE 가 비어 있으면 locale 로 결정; ko|en 이외는 exit 2
  local v="$1" src="$2" loc
  if [ -z "$v" ]; then
    loc="${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}"
    case "$loc" in ko*) v=ko ;; *) v=en ;; esac
  fi
  case "$v" in
    ko|en) LANG_SEL="$v" ;;
    *) printf '[%s] ERROR: %s must be ko|en (got '"'"'%s'"'"')\n' "$PROG" "$src" "$v" >&2; exit 2 ;;
  esac
}
resolve_lang "${GHES_SYNC_LANG:-}" "GHES_SYNC_LANG"
m() { if [ "$LANG_SEL" = ko ]; then printf '%s' "$1"; else printf '%s' "$2"; fi; }   # m KO EN → 선택된 언어의 문자열
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="$SCRIPT_DIR/sync.conf"
declare -a ONLY_REPOS=()
PULL_ONLY=0; PUSH_ONLY=0; DRY_RUN=0; TAGS=0; NO_PR=0; PRINT_CONFIG=0; CACHE_OVERRIDE=""; UPDATE_BRANCH=0; OVERRIDE=""; REVIEWERS_OVERRIDE=""; BRANCH_OVERRIDE=""
REVERSE=0; FORCE_LEASE=0; RESET_TO_BASE=0; NO_BACKUP=0

usage_ko() { sed -n '2,/^set -euo pipefail/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }
usage_en() { cat <<'USAGE_EN'
ghes-sync.sh — sync the configured branch of the github.com mirror (src) to the closed-network GHES (dst):
fetch → submodule pointer check → fast-forward push (never force) → create/refresh a PR into the configured base.

Usage:
  ghes-sync.sh [--config FILE] [--override FILE] [--branch NAME] [--repo NAME ...] [--pull-only | --push-only]
               [--dry-run] [--tags] [--no-pr] [--reviewers A,B] [--update-branch]
               [--reverse [--force-with-lease] [--reset-to-base [--no-backup]]]
               [--cache-dir DIR] [--print-config] [--lang ko|en] [--help]

  --config FILE     INI config (default: sync.conf next to this script)
  --override FILE   local overlay applied on top of --config (default: <config>.override.conf in the same
                    directory, i.e. sync.override.conf — gitignored; copy sync.override.conf.example).
                    Personal values (src_host = your mirror org, branch = your feature branch) live here so
                    sync.conf never shows up in `git status`.
  --branch NAME     the source branch to sync. Beats the config, the override file and
                    GHES_SYNC_BRANCH, and overrides a per-repo `branch` as well; a
                    `dst_branch` mapping is left alone.
  --repo NAME       only this repo (repeatable; config order is kept)
  --pull-only       fetch src/dst into the local cache, push nothing
  --push-only       skip the src fetch (use the cache), fetch dst, push
  --dry-run         fetch + classify only; print the push / gh commands instead of running them
  --tags            also push refs/tags/* (never force)
  --no-pr           do not create PRs (push only)
  --reviewers A,B   (re)request these reviewers on the PR after a push that moved the branch
                    (CREATE/FAST-FORWARD) — overrides `reviewers` in sync.conf
  --update-branch   when the PR base (pr_base) moved on dst: merge the base INTO the branch (merge commit —
                    no rebase, no force push) and ff-push. A conflict aborts leaving nothing behind and prints
                    the manual recipe. --dry-run still performs the local merge, so conflicts show without a push.
  --reverse         GHES -> mirror: per repo ff-only push `reverse_branches` (default: branch + pr_base + main)
                    from dst to src, no PR. The bare cache is the carrier: `--reverse --pull-only` where GHES is
                    reachable, `--reverse --push-only` where github.com is pushable.
  --force-with-lease (--reverse only) when DIVERGED, overwrite the mirror branch with the GHES branch
                    (lease = the mirror tip just fetched). Lists the dropped mirror-only commits first.
                    The forward direction never forces.
  --reset-to-base   (--reverse only) after the PR was (squash-)merged, set both `branch`es to the GHES `pr_base` tip.
                    · GHES side (when GHES is reachable = not --push-only; also under --pull-only): save the old GHES
                      feature branch as backup/<branch>/<timestamp> on GHES, look for a merged PR whose head is that
                      tip (dst token+curl or gh; warn otherwise), then --force-with-lease GHES `branch` := `pr_base`
                      tip (delete+recreate in one step; CREATE when the merge already deleted it).
                      Summary row: <repo>:<branch><=<pr_base>@GHES
                    · mirror side (not --pull-only): mirror `branch` := GHES `pr_base` tip — ff when possible, else
                      RESET: save the mirror tip as backup/<branch>/<timestamp> on the mirror, list the dropped
                      mirror-only commits, push with --force-with-lease (refused only if the mirror branch moved
                      between fetch and push).
                    --no-backup skips both backup branches. Flow: closed network `--reverse --pull-only --reset-to-base`
                    → open network `--reverse --push-only --reset-to-base` → the next forward run is UP-TO-DATE.
  --cache-dir DIR   bare-repo cache (default: cache_dir from the config, else $XDG_CACHE_HOME/ghes-sync)
  --print-config    print the effective per-repo config and exit
  --lang ko|en      output language. Default: GHES_SYNC_LANG, else the terminal locale (LC_ALL > LC_MESSAGES >
                    LANG starting with ko → ko, anything else → en). Action words, env/option names and git
                    commands are identical in both languages.

Config (INI): [defaults] src_host dst_host branch dst_branch pr_base mode cache_dir
              gitlink_check(strict|warn|off) reverse_branches reviewers; [repo NAME] src_url dst_url
              branch dst_branch pr_base mode gitlinks("<repo>:<path> ...") reverse_branches reviewers
              path (checkout path relative to the suite, for setup_remotes.sh).
              Required and intentionally EMPTY in the committed sync.conf: src_host, branch (dst_host too
              if emptied) — set them in sync.override.conf or export GHES_SYNC_SRC_HOST / GHES_SYNC_DST_HOST /
              GHES_SYNC_BRANCH; otherwise exit 2 with a hint.
Remote naming in dev checkouts (setup_remotes.sh): ghes = dst_host, mirror = src_host.
              Section order = processing order (nested repos before the parent that gitlinks them).

Per-repo verdict: CREATE (dst branch absent) · FAST-FORWARD · UP-TO-DATE · DST-AHEAD (dst contains the mirror
tip plus more, e.g. a merge-update — nothing to push, the mirror is behind: use --reverse) ·
DIVERGED (both sides have commits the other lacks → repo fails, nothing pushed — clean up on the mirror, rerun).
gitlink check: the submodule pointers of the new commits must be reachable from the sub-repo's synced tip;
otherwise the parent is not pushed (strict) / a warning is printed (warn).

Exit code: 0 every repo OK · 1 at least one repo failed · 2 usage / config / environment error

Requirements: bash >= 4, git. Optional: gh (PRs), curl (PRs via REST when gh is absent — Git for Windows'
  git bash has curl). With neither, branches are pushed and the PR is skipped with a warning.

Auth (closed network: https only, no SSH to github.com, private repos):
  the token is passed per call as `git -c http.<scheme://host>/.extraheader=AUTHORIZATION: basic <b64>`
  — never written to git config, a URL or the log. Non-interactive only: the tool never prompts
  (GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=Never, no PAT prompt). Before touching a host it runs a
  credential preflight: token env present → ok; else `git credential fill` (helper, no prompt) must answer;
  else the repo fails immediately with the exact fix.
  GHES_SYNC_SRC_TOKEN  PAT for the src host (github.com fine-grained PAT, Contents: read on the mirror-org repos).
                       fallback: GH_TOKEN.
  GHES_SYNC_DST_TOKEN  PAT for the dst host (GHES: repo write + pull-request). fallback:
                       GH_ENTERPRISE_TOKEN (what gh uses to create the PR), then GHES_TOKEN.
  Without env vars: `gh auth login --hostname <host> --with-token < pat.txt` then
  `gh auth setup-git --hostname <host>` (gh becomes that host's git credential helper).
Timeouts: GHES_SYNC_PROBE_TIMEOUT (ls-remote probe, default 30 s), GHES_SYNC_NET_TIMEOUT (fetch/push, default 1800 s)
  — an unreachable host fails fast instead of hanging. Transient network/TLS errors (GnuTLS -110 etc.) are retried
  GHES_SYNC_RETRIES (default 3) times, GHES_SYNC_RETRY_DELAY (default 5 s) apart, for probes and pushes alike.
USAGE_EN
}
usage() { if [ "$LANG_SEL" = ko ]; then usage_ko; else usage_en; fi; }

# ── 출력 형식 ─────────────────────────────────────────────────────────────────
# 전역 메시지:      [ghes-sync] 메시지
# repo별 메시지:    [ghes-sync] <repo(:branch)>  │ 메시지      (repo 열 폭은 이번 실행의 가장 긴 key)
# repo 헤더:        [ghes-sync] ▶ <repo>: ...
# 표(요약)의 셀은 ASCII만 사용해 열 정렬을 유지하고, 긴 설명은 표 아래 [n] 번호로 따로 출력한다.
NAME_W=12
log()   { printf '[%s] %s\n' "$PROG" "$*"; }
rlog()  { local k="$1"; shift; printf '[%s] %-*s │ %s\n' "$PROG" "$NAME_W" "$k" "$*"; }
hdr()   { printf '[%s] ▶ %s\n' "$PROG" "$*"; }
warn()  { printf '[%s] WARNING: %s\n' "$PROG" "$*" >&2; }
rwarn() { local k="$1"; shift; printf '[%s] %-*s │ WARNING: %s\n' "$PROG" "$NAME_W" "$k" "$*" >&2; }
die2()  { printf '[%s] ERROR: %s\n' "$PROG" "$*" >&2; exit 2; }
trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }
has_word() { local w; for w in $2; do [ "$w" = "$1" ] && return 0; done; return 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --config)    [ $# -ge 2 ] || die2 "$(m "--config 에 값이 필요합니다" "--config needs a value")"; CONFIG="$2"; shift 2 ;;
    --override)  [ $# -ge 2 ] || die2 "$(m "--override 에 값이 필요합니다" "--override needs a value")"; OVERRIDE="$2"; shift 2 ;;
    --branch)    [ $# -ge 2 ] || die2 "$(m "--branch 에 값이 필요합니다" "--branch needs a value")"; BRANCH_OVERRIDE="$2"; shift 2 ;;
    --repo)      [ $# -ge 2 ] || die2 "$(m "--repo 에 값이 필요합니다" "--repo needs a value")"; ONLY_REPOS+=("$2"); shift 2 ;;
    --cache-dir) [ $# -ge 2 ] || die2 "$(m "--cache-dir 에 값이 필요합니다" "--cache-dir needs a value")"; CACHE_OVERRIDE="$2"; shift 2 ;;
    --pull-only) PULL_ONLY=1; shift ;;
    --push-only) PUSH_ONLY=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --tags)      TAGS=1; shift ;;
    --no-pr)     NO_PR=1; shift ;;
    --reviewers) [ $# -ge 2 ] || die2 "$(m "--reviewers 에 값이 필요합니다" "--reviewers needs a value")"; REVIEWERS_OVERRIDE="$2"; shift 2 ;;
    --update-branch) UPDATE_BRANCH=1; shift ;;
    --reverse)   REVERSE=1; shift ;;
    --force-with-lease) FORCE_LEASE=1; shift ;;
    --reset-to-base) RESET_TO_BASE=1; shift ;;
    --no-backup) NO_BACKUP=1; shift ;;
    --print-config) PRINT_CONFIG=1; shift ;;
    --lang)      [ $# -ge 2 ] || die2 "$(m "--lang 에 값이 필요합니다 (ko|en)" "--lang needs a value (ko|en)")"; resolve_lang "$2" "--lang"; shift 2 ;;
    -h|--help)   usage; exit 0 ;;
    *) die2 "$(m "알 수 없는 인자 '$1' (--help 참고)" "unknown argument '$1' (see --help)")" ;;
  esac
done
[ "$PULL_ONLY" -eq 1 ] && [ "$PUSH_ONLY" -eq 1 ] && die2 "$(m "--pull-only 과 --push-only 는 함께 쓸 수 없습니다" "--pull-only and --push-only cannot be combined")"
[ "$FORCE_LEASE" -eq 1 ] && [ "$REVERSE" -eq 0 ] && die2 "$(m "--force-with-lease 는 --reverse 와 함께만 허용됩니다 (forward 방향 mirror -> GHES 는 절대 force하지 않음)" "--force-with-lease is only accepted together with --reverse (the forward direction mirror -> GHES never forces)")"
[ "$RESET_TO_BASE" -eq 1 ] && [ "$REVERSE" -eq 0 ] && die2 "$(m "--reset-to-base 는 --reverse 와 함께만 허용됩니다 (GHES의 pr_base 로 MIRROR 브랜치를 재작성함)" "--reset-to-base is only accepted together with --reverse (it rewrites the MIRROR branch to GHES pr_base)")"
command -v git >/dev/null 2>&1 || die2 "$(m "PATH 에 git 이 없습니다" "git is not on PATH")"
# 비대화형 전용: 터미널 prompt나 credential-manager UI 에서 절대 멈추지 않는다.
export GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never
HAVE_GH=0;   command -v gh   >/dev/null 2>&1 && HAVE_GH=1
HAVE_CURL=0; command -v curl >/dev/null 2>&1 && HAVE_CURL=1
# token 을 어느 env 변수에서 읽었는지(오류 메시지용).
SRC_TOKEN_SRC=none
if   [ -n "${GHES_SYNC_SRC_TOKEN:-}" ]; then SRC_TOKEN_SRC=GHES_SYNC_SRC_TOKEN
elif [ -n "${GH_TOKEN:-}" ];            then SRC_TOKEN_SRC=GH_TOKEN; fi
DST_TOKEN_SRC=none
if   [ -n "${GHES_SYNC_DST_TOKEN:-}" ];  then DST_TOKEN_SRC=GHES_SYNC_DST_TOKEN
elif [ -n "${GH_ENTERPRISE_TOKEN:-}" ];  then DST_TOKEN_SRC=GH_ENTERPRISE_TOKEN
elif [ -n "${GHES_TOKEN:-}" ];           then DST_TOKEN_SRC=GHES_TOKEN; fi
SRC_TOKEN="${GHES_SYNC_SRC_TOKEN:-${GH_TOKEN:-}}"
DST_TOKEN="${GHES_SYNC_DST_TOKEN:-${GH_ENTERPRISE_TOKEN:-${GHES_TOKEN:-}}}"
SRC_VARS="GHES_SYNC_SRC_TOKEN $(m "(또는 GH_TOKEN)" "(or GH_TOKEN)")"
DST_VARS="GHES_SYNC_DST_TOKEN $(m "(또는 GH_ENTERPRISE_TOKEN / GHES_TOKEN)" "(or GH_ENTERPRISE_TOKEN / GHES_TOKEN)")"

# network timeout(초): 접근 불가한 host는 TCP timeout까지 hang하지 않고 빨리 실패해야 한다.
PROBE_TIMEOUT="${GHES_SYNC_PROBE_TIMEOUT:-30}"   # ls-remote 연결 probe
NET_TIMEOUT="${GHES_SYNC_NET_TIMEOUT:-1800}"     # fetch / push (최초 대용량 fetch는 오래 걸림)
tmo() { local secs="$1"; shift; if command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"; else "$@"; fi; }
RETRIES="${GHES_SYNC_RETRIES:-3}"; RETRY_DELAY="${GHES_SYNC_RETRY_DELAY:-5}"
# 일시적(재시도 가치가 있는) network/TLS 오류의 stderr 패턴 — 인증 거부나 DNS 실패는 포함하지 않음
TRANSIENT_RE='GnuTLS|TLS|SSL|RPC failed|early EOF|Connection reset|timed out|remote end hung up|Recv failure|Empty reply|Connection timed'

# ── token 선택: side(src/dst) 가 아니라 URL 의 host 로 고른다 ────────────────
# 같은 host 에 mirror 와 다른 org(공개 채널 등)가 함께 있을 수 있으므로, side 로 고르면
# 엉뚱한 PAT 를 보내게 된다(GHES PAT 를 github.com 으로 보내면 public repo 라도 거절된다).
#   ① GHES_SYNC_TOKEN_<HOST>  (github.com → GHES_SYNC_TOKEN_GITHUB_COM)
#   ② 설정된 두 host(src_host / dst_host) 중 URL 과 같은 host 쪽의 token
#   ③ 그 외(설정에 없는 host) 는 종전대로 자기 side 의 token
host_of() { local h; case "$1" in http://*|https://*) h="${1#*://}"; printf '%s' "${h%%/*}" ;; *) printf '' ;; esac; }
token_env_for() { printf 'GHES_SYNC_TOKEN_%s' "$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]' | tr '.-' '__')"; }
SRC_HOST_H=""; DST_HOST_H=""          # 설정 파싱 후 채운다
TOKEN_VAL=""; TOKEN_VAR=none
pick_token() {  # pick_token src|dst URL → TOKEN_VAL / TOKEN_VAR (오류 메시지에 쓸 env 변수명)
  local side="$1" url="$2" host ev
  if [ "$side" = src ]; then TOKEN_VAL="$SRC_TOKEN"; TOKEN_VAR="$SRC_TOKEN_SRC"
  else TOKEN_VAL="$DST_TOKEN"; TOKEN_VAR="$DST_TOKEN_SRC"; fi
  host="$(host_of "$url")"; [ -n "$host" ] || return 0
  ev="$(token_env_for "$host")"
  if [ -n "${!ev:-}" ]; then TOKEN_VAL="${!ev}"; TOKEN_VAR="$ev"; return 0; fi
  if [ "$side" = src ] && [ -n "$DST_HOST_H" ] && [ "$host" = "$DST_HOST_H" ] && [ "$host" != "$SRC_HOST_H" ]; then
    TOKEN_VAL="$DST_TOKEN"; TOKEN_VAR="$DST_TOKEN_SRC"
  elif [ "$side" = dst ] && [ -n "$SRC_HOST_H" ] && [ "$host" = "$SRC_HOST_H" ] && [ "$host" != "$DST_HOST_H" ]; then
    TOKEN_VAL="$SRC_TOKEN"; TOKEN_VAR="$SRC_TOKEN_SRC"
  fi
  return 0
}
# token_for is the value-only form, written for `$(token_for side url)`: the subshell
# discards the TOKEN_VAL/TOKEN_VAR it sets, which is exactly what callers of the value
# want. Anything that needs the env-variable NAME (error messages) must call pick_token
# directly, in THIS shell — probe_reason is the only such caller.
token_for() { pick_token "$1" "$2"; printf '%s' "$TOKEN_VAL"; }

# push_target_ok side URL → 0: 허용. push 대상이 설정된 host/org 안인지 확인한다.
# per-repo dst_host/dst_url override 로 공개 채널(github.com/DEEPX-AI) 같은 남의 org 를 가리켜 두면
# forward 한 번에 private 브랜치가 공개 repo 로 push + PR 까지 되어 버린다 — 그 사고를 막는다.
# http(s) 끼리일 때만 검사(file:// 등 로컬/테스트 URL 은 대상 아님). allow_foreign_dst = yes 면 통과.
push_target_ok() {
  # `allowed` is the host+org this side is configured to write to: dst_host when pushing
  # to GHES (forward), src_host when pushing to the mirror (--reverse). The target URL
  # must sit under it.
  local side="$1" url="$2" allowed
  [ "${R_ALLOW_FOREIGN:-}" = yes ] && return 0
  case "$side" in
    src) allowed="${DEF[src_host]:-}" ;;
    *)   allowed="${DEF[dst_host]:-}" ;;
  esac
  case "$allowed" in http://*|https://*) ;; *) return 0 ;; esac
  case "$url"     in http://*|https://*) ;; *) return 0 ;; esac
  case "$url/"    in "${allowed%/}/"*) return 0 ;; esac
  return 1
}
push_target_msg() {  # push_target_msg side URL
  local base="${DEF[dst_host]:-}"; [ "$1" = src ] && base="${DEF[src_host]:-}"
  m "push 대상이 설정된 host/org 밖입니다: $2 (설정: $base). 실수로 남의 org(예: 공개 채널)에 push 하는 것을 막기 위해 차단했습니다 — 의도한 것이면 [repo $R_NAME] 에 allow_foreign_dst = yes 를 추가하세요 (sync 자체를 하지 않을 repo 라면 sync = off)" \
    "the push target is outside the configured host/org: $2 (configured: $base). Refused so a private branch cannot land in someone else's org (e.g. the public channel) by accident — if it is intended, add allow_foreign_dst = yes to [repo $R_NAME] (or sync = off if the repo should not be synced at all)"
}

# auth_opts URL TOKEN → http(s) URL이고 TOKEN이 있으면 전역 배열 AUTH_OPTS 를
# `-c http.<scheme://host>/.extraheader=...` 로, 아니면(file://, ssh, token 없음) 빈 배열로 설정.
declare -a AUTH_OPTS=()
auth_opts() {
  AUTH_OPTS=()
  local url="$1" token="$2" host b64
  [ -n "$token" ] || return 0
  case "$url" in http://*|https://*) ;; *) return 0 ;; esac
  host="${url#*://}"; host="${host%%/*}"
  b64="$(printf 'x-access-token:%s' "$token" | base64 | tr -d '\n')"
  AUTH_OPTS=(-c "http.${url%%://*}://${host}/.extraheader=AUTHORIZATION: basic ${b64}")
}
auth_hint() {  # auth_hint src|dst HOSTURL
  local var="$SRC_VARS"; [ "$1" = dst ] && var="$DST_VARS"
  if [ "$LANG_SEL" = ko ]; then printf '인증/네트워크 문제? private repo는 PAT가 필요합니다: export %s, 또는 `gh auth login --hostname <host> --with-token` + `gh auth setup-git --hostname <host>`; URL: %s' "$var" "$2"
  else printf 'auth/network problem? private repos need a PAT: export %s, or `gh auth login --hostname <host> --with-token` + `gh auth setup-git --hostname <host>`; URL: %s' "$var" "$2"; fi
}

# probe URL TOKEN → PROBE_OUT = `git ls-remote --heads` 출력, PROBE_ERR = git stderr 마지막 줄,
# PROBE_TRIES = 시도 횟수; 반환값 = git rc (124 = timeout). 일시적 network/TLS 오류는 재시도.
PROBE_OUT=""; PROBE_ERR=""; PROBE_TRIES=1
probe() {
  local url="$1" token="$2" errf rc attempt=1; errf="$(mktemp)"
  while :; do
    auth_opts "$url" "$token"
    PROBE_OUT="$(tmo "$PROBE_TIMEOUT" git "${AUTH_OPTS[@]}" ls-remote --heads "$url" 2>"$errf")"; rc=$?
    PROBE_ERR="$(grep -v '^$' "$errf" | tail -n1)"; PROBE_TRIES="$attempt"
    [ "$rc" -eq 0 ] && break
    [ "$rc" -eq 124 ] && break
    printf '%s' "$PROBE_ERR" | grep -qiE "$TRANSIENT_RE" || break
    [ "$attempt" -ge "$RETRIES" ] && break
    warn "$(m "probe $attempt/$RETRIES 회 실패 — 일시적 network/TLS 오류로 보임 (${PROBE_ERR:-stderr 없음}) — ${RETRY_DELAY}초 후 재시도" "probe attempt $attempt/$RETRIES failed — looks like a transient network/TLS error (${PROBE_ERR:-no stderr}) — retrying in ${RETRY_DELAY}s")"
    attempt=$((attempt + 1)); sleep "$RETRY_DELAY"
  done
  rm -f "$errf"
  return "$rc"
}
# probe_reason src|dst URL RC → 한 줄 진단: timeout / token REJECTED(어느 env 변수) / NETWORK / 기타
probe_reason() {
  local side="$1" url="$2" rc="$3" var pre=""
  pick_token "$side" "$url"; var="$TOKEN_VAR"
  [ "$PROBE_TRIES" -gt 1 ] && pre="$(m "${PROBE_TRIES}회 시도 후에도 실패 — " "still failing after ${PROBE_TRIES} attempts — ")"
  if [ "$rc" -eq 124 ]; then printf '%s' "$(m "${pre}probe timeout (${PROBE_TIMEOUT}초, GHES_SYNC_PROBE_TIMEOUT 초과) — 이 기계에서 $url 에 접근 가능한지 확인하세요" "${pre}probe timeout (${PROBE_TIMEOUT}s, GHES_SYNC_PROBE_TIMEOUT exceeded) — check that $url is reachable from this machine")"; return; fi
  # "repo 가 없다" 는 "token 이 거부됐다" 와 다른 문제다. GitHub/GHES 는 권한이 없는 private repo 에도
  # 404(Repository not found)를 주므로 둘을 한 문장으로 안내한다 — token 을 다시 발급하라고만 하면 오진이 된다.
  if printf '%s' "$PROBE_ERR" | grep -qiE 'repository not found|not appear to be a git repository'; then
    printf '%s' "$(m "${pre}git: $PROBE_ERR — repo 가 없거나 token 에 이 repo 접근 권한이 없습니다 — ① URL/이름 확인: $url ② org 에 repo 가 아직 생성되지 않았을 수 있습니다 ③ fine-grained PAT 의 repository 선택에서 이 repo 가 빠졌을 수 있습니다 (사용된 token: $var)" "${pre}git: $PROBE_ERR — the repo does not exist, or this token cannot see it — (1) check the URL/name: $url (2) the repo may not have been created in that org yet (3) a fine-grained PAT may not list this repository (token used: $var)")"
    return
  fi
  if printf '%s' "$PROBE_ERR" | grep -qiE 'authentication failed|invalid username|invalid (password|token)|error: 401|error: 403|could not read (username|password)|permission denied'; then
    if [ "$var" = none ]; then printf '%s' "$(m "${pre}git: $PROBE_ERR — token env 변수가 설정되지 않았습니다; $(auth_hint "$side" "$url")" "${pre}git: $PROBE_ERR — no token env variable is set; $(auth_hint "$side" "$url")")"
    else printf '%s' "$(m "${pre}git: $PROBE_ERR — $var 의 token이 REJECTED 되었습니다 (revoked/expired, 다른 org, 또는 이 repo 접근 권한 없음). 새 PAT를 발급해 $var 를 다시 export 하세요" "${pre}git: $PROBE_ERR — the token in $var was REJECTED (revoked/expired, wrong org, or no access to this repo). Mint a new PAT and export $var again")"; fi
  elif printf '%s' "$PROBE_ERR" | grep -qiE "could not resolve|unable to access|connection|timed out|ssl|tls|network|$TRANSIENT_RE"; then
    printf '%s' "$(m "${pre}git: $PROBE_ERR — NETWORK 문제 (이 기계에서 host에 접근 불가: 망 / proxy / DNS, 또는 일시적 TLS 오류) — 인증 문제가 아닙니다" "${pre}git: $PROBE_ERR — NETWORK problem (host not reachable from this machine: network / proxy / DNS, or a transient TLS error) — not an auth problem")"
  else
    printf '%s' "$(m "${pre}git: ${PROBE_ERR:-오류 텍스트 없음} — $(auth_hint "$side" "$url")" "${pre}git: ${PROBE_ERR:-no error text} — $(auth_hint "$side" "$url")")"
  fi
}

# credential preflight — 이 도구는 절대 prompt하지 않으므로, git이 인증할 수 있는지 먼저 확인한다.
has_creds() {  # has_creds URL TOKEN → token이 있거나, http(s)가 아니거나, credential helper가(prompt 없이) 답하면 0
  local url="$1" token="$2"
  [ -n "$token" ] && return 0
  case "$url" in http://*|https://*) ;; *) return 0 ;; esac
  printf 'url=%s\n\n' "$url" | git credential fill 2>/dev/null | grep -q '^password='
}
cred_hint() {  # cred_hint src|dst URL
  local host="${2#*://}"; host="${host%%/*}"
  local var="$SRC_VARS"; [ "$1" = dst ] && var="$DST_VARS"
  printf '%s' "$(m "$2 에 대한 credential이 없고 이 도구는 절대 입력을 요구하지 않습니다 — $var=<PAT> 를 export 하거나, 기계당 1회: gh auth login --hostname $host --with-token < pat.txt && gh auth setup-git --hostname $host" "no credential for $2 and this tool never prompts — export $var=<PAT>, or once per machine: gh auth login --hostname $host --with-token < pat.txt && gh auth setup-git --hostname $host")"
}

GPUSH_ERR=""   # 마지막 gpush의 git stderr 마지막 줄(알려진 network 오류면 힌트 추가)
# gpush URL TOKEN REFSPEC [PUSH-OPTS...] — $cache 에서 `git push -q OPTS URL REFSPEC`; 일시적(network/TLS)
# 오류는 재시도, 거부(non-ff, lease, 인증)는 재시도하지 않음. --force 는 절대 붙이지 않음.
gpush() {
  local url="$1" token="$2" refspec="$3"; shift 3
  local attempt=1 rc errf; errf="$(mktemp)"
  while :; do
    auth_opts "$url" "$token"
    tmo "$NET_TIMEOUT" git "${AUTH_OPTS[@]}" -C "$cache" push -q "$@" "$url" "$refspec" 2>"$errf"; rc=$?
    [ "$rc" -eq 0 ] && { rm -f "$errf"; GPUSH_ERR=""; return 0; }
    GPUSH_ERR="$(grep -vE '^(remote:|To |$)' "$errf" | tail -n1)"
    if grep -qiE 'rejected|non-fast-forward|stale info|force-with-lease|permission|denied|authentication|401|403|404' "$errf"; then break; fi
    if [ "$attempt" -ge "$RETRIES" ]; then break; fi
    warn "$(m "push $attempt/$RETRIES 회 실패 (${GPUSH_ERR:-stderr 없음}) — ${RETRY_DELAY}초 후 재시도" "push attempt $attempt/$RETRIES failed (${GPUSH_ERR:-no stderr}) — retrying in ${RETRY_DELAY}s")"
    attempt=$((attempt + 1)); sleep "$RETRY_DELAY"
  done
  rm -f "$errf"
  if printf '%s' "$GPUSH_ERR" | grep -qiE "$TRANSIENT_RE|Could not resolve|unable to access"; then
    GPUSH_ERR="$GPUSH_ERR $(m "[network/TLS 오류 — 재실행하세요; 계속되면: git config --global http.version HTTP/1.1  (및 http.postBuffer 524288000)]" "[network/TLS error — rerun; if it persists: git config --global http.version HTTP/1.1  (and http.postBuffer 524288000)]")"
  fi
  return "$rc"
}

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
declare -A DEF=() CFG=()
declare -a REPOS=()
KNOWN_DEF="src_host dst_host branch dst_branch pr_base mode cache_dir gitlink_check reverse_branches reviewers"
KNOWN_REPO="src_url dst_url src_host dst_host branch dst_branch pr_base mode sync ghcloud_url ghcloud_ref allow_foreign_dst gitlinks reverse_branches path reviewers"

parse_conf() {  # parse_conf FILE OVERLAY(0|1) — OVERLAY: 기본 파일에 이미 있는 [repo]는 병합(오류 아님)
  local file="$1" overlay="${2:-0}"
  [ -f "$file" ] || die2 "$(m "설정 파일을 찾을 수 없습니다: $file" "config file not found: $file")"
  local section="" raw line key val name
  while IFS= read -r raw || [ -n "$raw" ]; do
    line="$(trim "$raw")"
    [ -z "$line" ] && continue
    case "$line" in '#'*|';'*) continue ;; esac
    if [[ "$line" =~ ^(.*[^[:space:]])[[:space:]]+[#\;].*$ ]]; then line="${BASH_REMATCH[1]}"; fi
    if [[ "$line" =~ ^\[(.+)\]$ ]]; then
      section="$(trim "${BASH_REMATCH[1]}")"
      if [ "$section" = defaults ]; then :
      elif [[ "$section" == repo\ * ]]; then
        name="$(trim "${section#repo}")"
        if has_word "$name" "${REPOS[*]:-}"; then [ "$overlay" -eq 1 ] || die2 "$(m "$file 에 [repo $name] 이 중복됩니다" "duplicate [repo $name] in $file")"
        else REPOS+=("$name"); fi
        section="repo:$name"
      else die2 "$(m "$file 에 알 수 없는 섹션 [$section]" "unknown section [$section] in $file")"; fi
      continue
    fi
    [[ "$line" == *=* ]] || die2 "$(m "$file 의 잘못된 줄: '$line'" "malformed line in $file: '$line'")"
    key="$(trim "${line%%=*}")"; val="$(trim "${line#*=}")"
    case "$section" in
      defaults) has_word "$key" "$KNOWN_DEF" || die2 "$(m "$file 의 [defaults] 에 알 수 없는 key '$key' (허용: $KNOWN_DEF)" "unknown key '$key' in [defaults] of $file (allowed: $KNOWN_DEF)")"
                DEF[$key]="$val" ;;
      repo:*)   has_word "$key" "$KNOWN_REPO" || die2 "$(m "$file 의 [$section] 에 알 수 없는 key '$key' (허용: $KNOWN_REPO)" "unknown key '$key' in [$section] of $file (allowed: $KNOWN_REPO)")"
                CFG["${section#repo:}.$key"]="$val" ;;
      *)        die2 "$(m "$file 에서 key '$key' 가 [section] 앞에 나옵니다" "key '$key' appears before any [section] in $file")" ;;
    esac
  done < "$file"
}

# eff NAME KEY → repo 값, 없으면 [defaults], 없으면 내장 기본값
eff() {
  local name="$1" key="$2" v
  v="${CFG[$name.$key]:-}"; [ -n "$v" ] && { printf '%s' "$v"; return; }
  v="${DEF[$key]:-}";       [ -n "$v" ] && { printf '%s' "$v"; return; }
  case "$key" in
    pr_base)       printf 'main' ;;
    mode)          printf 'pr' ;;
    gitlink_check) printf 'strict' ;;
    cache_dir)     printf '%s' "${XDG_CACHE_HOME:-$HOME/.cache}/ghes-sync" ;;
    *)             printf '' ;;
  esac
}
join_url() { local host="$1" name="$2"; printf '%s/%s.git' "${host%/}" "$name"; }
# repo_slug URL → `gh -R` 용 HOST/OWNER/NAME (https, scp형 git@host:owner/name, file://)
repo_slug() {
  local u="$1"; u="${u%/}"; u="${u%.git}"; u="${u#*://}"; u="${u#*@}"; u="${u/:/\/}"
  local IFS=/; local -a p; read -r -a p <<<"$u"; local n=${#p[@]}
  [ "$n" -ge 3 ] || die2 "$(m "url '$1' 에서 HOST/OWNER/REPO 를 얻을 수 없습니다" "cannot derive HOST/OWNER/REPO from url '$1'")"
  printf '%s/%s/%s' "${p[n-3]}" "${p[n-2]}" "${p[n-1]}"
}

# resolve NAME → R_* 전역
resolve() {
  local name="$1" v
  R_NAME="$name"
  R_BRANCH="$(eff "$name" branch)"
  [ -n "$R_BRANCH" ] || die2 "$(m "[repo $name]: 'branch' 가 비어 있습니다 — $OVERRIDE_HINT 에 feature 브랜치를 설정([defaults] branch = feature/<topic>)하거나 export GHES_SYNC_BRANCH=<branch>" "[repo $name]: 'branch' is empty — set your feature branch in $OVERRIDE_HINT ([defaults] branch = feature/<topic>) or export GHES_SYNC_BRANCH=<branch>")"
  R_DST_BRANCH="$(eff "$name" dst_branch)"; [ -n "$R_DST_BRANCH" ] || R_DST_BRANCH="$R_BRANCH"
  R_SRC_URL="${CFG[$name.src_url]:-}"
  if [ -z "$R_SRC_URL" ]; then
    v="$(eff "$name" src_host)"
    [ -n "$v" ] || die2 "$(m "[repo $name]: 'src_host' 가 비어 있습니다 — $OVERRIDE_HINT 에 private mirror org를 설정([defaults] src_host = https://github.com/<MIRROR-ORG>)하거나 export GHES_SYNC_SRC_HOST=<url>" "[repo $name]: 'src_host' is empty — set your private mirror org in $OVERRIDE_HINT ([defaults] src_host = https://github.com/<MIRROR-ORG>) or export GHES_SYNC_SRC_HOST=<url>")"
    R_SRC_URL="$(join_url "$v" "$name")"
  fi
  R_DST_URL="${CFG[$name.dst_url]:-}"
  if [ -z "$R_DST_URL" ]; then
    v="$(eff "$name" dst_host)"
    [ -n "$v" ] || die2 "$(m "[repo $name]: 'dst_host' 가 비어 있습니다 — $OVERRIDE_HINT 에 GHES org를 설정([defaults] dst_host = https://gh.deepx.ai/deepx)하거나 export GHES_SYNC_DST_HOST=<url>" "[repo $name]: 'dst_host' is empty — set the GHES org in $OVERRIDE_HINT ([defaults] dst_host = https://gh.deepx.ai/deepx) or export GHES_SYNC_DST_HOST=<url>")"
    R_DST_URL="$(join_url "$v" "$name")"
  fi
  R_PR_BASE="$(eff "$name" pr_base)"
  R_MODE="$(eff "$name" mode)"; has_word "$R_MODE" "pr push" || die2 "$(m "[repo $name]: mode 는 pr|push 여야 합니다 (현재 '$R_MODE')" "[repo $name]: mode must be pr|push (got '$R_MODE')")"
  # sync = on|off — off: 이 repo 는 설정에만 존재(설정/경로는 setup_remotes.sh 가 사용)하고
  # ghes-sync 는 어느 방향으로도 fetch/push 하지 않는다 (예: dx_fw — 코드는 GHES, 배포 바이너리는 공개 채널).
  R_SYNC="${CFG[$name.sync]:-on}"; has_word "$R_SYNC" "on off" || die2 "$(m "[repo $name]: sync 는 on|off 여야 합니다 (현재 '$R_SYNC')" "[repo $name]: sync must be on|off (got '$R_SYNC')")"
  R_GHCLOUD_URL="${CFG[$name.ghcloud_url]:-}"      # setup_remotes.sh 전용: 세 번째 remote(public 채널)
  R_GHCLOUD_REF="${CFG[$name.ghcloud_ref]:-}"
  R_ALLOW_FOREIGN="${CFG[$name.allow_foreign_dst]:-}"
  R_GITLINKS="${CFG[$name.gitlinks]:-}"
  R_PATH="${CFG[$name.path]:-}"                    # suite 기준 checkout 경로(setup_remotes.sh)
  R_GL_CHECK="$(eff "$name" gitlink_check)"; has_word "$R_GL_CHECK" "strict warn off" || die2 "$(m "gitlink_check 는 strict|warn|off 여야 합니다" "gitlink_check must be strict|warn|off")"
  # reviewers: push 가 실제 일어난 PR 에 (재)요청할 reviewer 목록 (공백/쉼표 구분). 비어 있으면 off.
  R_REVIEWERS="$(eff "$name" reviewers)"; [ -n "$REVIEWERS_OVERRIDE" ] && R_REVIEWERS="$REVIEWERS_OVERRIDE"
  R_REVIEWERS="${R_REVIEWERS//,/ }"
}

validate() {
  local name sub pair i j seen
  for ((i = 0; i < ${#REPOS[@]}; i++)); do
    name="${REPOS[i]}"; resolve "$name"
    for pair in $R_GITLINKS; do
      [[ "$pair" == *:* ]] || die2 "$(m "[repo $name]: gitlinks 항목 '$pair' 는 <repo>:<path> 형식이어야 합니다" "[repo $name]: gitlinks entry '$pair' must be <repo>:<path>")"
      sub="${pair%%:*}"; seen=0
      for ((j = 0; j < i; j++)); do [ "${REPOS[j]}" = "$sub" ] && seen=1; done
      [ "$seen" -eq 1 ] || die2 "$(m "[repo $name]: gitlinks 가 가리키는 '$sub' 는 더 앞의 [repo] 섹션에 있어야 합니다 (nested repo 먼저)" "[repo $name]: gitlinks target '$sub' must be an earlier [repo] section (nested repos first)")"
    done
  done
  for name in "${ONLY_REPOS[@]:-}"; do
    [ -z "$name" ] && continue
    has_word "$name" "${REPOS[*]}" || die2 "$(m "--repo '$name' 은 $CONFIG 에 없습니다 (repos: ${REPOS[*]})" "--repo '$name' is not in $CONFIG (repos: ${REPOS[*]})")"
  done
}

parse_conf "$CONFIG" 0
OVERRIDE_FILE="${OVERRIDE:-${CONFIG%.conf}.override.conf}"
OVERRIDE_APPLIED=""
if [ -f "$OVERRIDE_FILE" ]; then parse_conf "$OVERRIDE_FILE" 1; OVERRIDE_APPLIED="$OVERRIDE_FILE"
elif [ -n "$OVERRIDE" ]; then die2 "$(m "--override 파일을 찾을 수 없습니다: $OVERRIDE" "--override file not found: $OVERRIDE")"; fi
OVERRIDE_HINT="$OVERRIDE_FILE $(m "(gitignored; $(dirname "$CONFIG")/sync.override.conf.example 을 복사)" "(gitignored; copy $(dirname "$CONFIG")/sync.override.conf.example)")"
[ "${#REPOS[@]}" -gt 0 ] || die2 "$(m "$CONFIG 에 [repo NAME] 섹션이 없습니다" "no [repo NAME] section in $CONFIG")"
# committed sync.conf 가 의도적으로 비워 둔 값의 env fallback
[ -n "${DEF[src_host]:-}" ] || DEF[src_host]="${GHES_SYNC_SRC_HOST:-}"
[ -n "${DEF[dst_host]:-}" ] || DEF[dst_host]="${GHES_SYNC_DST_HOST:-}"
SRC_HOST_H="$(host_of "${DEF[src_host]:-}")"; DST_HOST_H="$(host_of "${DEF[dst_host]:-}")"
[ -n "${DEF[branch]:-}" ]   || DEF[branch]="${GHES_SYNC_BRANCH:-}"
# --branch beats every config source. It also clears a per-repo `branch` (eff() reads CFG
# before DEF), because "sync THIS branch" is an explicit instruction and a repo-level mapping
# silently winning over it would be a trap. `dst_branch` mappings are left untouched.
if [ -n "$BRANCH_OVERRIDE" ]; then
  DEF[branch]="$BRANCH_OVERRIDE"
  for n in "${REPOS[@]}"; do unset "CFG[$n.branch]"; done
fi
# 빠진 필수 값을 한 번에 모두 보고한다(committed sync.conf 는 src_host 와 branch 를 의도적으로 비워 둠).
check_required() {
  local n missing="" k
  for n in "${REPOS[@]}"; do
    [ -n "${CFG[$n.src_url]:-}" ] || [ -n "$(eff "$n" src_host)" ] || has_word src_host "$missing" || missing="$missing src_host"
    [ -n "${CFG[$n.dst_url]:-}" ] || [ -n "$(eff "$n" dst_host)" ] || has_word dst_host "$missing" || missing="$missing dst_host"
    [ -n "$(eff "$n" branch)" ] || has_word branch "$missing" || missing="$missing branch"
  done
  [ -n "$missing" ] || return 0
  printf '[%s] ERROR: %s\n' "$PROG" "$(m "필수 설정이 비어 있습니다:$missing" "required settings are empty:$missing")" >&2
  printf '[%s]   %s\n' "$PROG" "$(m "sync.conf 에서는 의도적으로 비워 둔 값입니다. $OVERRIDE_HINT 에 설정하세요" "they are intentionally empty in sync.conf. Set them in $OVERRIDE_HINT")" >&2
  local or_; or_="$(m "또는" "or")"
  for k in $missing; do
    case "$k" in
      src_host) printf '[%s]     [defaults] src_host = https://github.com/<YOUR-MIRROR-ORG>   (%s)   %s: export GHES_SYNC_SRC_HOST=<url>\n' "$PROG" "$(m "https 전용" "https only")" "$or_" >&2 ;;
      dst_host) printf '[%s]     [defaults] dst_host = https://gh.deepx.ai/deepx                           %s: export GHES_SYNC_DST_HOST=<url>\n' "$PROG" "$or_" >&2 ;;
      branch)   printf '[%s]     [defaults] branch = feature/<your-topic>                                 %s: export GHES_SYNC_BRANCH=<branch>\n' "$PROG" "$or_" >&2 ;;
    esac
  done
  exit 2
}
check_required
validate

CACHE_DIR="${CACHE_OVERRIDE:-$(eff _ cache_dir)}"
# ${VAR:-default}/$VAR 를 먼저 확장(설정은 신뢰), 그 다음 선행 ~ (기본값이 만든 것도 포함)
case "$CACHE_DIR" in *'$'*) CACHE_DIR="$(eval "printf '%s' \"$CACHE_DIR\"")" ;; esac
CACHE_DIR="${CACHE_DIR/#\~/$HOME}"

declare -a TARGETS=()
if [ "${#ONLY_REPOS[@]}" -gt 0 ]; then
  for n in "${REPOS[@]}"; do has_word "$n" "${ONLY_REPOS[*]}" && TARGETS+=("$n"); done
else TARGETS=("${REPOS[@]}"); fi

if [ "$PRINT_CONFIG" -eq 1 ]; then
  printf 'cache_dir = %s\n' "$CACHE_DIR"
  printf 'override = %s\n' "${OVERRIDE_APPLIED:-none ($OVERRIDE_FILE not present)}"
  for n in "${TARGETS[@]}"; do
    resolve "$n"
    printf '[%s]\n' "$n"
    printf '  src_url = %s\n  dst_url = %s\n  path = %s\n  branch = %s\n  dst_branch = %s\n  pr_base = %s\n  mode = %s\n  gitlinks = %s\n  gitlink_check = %s\n' \
      "$R_SRC_URL" "$R_DST_URL" "$R_PATH" "$R_BRANCH" "$R_DST_BRANCH" "$R_PR_BASE" "$R_MODE" "$R_GITLINKS" "$R_GL_CHECK"
    [ "$R_SYNC" = off ]        && printf '  sync = off\n'
    [ -n "$R_GHCLOUD_URL" ]    && printf '  ghcloud_url = %s\n' "$R_GHCLOUD_URL"
    [ -n "$R_GHCLOUD_REF" ]    && printf '  ghcloud_ref = %s\n' "$R_GHCLOUD_REF"
    [ -n "$R_ALLOW_FOREIGN" ]  && printf '  allow_foreign_dst = %s\n' "$R_ALLOW_FOREIGN"
  done
  exit 0
fi

# reverse_branches NAME → 이 repo가 --reverse 에서 같은 이름으로 sync하는 브랜치 목록(설정, 없으면 branch + pr_base + main)
reverse_branches() {
  local n="$1" branches b
  branches="$(eff "$n" reverse_branches)"
  if [ -z "$branches" ]; then
    branches="$R_BRANCH"
    for b in "$R_PR_BASE" main; do [ -n "$b" ] && ! has_word "$b" "$branches" && branches="$branches $b"; done
  fi
  printf '%s' "$branches"
}
# repo 열 폭 = 이번 실행에 나올 가장 긴 key (forward: repo, reverse: repo:branch / repo:branch<=base)
compute_name_w() {
  local n w=4 b k
  for n in "${TARGETS[@]}"; do
    resolve "$n"
    if [ "$REVERSE" -eq 1 ]; then
      for b in $(reverse_branches "$n") "$R_BRANCH<=$R_PR_BASE" "$R_BRANCH<=$R_PR_BASE@GHES"; do k="$n:$b"; [ "${#k}" -gt "$w" ] && w="${#k}"; done
    else [ "${#n}" -gt "$w" ] && w="${#n}"; fi
  done
  NAME_W="$w"
}
compute_name_w

if [ "$NO_PR" -eq 0 ] && [ "$PULL_ONLY" -eq 0 ] && [ "$REVERSE" -eq 0 ] && [ "$HAVE_GH" -eq 0 ] && { [ "$HAVE_CURL" -eq 0 ] || [ -z "$DST_TOKEN" ]; }; then
  for n in "${TARGETS[@]}"; do
    if [ "$(eff "$n" mode)" = pr ]; then
      warn "$(m "gh CLI 도 없고 dst token 도 없습니다 — 브랜치는 push되지만 PR 생성은 SKIP 됩니다 (curl REST 로 PR을 만들려면 export $DST_VARS, 또는 gh 설치)" "neither gh CLI nor a dst token — branches are pushed but PR creation is SKIPPED (export $DST_VARS for PRs via curl REST, or install gh)")"
      break
    fi
  done
fi

# ---------------------------------------------------------------------------
# repo별 처리
# ---------------------------------------------------------------------------
declare -A ACTION=() STATUS=() DETAIL=() SRC_SHA=() DST_BEFORE=() DST_AFTER=() PRINFO=() SYNCED_OK=()
declare -a ROWS=()      # 요약 행: repo(forward) 또는 repo:branch(reverse)
ROW_KEY=""              # process_reverse 가 브랜치별로 설정; 비어 있으면 R_NAME 이 key
ANY_FAIL=0

fail() { local k="${ROW_KEY:-$R_NAME}"; STATUS[$k]=FAIL; DETAIL[$k]="$*"; ANY_FAIL=1; printf '[%s] %-*s │ FAIL: %s\n' "$PROG" "$NAME_W" "$k" "$*" >&2; }
short() { printf '%.7s' "${1:--}"; }
key() { printf '%s' "${ROW_KEY:-$R_NAME}"; }

ensure_cache() { [ -d "$1" ] || { mkdir -p "$1"; git init -q --bare "$1"; }; }

# prune_stale_refs CACHE PREFIX HEADS — 방금 ls-remote 로 확인한 HEADS(refs/heads/x 목록)에 없는
# refs/remotes/PREFIX/* 를 cache에서 삭제한다. 원격에서 삭제된 브랜치(예: squash-merge 후 지운
# feature 브랜치)가 cache에 남아 DIVERGED 로 오판되는 일을 막는다. 삭제한 ref 이름을 출력.
prune_stale_refs() {
  local cache="$1" prefix="$2" heads="$3" ref b
  git -C "$cache" for-each-ref --format='%(refname)' "refs/remotes/$prefix/" | while IFS= read -r ref; do
    b="${ref#refs/remotes/$prefix/}"
    if ! printf '%s\n' "$heads" | grep -qx "refs/heads/$b"; then
      git -C "$cache" update-ref -d "$ref" 2>/dev/null || true
      printf '%s\n' "$b"
    fi
  done
}

# fetch_dst_ref CACHE URL REF — refs/heads/REF 를 refs/remotes/dst/REF 로 fetch, 원격에 없으면 로컬 사본 삭제
fetch_dst_ref() {
  local cache="$1" url="$2" ref="$3"
  if printf '%s\n' "$DST_HEADS" | grep -qx "refs/heads/$ref"; then
    auth_opts "$url" "$(token_for dst "$url")"
    git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$url" "+refs/heads/$ref:refs/remotes/dst/$ref"
    git -C "$cache" update-ref -d "refs/ghes-sync/absent/$ref" 2>/dev/null || true
  else
    git -C "$cache" update-ref -d "refs/remotes/dst/$ref" 2>/dev/null || true
    # "GHES에 없음"을 기억해 두어, 나중의 --push-only(GHES 접근 불가)가 "fetch 안 됨"이 아니라 SKIPPED 로 보고하게 한다
    git -C "$cache" update-ref "refs/ghes-sync/absent/$ref" "$(printf 'absent' | git -C "$cache" hash-object -w --stdin)"
  fi
}

# sub_refs SUB → pointer가 도달 가능해야 하는 ref 목록(공백 구분): 이번 실행에서 sub가 정상 sync됐으면
# sub의 src tip(이제 dst에 있음 — --dry-run 이면 있게 될 것); 아니면 sub의 GHES 브랜치 중 의미 있는 것
# 전부 — dst_branch, pr_base, main (parent는 이미 main/dev에 merge된 sub commit을 가리키는 경우가 많고,
# 그때 sub의 feature 브랜치는 옛 것일 수 있다).
sub_refs() {
  local sub="$1" subcache="$CACHE_DIR/$sub.git" br dbr pb url b out=""
  br="$(eff "$sub" branch)"; dbr="$(eff "$sub" dst_branch)"; [ -n "$dbr" ] || dbr="$br"; pb="$(eff "$sub" pr_base)"
  if [ -n "${SYNCED_OK[$sub]:-}" ]; then printf 'refs/remotes/src/%s' "$br"; return; fi
  ensure_cache "$subcache"
  url="${CFG[$sub.dst_url]:-}"; [ -n "$url" ] || url="$(join_url "$(eff "$sub" dst_host)" "$sub")"
  auth_opts "$url" "$(token_for dst "$url")"
  for b in "$dbr" "$pb" main; do
    [ -n "$b" ] || continue; has_word "refs/remotes/dst/$b" "$out" && continue
    if git "${AUTH_OPTS[@]}" -C "$subcache" fetch -q --no-tags "$url" "+refs/heads/$b:refs/remotes/dst/$b" 2>/dev/null; then out="$out refs/remotes/dst/$b"; fi
  done
  printf '%s' "${out# }"
}

check_gitlinks() {  # R_*, S, D, cache 사용; strict 이고 pointer가 도달 불가면 1
  [ "$R_GL_CHECK" = off ] && return 0
  [ -n "$R_GITLINKS" ] || return 0
  local commits pair sub path sha bad=0 c
  if [ -n "$D" ]; then commits="$(git -C "$cache" rev-list "$D..$S")"
  elif git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1; then
    commits="$(git -C "$cache" rev-list "refs/remotes/dst/$R_PR_BASE..$S")"; [ -n "$commits" ] || commits="$S"
  else commits="$S"; fi
  for c in $commits; do
    for pair in $R_GITLINKS; do
      sub="${pair%%:*}"; path="${pair#*:}"
      sha="$(git -C "$cache" ls-tree "$c" -- "$path" | awk '$1=="160000"{print $3}')"
      [ -n "$sha" ] || continue
      local refs ok=0 ref
      refs="$(sub_refs "$sub")"
      for ref in $refs; do
        git -C "$CACHE_DIR/$sub.git" merge-base --is-ancestor "$sha" "$ref" 2>/dev/null && { ok=1; break; }
      done
      if [ "$ok" -eq 0 ]; then
        rwarn "$R_NAME" "$(m "gitlink $path @ $(short "$c") → $sub/$(short "$sha") 가 ${refs:-<fetch된 GHES 브랜치 없음>} 에서 NOT reachable ($( [ -n "${SYNCED_OK[$sub]:-}" ] && { [ "$DRY_RUN" -eq 1 ] && echo "이번 실행에서 sync 예정" || echo "이번 실행에서 sync됨"; } || echo "GHES 기준: dst_branch / pr_base / main" ))" "gitlink $path @ $(short "$c") → $sub/$(short "$sha") is NOT reachable from ${refs:-<no fetched GHES branch>} ($( [ -n "${SYNCED_OK[$sub]:-}" ] && { [ "$DRY_RUN" -eq 1 ] && echo "to be synced in this run" || echo "synced in this run"; } || echo "GHES side: dst_branch / pr_base / main" ))")"
        bad=1
      fi
    done
  done
  if [ "$bad" -eq 1 ]; then
    if [ "$R_GL_CHECK" = strict ]; then return 1; fi
    rwarn "$R_NAME" "$(m "submodule pointer 가 dst에서 도달 불가 — 그래도 push 합니다 (gitlink_check = warn)" "submodule pointer not reachable on dst — pushing anyway (gitlink_check = warn)")"
  fi
  return 0
}

# ── --update-branch: 앞서간 PR base를 브랜치에 merge (rebase / force 없음) ──
# 깨끗한 merge만 자동화한다. conflict는 사용자가 직접 해결(사용자 결정): 도구는 중단하고 worktree를
# 남기지 않으며 두 기계 각각의 절차를 안내한다.
manual_recipe() {
  [ "$LANG_SEL" = ko ] && printf '수동 해결 — 폐쇄망(GHES push 가능): checkout에서 git fetch %s %s && git merge FETCH_HEAD, 해결·commit 후 git push %s HEAD:refs/heads/%s (GHES 브랜치에 ff); 다음 forward 실행은 DST-AHEAD 가 되고 --reverse 로 mirror를 따라잡게 합니다. dev 기계(github.com push 가능): mirror checkout에서 같은 merge 후 mirror에 push하면 forward 실행이 FAST-FORWARD 로 올립니다. 이 경우 --force-with-lease / --reset-to-base 는 절대 쓰지 마세요.' \
    "$R_DST_URL" "$R_PR_BASE" "$R_DST_URL" "$R_DST_BRANCH" && return 0
  printf 'manual fix — closed network (GHES pushable): in your checkout git fetch %s %s && git merge FETCH_HEAD, resolve, commit, git push %s HEAD:refs/heads/%s (ff onto the GHES branch); the next forward run shows DST-AHEAD and --reverse brings the mirror up. Dev machine (github.com pushable): do the same merge in the mirror checkout and push to the mirror; the forward run then FAST-FORWARDs. Never use --force-with-lease / --reset-to-base for this.' \
    "$R_DST_URL" "$R_PR_BASE" "$R_DST_URL" "$R_DST_BRANCH"
}
merge_update() {  # $1 = 브랜치에 없는 base commit 수; R_*, cache, TIP 사용; TIP/ACTION 설정 또는 fail
  local behind="$1" wt m files name email msg
  name="${GHES_SYNC_GIT_NAME:-$(git config user.name 2>/dev/null || true)}";   [ -n "$name" ]  || name="ghes-sync"
  email="${GHES_SYNC_GIT_EMAIL:-$(git config user.email 2>/dev/null || true)}"; [ -n "$email" ] || email="ghes-sync@noreply.local"
  wt="$(mktemp -d "${TMPDIR:-/tmp}/ghes-sync-wt.XXXXXX")"; rmdir "$wt"
  git -C "$cache" worktree prune >/dev/null 2>&1 || true
  if ! git -C "$cache" worktree add -q --detach "$wt" "$TIP" >/dev/null 2>&1; then
    fail "$(m "merge-update 용 cache 임시 worktree 를 만들 수 없습니다" "cannot create the temporary cache worktree for merge-update")"; return 1
  fi
  msg="Merge $R_PR_BASE into $R_DST_BRANCH (ghes-sync --update-branch)"
  if git -C "$wt" -c user.name="$name" -c user.email="$email" merge -q --no-ff --no-edit -m "$msg" "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1; then
    m="$(git -C "$wt" rev-parse HEAD)"
    git -C "$cache" worktree remove --force "$wt" >/dev/null 2>&1 || true; git -C "$cache" worktree prune >/dev/null 2>&1 || true
    if [ "$DRY_RUN" -eq 1 ]; then
      rlog "$R_NAME" "$(m "DRY-RUN: $R_PR_BASE ($behind commit) 을 $R_DST_BRANCH 에 merge → $(short "$m") 후 git push $R_DST_URL $(short "$m"):refs/heads/$R_DST_BRANCH" "DRY-RUN: merge $R_PR_BASE ($behind commit) into $R_DST_BRANCH → $(short "$m"), then git push $R_DST_URL $(short "$m"):refs/heads/$R_DST_BRANCH")"
    else
      if ! gpush "$R_DST_URL" "$(token_for dst "$R_DST_URL")" "$m:refs/heads/$R_DST_BRANCH"; then
        fail "$(m "merge-update commit push 실패 (force 없음) — git: ${GPUSH_ERR:-?}" "push of the merge-update commit failed (no force) — git: ${GPUSH_ERR:-?}")"; return 1
      fi
      git -C "$cache" update-ref "refs/remotes/dst/$R_DST_BRANCH" "$m"; DST_AFTER[$R_NAME]="$m"
      rlog "$R_NAME" "$(m "$R_PR_BASE ($behind commit) 을 $R_DST_BRANCH 에 merge → $(short "$m"), push 완료" "merged $R_PR_BASE ($behind commit) into $R_DST_BRANCH → $(short "$m"), pushed")"
    fi
    TIP="$m"; ACTION[$R_NAME]=MERGE-UPDATED
    DETAIL[$R_NAME]="$(m "mirror 가 merge commit 만큼 뒤처져 있습니다 — github.com push 가능한 기계에서 --reverse 로 되돌려 받으세요" "the mirror is behind by the merge commit — bring it back with --reverse on a machine that can push to github.com")"
    return 0
  fi
  files="$(git -C "$wt" diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' ')"
  git -C "$wt" merge --abort >/dev/null 2>&1 || true
  git -C "$cache" worktree remove --force "$wt" >/dev/null 2>&1 || true; git -C "$cache" worktree prune >/dev/null 2>&1 || true
  fail "$(m "$R_PR_BASE 를 $R_DST_BRANCH 에 merge 하는 중 CONFLICT (files: ${files:-unknown}) — push 없음, 남긴 것 없음. $(manual_recipe)" "CONFLICT while merging $R_PR_BASE into $R_DST_BRANCH (files: ${files:-unknown}) — nothing pushed, nothing kept. $(manual_recipe)")"
  return 1
}

# ── PR backend: gh CLI, 또는 curl 로 REST API (Windows git bash 에는 gh 가 없음) ──
json_str() {  # stdin → JSON 문자열 리터럴(따옴표 포함)
  printf '"'; awk 'BEGIN{ORS=""} {gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); gsub(/\t/,"\\t"); gsub(/\r/,""); if (NR>1) printf "\\n"; printf "%s", $0}'; printf '"'
}
api_base() {  # api_base DST_URL → https://api.github.com | <scheme>://<host>/api/v3
  local url="$1" scheme host; scheme="${url%%://*}"; host="${url#*://}"; host="${host%%/*}"
  if [ "$host" = github.com ]; then printf 'https://api.github.com'; else printf '%s://%s/api/v3' "$scheme" "$host"; fi
}
# pr_url_of TEXT → the first PR URL in TEXT. `gh` prints notices on the same stream as
# the URL ("Warning: N uncommitted changes", trailing hints), so the whole output must not
# be treated as the URL: it lands in the summary's `pr` cell and breaks the table, and the
# PR number parsed off the end of that blob can come from the wrong line.
pr_url_of() { printf '%s' "$1" | grep -oE 'https?://[^[:space:]]+/pull/[0-9]+' | head -n1; }

rest_curl() {  # rest_curl OUTFILE METHOD URL [DATAFILE] → http code 출력; DST_TOKEN 은 -K 설정 파일로 전달(argv 아님)
  local out="$1" method="$2" url="$3" data="${4:-}" cfg code
  cfg="$(mktemp)"; chmod 600 "$cfg"
  printf 'header = "Authorization: token %s"\nheader = "Accept: application/vnd.github+json"\nheader = "Content-Type: application/json"\n' "$DST_TOKEN" > "$cfg"
  if [ -n "$data" ]; then code="$(tmo "$PROBE_TIMEOUT" curl -sS -K "$cfg" -X "$method" --data "@$data" -o "$out" -w '%{http_code}' "$url" 2>/dev/null || true)"
  else code="$(tmo "$PROBE_TIMEOUT" curl -sS -K "$cfg" -o "$out" -w '%{http_code}' "$url" 2>/dev/null || true)"; fi
  rm -f "$cfg"; printf '%s' "$code"
}

request_reviewers() {  # request_reviewers PR_NUM BACKEND API_REPO SLUG — push 가 실제 일어난(CREATE/FAST-FORWARD) PR 에만 (재)요청
  # 리뷰 봇(dci)은 PR 이 열릴 때만 돌고 이후 push 에는 돌지 않는다; reviewer 재요청(UI 의 "Re-request review" 와 같은
  # review_requested webhook)이 봇을 다시 깨운다. 실패는 warn — sync 자체는 성공.
  local num="$1" backend="$2" api_repo="$3" slug="$4" r list json resp payload code
  [ -n "$R_REVIEWERS" ] && [ -n "$num" ] || return 0
  case "${ACTION[$R_NAME]}" in CREATE|FAST-FORWARD) ;; *) return 0 ;; esac
  list="$(printf '%s' "$R_REVIEWERS" | tr ' ' ',')"
  if [ "$DRY_RUN" -eq 1 ]; then rlog "$R_NAME" "$(m "DRY-RUN: PR #$num reviewer 재요청 → $list" "DRY-RUN: PR #$num re-request reviewer → $list")"; return 0; fi
  if [ "$backend" = gh ]; then
    if gh pr edit "$num" -R "$slug" --add-reviewer "$list" >/dev/null 2>&1; then rlog "$R_NAME" "$(m "PR #$num reviewer 재요청: $list" "PR #$num reviewer re-requested: $list")"
    else rwarn "$R_NAME" "$(m "PR #$num reviewer 재요청 실패 (gh pr edit --add-reviewer $list) — sync 자체는 성공" "PR #$num reviewer re-request failed (gh pr edit --add-reviewer $list) — the sync itself succeeded")"; fi
    return 0
  fi
  json=""; for r in $R_REVIEWERS; do json="$json${json:+,}\"$r\""; done
  resp="$(mktemp)"; payload="$(mktemp)"; printf '{"reviewers":[%s]}' "$json" > "$payload"
  code="$(rest_curl "$resp" POST "$api_repo/pulls/$num/requested_reviewers" "$payload")"
  if [ "$code" = 201 ]; then rlog "$R_NAME" "$(m "PR #$num reviewer 재요청 (REST): $list" "PR #$num reviewer re-requested (REST): $list")"
  else rwarn "$R_NAME" "$(m "PR #$num reviewer 재요청 실패 (HTTP ${code:-none}) — token 의 pull request write 권한과 reviewer 계정명을 확인하세요; sync 자체는 성공" "PR #$num reviewer re-request failed (HTTP ${code:-none}) — check the token's pull-request write permission and the reviewer login; the sync itself succeeded")"; fi
  rm -f "$resp" "$payload"
}

ensure_pr() {  # R_*, TIP, cache 사용
  [ "$NO_PR" -eq 1 ] && return 0
  [ "$R_MODE" = pr ] || return 0
  [ -n "$R_PR_BASE" ] || return 0
  [ "$R_DST_BRANCH" != "$R_PR_BASE" ] || return 0
  local slug backend existing num url ahead title body resp code api owner name
  slug="$(repo_slug "$R_DST_URL")"; owner="${slug#*/}"; owner="${owner%/*}"; name="${slug##*/}"
  # backend: dst token + curl → REST · gh 있음 → gh · 아니면 SKIP (절대 prompt 없음)
  backend=""
  if [ -n "$DST_TOKEN" ] && [ "$HAVE_CURL" -eq 1 ]; then backend=rest
  elif [ "$HAVE_GH" -eq 1 ]; then backend=gh; fi
  if [ -z "$backend" ]; then
    rwarn "$R_NAME" "$(m "PR 생성 SKIP (gh CLI 없음, dst token 없음) — 브랜치는 push 되었습니다; export $DST_VARS (curl REST) 또는 gh 설치 후 재실행, 또는 수동으로 PR 을 만드세요" "PR skipped (no gh CLI, no dst token) — the branch was pushed; export $DST_VARS (curl REST) or install gh and rerun, or open the PR by hand")"
    PRINFO[$R_NAME]="skipped (no gh, no token)"; return 0
  fi
  api="$(api_base "$R_DST_URL")"; resp="$(mktemp)"
  # 1. 이미 열린 PR?
  if [ "$backend" = gh ]; then
    if ! existing="$(gh pr list -R "$slug" --head "$R_DST_BRANCH" --base "$R_PR_BASE" --state open --json number,url 2>&1)"; then
      rm -f "$resp"; fail "$(m "gh pr list 실패 ($slug): $existing" "gh pr list failed ($slug): $existing")"; return 1
    fi
  else
    code="$(rest_curl "$resp" GET "$api/repos/$owner/$name/pulls?state=open&head=$owner:$R_DST_BRANCH&base=$R_PR_BASE")"
    if [ "$code" != 200 ]; then fail "$(m "REST pr list 실패 (HTTP ${code:-none}) — $api/repos/$owner/$name — token scope / host 를 확인하세요" "REST pr list failed (HTTP ${code:-none}) — $api/repos/$owner/$name — check the token scope / host")"; rm -f "$resp"; return 1; fi
    existing="$(cat "$resp")"
  fi
  num="$(printf '%s' "$existing" | grep -o '"number": *[0-9]*' | head -n1 | grep -o '[0-9]*$' || true)"
  # web URL: REST 는 html_url(그 `url` 은 API endpoint); gh 의 --json url 은 이미 web URL
  url="$(printf '%s' "$existing" | grep -o '"html_url": *"[^"]*"' | head -n1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  [ -n "$url" ] || url="$(printf '%s' "$existing" | grep -o '"url": *"[^"]*"' | head -n1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  if [ -n "$num" ]; then
    PRINFO[$R_NAME]="#$num (existing) $url"; rlog "$R_NAME" "$(m "PR #$num 이미 열려 있음 $url" "PR #$num already open $url")"; rm -f "$resp"
    request_reviewers "$num" "$backend" "$api/repos/$owner/$name" "$slug"; return 0
  fi
  # 2. 제안할 commit 이 있는가?
  if ! git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1; then
    rwarn "$R_NAME" "$(m "PR base '$R_PR_BASE' 가 dst 에 없습니다 — PR 을 만들지 않음" "PR base '$R_PR_BASE' does not exist on dst — no PR created")"
    PRINFO[$R_NAME]="no base '$R_PR_BASE' on dst"; rm -f "$resp"; return 0
  fi
  ahead="$(git -C "$cache" rev-list --count "refs/remotes/dst/$R_PR_BASE..$TIP")"
  if [ "$ahead" -eq 0 ]; then PRINFO[$R_NAME]="nothing ahead of $R_PR_BASE"; rm -f "$resp"; return 0; fi
  # conventional-commit 형식: GHES 의 commit-message-checker-pr workflow 가 "sync(<repo>): ..." 를 거부함
  title="ci: sync $R_NAME $R_BRANCH -> $R_PR_BASE ($ahead commits)"
  body="$(mktemp)"
  {
    printf 'Automated sync by ghes-sync.sh from the github.com mirror.\n\nSource: %s @ %s\nCommits ahead of `%s`: %s\n\n' \
      "$R_BRANCH" "$(short "$TIP")" "$R_PR_BASE" "$ahead"
    git -C "$cache" log --format='- %h %s' -n 50 "refs/remotes/dst/$R_PR_BASE..$TIP"
    [ "$ahead" -gt 50 ] && printf -- '- ... (%s more)\n' "$((ahead - 50))"
  } > "$body"
  # 3. 생성
  rlog "$R_NAME" "PR title: $title"
  if [ "$DRY_RUN" -eq 1 ]; then
    if [ "$backend" = gh ]; then rlog "$R_NAME" "DRY-RUN: gh pr create -R $slug -B $R_PR_BASE -H $R_DST_BRANCH -t '$title'"
    else rlog "$R_NAME" "DRY-RUN: POST $api/repos/$owner/$name/pulls  head=$R_DST_BRANCH base=$R_PR_BASE title='$title'"; fi
    PRINFO[$R_NAME]="(dry-run) would create"; rm -f "$body" "$resp"; return 0
  fi
  if [ "$backend" = gh ]; then
    if ghout="$(gh pr create -R "$slug" -B "$R_PR_BASE" -H "$R_DST_BRANCH" -t "$title" -F "$body" 2>&1)"; then
      url="$(pr_url_of "$ghout")"
      num="$(printf '%s' "$url" | grep -oE '[0-9]+$' || true)"
      # No URL in the output at all: keep the text, but on one line so the summary table survives.
      [ -n "$url" ] || url="$(printf '%s' "$ghout" | tr '\n' ' ')"
      PRINFO[$R_NAME]="created $url"; rlog "$R_NAME" "$(m "PR 생성됨 $url" "PR created $url")"; rm -f "$body" "$resp"
      request_reviewers "$num" "$backend" "$api/repos/$owner/$name" "$slug"; return 0
    fi
    rm -f "$body" "$resp"; fail "$(m "gh pr create 실패 (브랜치는 push 되었음): $(printf '%s' "$ghout" | tr '\n' ' ')" "gh pr create failed (the branch was pushed): $(printf '%s' "$ghout" | tr '\n' ' ')")"; return 1
  fi
  local payload; payload="$(mktemp)"
  printf '{"title":%s,"head":%s,"base":%s,"body":%s}' \
    "$(printf '%s' "$title" | json_str)" "$(printf '%s' "$R_DST_BRANCH" | json_str)" \
    "$(printf '%s' "$R_PR_BASE" | json_str)" "$(json_str < "$body")" > "$payload"
  code="$(rest_curl "$resp" POST "$api/repos/$owner/$name/pulls" "$payload")"
  rm -f "$body" "$payload"
  if [ "$code" = 201 ]; then
    num="$(grep -o '"number": *[0-9]*' "$resp" | head -n1 | grep -o '[0-9]*$' || true)"
    url="$(grep -o '"html_url": *"[^"]*"' "$resp" | head -n1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
    PRINFO[$R_NAME]="created $url"; rlog "$R_NAME" "$(m "PR #$num 생성됨 (REST) $url" "PR #$num created (REST) $url")"; rm -f "$resp"
    request_reviewers "$num" "$backend" "$api/repos/$owner/$name" "$slug"; return 0
  fi
  fail "$(m "REST pr create 실패 (HTTP ${code:-none}, 브랜치는 push 되었음): $(head -c 300 "$resp" 2>/dev/null)" "REST pr create failed (HTTP ${code:-none}, the branch was pushed): $(head -c 300 "$resp" 2>/dev/null)")"; rm -f "$resp"; return 1
}

process() {
  resolve "$1"
  local cache="$CACHE_DIR/$R_NAME.git" S D TIP pruned
  ROWS+=("$R_NAME"); STATUS[$R_NAME]=OK; ACTION[$R_NAME]=-; DETAIL[$R_NAME]=""; PRINFO[$R_NAME]="-"
  hdr "$R_NAME: $R_SRC_URL [$R_BRANCH] → $R_DST_URL [$R_DST_BRANCH]"
  ensure_cache "$cache"
  if [ "$PUSH_ONLY" -eq 0 ] && ! has_creds "$R_SRC_URL" "$(token_for src "$R_SRC_URL")"; then fail "$(cred_hint src "$R_SRC_URL")"; return; fi
  if ! has_creds "$R_DST_URL" "$(token_for dst "$R_DST_URL")"; then fail "$(cred_hint dst "$R_DST_URL")"; return; fi
  if [ "$PULL_ONLY" -eq 0 ] && ! push_target_ok dst "$R_DST_URL"; then fail "$(push_target_msg dst "$R_DST_URL")"; return; fi

  if [ "$PUSH_ONLY" -eq 0 ]; then
    auth_opts "$R_SRC_URL" "$(token_for src "$R_SRC_URL")"
    local frc=0
    tmo "$NET_TIMEOUT" git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$R_SRC_URL" "+refs/heads/$R_BRANCH:refs/remotes/src/$R_BRANCH" || frc=$?
    if [ "$frc" -eq 124 ]; then fail "$(m "src fetch timeout (${NET_TIMEOUT}초, GHES_SYNC_NET_TIMEOUT) — $R_SRC_URL" "src fetch timeout (${NET_TIMEOUT}s, GHES_SYNC_NET_TIMEOUT) — $R_SRC_URL")"; return
    elif [ "$frc" -ne 0 ]; then fail "$(m "src [$R_BRANCH] 를 fetch 할 수 없음 — $(auth_hint src "$R_SRC_URL")" "cannot fetch src [$R_BRANCH] — $(auth_hint src "$R_SRC_URL")")"; return; fi
    [ "$TAGS" -eq 1 ] && tmo "$NET_TIMEOUT" git "${AUTH_OPTS[@]}" -C "$cache" fetch -q "$R_SRC_URL" "+refs/tags/*:refs/tags/*"
  fi
  local probe_rc=0
  probe "$R_DST_URL" "$(token_for dst "$R_DST_URL")" || probe_rc=$?
  DST_HEADS="$(printf '%s\n' "$PROBE_OUT" | awk '{print $2}')"
  if [ "$probe_rc" -ne 0 ]; then fail "$(m "dst(GHES) 에 접근할 수 없음 — $(probe_reason dst "$R_DST_URL" "$probe_rc")" "cannot reach dst (GHES) — $(probe_reason dst "$R_DST_URL" "$probe_rc")")"; return; fi
  pruned="$(prune_stale_refs "$cache" dst "$DST_HEADS" | tr '\n' ' ')"
  [ -n "$pruned" ] && rlog "$R_NAME" "$(m "cache 정리: GHES 에서 삭제된 브랜치의 옛 사본 제거 — ${pruned% }" "cache cleanup: dropped stale copies of branches deleted on GHES — ${pruned% }")"
  fetch_dst_ref "$cache" "$R_DST_URL" "$R_DST_BRANCH"
  [ -n "$R_PR_BASE" ] && [ "$R_PR_BASE" != "$R_DST_BRANCH" ] && fetch_dst_ref "$cache" "$R_DST_URL" "$R_PR_BASE"

  S="$(git -C "$cache" rev-parse -q --verify "refs/remotes/src/$R_BRANCH" 2>/dev/null || true)"
  [ -n "$S" ] || { fail "$(m "source 브랜치 '$R_BRANCH' 가 cache 에 없음 (fetch 된 적이 없나요?)" "source branch '$R_BRANCH' is not in the cache (never fetched?)")"; return; }
  D="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_DST_BRANCH" 2>/dev/null || true)"
  SRC_SHA[$R_NAME]="$S"; DST_BEFORE[$R_NAME]="$D"; DST_AFTER[$R_NAME]="$D"

  if [ "$PULL_ONLY" -eq 1 ]; then ACTION[$R_NAME]=FETCHED; rlog "$R_NAME" "$(m "fetch 완료: src $(short "$S"), dst $(short "$D")" "fetched: src $(short "$S"), dst $(short "$D")")"; return; fi

  TIP="$S"
  if [ -z "$D" ]; then ACTION[$R_NAME]=CREATE
  elif [ "$D" = "$S" ]; then ACTION[$R_NAME]=UP-TO-DATE
  elif git -C "$cache" merge-base --is-ancestor "$D" "$S"; then ACTION[$R_NAME]=FAST-FORWARD
  elif git -C "$cache" merge-base --is-ancestor "$S" "$D"; then
    ACTION[$R_NAME]=DST-AHEAD; TIP="$D"
    local ahead_n; ahead_n="$(git -C "$cache" rev-list --count "$S..$D")"
    DETAIL[$R_NAME]="$(m "dst 가 mirror 보다 $ahead_n commit 앞서 있음 — push 할 것 없음; github.com push 가능한 기계에서 --reverse 로 mirror 를 따라잡게 하세요" "dst is $ahead_n commit(s) ahead of the mirror — nothing to push; run --reverse on a machine that can push to github.com to bring the mirror up")"
    rlog "$R_NAME" "$(m "DST-AHEAD — dst [$R_DST_BRANCH] @ $(short "$D") 가 mirror tip $(short "$S") 를 포함하고 $ahead_n commit 더 있음 (merge-update 또는 GHES 측 commit). push 할 것 없음; MIRROR 가 뒤처져 있음 — github.com push 가능한 기계에서 ghes-sync.sh --reverse 실행" "DST-AHEAD — dst [$R_DST_BRANCH] @ $(short "$D") contains the mirror tip $(short "$S") plus $ahead_n more commit(s) (merge-update or a GHES-side commit). Nothing to push; the MIRROR is behind — run ghes-sync.sh --reverse on a machine that can push to github.com")"
  else
    ACTION[$R_NAME]=DIVERGED
    fail "$(m "DIVERGED — dst [$R_DST_BRANCH] @ $(short "$D") 와 src @ $(short "$S") 가 서로 없는 commit 을 가지고 있음. forward 방향은 절대 force-push 하지 않습니다. 어느 쪽이 맞는지 정하세요: (a) MIRROR 가 맞음 → dev 기계에서 git fetch $R_DST_URL $R_DST_BRANCH && merge/rebase, mirror 에 push, 재실행. (b) GHES 가 맞음 (예: conflict 해결 후 GHES 의 $R_DST_BRANCH 를 force-push 함) → mirror 를 덮어쓰기: 여기서 '--reverse --pull-only', github.com push 가능한 곳에서 '--reverse --push-only --force-with-lease', 로컬 checkout 을 새 mirror 브랜치로 reset, 재실행. (c) GHES 의 $R_DST_BRANCH 가 이미 squash-merge 된 옛 브랜치(merge 후 삭제되지 않음)라면 → GHES 에서 삭제: git push ghes --delete $R_DST_BRANCH, 재실행하면 CREATE. SUB-repo 브랜치가 재작성됐다면 parent repo 의 submodule pointer 도 새 commit 으로 올리세요." "DIVERGED — dst [$R_DST_BRANCH] @ $(short "$D") and src @ $(short "$S") have commits the other lacks. The forward direction never force-pushes. Decide which side is right: (a) the MIRROR is right → on the dev machine git fetch $R_DST_URL $R_DST_BRANCH && merge/rebase, push to the mirror, rerun. (b) GHES is right (e.g. $R_DST_BRANCH was force-pushed on GHES after a conflict fix) → overwrite the mirror: here '--reverse --pull-only', where github.com is pushable '--reverse --push-only --force-with-lease', reset your local checkout to the new mirror branch, rerun. (c) GHES $R_DST_BRANCH is an old branch that was already squash-merged (not deleted after the merge) → delete it on GHES: git push ghes --delete $R_DST_BRANCH; the rerun is CREATE. If a SUB-repo branch was rewritten, bump the parent repo's submodule pointer to the new commit too.")"
    return
  fi
  rlog "$R_NAME" "${ACTION[$R_NAME]} (src $(short "$S"), dst $(short "$D"))"

  if [ "${ACTION[$R_NAME]}" = CREATE ] || [ "${ACTION[$R_NAME]}" = FAST-FORWARD ]; then
    if ! check_gitlinks; then
      fail "$(m "submodule pointer 가 dst 에서 도달 불가 — parent 는 push 하지 않음 (gitlink_check = strict). 그 commit 을 포함하는 sub-repo 브랜치를 먼저 sync 하세요." "submodule pointer not reachable on dst — the parent is not pushed (gitlink_check = strict). Sync the sub-repo branch that contains that commit first.")"
      return
    fi
    local pushcmd="git push $R_DST_URL refs/remotes/src/$R_BRANCH:refs/heads/$R_DST_BRANCH"
    if [ "$DRY_RUN" -eq 1 ]; then rlog "$R_NAME" "DRY-RUN: $pushcmd"
    else
      rlog "$R_NAME" "$pushcmd"
      if ! gpush "$R_DST_URL" "$(token_for dst "$R_DST_URL")" "refs/remotes/src/$R_BRANCH:refs/heads/$R_DST_BRANCH"; then
        fail "$(m "dst push 실패 (force 없음) — git: ${GPUSH_ERR:-?}" "dst push failed (no force) — git: ${GPUSH_ERR:-?}")"; return
      fi
      git -C "$cache" update-ref "refs/remotes/dst/$R_DST_BRANCH" "$S"
      DST_AFTER[$R_NAME]="$S"
    fi
  fi
  SYNCED_OK[$R_NAME]=1   # --dry-run 에서는 "sync 예정" — parent 의 gitlink 검사가 실제 실행을 시뮬레이션하게 함
  # 브랜치를 딴 뒤 dst 의 PR base 가 앞서갔는가? (PR 브랜치에만 의미 있음)
  if [ "$R_MODE" = pr ] && [ -n "$R_PR_BASE" ] && [ "$R_DST_BRANCH" != "$R_PR_BASE" ] \
     && git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1 \
     && ! git -C "$cache" merge-base --is-ancestor "refs/remotes/dst/$R_PR_BASE" "$TIP"; then
    local behind; behind="$(git -C "$cache" rev-list --count "$TIP..refs/remotes/dst/$R_PR_BASE")"
    if [ "$UPDATE_BRANCH" -eq 1 ]; then
      merge_update "$behind" || return
    else
      rlog "$R_NAME" "$(m "base '$R_PR_BASE' 에 $R_DST_BRANCH 가 없는 새 commit $behind 개 — PR 이 base 와 최신 상태가 아닙니다; --update-branch 로 재실행하면 base 를 브랜치에 merge 합니다" "base '$R_PR_BASE' has $behind new commit(s) that $R_DST_BRANCH lacks — the PR is not up to date with its base; rerun with --update-branch to merge the base into the branch")"
    fi
  fi
  if [ "$TAGS" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then rlog "$R_NAME" "DRY-RUN: git push $R_DST_URL 'refs/tags/*:refs/tags/*'"
    else
      if ! gpush "$R_DST_URL" "$(token_for dst "$R_DST_URL")" 'refs/tags/*:refs/tags/*'; then fail "$(m "tag push 실패 (tag 는 절대 force 하지 않음) — git: ${GPUSH_ERR:-?}" "tag push failed (tags are never forced) — git: ${GPUSH_ERR:-?}")"; return; fi
    fi
  fi
  ensure_pr || true
}

# ── --reverse: GHES(dst 역할) -> mirror(src 역할); bare cache 가 운반체 ──
rv_row() {  # rv_row BRANCH → 이 repo/branch 의 요약 행 시작
  ROW_KEY="$R_NAME:$1"; ROWS+=("$ROW_KEY")
  STATUS[$ROW_KEY]=OK; ACTION[$ROW_KEY]=-; DETAIL[$ROW_KEY]=""; PRINFO[$ROW_KEY]="-"
}
rv_fail_all() {  # rv_fail_all BRANCHES MSG — repo 수준 실패, 브랜치마다 FAIL 행 하나
  local b; for b in $1; do rv_row "$b"; fail "$2"; done; ROW_KEY=""
}
check_gitlinks_reverse() {  # $1=from sha $2=to sha(비어 있을 수 있음): 새 commit 의 pointer 가 sub cache 에 있어야 함
  [ "$R_GL_CHECK" = off ] && return 0
  [ -n "$R_GITLINKS" ] || return 0
  local commits c pair sub path sha bad=0
  if [ -n "$2" ]; then commits="$(git -C "$cache" rev-list "$2..$1")"; else commits="$1"; fi
  for c in $commits; do
    for pair in $R_GITLINKS; do
      sub="${pair%%:*}"; path="${pair#*:}"
      sha="$(git -C "$cache" ls-tree "$c" -- "$path" | awk '$1=="160000"{print $3}')"
      [ -n "$sha" ] || continue
      if ! git -C "$CACHE_DIR/$sub.git" cat-file -e "$sha^{commit}" 2>/dev/null; then
        rwarn "$ROW_KEY" "$(m "gitlink $path @ $(short "$c") → $sub/$(short "$sha") 가 $sub cache 에 없음 (sub-repo 브랜치가 reverse_branches 에 없거나 fetch 되지 않음)" "gitlink $path @ $(short "$c") → $sub/$(short "$sha") is not in the $sub cache (sub-repo branch missing from reverse_branches or not fetched)")"
        bad=1
      fi
    done
  done
  if [ "$bad" -eq 1 ]; then
    [ "$R_GL_CHECK" = strict ] && return 1
    rwarn "$ROW_KEY" "$(m "submodule pointer 가 sub-repo cache 에 없음 — 그래도 push 합니다 (gitlink_check = warn)" "submodule pointer not in the sub-repo cache — pushing anyway (gitlink_check = warn)")"
  fi
  return 0
}
process_reverse() {
  resolve "$1"
  local cache="$CACHE_DIR/$R_NAME.git" branches b S D probe_rc MIRROR_HEADS MIRROR_LS DST_LS dropped n pruned
  branches="$(reverse_branches "$R_NAME")"
  if [ "$RESET_TO_BASE" -eq 1 ]; then   # feature 브랜치는 base 로 대체될 예정 — 같은 이름으로도 sync 하지 않음
    local kept="" ; for b in $branches; do [ "$b" = "$R_BRANCH" ] || kept="$kept $b"; done; branches="${kept# }"
  fi
  hdr "$R_NAME (REVERSE): GHES $R_DST_URL → mirror $R_SRC_URL | $(m "같은 이름으로 sync: ${branches:-없음}" "same-name sync: ${branches:-none}")$( [ "$RESET_TO_BASE" -eq 1 ] && [ -n "$R_PR_BASE" ] && [ "$R_PR_BASE" != "$R_BRANCH" ] && { [ "$PUSH_ONLY" -eq 0 ] && printf ' | reset@GHES: GHES %s <= GHES %s' "$R_BRANCH" "$R_PR_BASE"; [ "$PULL_ONLY" -eq 0 ] && printf ' | reset: mirror %s <= GHES %s' "$R_BRANCH" "$R_PR_BASE"; } )"
  ensure_cache "$cache"
  if [ "$PUSH_ONLY" -eq 0 ] && ! has_creds "$R_DST_URL" "$(token_for dst "$R_DST_URL")"; then rv_fail_all "$branches" "$(cred_hint dst "$R_DST_URL")"; return; fi
  if ! has_creds "$R_SRC_URL" "$(token_for src "$R_SRC_URL")"; then rv_fail_all "$branches" "$(cred_hint src "$R_SRC_URL")"; return; fi
  if [ "$PULL_ONLY" -eq 0 ] && ! push_target_ok src "$R_SRC_URL"; then rv_fail_all "$branches" "$(push_target_msg src "$R_SRC_URL")"; return; fi
  if [ "$RESET_TO_BASE" -eq 1 ] && [ "$PUSH_ONLY" -eq 0 ] && ! push_target_ok dst "$R_DST_URL"; then rv_fail_all "$branches" "$(push_target_msg dst "$R_DST_URL")"; return; fi
  # FROM = GHES. --push-only 면 생략: cache 에 --pull-only 가 가져온 것이 이미 있음.
  if [ "$PUSH_ONLY" -eq 0 ]; then
    probe_rc=0; probe "$R_DST_URL" "$(token_for dst "$R_DST_URL")" || probe_rc=$?
    DST_HEADS="$(printf '%s\n' "$PROBE_OUT" | awk '{print $2}')"
    if [ "$probe_rc" -ne 0 ]; then rv_fail_all "$branches" "$(m "GHES(from) 에 접근할 수 없음 — $(probe_reason dst "$R_DST_URL" "$probe_rc"). GHES 가 이 기계에서 원래 접근 불가라면: 접근 가능한 곳에서 '--reverse --pull-only', 이 기계에서 '--reverse --push-only'" "cannot reach GHES (from) — $(probe_reason dst "$R_DST_URL" "$probe_rc"). If GHES is never reachable from this machine: run '--reverse --pull-only' where it is, then '--reverse --push-only' here")"; return; fi
    DST_LS="$PROBE_OUT"
    pruned="$(prune_stale_refs "$cache" dst "$DST_HEADS" | tr '\n' ' ')"
    [ -n "$pruned" ] && rlog "$R_NAME" "$(m "cache 정리: GHES 에서 삭제된 브랜치의 옛 사본 제거 — ${pruned% }" "cache cleanup: dropped stale copies of branches deleted on GHES — ${pruned% }")"
    for b in $branches; do fetch_dst_ref "$cache" "$R_DST_URL" "$b"; done
    if [ "$RESET_TO_BASE" -eq 1 ]; then
      fetch_dst_ref "$cache" "$R_DST_URL" "$R_BRANCH"     # the (stale) GHES feature tip — the GHES-side reset needs it
      reset_ghes_branch; ROW_KEY=""
    fi
  fi
  # TO = mirror: 항상 probe (분류에 필요), refs/remotes/src/<b> 로 fetch
  probe_rc=0; probe "$R_SRC_URL" "$(token_for src "$R_SRC_URL")" || probe_rc=$?
  MIRROR_LS="$PROBE_OUT"
  MIRROR_HEADS="$(printf '%s\n' "$MIRROR_LS" | awk '{print $2}')"
  if [ "$probe_rc" -ne 0 ]; then rv_fail_all "$branches" "$(m "mirror(to) 에 접근할 수 없음 — $(probe_reason src "$R_SRC_URL" "$probe_rc")" "cannot reach the mirror (to) — $(probe_reason src "$R_SRC_URL" "$probe_rc")")"; return; fi
  pruned="$(prune_stale_refs "$cache" src "$MIRROR_HEADS" | tr '\n' ' ')"
  [ -n "$pruned" ] && rlog "$R_NAME" "$(m "cache 정리: mirror 에서 삭제된 브랜치의 옛 사본 제거 — ${pruned% }" "cache cleanup: dropped stale copies of branches deleted on the mirror — ${pruned% }")"
  for b in $branches; do
    if printf '%s\n' "$MIRROR_HEADS" | grep -qx "refs/heads/$b"; then
      git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$R_SRC_URL" "+refs/heads/$b:refs/remotes/src/$b"
    else git -C "$cache" update-ref -d "refs/remotes/src/$b" 2>/dev/null || true; fi
  done
  for b in $branches; do
    rv_row "$b"
    S="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$b" 2>/dev/null || true)"
    D="$(git -C "$cache" rev-parse -q --verify "refs/remotes/src/$b" 2>/dev/null || true)"
    SRC_SHA[$ROW_KEY]="$S"; DST_BEFORE[$ROW_KEY]="$D"; DST_AFTER[$ROW_KEY]="$D"
    if [ -z "$S" ]; then
      if [ "$PUSH_ONLY" -eq 1 ] && ! git -C "$cache" rev-parse -q --verify "refs/ghes-sync/absent/$b" >/dev/null 2>&1; then
        fail "$(m "GHES 브랜치 '$b' 가 cache 에 없음 — GHES 접근 가능한 곳에서 먼저 '--reverse --pull-only' 를 실행하세요" "GHES branch '$b' is not in the cache — run '--reverse --pull-only' where GHES is reachable first")"
      else ACTION[$ROW_KEY]=SKIPPED; DETAIL[$ROW_KEY]="$(m "브랜치 '$b' 가 GHES 에 없음" "branch '$b' does not exist on GHES")"; rlog "$ROW_KEY" "$(m "'$b' 는 GHES 에 없음 — SKIP" "'$b' does not exist on GHES — SKIP")"; fi
      continue
    fi
    if [ "$PULL_ONLY" -eq 1 ]; then ACTION[$ROW_KEY]=FETCHED; rlog "$ROW_KEY" "$(m "fetch 완료: GHES $(short "$S"), mirror $(short "$D")" "fetched: GHES $(short "$S"), mirror $(short "$D")")"; continue; fi
    local lease=""
    if [ -z "$D" ]; then ACTION[$ROW_KEY]=CREATE
    elif [ "$D" = "$S" ]; then ACTION[$ROW_KEY]=UP-TO-DATE; rlog "$ROW_KEY" "UP-TO-DATE ($(short "$S"))"; continue
    elif git -C "$cache" merge-base --is-ancestor "$D" "$S"; then ACTION[$ROW_KEY]=FAST-FORWARD
    elif git -C "$cache" merge-base --is-ancestor "$S" "$D"; then
      ACTION[$ROW_KEY]=TO-AHEAD
      n="$(git -C "$cache" rev-list --count "$S..$D")"
      if [ "$b" = "$R_BRANCH" ]; then
        DETAIL[$ROW_KEY]="$(m "mirror 가 GHES 보다 $n commit 앞서 있음 — 할 일 없음 (forward 실행이 push 합니다)" "the mirror is $n commit(s) ahead of GHES — nothing to do (the forward run pushes it)")"
      else
        DETAIL[$ROW_KEY]="$(m "mirror 가 GHES 보다 $n commit 앞서 있음 — forward 실행은 '$R_BRANCH' 만 sync 하므로 이 브랜치는 push되지 않음; mirror 의 $b 가 왜 앞서는지 확인 필요 (GHES $b 가 reset/rewind 되었나?)" "the mirror is $n commit(s) ahead of GHES — the forward run syncs only '$R_BRANCH', so this branch is not pushed; check why the mirror's $b is ahead (was GHES $b reset/rewound?)")"
      fi
      rlog "$ROW_KEY" "TO-AHEAD — ${DETAIL[$ROW_KEY]}"; continue
    else
      n="$(git -C "$cache" rev-list --count "$S..$D")"
      dropped="$(git -C "$cache" log --format='- %h %s' "$S..$D")"
      if [ "$FORCE_LEASE" -eq 1 ]; then
        ACTION[$ROW_KEY]=FORCED; lease="--force-with-lease=refs/heads/$b:$D"
        rlog "$ROW_KEY" "$(m "DIVERGED — --force-with-lease 지정: mirror 브랜치를 GHES 로 덮어씁니다; mirror 에만 있는 commit $n 개 DROP:" "DIVERGED — --force-with-lease given: overwriting the mirror branch with GHES; DROPPING $n mirror-only commit(s):")"
        printf '%s\n' "$dropped"
        DETAIL[$ROW_KEY]="$(m "mirror 브랜치를 덮어씀; mirror-only commit $n 개 drop" "mirror branch overwritten; $n mirror-only commit(s) dropped")"
      else
        ACTION[$ROW_KEY]=DIVERGED
        fail "$(m "DIVERGED — mirror [$b] 에 GHES 가 없는 commit $n 개가 있고, GHES 에도 mirror 가 없는 commit 이 있음. push 없음. mirror 브랜치를 GHES 로 덮어쓰려면 --force-with-lease 로 재실행 (drop 대상: $(printf '%s' "$dropped" | tr '\n' ';'))" "DIVERGED — mirror [$b] has $n commit(s) GHES lacks and GHES has commits the mirror lacks. Nothing pushed. To overwrite the mirror branch with GHES rerun with --force-with-lease (would drop: $(printf '%s' "$dropped" | tr '\n' ';'))")"
        continue
      fi
    fi
    rlog "$ROW_KEY" "${ACTION[$ROW_KEY]} (GHES $(short "$S"), mirror $(short "$D"))"
    if ! check_gitlinks_reverse "$S" "$D"; then
      fail "$(m "submodule pointer 가 sub-repo cache 에 없음 — parent 는 push 하지 않음 (gitlink_check = strict). sub-repo 브랜치를 reverse_branches 에 추가하거나 먼저 fetch 하세요." "submodule pointer not in the sub-repo cache — the parent is not pushed (gitlink_check = strict). Add the sub-repo branch to reverse_branches or fetch it first.")"; continue
    fi
    local pushcmd="git push ${lease:+$lease }$R_SRC_URL refs/remotes/dst/$b:refs/heads/$b"
    if [ "$DRY_RUN" -eq 1 ]; then rlog "$ROW_KEY" "DRY-RUN: $pushcmd"; continue; fi
    rlog "$ROW_KEY" "$pushcmd"
    if [ -n "$lease" ]; then
      gpush "$R_SRC_URL" "$(token_for src "$R_SRC_URL")" "refs/remotes/dst/$b:refs/heads/$b" "$lease" || { fail "$(m "mirror push 실패 — git: ${GPUSH_ERR:-?}" "mirror push failed — git: ${GPUSH_ERR:-?}")"; continue; }
    else
      gpush "$R_SRC_URL" "$(token_for src "$R_SRC_URL")" "refs/remotes/dst/$b:refs/heads/$b" || { fail "$(m "mirror push 실패 (force 없음) — git: ${GPUSH_ERR:-?}" "mirror push failed (no force) — git: ${GPUSH_ERR:-?}")"; continue; }
    fi
    git -C "$cache" update-ref "refs/remotes/src/$b" "$S"; DST_AFTER[$ROW_KEY]="$S"
  done
  [ "$RESET_TO_BASE" -eq 1 ] && [ "$PULL_ONLY" -eq 0 ] && reset_to_base
  ROW_KEY=""
}

# ghes_branch_merged SHA → yes|no|unknown: SHA 를 head 로 하는 merged PR(branch → pr_base)이 GHES 에 있는가
ghes_branch_merged() {
  local sha="$1" slug owner name api resp code out=unknown
  slug="$(repo_slug "$R_DST_URL")"; owner="${slug#*/}"; owner="${owner%/*}"; name="${slug##*/}"
  if [ -n "$DST_TOKEN" ] && [ "$HAVE_CURL" -eq 1 ]; then
    api="$(api_base "$R_DST_URL")"; resp="$(mktemp)"
    code="$(rest_curl "$resp" GET "$api/repos/$owner/$name/pulls?state=closed&head=$owner:$R_BRANCH&base=$R_PR_BASE&per_page=30")"
    if [ "$code" = 200 ]; then
      if grep -q "\"sha\": *\"$sha\"" "$resp" && grep -qE '"merged_at": *"[0-9]' "$resp"; then out=yes; else out=no; fi
    fi
    rm -f "$resp"
  elif [ "$HAVE_GH" -eq 1 ]; then
    local lst
    if lst="$(gh pr list -R "$slug" --head "$R_BRANCH" --base "$R_PR_BASE" --state merged --json headRefOid 2>/dev/null)"; then
      if printf '%s' "$lst" | grep -q "$sha"; then out=yes; else out=no; fi
    fi
  fi
  printf '%s' "$out"
}

# --reset-to-base, GHES 쪽: GHES <branch>  <-  GHES <pr_base>   (squash-merge 뒤 GHES 에 남은 옛 feature 브랜치를
# backup 하고 base tip 으로 재작성; merge 시 삭제되어 없으면 재생성). GHES 에 접근 가능한 실행(--push-only 아님)에서 수행.
reset_ghes_branch() {
  # 전제: process_reverse() 안에서만 호출 — 그 함수의 `local cache`(bare cache 경로)와 R_* 를 동적 스코프로 읽는다.
  # 다른 곳에서 부르면 cache 가 비어 있으므로 여기서 즉시 멈춘다(무음 오동작 방지 — PR #91 review).
  [ -n "${cache:-}" ] || die2 "reset_ghes_branch: internal error — \$cache is not set (must be called from process_reverse)"
  local b="$R_BRANCH" base="$R_PR_BASE" S G n dropped ts backup existing_backup lease="" refspec merged
  [ -n "$base" ] && [ "$base" != "$b" ] || return 0
  rv_row "$b<=$base@GHES"
  S="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$base" 2>/dev/null || true)"
  if [ -z "$S" ]; then fail "$(m "GHES 에 '$base' 가 없음 — pr_base 설정을 확인하세요" "'$base' does not exist on GHES — check the pr_base setting")"; return; fi
  G="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$b" 2>/dev/null || true)"
  SRC_SHA[$ROW_KEY]="$S"; DST_BEFORE[$ROW_KEY]="$G"; DST_AFTER[$ROW_KEY]="$G"
  refspec="refs/remotes/dst/$base:refs/heads/$b"
  if [ -z "$G" ]; then
    ACTION[$ROW_KEY]=CREATE; DETAIL[$ROW_KEY]="$(m "GHES 에 '$b' 가 없어(merge 시 삭제됨) $base tip 으로 재생성" "'$b' is absent on GHES (deleted at merge) — recreated at the $base tip")"
  elif [ "$G" = "$S" ]; then
    ACTION[$ROW_KEY]=UP-TO-DATE; rlog "$ROW_KEY" "$(m "GHES $b 는 이미 GHES $base $(short "$S") 와 동일" "GHES $b already equals GHES $base $(short "$S")")"; return
  elif git -C "$cache" merge-base --is-ancestor "$G" "$S"; then
    ACTION[$ROW_KEY]=FAST-FORWARD
  else
    ACTION[$ROW_KEY]=RESET; lease="--force-with-lease=refs/heads/$b:$G"
    n="$(git -C "$cache" rev-list --count "$S..$G")"; dropped="$(git -C "$cache" log --format='- %h %s' "$S..$G")"
    rlog "$ROW_KEY" "$(m "RESET — GHES $b @ $(short "$G") 를 GHES $base @ $(short "$S") 로 덮어씁니다 (squash-merge 된 옛 feature 브랜치 정리); GHES 브랜치에만 있는 commit $n 개:" "RESET — overwriting GHES $b @ $(short "$G") with GHES $base @ $(short "$S") (cleaning the squash-merged old feature branch); $n commit(s) only on the GHES branch:")"
    printf '%s\n' "$dropped"
    merged="$(ghes_branch_merged "$G")"
    case "$merged" in
      yes) rlog "$ROW_KEY" "$(m "merged PR 확인: head $(short "$G") 인 PR 이 $base 에 merge 되어 있음 — 안전하게 정리합니다" "merged PR confirmed: a PR with head $(short "$G") is merged into $base — safe to clean up")" ;;
      no)  rwarn "$ROW_KEY" "$(m "head $(short "$G") 인 merged PR 을 찾지 못함 — merge 되지 않은 commit 이 있을 수 있습니다. backup 브랜치에 남으므로 진행하지만 위 목록을 확인하세요" "no merged PR with head $(short "$G") found — there may be unmerged commits. Proceeding because they stay on the backup branch; check the list above")" ;;
      *)   rlog "$ROW_KEY" "$(m "merged PR 확인 생략 (dst token + curl 또는 gh 가 없음) — 위 commit 이 $base 에 merge 되었는지 직접 확인하세요; backup 브랜치에는 남습니다" "merged-PR check skipped (no dst token + curl, no gh) — verify yourself that the commits above are merged into $base; they stay on the backup branch")" ;;
    esac
    if [ "$NO_BACKUP" -eq 0 ]; then
      existing_backup="$(printf '%s\n' "$DST_LS" | awk -v s="$G" -v pre="refs/heads/backup/$b/" 'index($2, pre)==1 && $1==s {print $2; exit}')"
      if [ -n "$existing_backup" ]; then
        backup="$existing_backup"; rlog "$ROW_KEY" "$(m "옛 GHES tip $(short "$G") 는 이미 backup 되어 있음 ($backup) — 재사용" "old GHES tip $(short "$G") is already backed up ($backup) — reusing it")"
      else
        ts="$(date +%Y%m%d-%H%M%S)"; backup="refs/heads/backup/$b/$ts"
        if [ "$DRY_RUN" -eq 1 ]; then rlog "$ROW_KEY" "DRY-RUN: git push $R_DST_URL $(short "$G"):$backup"
        else
          gpush "$R_DST_URL" "$(token_for dst "$R_DST_URL")" "$G:$backup" \
            || { fail "$(m "backup 브랜치 $backup 을 GHES 에 push 하지 못함 — 덮어쓰지 않음 — git: ${GPUSH_ERR:-?}" "could not push the backup branch $backup to GHES — not overwriting — git: ${GPUSH_ERR:-?}")"; return; }
          rlog "$ROW_KEY" "$(m "옛 GHES tip 을 $backup 으로 backup" "old GHES tip backed up as $backup")"
        fi
      fi
      DETAIL[$ROW_KEY]="$(m "옛 GHES tip 은 ${backup#refs/heads/} 로 저장" "old GHES tip saved as ${backup#refs/heads/}")"
    else DETAIL[$ROW_KEY]="$(m "backup 없음 (--no-backup)" "no backup (--no-backup)")"; fi
  fi
  rlog "$ROW_KEY" "${ACTION[$ROW_KEY]} (GHES $base $(short "$S"), GHES $b $(short "$G"))"
  local pushcmd="git push ${lease:+$lease }$R_DST_URL $refspec"
  if [ "$DRY_RUN" -eq 1 ]; then rlog "$ROW_KEY" "DRY-RUN: $pushcmd"; return; fi
  rlog "$ROW_KEY" "$pushcmd"
  if [ -n "$lease" ]; then
    gpush "$R_DST_URL" "$(token_for dst "$R_DST_URL")" "$refspec" "$lease" \
      || { case "$GPUSH_ERR" in *stale*|*lease*) fail "$(m "fetch 와 push 사이에 GHES 브랜치가 움직였음 (lease) — 재실행하세요 — git: $GPUSH_ERR" "the GHES branch moved between fetch and push (lease) — rerun — git: $GPUSH_ERR")";; *) fail "$(m "GHES push 실패 — git: ${GPUSH_ERR:-?}" "GHES push failed — git: ${GPUSH_ERR:-?}")";; esac; return; }
  else
    gpush "$R_DST_URL" "$(token_for dst "$R_DST_URL")" "$refspec" \
      || { fail "$(m "GHES push 실패 (force 없음) — git: ${GPUSH_ERR:-?}" "GHES push failed (no force) — git: ${GPUSH_ERR:-?}")"; return; }
  fi
  git -C "$cache" update-ref "refs/remotes/dst/$b" "$S"; git -C "$cache" update-ref -d "refs/ghes-sync/absent/$b" 2>/dev/null || true
  DST_AFTER[$ROW_KEY]="$S"
  rlog "$ROW_KEY" "$(m "완료. GHES $b == GHES $base. mirror 쪽은 github.com push 가능한 곳에서 '--reverse --push-only --reset-to-base' 로 맞추면 다음 forward 는 UP-TO-DATE" "done. GHES $b == GHES $base. Align the mirror with '--reverse --push-only --reset-to-base' where github.com is pushable and the next forward run is UP-TO-DATE")"
}

# --reset-to-base, mirror 쪽: mirror <branch>  <-  GHES <pr_base>   (PR 이 squash-merge 된 뒤)
reset_to_base() {
  local b="$R_BRANCH" base="$R_PR_BASE" S D n dropped ts backup
  [ -n "$base" ] && [ "$base" != "$b" ] || return 0
  rv_row "$b<=$base"
  S="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$base" 2>/dev/null || true)"
  if [ -z "$S" ]; then fail "$(m "GHES '$base' 가 cache 에 없음 — GHES 접근 가능한 곳에서 먼저 '--reverse --pull-only' 를 실행하세요" "GHES '$base' is not in the cache — run '--reverse --pull-only' where GHES is reachable first")"; return; fi
  # mirror <branch> 는 위 루프에서 fetch 되지 않았을 수 있음 (reverse_branches 에 있을 때만 fetch 됨)
  if printf '%s\n' "$MIRROR_HEADS" | grep -qx "refs/heads/$b"; then
    auth_opts "$R_SRC_URL" "$(token_for src "$R_SRC_URL")"
    git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$R_SRC_URL" "+refs/heads/$b:refs/remotes/src/$b"
  else git -C "$cache" update-ref -d "refs/remotes/src/$b" 2>/dev/null || true; fi
  D="$(git -C "$cache" rev-parse -q --verify "refs/remotes/src/$b" 2>/dev/null || true)"
  SRC_SHA[$ROW_KEY]="$S"; DST_BEFORE[$ROW_KEY]="$D"; DST_AFTER[$ROW_KEY]="$D"
  local refspec="refs/remotes/dst/$base:refs/heads/$b" lease=""
  if [ -z "$D" ]; then ACTION[$ROW_KEY]=CREATE
  elif [ "$D" = "$S" ]; then ACTION[$ROW_KEY]=UP-TO-DATE; rlog "$ROW_KEY" "$(m "mirror $b 는 이미 GHES $base $(short "$S") 와 동일" "mirror $b already equals GHES $base $(short "$S")")"; return
  elif git -C "$cache" merge-base --is-ancestor "$D" "$S"; then ACTION[$ROW_KEY]=FAST-FORWARD
  else
    ACTION[$ROW_KEY]=RESET; lease="--force-with-lease=refs/heads/$b:$D"
    n="$(git -C "$cache" rev-list --count "$S..$D")"; dropped="$(git -C "$cache" log --format='- %h %s' "$S..$D")"
    rlog "$ROW_KEY" "$(m "RESET — mirror $b @ $(short "$D") 를 GHES $base @ $(short "$S") 로 덮어씁니다; mirror 에만 있는 commit $n 개가 브랜치에서 빠집니다:" "RESET — overwriting mirror $b @ $(short "$D") with GHES $base @ $(short "$S"); $n mirror-only commit(s) leave the branch:")"
    printf '%s\n' "$dropped"
    if [ "$NO_BACKUP" -eq 0 ]; then
      # 이전에 중단된 실행이 정확히 이 tip 을 이미 저장했을 수 있음 — 재사용
      local existing_backup
      existing_backup="$(printf '%s\n' "$MIRROR_LS" | awk -v s="$D" -v pre="refs/heads/backup/$b/" 'index($2, pre)==1 && $1==s {print $2; exit}')"
      if [ -n "$existing_backup" ]; then
        backup="$existing_backup"; rlog "$ROW_KEY" "$(m "옛 mirror tip $(short "$D") 는 이미 backup 되어 있음 ($backup) — 재사용" "old mirror tip $(short "$D") is already backed up ($backup) — reusing it")"
      else
        ts="$(date +%Y%m%d-%H%M%S)"; backup="refs/heads/backup/$b/$ts"
        if [ "$DRY_RUN" -eq 1 ]; then rlog "$ROW_KEY" "DRY-RUN: git push $R_SRC_URL $(short "$D"):$backup"
        else
          gpush "$R_SRC_URL" "$(token_for src "$R_SRC_URL")" "$D:$backup" \
            || { fail "$(m "backup 브랜치 $backup 을 mirror 에 push 하지 못함 — 덮어쓰지 않음 — git: ${GPUSH_ERR:-?}" "could not push the backup branch $backup to the mirror — not overwriting — git: ${GPUSH_ERR:-?}")"; return; }
          rlog "$ROW_KEY" "$(m "옛 mirror tip 을 $backup 으로 backup" "old mirror tip backed up as $backup")"
        fi
      fi
      DETAIL[$ROW_KEY]="$(m "옛 tip 은 ${backup#refs/heads/} 로 저장" "old tip saved as ${backup#refs/heads/}")"
    else DETAIL[$ROW_KEY]="$(m "backup 없음 (--no-backup)" "no backup (--no-backup)")"; fi
  fi
  rlog "$ROW_KEY" "${ACTION[$ROW_KEY]} (GHES $base $(short "$S"), mirror $b $(short "$D"))"
  local pushcmd="git push ${lease:+$lease }$R_SRC_URL $refspec"
  if [ "$DRY_RUN" -eq 1 ]; then rlog "$ROW_KEY" "DRY-RUN: $pushcmd"; return; fi
  rlog "$ROW_KEY" "$pushcmd"
  if [ -n "$lease" ]; then
    gpush "$R_SRC_URL" "$(token_for src "$R_SRC_URL")" "$refspec" "$lease" \
      || { case "$GPUSH_ERR" in *stale*|*lease*) fail "$(m "fetch 와 push 사이에 mirror 브랜치가 움직였음 (lease) — 재실행하세요 — git: $GPUSH_ERR" "the mirror branch moved between fetch and push (lease) — rerun — git: $GPUSH_ERR")";; *) fail "$(m "mirror push 실패 — git: ${GPUSH_ERR:-?}" "mirror push failed — git: ${GPUSH_ERR:-?}")";; esac; return; }
  else
    gpush "$R_SRC_URL" "$(token_for src "$R_SRC_URL")" "$refspec" \
      || { fail "$(m "mirror push 실패 (force 없음) — git: ${GPUSH_ERR:-?}" "mirror push failed (no force) — git: ${GPUSH_ERR:-?}")"; return; }
  fi
  git -C "$cache" update-ref "refs/remotes/src/$b" "$S"; DST_AFTER[$ROW_KEY]="$S"
  rlog "$ROW_KEY" "$(m "완료. dev checkout 갱신: git fetch mirror && git reset --hard mirror/$b   (remote 이름: setup_remotes.sh)" "done. Refresh your dev checkout: git fetch mirror && git reset --hard mirror/$b   (remote names: setup_remotes.sh)")"
}

# sync = off 인 repo: 양방향 모두 건너뛰고 요약에 한 줄만 남긴다 (FAIL 아님).
skip_sync_off() {
  resolve "$1"
  ROWS+=("$R_NAME"); STATUS[$R_NAME]=OK; ACTION[$R_NAME]=SKIPPED; PRINFO[$R_NAME]="-"
  DETAIL[$R_NAME]="$(m "sync=off — ghes-sync 는 이 repo 를 sync 하지 않습니다${R_GHCLOUD_URL:+ (소스: $R_GHCLOUD_URL — setup_remotes.sh 의 ghcloud remote)}" "sync=off — ghes-sync does not sync this repo${R_GHCLOUD_URL:+ (source: $R_GHCLOUD_URL — the ghcloud remote from setup_remotes.sh)}")"
  rlog "$R_NAME" "${DETAIL[$R_NAME]}"
}
if [ "$REVERSE" -eq 1 ]; then
  [ "$UPDATE_BRANCH" -eq 1 ] && warn "$(m "--reverse 에서는 --update-branch 가 무시됩니다" "--update-branch is ignored under --reverse")"
  for n in "${TARGETS[@]}"; do
    if [ "${CFG[$n.sync]:-on}" = off ]; then skip_sync_off "$n"; else process_reverse "$n"; fi
  done
else
  for n in "${TARGETS[@]}"; do
    if [ "${CFG[$n.sync]:-on}" = off ]; then skip_sync_off "$n"; else process "$n"; fi
  done
fi

# ---------------------------------------------------------------------------
# 요약 — 셀은 ASCII 만(열 정렬 유지), 긴 설명은 표 아래 [n] 로
# ---------------------------------------------------------------------------
printf '\n[%s] ══ %s%s ══%s\n' "$PROG" "$(m "요약 (SUMMARY)" "SUMMARY")" \
  "$( [ "$REVERSE" -eq 1 ] && printf ' · REVERSE: GHES → mirror' )" \
  "$( [ "$DRY_RUN" -eq 1 ] && printf '%s' "$(m '  — DRY-RUN: push / PR 생성 없음' '  — DRY-RUN: no push, no PR')" )"
declare -a C1=() C2=() C3=() C4=() C5=() C6=() C7=() NOTES=()
if [ "$REVERSE" -eq 1 ]; then C1+=(repo:branch); C2+=(action); C3+=(ghes); C4+=(mirror-before); C5+=(mirror-after); C6+=(pr); C7+=(status)
else C1+=(repo); C2+=(action); C3+=(src); C4+=(dst-before); C5+=(dst-after); C6+=(pr); C7+=(status); fi
for n in "${ROWS[@]}"; do
  st="${STATUS[$n]:-SKIPPED}"
  if [ -n "${DETAIL[$n]:-}" ]; then NOTES+=("$n: ${DETAIL[$n]}"); st="$st [${#NOTES[@]}]"; fi
  C1+=("$n"); C2+=("${ACTION[$n]:--}"); C3+=("$(short "${SRC_SHA[$n]:-}")")
  C4+=("$(short "${DST_BEFORE[$n]:-}")"); C5+=("$(short "${DST_AFTER[$n]:-}")"); C6+=("${PRINFO[$n]:--}"); C7+=("$st")
done
colw() { local w=0 c; for c in "$@"; do [ "${#c}" -gt "$w" ] && w="${#c}"; done; printf '%s' "$w"; }
W1="$(colw "${C1[@]}")"; W2="$(colw "${C2[@]}")"; W3="$(colw "${C3[@]}")"; W4="$(colw "${C4[@]}")"; W5="$(colw "${C5[@]}")"; W6="$(colw "${C6[@]}")"
rule() { printf '%*s' "$1" '' | tr ' ' '-'; }
for ((i = 0; i < ${#C1[@]}; i++)); do
  printf '  %-*s  %-*s  %-*s  %-*s  %-*s  %-*s  %s\n' "$W1" "${C1[i]}" "$W2" "${C2[i]}" "$W3" "${C3[i]}" "$W4" "${C4[i]}" "$W5" "${C5[i]}" "$W6" "${C6[i]}" "${C7[i]}"
  [ "$i" -eq 0 ] && printf '  %s  %s  %s  %s  %s  %s  %s\n' "$(rule "$W1")" "$(rule "$W2")" "$(rule "$W3")" "$(rule "$W4")" "$(rule "$W5")" "$(rule "$W6")" "$(rule 6)"
done
if [ "${#NOTES[@]}" -gt 0 ]; then
  printf '\n'
  for ((i = 0; i < ${#NOTES[@]}; i++)); do printf '  [%d] %s\n' "$((i + 1))" "${NOTES[i]}"; done
fi
[ "$ANY_FAIL" -eq 0 ] && exit 0 || exit 1
