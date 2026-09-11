#!/usr/bin/env bash
# setup_remotes.sh — apply the remote naming convention to a dev checkout of the suite and
# its four harness sub-repos, from the same sync.conf ghes-sync.sh uses:
#
#   ghes     dst_host/<repo>.git      gh.deepx.ai/deepx/*        (closed-network SCM)
#   mirror   src_host/<repo>.git      github.com/deepx-dhyang/*  (private mirror)
#   ghcloud  ghcloud_host/<repo>.git  github.com/DEEPX-AI/*      (public channel, read-only)
#
# Usage: setup_remotes.sh [--config FILE] [--suite-dir DIR] [--rename-origin] [--dry-run] [--help]
#   --suite-dir DIR   the suite checkout (default: the dir containing internal/tools/ghes-sync)
#   --rename-origin   when a repo's `origin` URL equals one of the three, rename it instead
#                     of keeping a duplicate (a foreign origin is left alone)
#   --dry-run         print what would change, change nothing
# Repos and their checkout paths come from sync.conf ([repo NAME] path = ...). Idempotent:
# an existing remote with the right URL is reported as ok, a wrong URL is fixed (set-url).
# Exit codes: 0 ok · 1 a git command failed · 2 usage/config error
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="$HERE/sync.conf"; SUITE_DIR="$(cd "$HERE/../../.." && pwd -P)"; RENAME=0; DRY=0
usage() { sed -n '2,/^set -euo pipefail/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }
die2() { printf '[setup-remotes] ERROR: %s\n' "$*" >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || die2 "--config needs a value"; CONFIG="$2"; shift 2 ;;
    --suite-dir) [ $# -ge 2 ] || die2 "--suite-dir needs a value"; SUITE_DIR="$(cd "$2" && pwd -P)"; shift 2 ;;
    --rename-origin) RENAME=1; shift ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die2 "unknown argument '$1'" ;;
  esac
done
[ -f "$CONFIG" ] || die2 "config not found: $CONFIG"
CFG_OUT="$(bash "$HERE/ghes-sync.sh" --config "$CONFIG" --print-config)" || die2 "ghes-sync.sh --print-config failed"
RC=0
ensure_remote() {  # ensure_remote DIR NAME URL
  local dir="$1" name="$2" url="$3" cur
  cur="$(git -C "$dir" config --get "remote.$name.url" 2>/dev/null || true)"
  if [ "$cur" = "$url" ]; then printf '  %-8s ok       %s\n' "$name" "$url"; return; fi
  if [ -n "$cur" ]; then
    printf '  %-8s set-url  %s  (was %s)%s\n' "$name" "$url" "$cur" "$( [ "$DRY" -eq 1 ] && echo '  [DRY-RUN]')"
    [ "$DRY" -eq 1 ] || git -C "$dir" remote set-url "$name" "$url" || RC=1
  else
    printf '  %-8s added    %s%s\n' "$name" "$url" "$( [ "$DRY" -eq 1 ] && echo '  [DRY-RUN]')"
    [ "$DRY" -eq 1 ] || git -C "$dir" remote add "$name" "$url" || RC=1
  fi
}
name=""; declare -A V=()
flush() {
  [ -n "$name" ] || return 0
  local rel="${V[path]:-}" dir origin_url
  if [ -z "$rel" ]; then printf '[setup-remotes] %s: no `path` in sync.conf — skipped\n' "$name"; name=""; V=(); return 0; fi
  dir="$SUITE_DIR/$rel"
  if [ ! -d "$dir/.git" ] && [ ! -f "$dir/.git" ]; then printf '[setup-remotes] %s: %s is not a git checkout — skipped\n' "$name" "$dir"; name=""; V=(); return 0; fi
  printf '[setup-remotes] %s (%s)\n' "$name" "$dir"
  origin_url="$(git -C "$dir" config --get remote.origin.url 2>/dev/null || true)"
  if [ -n "$origin_url" ]; then
    local target=""
    [ "$origin_url" = "${V[src_url]}" ] && target=mirror
    [ "$origin_url" = "${V[dst_url]}" ] && target=ghes
    [ "$origin_url" = "${V[ghcloud_url]}" ] && target=ghcloud
    if [ -n "$target" ]; then
      if [ "$RENAME" -eq 1 ]; then
        if git -C "$dir" config --get "remote.$target.url" >/dev/null 2>&1; then
          printf '  origin   removed  (same URL as existing %s)%s\n' "$target" "$( [ "$DRY" -eq 1 ] && echo '  [DRY-RUN]')"
          [ "$DRY" -eq 1 ] || git -C "$dir" remote remove origin || RC=1
        else
          printf '  origin   renamed  -> %s%s\n' "$target" "$( [ "$DRY" -eq 1 ] && echo '  [DRY-RUN]')"
          [ "$DRY" -eq 1 ] || git -C "$dir" remote rename origin "$target" || RC=1
        fi
      else
        printf '  origin   kept     %s == %s (use --rename-origin to rename it)\n' "$origin_url" "$target"
      fi
    else
      printf '  origin   kept     %s (foreign URL, left alone)\n' "$origin_url"
    fi
  fi
  ensure_remote "$dir" ghes    "${V[dst_url]}"
  ensure_remote "$dir" mirror  "${V[src_url]}"
  ensure_remote "$dir" ghcloud "${V[ghcloud_url]}"
  name=""; V=()
}
while IFS= read -r line; do
  case "$line" in
    \[*\]) flush; name="${line#[}"; name="${name%]}" ;;
    "  "*" = "*) k="${line#  }"; k="${k%% = *}"; v="${line#*= }"; V[$k]="$v" ;;
  esac
done <<< "$CFG_OUT"
flush
[ "$DRY" -eq 1 ] && echo "[setup-remotes] DRY-RUN — nothing was changed"
exit $RC
