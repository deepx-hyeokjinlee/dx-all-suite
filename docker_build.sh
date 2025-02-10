#!/bin/bash

SCRIPT_DIR=$(realpath "$(dirname "$0")")

# git archive
OUTPUT_DIR="$SCRIPT_DIR/archives"
mkdir -p "$OUTPUT_DIR"
EXCLUDED_DIRS=("dx_fw" "dx_rt_npu_linux_driver")

find "$SCRIPT_DIR/dx-runtime" -mindepth 1 -maxdepth 1 -type d | while read -r subdir; do
    dir_name=$(basename "$subdir")

    if [[ " ${EXCLUDED_DIRS[@]} " =~ " ${dir_name} " ]]; then
        echo "Skipping excluded directory: $dir_name"
        continue
    fi

    if [[ -d "$subdir/.github" ]]; then
        archive_file="$OUTPUT_DIR/${dir_name}.tar.gz"
        echo "Archiving repository: $dir_name"
        (cd "$subdir" && git archive --format=tar.gz --output="$archive_file" main)
        if [[ $? -eq 0 ]]; then
            echo "Archive created successfully: $archive_file"
        else
            echo "Failed to create archive for: $dir_name"
        fi
    else
        echo "No .git directory found in: $dir_name"
    fi
done

# build docker image
cd "$SCRIPT_DIR"
docker compose -f docker/docker-compose.yml build

# remove archives
if [[ -d "$OUTPUT_DIR" ]]; then
    echo "Removing archive directory: $OUTPUT_DIR"
    rm -rf "$OUTPUT_DIR"
fi
