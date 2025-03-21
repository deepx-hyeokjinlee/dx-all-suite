#!/bin/bash

# git archive
./archive_dx-runtime.sh

SCRIPT_DIR=$(realpath "$(dirname "$0")")
OUTPUT_DIR="$SCRIPT_DIR/archives"

# build docker image
cd "$SCRIPT_DIR"
docker compose -f docker/docker-compose.yml build

# remove archives
if [[ -d "$OUTPUT_DIR" ]]; then
    echo "Removing archive directory: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi

