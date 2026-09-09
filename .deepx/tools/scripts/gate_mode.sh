#!/usr/bin/env bash
#
# gate_mode.sh — decide how the suite harness gate (dx-agent-dev-gate-{ghes,cloud}.yml,
# job `harness-gate`) checks out the four harness sub-repos:
#
#   branch-tip  (default) tip of the same-name branch in each sub-repo, default branch
#               if that branch does not exist — validates the state that exists once
#               the in-flight PRs are merged, so pointer lag never turns the gate red
#   pointer     the commits recorded by the suite commit under test (integration truth)
#
# pointer is selected automatically when the pushed / PR'd range changed a submodule
# gitlink (e.g. update-submodule.yml's `ci(<date>): Update dx-runtime` commit, or a
# manual pointer-bump PR), and explicitly via workflow_dispatch (--input-mode).
#
# Usage:
#   gate_mode.sh --event <push|pull_request|workflow_dispatch|...>
#                [--from SHA] [--to SHA]      # range to inspect (push: event.before..sha,
#                                             #   pull_request: base.sha..merge sha). The
#                                             #   caller must have fetched --from already.
#                [--input-mode MODE]          # workflow_dispatch input (branch-tip|pointer)
#                [--repo DIR]                 # git repo to inspect (default: $PWD)
#                [--help]
#
# Output (stdout, one per line):  mode=<branch-tip|pointer>   reason=<why>
# Exit: 0 decided · 2 usage error
set -uo pipefail

EVENT="" FROM="" TO="HEAD" INPUT_MODE="" REPO="$PWD"
usage() { sed -n '2,/^set -uo pipefail/p' "${BASH_SOURCE[0]}" | sed '$d' | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
    case "$1" in
        --event)      EVENT="${2:-}"; shift 2 ;;
        --from)       FROM="${2:-}"; shift 2 ;;
        --to)         TO="${2:-HEAD}"; shift 2 ;;
        --input-mode) INPUT_MODE="${2:-}"; shift 2 ;;
        --repo)       REPO="${2:-}"; shift 2 ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "Usage error: unknown argument '$1'" >&2; usage >&2; exit 2 ;;
    esac
done
[ -n "$EVENT" ] || { echo "Usage error: --event is required" >&2; exit 2; }

emit() { echo "mode=$1"; echo "reason=$2"; exit 0; }

if [ "$EVENT" = "workflow_dispatch" ]; then
    m="${INPUT_MODE:-branch-tip}"
    case "$m" in
        branch-tip|pointer) emit "$m" "workflow_dispatch input mode=$m" ;;
        *) echo "Usage error: --input-mode must be branch-tip or pointer, got '$m'" >&2; exit 2 ;;
    esac
fi

ZERO="0000000000000000000000000000000000000000"
if [ -z "$FROM" ] || [ "$FROM" = "$ZERO" ]; then
    emit branch-tip "no base commit for $EVENT (new branch or first push) — default"
fi
if ! git -C "$REPO" cat-file -e "${FROM}^{commit}" 2>/dev/null; then
    emit branch-tip "base $FROM not available locally (fetch failed or history rewritten) — default"
fi
# gitlinks (mode 160000) in the tree under test = the submodule pointer paths
mapfile -t GITLINKS < <(git -C "$REPO" ls-files -s | awk '$1=="160000"{print $4}')
if [ "${#GITLINKS[@]}" -eq 0 ]; then
    emit branch-tip "no submodule gitlinks in $REPO — default"
fi
changed="$(git -C "$REPO" diff --name-only "$FROM" "$TO" -- "${GITLINKS[@]}" 2>/dev/null | tr '\n' ' ' | sed 's/ *$//')"
if [ -n "$changed" ]; then
    emit pointer "submodule pointer changed in this $EVENT range ${FROM:0:7}..${TO:0:7}: $changed"
fi
emit branch-tip "no submodule pointer change in this $EVENT range ${FROM:0:7}..${TO:0:7}"
