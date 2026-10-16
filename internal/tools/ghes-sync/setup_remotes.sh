#!/usr/bin/env bash
# setup_remotes.sh — apply the remote naming convention to a dev checkout of the suite and
# its four harness sub-repos, from the same sync.conf ghes-sync.sh uses:
#
#   ghes     dst_host/<repo>.git      gh.deepx.ai/deepx/*              (closed-network SCM)
#   mirror   src_host/<repo>.git      github.com/{DEEPX-MIRROR-ORG}/*  (your private mirror)
#   ghcloud  ghcloud_url              github.com/DEEPX-AI/*            (ONLY for repos that set it)
#
# The public channel is normally the release export, not a dev remote. The exception is a repo
# whose usable content exists ONLY there — dx_fw: the source lives on GHES, but the fw.bin that
# gets consumed is published on the public channel and never reaches GHES. Such a repo is marked
# `sync = off` in sync.conf (ghes-sync never touches it) and carries `ghcloud_url` instead; here it
# gets the `ghcloud` remote and the parent's submodule policy:
#   submodule.<name>.url    = ghcloud_url   (the mirror org has no counterpart repo)
#   submodule.<name>.update = none          (its gitlink is a GHES commit the public history lacks,
#                                            so `submodule update --init` must not die on it)
#   submodule.<name>.ignore = all           (the checked-out content differs from the gitlink by design)
# .gitmodules itself is never edited — it belongs to the GHES repo; these are local config overrides.
#
# Usage: setup_remotes.sh [--config FILE] [--suite-dir DIR] [--rename-origin] [--checkout-ghcloud]
#                         [--dry-run] [--help]
#   --suite-dir DIR   the suite checkout (default: the dir containing internal/tools/ghes-sync)
#   --rename-origin   when a repo's `origin` URL equals one of the two, rename it instead
#                     of keeping a duplicate (a foreign origin is left alone)
#   --checkout-ghcloud  also fetch ghcloud and check out ghcloud/<ghcloud_ref> in those repos
#                     (off by default: the tool otherwise never touches a worktree)
#   --dry-run         print what would change, change nothing
# Repos and their checkout paths come from sync.conf ([repo NAME] path = ...). Idempotent:
# an existing remote with the right URL is reported as ok, a wrong URL is fixed (set-url).
# Exit codes: 0 ok · 1 a git command failed · 2 usage/config error
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CONFIG="$HERE/sync.conf"; SUITE_DIR="$(cd "$HERE/../../.." && pwd -P)"; RENAME=0; DRY=0; CHECKOUT=0
usage() { sed -n '2,/^set -euo pipefail/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }
die2() { printf '[setup-remotes] ERROR: %s\n' "$*" >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || die2 "--config needs a value"; CONFIG="$2"; shift 2 ;;
    --suite-dir) [ $# -ge 2 ] || die2 "--suite-dir needs a value"; SUITE_DIR="$(cd "$2" && pwd -P)"; shift 2 ;;
    --rename-origin) RENAME=1; shift ;;
    --checkout-ghcloud) CHECKOUT=1; shift ;;
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
ensure_submodule_policy() {  # ensure_submodule_policy SUBDIR NAME URL — local overrides in the PARENT checkout
  local dir="$1" sub="$2" url="$3" parent cur k v
  parent="$(dirname "$dir")"
  if [ ! -d "$parent/.git" ] && [ ! -f "$parent/.git" ]; then
    printf '  %-8s skipped  %s is not a git checkout — submodule policy not applied\n' "submodule" "$parent"
    return
  fi
  # The policy is keyed by submodule NAME in the parent's config, so it is a silent no-op
  # unless the parent really registers that submodule at this path. Check before writing.
  local want registered
  want="$(basename "$dir")"
  registered="$(git -C "$parent" config -f .gitmodules --get "submodule.$sub.path" 2>/dev/null || true)"
  if [ "$registered" != "$want" ]; then
    printf '  %-8s skipped  %s does not register submodule.%s at %s (.gitmodules says %s) — not registered, policy not applied\n' \
      "submodule" "$parent" "$sub" "$want" "${registered:-<nothing>}"
    return
  fi
  for k in url update ignore; do
    case "$k" in url) v="$url" ;; update) v=none ;; ignore) v=all ;; esac
    cur="$(git -C "$parent" config --get "submodule.$sub.$k" 2>/dev/null || true)"
    if [ "$cur" = "$v" ]; then printf '  %-8s ok       submodule.%s.%s = %s\n' "parent" "$sub" "$k" "$v"; continue; fi
    printf '  %-8s set      submodule.%s.%s = %s%s\n' "parent" "$sub" "$k" "$v" "$( [ "$DRY" -eq 1 ] && echo '  [DRY-RUN]')"
    [ "$DRY" -eq 1 ] || git -C "$parent" config "submodule.$sub.$k" "$v" || RC=1
  done
}
checkout_ghcloud() {  # checkout_ghcloud DIR REF — opt-in; otherwise just print the command
  local dir="$1" ref="$2"
  if [ "$CHECKOUT" -eq 0 ] || [ "$DRY" -eq 1 ]; then
    printf '  %-8s manual   git -C %s fetch ghcloud && git -C %s checkout -B ghcloud-%s ghcloud/%s   (--checkout-ghcloud does it)\n' \
      "ghcloud" "$dir" "$dir" "$ref" "$ref"
    return
  fi
  printf '  %-8s fetch    ghcloud/%s -> ghcloud-%s\n' "ghcloud" "$ref" "$ref"
  git -C "$dir" fetch -q ghcloud || { RC=1; return; }
  git -C "$dir" checkout -q -B "ghcloud-$ref" "ghcloud/$ref" || RC=1
}
name=""; declare -A V=()
flush() {
  [ -n "$name" ] || return 0
  local rel="${V[path]:-}" dir origin_url
  if [ -z "$rel" ]; then printf '[setup-remotes] %s: no `path` in sync.conf — skipped\n' "$name"; name=""; V=(); return 0; fi
  dir="$SUITE_DIR/$rel"
  if [ ! -d "$dir/.git" ] && [ ! -f "$dir/.git" ]; then
    # A ghcloud repo is NOT cloned by `submodule update --init` (update = none), so after a fresh
    # clone of the parent there is nothing here yet — create it instead of silently skipping.
    if [ -n "${V[ghcloud_url]:-}" ]; then
      printf '[setup-remotes] %s (%s)\n' "$name" "$dir"
      if [ "$CHECKOUT" -eq 1 ] && [ "$DRY" -eq 0 ]; then
        printf '  %-8s clone    %s\n' "ghcloud" "${V[ghcloud_url]}"
        if git clone -q --origin ghcloud -b "${V[ghcloud_ref]:-main}" "${V[ghcloud_url]}" "$dir"; then
          # clone -b already checked the ref out; rename that branch instead of creating a
          # second one at the same commit, so the result matches the existing-checkout path.
          git -C "$dir" branch -M "ghcloud-${V[ghcloud_ref]:-main}" || RC=1
          ensure_submodule_policy "$dir" "$name" "${V[ghcloud_url]}"
        else RC=1; fi
      else
        printf '  %-8s manual   git clone --origin ghcloud -b %s %s %s   (--checkout-ghcloud does it)%s\n' \
          "ghcloud" "${V[ghcloud_ref]:-main}" "${V[ghcloud_url]}" "$dir" "$( [ "$DRY" -eq 1 ] && echo '  [DRY-RUN]')"
      fi
      name=""; V=(); return 0
    fi
    printf '[setup-remotes] %s: %s is not a git checkout — skipped\n' "$name" "$dir"; name=""; V=(); return 0
  fi
  printf '[setup-remotes] %s (%s)\n' "$name" "$dir"
  origin_url="$(git -C "$dir" config --get remote.origin.url 2>/dev/null || true)"
  if [ -n "$origin_url" ]; then
    local target=""
    [ "$origin_url" = "${V[src_url]}" ] && target=mirror
    [ "$origin_url" = "${V[dst_url]}" ] && target=ghes
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
  if [ -n "${V[ghcloud_url]:-}" ]; then
    ensure_remote "$dir" ghcloud "${V[ghcloud_url]}"
    ensure_submodule_policy "$dir" "$name" "${V[ghcloud_url]}"
    checkout_ghcloud "$dir" "${V[ghcloud_ref]:-main}"
  fi
  if [ "${V[sync]:-on}" = off ]; then
    printf '  %-8s skipped  sync = off (no mirror/GHES counterpart)\n' "ghes/mirror"
  else
    ensure_remote "$dir" ghes    "${V[dst_url]}"
    ensure_remote "$dir" mirror  "${V[src_url]}"
  fi
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
