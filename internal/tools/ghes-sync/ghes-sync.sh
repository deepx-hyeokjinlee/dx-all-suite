#!/usr/bin/env bash
# ghes-sync.sh — sync configured branches from the github.com mirror (src) to the
# closed-network GHES (dst): fetch → verify submodule pointers → fast-forward push
# (never force) → open/refresh a PR into the configured base branch.
#
# Usage:
#   ghes-sync.sh [--config FILE] [--override FILE] [--repo NAME ...] [--pull-only | --push-only]
#                [--dry-run] [--tags] [--no-pr] [--update-branch]
#                [--reverse [--force-with-lease] [--reset-to-base [--no-backup]]]
#                [--cache-dir DIR] [--print-config] [--help]
#
#   --config FILE     INI config (default: sync.conf next to this script)
#   --override FILE   local overlay applied on top of --config (default: <config>.override.conf
#                     next to it, i.e. sync.override.conf — gitignored; copy sync.override.conf.example).
#                     Put YOUR values there (src_host = your mirror org, branch = your feature branch)
#                     so sync.conf itself never shows up in `git status`.
#   --repo NAME       process only this repo (repeatable; conf order is kept)
#   --pull-only       fetch src/dst into the local cache, push nothing
#   --push-only       skip the src fetch (use the cache), still fetch dst, push
#   --dry-run         fetch and classify; print the push / gh commands, run none
#   --tags            also push refs/tags/* (never forced)
#   --no-pr           never create PRs (push only)
#   --update-branch   when the PR base (pr_base) moved on dst, merge it INTO the branch (a merge
#                     commit — never a rebase, never a force push) and ff-push it; a conflict
#                     aborts (nothing kept) and prints the manual recipe. --dry-run still merges
#                     locally, so conflicts are detected without pushing.
#   --reverse         GHES -> mirror: for each repo push the branches in `reverse_branches`
#                     (default: branch + pr_base + main) from dst to src, ff-only, no PRs. The bare
#                     cache is the carrier: `--reverse --pull-only` where GHES is reachable,
#                     then `--reverse --push-only` where github.com is pushable.
#   --force-with-lease (--reverse only) on DIVERGED overwrite the mirror branch with the GHES
#                     branch (lease = the mirror tip just fetched) after listing the mirror-only
#                     commits that are dropped. The forward direction never forces.
#   --reset-to-base   (--reverse only) after the PRs were (squash-)merged: point the mirror's
#                     `branch` at GHES's `pr_base` tip per repo — ff when possible, otherwise
#                     RESET: save the mirror tip to backup/<branch>/<timestamp> on the mirror,
#                     list the dropped mirror-only commits, push with --force-with-lease (an
#                     unconditional overwrite for you; refused only if the mirror branch moved
#                     between fetch and push). --no-backup skips the backup branch.
#   --cache-dir DIR   bare-repo cache (default: conf cache_dir, else $XDG_CACHE_HOME/ghes-sync)
#   --print-config    print the effective per-repo settings and exit
#
# Config (INI): [defaults] src_host dst_host branch dst_branch pr_base mode cache_dir
#               gitlink_check(strict|warn|off) reverse_branches; [repo NAME] src_url dst_url
#               branch dst_branch pr_base mode gitlinks("<repo>:<path> ...") reverse_branches
#               path(checkout dir relative to the suite, for setup_remotes.sh).
#               REQUIRED and intentionally empty in the committed sync.conf: src_host, branch
#               (dst_host too if you clear it) — set them in sync.override.conf or export
#               GHES_SYNC_SRC_HOST / GHES_SYNC_DST_HOST / GHES_SYNC_BRANCH; otherwise exit 2 + hint.
# Remote naming convention for dev checkouts (setup_remotes.sh): ghes = dst_host, mirror = src_host.
#               Section order =
#               processing order (nested repos BEFORE the parent that points at them).
#
# Per repo: CREATE (dst branch absent) · FAST-FORWARD · UP-TO-DATE · DST-AHEAD (dst contains
# the mirror tip plus more, e.g. a merge-update — nothing to push, the mirror is behind: use
# --reverse) · DIVERGED (both sides have commits the other lacks → repo fails, nothing pushed
# — reconcile in the mirror, rerun).
# Gitlink check: every new commit's submodule pointers must be reachable from the
# sub-repo's synced tip, else the parent is not pushed (strict) / warned (warn).
#
# Exit codes: 0 all repos OK · 1 at least one repo failed · 2 usage/config/setup error
#
# Requirements: bash >= 4, git. Optional: gh (PRs), curl (PRs via REST when gh is absent —
#   Git for Windows' git bash ships curl). With neither, branches are pushed and the PR is
#   skipped with a warning.
#
# Auth (closed network: https only, no SSH to github.com, private repos):
#   Tokens are sent per call as `git -c http.<scheme://host>/.extraheader=AUTHORIZATION: basic <b64>`
#   — nothing is written to any git config, URL or log. The tool is NON-INTERACTIVE ONLY: it never
#   prompts (GIT_TERMINAL_PROMPT=0, GCM_INTERACTIVE=Never, no PAT prompt). Before touching a host it
#   runs a credential preflight: token env set → ok; else `git credential fill` (helper, no prompt)
#   must answer; else the repo fails at once with the exact fix.
#   GHES_SYNC_SRC_TOKEN  PAT for the src host (github.com fine-grained PAT, Contents: read on the
#                        mirror-org repos). Fallback: GH_TOKEN.
#   GHES_SYNC_DST_TOKEN  PAT for the dst host (GHES: repo write + pull-request). Fallback:
#                        GH_ENTERPRISE_TOKEN — the same variable `gh` uses for PR creation.
#   Alternative without env vars: `gh auth login --hostname <host> --with-token < pat.txt` then
#   `gh auth setup-git --hostname <host>` (gh becomes git's credential helper for that host).
# Timeouts: GHES_SYNC_PROBE_TIMEOUT (ls-remote probe, default 30 s), GHES_SYNC_NET_TIMEOUT
#   (fetch/push, default 1800 s) — an unreachable host fails fast instead of hanging.
set -euo pipefail

PROG="ghes-sync"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="$SCRIPT_DIR/sync.conf"
declare -a ONLY_REPOS=()
PULL_ONLY=0; PUSH_ONLY=0; DRY_RUN=0; TAGS=0; NO_PR=0; PRINT_CONFIG=0; CACHE_OVERRIDE=""; UPDATE_BRANCH=0; OVERRIDE=""
REVERSE=0; FORCE_LEASE=0; RESET_TO_BASE=0; NO_BACKUP=0

usage() { sed -n '2,/^set -euo pipefail/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }
log()   { printf '[%s] %s\n' "$PROG" "$*"; }
warn()  { printf '[%s] WARNING: %s\n' "$PROG" "$*" >&2; }
die2()  { printf '[%s] ERROR: %s\n' "$PROG" "$*" >&2; exit 2; }
trim()  { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; s="${s%"${s##*[![:space:]]}"}"; printf '%s' "$s"; }
has_word() { local w; for w in $2; do [ "$w" = "$1" ] && return 0; done; return 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --config)    [ $# -ge 2 ] || die2 "--config needs a value"; CONFIG="$2"; shift 2 ;;
    --override)  [ $# -ge 2 ] || die2 "--override needs a value"; OVERRIDE="$2"; shift 2 ;;
    --repo)      [ $# -ge 2 ] || die2 "--repo needs a value"; ONLY_REPOS+=("$2"); shift 2 ;;
    --cache-dir) [ $# -ge 2 ] || die2 "--cache-dir needs a value"; CACHE_OVERRIDE="$2"; shift 2 ;;
    --pull-only) PULL_ONLY=1; shift ;;
    --push-only) PUSH_ONLY=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --tags)      TAGS=1; shift ;;
    --no-pr)     NO_PR=1; shift ;;
    --update-branch) UPDATE_BRANCH=1; shift ;;
    --reverse)   REVERSE=1; shift ;;
    --force-with-lease) FORCE_LEASE=1; shift ;;
    --reset-to-base) RESET_TO_BASE=1; shift ;;
    --no-backup) NO_BACKUP=1; shift ;;
    --print-config) PRINT_CONFIG=1; shift ;;
    -h|--help)   usage; exit 0 ;;
    *) die2 "unknown argument '$1' (see --help)" ;;
  esac
done
[ "$PULL_ONLY" -eq 1 ] && [ "$PUSH_ONLY" -eq 1 ] && die2 "--pull-only and --push-only are mutually exclusive"
[ "$FORCE_LEASE" -eq 1 ] && [ "$REVERSE" -eq 0 ] && die2 "--force-with-lease is only accepted together with --reverse (the forward direction mirror -> GHES never forces)"
[ "$RESET_TO_BASE" -eq 1 ] && [ "$REVERSE" -eq 0 ] && die2 "--reset-to-base is only accepted together with --reverse (it rewrites the MIRROR branch from GHES's pr_base)"
command -v git >/dev/null 2>&1 || die2 "git not found in PATH"
# Non-interactive only: never block on a terminal prompt or a credential-manager UI.
export GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never
HAVE_GH=0;   command -v gh   >/dev/null 2>&1 && HAVE_GH=1
HAVE_CURL=0; command -v curl >/dev/null 2>&1 && HAVE_CURL=1
# Credential preflight — the tool never prompts, so make sure git WILL be able to authenticate.
has_creds() {  # has_creds URL TOKEN → 0 when a token is set, the URL is not http(s), or a credential helper answers (no prompt)
  local url="$1" token="$2"
  [ -n "$token" ] && return 0
  case "$url" in http://*|https://*) ;; *) return 0 ;; esac
  printf 'url=%s\n\n' "$url" | git credential fill 2>/dev/null | grep -q '^password='
}
cred_hint() {  # cred_hint src|dst URL
  local host="${2#*://}"; host="${host%%/*}"
  local var="GHES_SYNC_SRC_TOKEN (or GH_TOKEN)"; [ "$1" = dst ] && var="GHES_SYNC_DST_TOKEN (or GH_ENTERPRISE_TOKEN)"
  printf 'no credentials for %s and the tool never prompts — either export %s=<PAT>, or once per machine: gh auth login --hostname %s --with-token < pat.txt && gh auth setup-git --hostname %s' \
    "$2" "$var" "$host" "$host"
}
# Network timeouts (seconds): an unreachable host must fail fast, not hang until the TCP timeout.
PROBE_TIMEOUT="${GHES_SYNC_PROBE_TIMEOUT:-30}"   # ls-remote connectivity probe
NET_TIMEOUT="${GHES_SYNC_NET_TIMEOUT:-1800}"     # fetch / push (large first fetches take a while)
tmo() { local secs="$1"; shift; if command -v timeout >/dev/null 2>&1; then timeout "$secs" "$@"; else "$@"; fi; }
RETRIES="${GHES_SYNC_RETRIES:-3}"; RETRY_DELAY="${GHES_SYNC_RETRY_DELAY:-5}"
GPUSH_ERR=""   # last git stderr line of the last gpush (plus a hint for known network errors)
# gpush URL TOKEN REFSPEC [PUSH-OPTS...] — `git push -q OPTS URL REFSPEC` from $cache, retried on
# transient (network/TLS) errors; rejections (non-ff, lease, auth) are not retried. Never adds --force.
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
    warn "push attempt $attempt/$RETRIES failed (${GPUSH_ERR:-no stderr}) — retry in ${RETRY_DELAY}s"
    attempt=$((attempt + 1)); sleep "$RETRY_DELAY"
  done
  rm -f "$errf"
  if printf '%s' "$GPUSH_ERR" | grep -qiE 'GnuTLS|TLS|SSL|RPC failed|early EOF|Connection reset|timed out|Could not resolve|unable to access|remote end hung up'; then
    GPUSH_ERR="$GPUSH_ERR [network/TLS error — rerun; if it persists: git config --global http.version HTTP/1.1  (and http.postBuffer 524288000)]"
  fi
  return "$rc"
}
SRC_TOKEN="${GHES_SYNC_SRC_TOKEN:-${GH_TOKEN:-}}"
DST_TOKEN="${GHES_SYNC_DST_TOKEN:-${GH_ENTERPRISE_TOKEN:-}}"

# auth_opts URL TOKEN → sets the global array AUTH_OPTS to `-c http.<scheme://host>/.extraheader=...`
# for http(s) URLs when TOKEN is non-empty, else to nothing (file://, ssh, no token).
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
  local var="GHES_SYNC_SRC_TOKEN (or GH_TOKEN)"; [ "$1" = dst ] && var="GHES_SYNC_DST_TOKEN (or GH_ENTERPRISE_TOKEN)"
  printf 'auth/network? private repos need a PAT: export %s, or `gh auth login --hostname <host> --with-token` + `gh auth setup-git --hostname <host>`; URL: %s' "$var" "$2"
}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
declare -A DEF=() CFG=()
declare -a REPOS=()
KNOWN_DEF="src_host dst_host branch dst_branch pr_base mode cache_dir gitlink_check reverse_branches"
KNOWN_REPO="src_url dst_url src_host dst_host branch dst_branch pr_base mode gitlinks reverse_branches path"

parse_conf() {  # parse_conf FILE OVERLAY(0|1) — OVERLAY: a [repo] already known from the base file is merged, not an error
  local file="$1" overlay="${2:-0}"
  [ -f "$file" ] || die2 "config not found: $file"
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
        if has_word "$name" "${REPOS[*]:-}"; then [ "$overlay" -eq 1 ] || die2 "duplicate [repo $name] in $file"
        else REPOS+=("$name"); fi
        section="repo:$name"
      else die2 "unknown section [$section] in $file"; fi
      continue
    fi
    [[ "$line" == *=* ]] || die2 "malformed line in $file: '$line'"
    key="$(trim "${line%%=*}")"; val="$(trim "${line#*=}")"
    case "$section" in
      defaults) has_word "$key" "$KNOWN_DEF" || die2 "unknown key '$key' in [defaults] of $file (known: $KNOWN_DEF)"
                DEF[$key]="$val" ;;
      repo:*)   has_word "$key" "$KNOWN_REPO" || die2 "unknown key '$key' in [$section] of $file (known: $KNOWN_REPO)"
                CFG["${section#repo:}.$key"]="$val" ;;
      *)        die2 "key '$key' appears before any [section] in $file" ;;
    esac
  done < "$file"
}

# eff NAME KEY → repo value, else [defaults], else built-in default
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
# repo_slug URL → HOST/OWNER/NAME for `gh -R` (https, scp-like git@host:owner/name, file://)
repo_slug() {
  local u="$1"; u="${u%/}"; u="${u%.git}"; u="${u#*://}"; u="${u#*@}"; u="${u/:/\/}"
  local IFS=/; local -a p; read -r -a p <<<"$u"; local n=${#p[@]}
  [ "$n" -ge 3 ] || die2 "cannot derive HOST/OWNER/REPO from url '$1'"
  printf '%s/%s/%s' "${p[n-3]}" "${p[n-2]}" "${p[n-1]}"
}

# resolve NAME → R_* globals
resolve() {
  local name="$1" v
  R_NAME="$name"
  R_BRANCH="$(eff "$name" branch)"
  [ -n "$R_BRANCH" ] || die2 "[repo $name]: 'branch' is EMPTY — set your feature branch in $OVERRIDE_HINT ([defaults] branch = feature/<topic>) or export GHES_SYNC_BRANCH=<branch>"
  R_DST_BRANCH="$(eff "$name" dst_branch)"; [ -n "$R_DST_BRANCH" ] || R_DST_BRANCH="$R_BRANCH"
  R_SRC_URL="${CFG[$name.src_url]:-}"
  if [ -z "$R_SRC_URL" ]; then
    v="$(eff "$name" src_host)"
    [ -n "$v" ] || die2 "[repo $name]: 'src_host' is EMPTY — set your private mirror org in $OVERRIDE_HINT ([defaults] src_host = https://github.com/<MIRROR-ORG>) or export GHES_SYNC_SRC_HOST=<url>"
    R_SRC_URL="$(join_url "$v" "$name")"
  fi
  R_DST_URL="${CFG[$name.dst_url]:-}"
  if [ -z "$R_DST_URL" ]; then
    v="$(eff "$name" dst_host)"
    [ -n "$v" ] || die2 "[repo $name]: 'dst_host' is EMPTY — set the GHES org in $OVERRIDE_HINT ([defaults] dst_host = https://gh.deepx.ai/deepx) or export GHES_SYNC_DST_HOST=<url>"
    R_DST_URL="$(join_url "$v" "$name")"
  fi
  R_PR_BASE="$(eff "$name" pr_base)"
  R_MODE="$(eff "$name" mode)"; has_word "$R_MODE" "pr push" || die2 "[repo $name]: mode must be pr|push (got '$R_MODE')"
  R_GITLINKS="${CFG[$name.gitlinks]:-}"
  R_PATH="${CFG[$name.path]:-}"                    # checkout path relative to the suite dir (setup_remotes.sh)
  R_GL_CHECK="$(eff "$name" gitlink_check)"; has_word "$R_GL_CHECK" "strict warn off" || die2 "gitlink_check must be strict|warn|off"
}

validate() {
  local name sub pair i j seen
  for ((i = 0; i < ${#REPOS[@]}; i++)); do
    name="${REPOS[i]}"; resolve "$name"
    for pair in $R_GITLINKS; do
      [[ "$pair" == *:* ]] || die2 "[repo $name]: gitlinks entry '$pair' must be <repo>:<path>"
      sub="${pair%%:*}"; seen=0
      for ((j = 0; j < i; j++)); do [ "${REPOS[j]}" = "$sub" ] && seen=1; done
      [ "$seen" -eq 1 ] || die2 "[repo $name]: gitlinks refers to '$sub', which must be listed as an EARLIER [repo] section (nested repos first)"
    done
  done
  for name in "${ONLY_REPOS[@]:-}"; do
    [ -z "$name" ] && continue
    has_word "$name" "${REPOS[*]}" || die2 "--repo '$name' is not in $CONFIG (repos: ${REPOS[*]})"
  done
}

parse_conf "$CONFIG" 0
OVERRIDE_FILE="${OVERRIDE:-${CONFIG%.conf}.override.conf}"
OVERRIDE_APPLIED=""
if [ -f "$OVERRIDE_FILE" ]; then parse_conf "$OVERRIDE_FILE" 1; OVERRIDE_APPLIED="$OVERRIDE_FILE"
elif [ -n "$OVERRIDE" ]; then die2 "--override file not found: $OVERRIDE"; fi
OVERRIDE_HINT="$OVERRIDE_FILE (gitignored; copy $(dirname "$CONFIG")/sync.override.conf.example)"
[ "${#REPOS[@]}" -gt 0 ] || die2 "no [repo NAME] sections in $CONFIG"
# env fallbacks for the values the committed sync.conf leaves empty on purpose
[ -n "${DEF[src_host]:-}" ] || DEF[src_host]="${GHES_SYNC_SRC_HOST:-}"
[ -n "${DEF[dst_host]:-}" ] || DEF[dst_host]="${GHES_SYNC_DST_HOST:-}"
[ -n "${DEF[branch]:-}" ]   || DEF[branch]="${GHES_SYNC_BRANCH:-}"
# Report EVERY missing required value at once (the committed sync.conf leaves src_host and branch empty on purpose).
check_required() {
  local n missing="" k
  for n in "${REPOS[@]}"; do
    [ -n "${CFG[$n.src_url]:-}" ] || [ -n "$(eff "$n" src_host)" ] || has_word src_host "$missing" || missing="$missing src_host"
    [ -n "${CFG[$n.dst_url]:-}" ] || [ -n "$(eff "$n" dst_host)" ] || has_word dst_host "$missing" || missing="$missing dst_host"
    [ -n "$(eff "$n" branch)" ] || has_word branch "$missing" || missing="$missing branch"
  done
  [ -n "$missing" ] || return 0
  printf '[%s] ERROR: required setting(s) not set:%s\n' "$PROG" "$missing" >&2
  printf '[%s]   They are left EMPTY in sync.conf on purpose. Set them in %s\n' "$PROG" "$OVERRIDE_HINT" >&2
  for k in $missing; do
    case "$k" in
      src_host) printf '[%s]     [defaults] src_host = https://github.com/<YOUR-MIRROR-ORG>   (https only)   or: export GHES_SYNC_SRC_HOST=<url>\n' "$PROG" >&2 ;;
      dst_host) printf '[%s]     [defaults] dst_host = https://gh.deepx.ai/deepx                          or: export GHES_SYNC_DST_HOST=<url>\n' "$PROG" >&2 ;;
      branch)   printf '[%s]     [defaults] branch = feature/<your-topic>                                or: export GHES_SYNC_BRANCH=<branch>\n' "$PROG" >&2 ;;
    esac
  done
  exit 2
}
check_required
validate

CACHE_DIR="${CACHE_OVERRIDE:-$(eff _ cache_dir)}"
# expand ${VAR:-default}/$VAR first (config is trusted), then a leading ~ (also one produced by the default)
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
  done
  exit 0
fi

if [ "$NO_PR" -eq 0 ] && [ "$PULL_ONLY" -eq 0 ] && [ "$HAVE_GH" -eq 0 ] && { [ "$HAVE_CURL" -eq 0 ] || [ -z "$DST_TOKEN" ]; }; then
  for n in "${TARGETS[@]}"; do
    if [ "$(eff "$n" mode)" = pr ]; then
      warn "no gh CLI and no dst token — branches will be pushed but PRs will be SKIPPED (set GHES_SYNC_DST_TOKEN for REST via curl, or install gh)"
      break
    fi
  done
fi

# ---------------------------------------------------------------------------
# Per-repo processing
# ---------------------------------------------------------------------------
declare -A ACTION=() STATUS=() DETAIL=() SRC_SHA=() DST_BEFORE=() DST_AFTER=() PRINFO=() SYNCED_OK=()
declare -a ROWS=()      # summary rows: repo (forward) or repo:branch (reverse)
ROW_KEY=""              # set by process_reverse per branch; empty = key by R_NAME
ANY_FAIL=0

fail() { local k="${ROW_KEY:-$R_NAME}"; STATUS[$k]=FAIL; DETAIL[$k]="$*"; ANY_FAIL=1; printf '[%s] %s: FAIL — %s\n' "$PROG" "$k" "$*" >&2; }
short() { printf '%.7s' "${1:--}"; }

ensure_cache() { [ -d "$1" ] || { mkdir -p "$1"; git init -q --bare "$1"; }; }

# fetch_dst_ref CACHE URL REF  — fetch refs/heads/REF into refs/remotes/dst/REF, or drop the stale local copy
fetch_dst_ref() {
  local cache="$1" url="$2" ref="$3"
  if printf '%s\n' "$DST_HEADS" | grep -qx "refs/heads/$ref"; then
    auth_opts "$url" "$DST_TOKEN"
    git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$url" "+refs/heads/$ref:refs/remotes/dst/$ref"
    git -C "$cache" update-ref -d "refs/ghes-sync/absent/$ref" 2>/dev/null || true
  else
    git -C "$cache" update-ref -d "refs/remotes/dst/$ref" 2>/dev/null || true
    # remember "absent on GHES" so a later --push-only (GHES unreachable) reports SKIPPED, not "not fetched"
    git -C "$cache" update-ref "refs/ghes-sync/absent/$ref" "$(printf 'absent' | git -C "$cache" hash-object -w --stdin)"
  fi
}

# sub_ref SUB → the ref the pointer must be reachable from: the sub's src tip when it
# was synced OK in this run (it IS on dst now — or WOULD be, in --dry-run), else
# whatever dst currently has.
sub_ref() {
  local sub="$1" subcache="$CACHE_DIR/$sub.git" br dbr
  br="$(eff "$sub" branch)"; dbr="$(eff "$sub" dst_branch)"; [ -n "$dbr" ] || dbr="$br"
  if [ -n "${SYNCED_OK[$sub]:-}" ]; then printf 'refs/remotes/src/%s' "$br"; return; fi
  ensure_cache "$subcache"
  local url="${CFG[$sub.dst_url]:-}"; [ -n "$url" ] || url="$(join_url "$(eff "$sub" dst_host)" "$sub")"
  auth_opts "$url" "$DST_TOKEN"
  git "${AUTH_OPTS[@]}" -C "$subcache" fetch -q --no-tags "$url" "+refs/heads/$dbr:refs/remotes/dst/$dbr" 2>/dev/null || true
  printf 'refs/remotes/dst/%s' "$dbr"
}

check_gitlinks() {  # uses R_*, S, D, cache; returns 1 when strict and a pointer is unreachable
  [ "$R_GL_CHECK" = off ] && return 0
  [ -n "$R_GITLINKS" ] || return 0
  local commits pair sub path sha ref bad=0 c
  if [ -n "$D" ]; then commits="$(git -C "$cache" rev-list "$D..$S")"
  elif git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1; then
    commits="$(git -C "$cache" rev-list "refs/remotes/dst/$R_PR_BASE..$S")"; [ -n "$commits" ] || commits="$S"
  else commits="$S"; fi
  for c in $commits; do
    for pair in $R_GITLINKS; do
      sub="${pair%%:*}"; path="${pair#*:}"
      sha="$(git -C "$cache" ls-tree "$c" -- "$path" | awk '$1=="160000"{print $3}')"
      [ -n "$sha" ] || continue
      ref="$(sub_ref "$sub")"
      if ! git -C "$CACHE_DIR/$sub.git" merge-base --is-ancestor "$sha" "$ref" 2>/dev/null; then
        printf '[%s] %s: gitlink %s @ %s -> %s/%s is NOT reachable from %s (%s)\n' \
          "$PROG" "$R_NAME" "$path" "$(short "$c")" "$sub" "$(short "$sha")" "$ref" \
          "$( [ -n "${SYNCED_OK[$sub]:-}" ] && { [ "$DRY_RUN" -eq 1 ] && echo "would be synced this run" || echo "synced this run"; } || echo "as on dst" )" >&2
        bad=1
      fi
    done
  done
  if [ "$bad" -eq 1 ]; then
    if [ "$R_GL_CHECK" = strict ]; then return 1; fi
    warn "$R_NAME: submodule pointer(s) not reachable on dst — pushing anyway (gitlink_check = warn)"
  fi
  return 0
}

# ── --update-branch: merge the moved PR base into the branch (never rebase / force) ──
# Only a clean merge is automated. A conflict is resolved BY HAND (user decision): the tool
# aborts, keeps no worktree and prints the recipe for both machines.
manual_recipe() {
  printf 'Resolve it by hand — closed network (GHES pushable): in your checkout run git fetch %s %s && git merge FETCH_HEAD, resolve, commit, then git push %s HEAD:refs/heads/%s (ff onto the GHES branch); the next forward run shows DST-AHEAD and --reverse brings the mirror up. Dev machine (github.com pushable): the same merge in the mirror checkout, push the mirror, the forward run pushes it as FAST-FORWARD. Never --force-with-lease / --reset-to-base for this.' \
    "$R_DST_URL" "$R_PR_BASE" "$R_DST_URL" "$R_DST_BRANCH"
}
merge_update() {  # $1 = number of base commits the branch lacks; uses R_*, cache, TIP; sets TIP/ACTION or fails
  local behind="$1" wt m files name email msg
  name="${GHES_SYNC_GIT_NAME:-$(git config user.name 2>/dev/null || true)}";   [ -n "$name" ]  || name="ghes-sync"
  email="${GHES_SYNC_GIT_EMAIL:-$(git config user.email 2>/dev/null || true)}"; [ -n "$email" ] || email="ghes-sync@noreply.local"
  wt="$(mktemp -d "${TMPDIR:-/tmp}/ghes-sync-wt.XXXXXX")"; rmdir "$wt"
  git -C "$cache" worktree prune >/dev/null 2>&1 || true
  if ! git -C "$cache" worktree add -q --detach "$wt" "$TIP" >/dev/null 2>&1; then
    fail "cannot create a temporary worktree of the cache for the merge-update"; return 1
  fi
  msg="Merge $R_PR_BASE into $R_DST_BRANCH (ghes-sync --update-branch)"
  if git -C "$wt" -c user.name="$name" -c user.email="$email" merge -q --no-ff --no-edit -m "$msg" "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1; then
    m="$(git -C "$wt" rev-parse HEAD)"
    git -C "$cache" worktree remove --force "$wt" >/dev/null 2>&1 || true; git -C "$cache" worktree prune >/dev/null 2>&1 || true
    if [ "$DRY_RUN" -eq 1 ]; then
      log "$R_NAME: DRY-RUN: would merge $R_PR_BASE ($behind commit(s)) into $R_DST_BRANCH -> $(short "$m") and git push $R_DST_URL $(short "$m"):refs/heads/$R_DST_BRANCH"
    else
      if ! gpush "$R_DST_URL" "$DST_TOKEN" "$m:refs/heads/$R_DST_BRANCH"; then
        fail "push of the merge-update commit failed (nothing forced) — git: ${GPUSH_ERR:-?}"; return 1
      fi
      git -C "$cache" update-ref "refs/remotes/dst/$R_DST_BRANCH" "$m"; DST_AFTER[$R_NAME]="$m"
      log "$R_NAME: merged $R_PR_BASE ($behind commit(s)) into $R_DST_BRANCH -> $(short "$m"), pushed"
    fi
    TIP="$m"; ACTION[$R_NAME]=MERGE-UPDATED
    DETAIL[$R_NAME]="mirror is behind by the merge commit — bring it back with --reverse (from a machine that can push github.com)"
    return 0
  fi
  files="$(git -C "$wt" diff --name-only --diff-filter=U 2>/dev/null | tr '\n' ' ')"
  git -C "$wt" merge --abort >/dev/null 2>&1 || true
  git -C "$cache" worktree remove --force "$wt" >/dev/null 2>&1 || true; git -C "$cache" worktree prune >/dev/null 2>&1 || true
  fail "merge CONFLICT merging $R_PR_BASE into $R_DST_BRANCH (files: ${files:-unknown}) — nothing pushed, nothing kept. $(manual_recipe)"
  return 1
}

# ── PR backends: gh CLI, or the REST API via curl (no gh on Windows git bash) ──
json_str() {  # stdin → JSON string literal (with quotes)
  printf '"'; awk 'BEGIN{ORS=""} {gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); gsub(/\t/,"\\t"); gsub(/\r/,""); if (NR>1) printf "\\n"; printf "%s", $0}'; printf '"'
}
api_base() {  # api_base DST_URL → https://api.github.com | <scheme>://<host>/api/v3
  local url="$1" scheme host; scheme="${url%%://*}"; host="${url#*://}"; host="${host%%/*}"
  if [ "$host" = github.com ]; then printf 'https://api.github.com'; else printf '%s://%s/api/v3' "$scheme" "$host"; fi
}
rest_curl() {  # rest_curl OUTFILE METHOD URL [DATAFILE] → prints http code; uses DST_TOKEN via a -K config (never argv)
  local out="$1" method="$2" url="$3" data="${4:-}" cfg code
  cfg="$(mktemp)"; chmod 600 "$cfg"
  printf 'header = "Authorization: token %s"\nheader = "Accept: application/vnd.github+json"\nheader = "Content-Type: application/json"\n' "$DST_TOKEN" > "$cfg"
  if [ -n "$data" ]; then code="$(tmo "$PROBE_TIMEOUT" curl -sS -K "$cfg" -X "$method" --data "@$data" -o "$out" -w '%{http_code}' "$url" 2>/dev/null || true)"
  else code="$(tmo "$PROBE_TIMEOUT" curl -sS -K "$cfg" -o "$out" -w '%{http_code}' "$url" 2>/dev/null || true)"; fi
  rm -f "$cfg"; printf '%s' "$code"
}

ensure_pr() {  # uses R_*, TIP, cache
  [ "$NO_PR" -eq 1 ] && return 0
  [ "$R_MODE" = pr ] || return 0
  [ -n "$R_PR_BASE" ] || return 0
  [ "$R_DST_BRANCH" != "$R_PR_BASE" ] || return 0
  local slug backend existing num url ahead title body resp code api owner name
  slug="$(repo_slug "$R_DST_URL")"; owner="${slug#*/}"; owner="${owner%/*}"; name="${slug##*/}"
  # backend: explicit dst token + curl → REST · gh present → gh · else skip (never prompts)
  backend=""
  if [ -n "$DST_TOKEN" ] && [ "$HAVE_CURL" -eq 1 ]; then backend=rest
  elif [ "$HAVE_GH" -eq 1 ]; then backend=gh; fi
  if [ -z "$backend" ]; then
    warn "$R_NAME: PR skipped (no gh CLI and no dst token) — branch is pushed; set GHES_SYNC_DST_TOKEN (REST via curl) or install gh and rerun, or open the PR by hand"
    PRINFO[$R_NAME]="skipped (no gh, no token)"; return 0
  fi
  api="$(api_base "$R_DST_URL")"; resp="$(mktemp)"
  # 1. existing open PR?
  if [ "$backend" = gh ]; then
    if ! existing="$(gh pr list -R "$slug" --head "$R_DST_BRANCH" --base "$R_PR_BASE" --state open --json number,url 2>&1)"; then
      rm -f "$resp"; fail "gh pr list failed for $slug: $existing"; return 1
    fi
  else
    code="$(rest_curl "$resp" GET "$api/repos/$owner/$name/pulls?state=open&head=$owner:$R_DST_BRANCH&base=$R_PR_BASE")"
    if [ "$code" != 200 ]; then fail "REST pr list failed (HTTP ${code:-none}) for $api/repos/$owner/$name — token scope / host?"; rm -f "$resp"; return 1; fi
    existing="$(cat "$resp")"
  fi
  num="$(printf '%s' "$existing" | grep -o '"number": *[0-9]*' | head -n1 | grep -o '[0-9]*$' || true)"
  # web URL: REST has html_url (its `url` is the API endpoint); gh's --json url is already the web URL
  url="$(printf '%s' "$existing" | grep -o '"html_url": *"[^"]*"' | head -n1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  [ -n "$url" ] || url="$(printf '%s' "$existing" | grep -o '"url": *"[^"]*"' | head -n1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  if [ -n "$num" ]; then PRINFO[$R_NAME]="#$num (existing) $url"; log "$R_NAME: PR #$num already open $url"; rm -f "$resp"; return 0; fi
  # 2. anything to propose?
  if ! git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1; then
    warn "$R_NAME: PR base '$R_PR_BASE' does not exist on dst — no PR created"
    PRINFO[$R_NAME]="no base '$R_PR_BASE' on dst"; rm -f "$resp"; return 0
  fi
  ahead="$(git -C "$cache" rev-list --count "refs/remotes/dst/$R_PR_BASE..$TIP")"
  if [ "$ahead" -eq 0 ]; then PRINFO[$R_NAME]="nothing ahead of $R_PR_BASE"; rm -f "$resp"; return 0; fi
  # conventional-commit style: GHES's commit-message-checker-pr workflow rejects "sync(<repo>): ..."
  title="ci: sync $R_NAME $R_BRANCH -> $R_PR_BASE ($ahead commits)"
  body="$(mktemp)"
  {
    printf 'Automated sync by ghes-sync.sh from the github.com mirror.\n\nSource: %s @ %s\nCommits ahead of `%s`: %s\n\n' \
      "$R_BRANCH" "$(short "$TIP")" "$R_PR_BASE" "$ahead"
    git -C "$cache" log --format='- %h %s' -n 50 "refs/remotes/dst/$R_PR_BASE..$TIP"
    [ "$ahead" -gt 50 ] && printf -- '- ... (%s more)\n' "$((ahead - 50))"
  } > "$body"
  # 3. create
  log "$R_NAME: PR title: $title"
  if [ "$DRY_RUN" -eq 1 ]; then
    if [ "$backend" = gh ]; then log "$R_NAME: DRY-RUN: gh pr create -R $slug -B $R_PR_BASE -H $R_DST_BRANCH -t '$title'"
    else log "$R_NAME: DRY-RUN: POST $api/repos/$owner/$name/pulls  head=$R_DST_BRANCH base=$R_PR_BASE title='$title'"; fi
    PRINFO[$R_NAME]="(dry-run) would create"; rm -f "$body" "$resp"; return 0
  fi
  if [ "$backend" = gh ]; then
    if url="$(gh pr create -R "$slug" -B "$R_PR_BASE" -H "$R_DST_BRANCH" -t "$title" -F "$body" 2>&1)"; then
      PRINFO[$R_NAME]="created $url"; log "$R_NAME: PR created $url"; rm -f "$body" "$resp"; return 0
    fi
    rm -f "$body" "$resp"; fail "gh pr create failed (branch was pushed): $url"; return 1
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
    PRINFO[$R_NAME]="created $url"; log "$R_NAME: PR #$num created via REST $url"; rm -f "$resp"; return 0
  fi
  fail "REST pr create failed (HTTP ${code:-none}, branch was pushed): $(head -c 300 "$resp" 2>/dev/null)"; rm -f "$resp"; return 1
}

process() {
  resolve "$1"
  local cache="$CACHE_DIR/$R_NAME.git" S D TIP
  ROWS+=("$R_NAME"); STATUS[$R_NAME]=OK; ACTION[$R_NAME]=-; DETAIL[$R_NAME]=""; PRINFO[$R_NAME]="-"
  log "== $R_NAME: $R_SRC_URL [$R_BRANCH] -> $R_DST_URL [$R_DST_BRANCH]"
  ensure_cache "$cache"
  if [ "$PUSH_ONLY" -eq 0 ] && ! has_creds "$R_SRC_URL" "$SRC_TOKEN"; then fail "$(cred_hint src "$R_SRC_URL")"; return; fi
  if ! has_creds "$R_DST_URL" "$DST_TOKEN"; then fail "$(cred_hint dst "$R_DST_URL")"; return; fi

  if [ "$PUSH_ONLY" -eq 0 ]; then
    auth_opts "$R_SRC_URL" "$SRC_TOKEN"
    local frc=0
    tmo "$NET_TIMEOUT" git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$R_SRC_URL" "+refs/heads/$R_BRANCH:refs/remotes/src/$R_BRANCH" || frc=$?
    if [ "$frc" -eq 124 ]; then fail "src fetch timed out after ${NET_TIMEOUT}s (GHES_SYNC_NET_TIMEOUT) — $R_SRC_URL"; return
    elif [ "$frc" -ne 0 ]; then fail "cannot fetch src [$R_BRANCH] — $(auth_hint src "$R_SRC_URL")"; return; fi
    [ "$TAGS" -eq 1 ] && tmo "$NET_TIMEOUT" git "${AUTH_OPTS[@]}" -C "$cache" fetch -q "$R_SRC_URL" "+refs/tags/*:refs/tags/*"
  fi
  auth_opts "$R_DST_URL" "$DST_TOKEN"
  local probe_rc=0
  DST_HEADS="$(tmo "$PROBE_TIMEOUT" git "${AUTH_OPTS[@]}" ls-remote --heads "$R_DST_URL" 2>/dev/null | awk '{print $2}')" || probe_rc=$?
  if [ "$probe_rc" -eq 124 ]; then
    fail "dst probe timed out after ${PROBE_TIMEOUT}s (GHES_SYNC_PROBE_TIMEOUT) — is $R_DST_URL reachable from this machine?"; return
  elif [ "$probe_rc" -ne 0 ]; then
    fail "cannot reach dst — $(auth_hint dst "$R_DST_URL")"; return
  fi
  fetch_dst_ref "$cache" "$R_DST_URL" "$R_DST_BRANCH"
  [ -n "$R_PR_BASE" ] && [ "$R_PR_BASE" != "$R_DST_BRANCH" ] && fetch_dst_ref "$cache" "$R_DST_URL" "$R_PR_BASE"

  S="$(git -C "$cache" rev-parse -q --verify "refs/remotes/src/$R_BRANCH" 2>/dev/null || true)"
  [ -n "$S" ] || { fail "source branch '$R_BRANCH' not in cache (never fetched?)"; return; }
  D="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_DST_BRANCH" 2>/dev/null || true)"
  SRC_SHA[$R_NAME]="$S"; DST_BEFORE[$R_NAME]="$D"; DST_AFTER[$R_NAME]="$D"

  if [ "$PULL_ONLY" -eq 1 ]; then ACTION[$R_NAME]=FETCHED; log "$R_NAME: fetched src $(short "$S"), dst $(short "$D")"; return; fi

  TIP="$S"
  if [ -z "$D" ]; then ACTION[$R_NAME]=CREATE
  elif [ "$D" = "$S" ]; then ACTION[$R_NAME]=UP-TO-DATE
  elif git -C "$cache" merge-base --is-ancestor "$D" "$S"; then ACTION[$R_NAME]=FAST-FORWARD
  elif git -C "$cache" merge-base --is-ancestor "$S" "$D"; then
    ACTION[$R_NAME]=DST-AHEAD; TIP="$D"
    DETAIL[$R_NAME]="dst is $(git -C "$cache" rev-list --count "$S..$D") commit(s) ahead of the mirror — nothing to push; bring the mirror up with --reverse"
    log "$R_NAME: DST-AHEAD — dst [$R_DST_BRANCH] @ $(short "$D") contains the mirror tip $(short "$S") plus $(git -C "$cache" rev-list --count "$S..$D") commit(s) (merge-update or GHES-side commits). Nothing to push; the MIRROR is behind — run ghes-sync.sh --reverse from a machine that can push github.com."
  else
    ACTION[$R_NAME]=DIVERGED
    fail "dst [$R_DST_BRANCH] @ $(short "$D") has commits not in src @ $(short "$S") and vice versa — this tool never force-pushes forward. Pick the truth: (a) the MIRROR is right → on the dev machine: git fetch $R_DST_URL $R_DST_BRANCH && merge/rebase, push the mirror, rerun; (b) GHES is right (e.g. you resolved a conflict and force-pushed $R_DST_BRANCH on GHES) → overwrite the mirror: '--reverse --pull-only' here, then '--reverse --push-only --force-with-lease' where github.com is pushable, reset your local checkout to the new mirror branch, rerun. If a SUB-repo branch was rewritten, bump the parent repos' submodule pointers to the new commits too."
    return
  fi
  log "$R_NAME: ${ACTION[$R_NAME]} (src $(short "$S"), dst $(short "$D"))"

  if [ "${ACTION[$R_NAME]}" = CREATE ] || [ "${ACTION[$R_NAME]}" = FAST-FORWARD ]; then
    if ! check_gitlinks; then
      fail "submodule pointer(s) not reachable on dst — parent NOT pushed (gitlink_check = strict). Sync the sub-repo branch that contains them first."
      return
    fi
    local pushcmd="git push $R_DST_URL refs/remotes/src/$R_BRANCH:refs/heads/$R_DST_BRANCH"
    if [ "$DRY_RUN" -eq 1 ]; then log "$R_NAME: DRY-RUN: $pushcmd"
    else
      log "$R_NAME: $pushcmd"
      if ! gpush "$R_DST_URL" "$DST_TOKEN" "refs/remotes/src/$R_BRANCH:refs/heads/$R_DST_BRANCH"; then
        fail "push to dst failed (nothing forced) — git: ${GPUSH_ERR:-?}"; return
      fi
      git -C "$cache" update-ref "refs/remotes/dst/$R_DST_BRANCH" "$S"
      DST_AFTER[$R_NAME]="$S"
    fi
  fi
  SYNCED_OK[$R_NAME]=1   # in --dry-run: "would be synced" — lets the parent's gitlink check simulate the real run
  # PR base moved on dst since the branch was cut? (only meaningful for a PR branch)
  if [ "$R_MODE" = pr ] && [ -n "$R_PR_BASE" ] && [ "$R_DST_BRANCH" != "$R_PR_BASE" ] \
     && git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$R_PR_BASE" >/dev/null 2>&1 \
     && ! git -C "$cache" merge-base --is-ancestor "refs/remotes/dst/$R_PR_BASE" "$TIP"; then
    local behind; behind="$(git -C "$cache" rev-list --count "$TIP..refs/remotes/dst/$R_PR_BASE")"
    if [ "$UPDATE_BRANCH" -eq 1 ]; then
      merge_update "$behind" || return
    else
      log "$R_NAME: base '$R_PR_BASE' has $behind new commit(s) not in $R_DST_BRANCH — the PR is not up to date with its base; rerun with --update-branch to merge the base into the branch"
    fi
  fi
  if [ "$TAGS" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then log "$R_NAME: DRY-RUN: git push $R_DST_URL 'refs/tags/*:refs/tags/*'"
    else
      if ! gpush "$R_DST_URL" "$DST_TOKEN" 'refs/tags/*:refs/tags/*'; then fail "tag push failed (tags are never forced) — git: ${GPUSH_ERR:-?}"; return; fi
    fi
  fi
  ensure_pr || true
}

# ── --reverse: GHES (dst role) -> mirror (src role); the bare cache is the carrier ──
rv_row() {  # rv_row BRANCH → start a summary row for this repo/branch
  ROW_KEY="$R_NAME:$1"; ROWS+=("$ROW_KEY")
  STATUS[$ROW_KEY]=OK; ACTION[$ROW_KEY]=-; DETAIL[$ROW_KEY]=""; PRINFO[$ROW_KEY]="-"
}
rv_fail_all() {  # rv_fail_all BRANCHES MSG — repo-level failure, one FAIL row per branch
  local b; for b in $1; do rv_row "$b"; fail "$2"; done; ROW_KEY=""
}
check_gitlinks_reverse() {  # $1=from sha $2=to sha(may be empty): every new commit's pointers must be in the sub cache
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
        printf '[%s] %s: gitlink %s @ %s -> %s/%s is not in the %s cache (sub-repo branch missing from reverse_branches, or not fetched)\n' \
          "$PROG" "$ROW_KEY" "$path" "$(short "$c")" "$sub" "$(short "$sha")" "$sub" >&2
        bad=1
      fi
    done
  done
  if [ "$bad" -eq 1 ]; then
    [ "$R_GL_CHECK" = strict ] && return 1
    warn "$ROW_KEY: submodule pointer(s) not in the sub-repo cache — pushing anyway (gitlink_check = warn)"
  fi
  return 0
}
process_reverse() {
  resolve "$1"
  local cache="$CACHE_DIR/$R_NAME.git" branches b S D probe_rc MIRROR_HEADS MIRROR_LS dropped n
  branches="$(eff "$R_NAME" reverse_branches)"
  if [ -z "$branches" ]; then   # default: the PR branch, its base, and main (dci / release commits)
    branches="$R_BRANCH"
    for b in "$R_PR_BASE" main; do
      [ -n "$b" ] && ! has_word "$b" "$branches" && branches="$branches $b"
    done
  fi
  if [ "$RESET_TO_BASE" -eq 1 ]; then   # the feature branch is about to be replaced by the base — never sync it by name too
    local kept="" ; for b in $branches; do [ "$b" = "$R_BRANCH" ] || kept="$kept $b"; done; branches="${kept# }"
  fi
  log "== $R_NAME (REVERSE): $R_DST_URL -> $R_SRC_URL [$branches]"
  ensure_cache "$cache"
  if [ "$PUSH_ONLY" -eq 0 ] && ! has_creds "$R_DST_URL" "$DST_TOKEN"; then rv_fail_all "$branches" "$(cred_hint dst "$R_DST_URL")"; return; fi
  if ! has_creds "$R_SRC_URL" "$SRC_TOKEN"; then rv_fail_all "$branches" "$(cred_hint src "$R_SRC_URL")"; return; fi
  # FROM = GHES. Skipped with --push-only: the cache already carries what --pull-only fetched.
  if [ "$PUSH_ONLY" -eq 0 ]; then
    auth_opts "$R_DST_URL" "$DST_TOKEN"; probe_rc=0
    DST_HEADS="$(tmo "$PROBE_TIMEOUT" git "${AUTH_OPTS[@]}" ls-remote --heads "$R_DST_URL" 2>/dev/null | awk '{print $2}')" || probe_rc=$?
    if [ "$probe_rc" -eq 124 ]; then rv_fail_all "$branches" "GHES probe timed out after ${PROBE_TIMEOUT}s — run '--reverse --pull-only' where $R_DST_URL is reachable, then '--reverse --push-only' here"; return
    elif [ "$probe_rc" -ne 0 ]; then rv_fail_all "$branches" "cannot reach GHES (from) — $(auth_hint dst "$R_DST_URL"); or run '--reverse --pull-only' where it is reachable and '--reverse --push-only' here"; return; fi
    for b in $branches; do fetch_dst_ref "$cache" "$R_DST_URL" "$b"; done
  fi
  # TO = mirror: always probed (needed to classify), fetched into refs/remotes/src/<b>
  auth_opts "$R_SRC_URL" "$SRC_TOKEN"; probe_rc=0
  MIRROR_LS="$(tmo "$PROBE_TIMEOUT" git "${AUTH_OPTS[@]}" ls-remote --heads "$R_SRC_URL" 2>/dev/null)" || probe_rc=$?
  MIRROR_HEADS="$(printf '%s\n' "$MIRROR_LS" | awk '{print $2}')"
  if [ "$probe_rc" -eq 124 ]; then rv_fail_all "$branches" "mirror probe timed out after ${PROBE_TIMEOUT}s — is $R_SRC_URL reachable?"; return
  elif [ "$probe_rc" -ne 0 ]; then rv_fail_all "$branches" "cannot reach the mirror (to) — $(auth_hint src "$R_SRC_URL")"; return; fi
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
        fail "GHES branch '$b' is not in the cache — run '--reverse --pull-only' where GHES is reachable first"
      else ACTION[$ROW_KEY]=SKIPPED; DETAIL[$ROW_KEY]="branch '$b' does not exist on GHES"; log "$ROW_KEY: '$b' not on GHES — skipped"; fi
      continue
    fi
    if [ "$PULL_ONLY" -eq 1 ]; then ACTION[$ROW_KEY]=FETCHED; log "$ROW_KEY: fetched GHES $(short "$S"), mirror $(short "$D")"; continue; fi
    local lease=""
    if [ -z "$D" ]; then ACTION[$ROW_KEY]=CREATE
    elif [ "$D" = "$S" ]; then ACTION[$ROW_KEY]=UP-TO-DATE; log "$ROW_KEY: UP-TO-DATE ($(short "$S"))"; continue
    elif git -C "$cache" merge-base --is-ancestor "$D" "$S"; then ACTION[$ROW_KEY]=FAST-FORWARD
    elif git -C "$cache" merge-base --is-ancestor "$S" "$D"; then
      ACTION[$ROW_KEY]=TO-AHEAD
      if [ "$b" = "$R_BRANCH" ]; then
        DETAIL[$ROW_KEY]="mirror is $(git -C "$cache" rev-list --count "$S..$D") commit(s) ahead of GHES — nothing to do (the forward run pushes them)"
      else
        DETAIL[$ROW_KEY]="mirror is $(git -C "$cache" rev-list --count "$S..$D") commit(s) ahead of GHES — NOT pushed by the forward run (it only syncs '$R_BRANCH'); check why the mirror's $b is ahead (GHES $b reset/rewound?)"
      fi
      log "$ROW_KEY: TO-AHEAD — ${DETAIL[$ROW_KEY]}"; continue
    else
      n="$(git -C "$cache" rev-list --count "$S..$D")"
      dropped="$(git -C "$cache" log --format='- %h %s' "$S..$D")"
      if [ "$FORCE_LEASE" -eq 1 ]; then
        ACTION[$ROW_KEY]=FORCED; lease="--force-with-lease=refs/heads/$b:$D"
        log "$ROW_KEY: DIVERGED — --force-with-lease given: the mirror branch will be overwritten with GHES; DROPPING $n mirror-only commit(s):"
        printf '%s\n' "$dropped"
        DETAIL[$ROW_KEY]="overwrote the mirror branch; dropped $n mirror-only commit(s)"
      else
        ACTION[$ROW_KEY]=DIVERGED
        fail "DIVERGED — the mirror [$b] has $n commit(s) GHES lacks AND GHES has commits the mirror lacks. Nothing pushed. Rerun with --force-with-lease to overwrite the mirror branch with GHES (would drop: $(printf '%s' "$dropped" | tr '\n' ';'))"
        continue
      fi
    fi
    log "$ROW_KEY: ${ACTION[$ROW_KEY]} (GHES $(short "$S"), mirror $(short "$D"))"
    if ! check_gitlinks_reverse "$S" "$D"; then
      fail "submodule pointer(s) not in the sub-repo cache — parent NOT pushed (gitlink_check = strict). Add the sub-repo branch to reverse_branches / fetch it first."; continue
    fi
    local pushcmd="git push ${lease:+$lease }$R_SRC_URL refs/remotes/dst/$b:refs/heads/$b"
    if [ "$DRY_RUN" -eq 1 ]; then log "$ROW_KEY: DRY-RUN: $pushcmd"; continue; fi
    log "$ROW_KEY: $pushcmd"
    if [ -n "$lease" ]; then
      gpush "$R_SRC_URL" "$SRC_TOKEN" "refs/remotes/dst/$b:refs/heads/$b" "$lease" || { fail "push to the mirror failed — git: ${GPUSH_ERR:-?}"; continue; }
    else
      gpush "$R_SRC_URL" "$SRC_TOKEN" "refs/remotes/dst/$b:refs/heads/$b" || { fail "push to the mirror failed (nothing forced) — git: ${GPUSH_ERR:-?}"; continue; }
    fi
    git -C "$cache" update-ref "refs/remotes/src/$b" "$S"; DST_AFTER[$ROW_KEY]="$S"
  done
  [ "$RESET_TO_BASE" -eq 1 ] && [ "$PULL_ONLY" -eq 0 ] && reset_to_base
  ROW_KEY=""
}

# --reset-to-base: mirror <branch>  <-  GHES <pr_base>   (after the PR was squash-merged)
reset_to_base() {
  local b="$R_BRANCH" base="$R_PR_BASE" S D n dropped ts backup
  [ -n "$base" ] && [ "$base" != "$b" ] || return 0
  rv_row "$b<=$base"
  S="$(git -C "$cache" rev-parse -q --verify "refs/remotes/dst/$base" 2>/dev/null || true)"
  if [ -z "$S" ]; then fail "GHES '$base' is not in the cache — run '--reverse --pull-only' where GHES is reachable first"; return; fi
  # mirror <branch> may not have been fetched by the loop above (it is when it is in reverse_branches)
  if printf '%s\n' "$MIRROR_HEADS" | grep -qx "refs/heads/$b"; then
    auth_opts "$R_SRC_URL" "$SRC_TOKEN"
    git "${AUTH_OPTS[@]}" -C "$cache" fetch -q --no-tags "$R_SRC_URL" "+refs/heads/$b:refs/remotes/src/$b"
  else git -C "$cache" update-ref -d "refs/remotes/src/$b" 2>/dev/null || true; fi
  D="$(git -C "$cache" rev-parse -q --verify "refs/remotes/src/$b" 2>/dev/null || true)"
  SRC_SHA[$ROW_KEY]="$S"; DST_BEFORE[$ROW_KEY]="$D"; DST_AFTER[$ROW_KEY]="$D"
  local refspec="refs/remotes/dst/$base:refs/heads/$b" lease=""
  if [ -z "$D" ]; then ACTION[$ROW_KEY]=CREATE
  elif [ "$D" = "$S" ]; then ACTION[$ROW_KEY]=UP-TO-DATE; log "$ROW_KEY: mirror $b already at GHES $base $(short "$S")"; return
  elif git -C "$cache" merge-base --is-ancestor "$D" "$S"; then ACTION[$ROW_KEY]=FAST-FORWARD
  else
    ACTION[$ROW_KEY]=RESET; lease="--force-with-lease=refs/heads/$b:$D"
    n="$(git -C "$cache" rev-list --count "$S..$D")"; dropped="$(git -C "$cache" log --format='- %h %s' "$S..$D")"
    log "$ROW_KEY: RESET — mirror $b @ $(short "$D") will be overwritten with GHES $base @ $(short "$S"); $n mirror-only commit(s) leave the branch:"
    printf '%s\n' "$dropped"
    if [ "$NO_BACKUP" -eq 0 ]; then
      # an earlier (interrupted) run may already have saved exactly this tip — reuse it
      local existing_backup
      existing_backup="$(printf '%s\n' "$MIRROR_LS" | awk -v s="$D" -v pre="refs/heads/backup/$b/" 'index($2, pre)==1 && $1==s {print $2; exit}')"
      if [ -n "$existing_backup" ]; then
        backup="$existing_backup"; log "$ROW_KEY: old mirror tip $(short "$D") is already backed up as $backup — reusing it"
      else
        ts="$(date +%Y%m%d-%H%M%S)"; backup="refs/heads/backup/$b/$ts"
        if [ "$DRY_RUN" -eq 1 ]; then log "$ROW_KEY: DRY-RUN: git push $R_SRC_URL $(short "$D"):$backup"
        else
          gpush "$R_SRC_URL" "$SRC_TOKEN" "$D:$backup" \
            || { fail "could not push the backup branch $backup to the mirror — nothing overwritten — git: ${GPUSH_ERR:-?}"; return; }
          log "$ROW_KEY: backed up the old mirror tip to $backup"
        fi
      fi
      DETAIL[$ROW_KEY]="old tip saved as ${backup#refs/heads/}"
    else DETAIL[$ROW_KEY]="no backup (--no-backup)"; fi
  fi
  log "$ROW_KEY: ${ACTION[$ROW_KEY]} (GHES $base $(short "$S"), mirror $b $(short "$D"))"
  local pushcmd="git push ${lease:+$lease }$R_SRC_URL $refspec"
  if [ "$DRY_RUN" -eq 1 ]; then log "$ROW_KEY: DRY-RUN: $pushcmd"; return; fi
  log "$ROW_KEY: $pushcmd"
  if [ -n "$lease" ]; then
    gpush "$R_SRC_URL" "$SRC_TOKEN" "$refspec" "$lease" \
      || { case "$GPUSH_ERR" in *stale*|*lease*) fail "the mirror branch moved between fetch and push (lease) — rerun — git: $GPUSH_ERR";; *) fail "push to the mirror failed — git: ${GPUSH_ERR:-?}";; esac; return; }
  else
    gpush "$R_SRC_URL" "$SRC_TOKEN" "$refspec" \
      || { fail "push to the mirror failed (nothing forced) — git: ${GPUSH_ERR:-?}"; return; }
  fi
  git -C "$cache" update-ref "refs/remotes/src/$b" "$S"; DST_AFTER[$ROW_KEY]="$S"
  log "$ROW_KEY: done. Update your dev checkout: git fetch mirror && git reset --hard mirror/$b   (remote names: setup_remotes.sh)"
}

if [ "$REVERSE" -eq 1 ]; then
  [ "$UPDATE_BRANCH" -eq 1 ] && warn "--update-branch is ignored with --reverse"
  for n in "${TARGETS[@]}"; do process_reverse "$n"; done
else
  for n in "${TARGETS[@]}"; do process "$n"; done
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
printf '\n[%s] SUMMARY%s%s\n' "$PROG" "$( [ "$REVERSE" -eq 1 ] && echo ' (REVERSE: GHES -> mirror)' )" "$( [ "$DRY_RUN" -eq 1 ] && echo ' (DRY-RUN — nothing was pushed or created)' )"
if [ "$REVERSE" -eq 1 ]; then
  printf '%-28s %-13s %-8s %-10s %-9s %-40s %s\n' repo:branch action ghes mirror-bef mirror-aft pr status
else
  printf '%-28s %-13s %-8s %-10s %-9s %-40s %s\n' repo action src dst-before dst-after pr status
fi
for n in "${ROWS[@]}"; do
  printf '%-28s %-13s %-8s %-10s %-9s %-40s %s\n' "$n" "${ACTION[$n]:--}" "$(short "${SRC_SHA[$n]:-}")" \
    "$(short "${DST_BEFORE[$n]:-}")" "$(short "${DST_AFTER[$n]:-}")" "${PRINFO[$n]:--}" \
    "${STATUS[$n]:-SKIPPED}${DETAIL[$n]:+ — ${DETAIL[$n]}}"
done
[ "$ANY_FAIL" -eq 0 ] && exit 0 || exit 1
