#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export DX_BENCHMARK_ROOT="$SCRIPT_DIR"
cd "$SCRIPT_DIR"

PORT=8097
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --port|-p) PORT="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

python3 server.py --port "$PORT"
