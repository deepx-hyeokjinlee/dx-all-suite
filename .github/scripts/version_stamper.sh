#!/bin/bash
# .github/scripts/version_stamper.sh
# Read the DX-AllSuite version from release.ver and stamp the version-compatibility
# matrix (EN + KOR) from the recursively-checked-out submodule tree.
# Idempotent: writes only when a value actually changed, so it is safe to run on
# every dispatch (nothing changed -> no-op).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || (cd "$SCRIPT_DIR/../.." && pwd))"
DATE="$(date +%F)"

norm() { printf 'v%s' "$(tr -d ' \r\nv' < "$1")"; }   # -> vX.Y.Z

SUITE="$(norm "$ROOT/release.ver")"                    # suite = root release.ver (own source of truth)
RUNTIME="$(norm "$ROOT/dx-runtime/release.ver")"
COMPILER="$(norm "$ROOT/dx-compiler/release.ver")"
MODELZOO="$(norm "$ROOT/dx-modelzoo/release.ver")"

# release.ver is the suite's own version -> NOT overwritten here (bump it elsewhere / by hand)

python3 "$SCRIPT_DIR/compat_table.py" \
  --date "$DATE" \
  --suite "$SUITE" \
  --compiler "$COMPILER" \
  --runtime "$RUNTIME" \
  --modelzoo "$MODELZOO" \
  --dxcom "$COMPILER" \
  --dxfw "$(norm "$ROOT/dx-runtime/dx_fw/release.ver")" \
  --driver "$(norm "$ROOT/dx-runtime/dx_rt_npu_linux_driver/release.ver")" \
  --dxrt "$(norm "$ROOT/dx-runtime/dx_rt/release.ver")" \
  --dxstream "$(norm "$ROOT/dx-runtime/dx_stream/release.ver")" \
  --dxapp "$(norm "$ROOT/dx-runtime/dx_app/release.ver")" \
  "$ROOT/docs/source/04_Version_Compatibility.md" \
  "$ROOT/docs/source/04_Version_Compatibility_kor.md"

echo "version_stamper: done (suite=$SUITE runtime=$RUNTIME modelzoo=$MODELZOO)"
