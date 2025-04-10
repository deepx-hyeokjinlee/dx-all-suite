#!/bin/sh
SCRIPT_DIR=$(cd "$(dirname "$0")"; pwd)
DX_AS_PATH=$(cd "${SCRIPT_DIR}/../"; pwd)
WORKSPACE_PATH="${DX_AS_PATH}/workspace"

printf "SCRIPT_DIR(%b)\n" "${SCRIPT_DIR}"
printf "DX_AS_PATH(%b)\n" "${DX_AS_PATH}"
printf "WORKSPACE_PATH(%b)\n" "${WORKSPACE_PATH}"

# color env settings
. "${DX_AS_PATH}/scripts/color_env.sh"

OLD_DIR=$(pwd)
cd "${SCRIPT_DIR}"

main() {
    find "${SCRIPT_DIR}"/* -depth ! -name "runtime-*.sh" -delete
    if [ $? -ne 0 ]; then
        printf "%b Failed to remove 'getting-start' artifacts\n" "${TAG_ERROR}"
        exit 1
    fi

    printf "=== remove 'getting-start' artifacts %b ===\n" "${TAG_DONE}"
}

main

cd "${OLD_DIR}"

exit 0
