#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
DX_ALL_DIR=$(realpath -s "${SCRIPT_DIR}")

# color env settings
source ${DX_ALL_DIR}/scripts/color_env.sh

pushd "$SCRIPT_DIR"

OUTPUT_DIR="$SCRIPT_DIR/archives"
UBUNTU_VERSION=""

# Function to display help message
show_help() {
    echo "Usage: $(basename "$0") OPTIONS(--all | target=<environment_name>) --ubuntu_version=<version> [--help]"
    echo "Example:1) $0 --all --ubuntu_version=24.04"
    echo "Example 2) $0 --target=dx-compiler --ubuntu_version=24.04"
    echo "Example 3) $0 --target=dx-runtime --ubuntu_version=24.04"
    echo "Options:"
    echo "  --all                          : Install DXNN® Software Stack (dx-compiler & dx-runtime)"
    echo "  --target=<environment_name>    : Install specify target DXNN® environment (ex> dx-compiler | dx-runtime)"
    echo "  --ubuntu_version=<version>     : Specify Ubuntu version (ex> 24.04)"
    echo "  [--help]                       : Show this help message"

    if [ "$1" == "error" ] && [[ ! -n "$2" ]]; then
        echo -e "${TAG_ERROR} Invalid or missing arguments."
        exit 1
    elif [ "$1" == "error" ] && [[ -n "$2" ]]; then
        echo -e "${TAG_ERROR} $2"
        exit 1
    elif [[ "$1" == "warn" ]] && [[ -n "$2" ]]; then
        echo -e "${TAG_WARN} $2"
        return 0
    fi
    exit 0
}

docker_run_all() 
{
    # Run Docker Container
    export COMPOSE_BAKE=true
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    CMD="docker compose -f docker/docker-compose.yml up -d --remove-orphans"
    echo "${CMD}"

    ${CMD}
}

docker_run_dx-compiler() 
{
    # Run Docker Container
    export COMPOSE_BAKE=true
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    CMD="docker compose -f docker/docker-compose.yml up -d --remove-orphans dxnn-sdk-compiler"
    echo "${CMD}"

    ${CMD}
}

docker_run_dx-runtime() 
{
    # Run Docker Container
    export COMPOSE_BAKE=true
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    CMD="docker compose -f docker/docker-compose.yml up -d --remove-orphans dxnn-sdk-runtime"
    echo "${CMD}"

    ${CMD}
}

main() {
    # usage
    if [ -z "$UBUNTU_VERSION" ]; then
        show_help "error" "--ubuntu_version ($UBUNTU_VERSION) does not exist."
    else
        echo -e "${TAG_INFO} UBUNTU_VERSSION($UBUNTU_VERSION) is set."
        echo -e "${TAG_INFO} TARGET_ENV($TARGET_ENV) is set."
    fi

    case $TARGET_ENV in
        dx-compiler)
            echo "Installing dx-compiler"
            docker_run_dx-compiler
            ;;
        dx-runtime)
            echo "Installing dx-runtime"
            docker_run_dx-runtime
            ;;
        all)
            echo "Installing all DXNN® environments"
            docker_run_all
            ;;
        *)
            echo -e "${TAG_ERROR} Unknown '--target' option '$TARGET_ENV'"
            show_help "error" "${TAG_INFO} (Hint) Please specify either the '--all' option or the '--target=<dx-compiler | dx-runtime>' option."
            ;;
    esac
}

# parse args
for i in "$@"; do
    case "$1" in
        --all)
            TARGET_ENV=all
            ;;
        --target=*)
            TARGET_ENV="${1#*=}"
            ;;
        --ubuntu_version=*)
            UBUNTU_VERSION="${1#*=}"
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${TAG_ERROR}: Invalid option '$1'"
            show_help
            exit 1
            ;;
    esac
    shift
done

main

popd

exit 0
