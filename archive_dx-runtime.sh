#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
DX_ALL_DIR=$(realpath -s "${SCRIPT_DIR}")

pushd $SCRIPT_DIR

# color env settings
source ${DX_ALL_DIR}/scripts/color_env.sh

main() {
    # git archive
    echo -e "=== Archiving dx-runtime ... ${TAG_START} ==="

    OUTPUT_DIR="$SCRIPT_DIR/archives"
    mkdir -p "$OUTPUT_DIR"
    EXCLUDED_DIRS=("dx_fw" "dx_rt_npu_linux_driver" "workspace")

    find "$SCRIPT_DIR/dx-runtime" -mindepth 1 -maxdepth 1 -type d | while read -r subdir; do
        dir_name=$(basename "$subdir")

        if [[ " ${EXCLUDED_DIRS[@]} " =~ " ${dir_name} " ]]; then
            echo -e "${TAG_INFO} Skipping excluded directory: $dir_name"
            continue
        fi

        if [ -f "$subdir/.git" ] || [ -d "$subdir/.git" ]; then
            archive_file="$OUTPUT_DIR/${dir_name}.tar.gz"
            echo -e "${TAG_INFO} Archiving repository: $dir_name"
            (cd "$subdir" && git archive --format=tar.gz --output="$archive_file" $(git symbolic-ref --short HEAD || git rev-parse HEAD))
            if [[ $? -eq 0 ]]; then
                echo -e "${TAG_SUCC} Archive created successfully: $archive_file"
            else
                echo -e "${TAG_WARN} Failed to create archive for: $dir_name"
            fi
        else
            echo -e "${TAG_ERROR} No .git directory found in: $dir_name"
        fi
    done

    echo -e "=== Archiving dx-runtime ... ${TAG_DONE} ==="
}


popd

exit 0

