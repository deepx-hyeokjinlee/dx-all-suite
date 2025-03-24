#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
pushd "$SCRIPT_DIR"

OUTPUT_DIR="$SCRIPT_DIR/archives"
UBUNTU_VERSION=""

# Function to display help message
show_help() {
    echo "Usage: $(basename "$0") OPTIONS(--all | target=<environment_name>) --ubuntu_version=<version> [--help]"
    echo "Example:1) $0 --all --ubuntu_version=24.04"
    echo "Example 2) $0 --target=dx-runtime --ubuntu_version=24.04"
    echo "Options:"
    echo "  --all                          : install DXNN® Software Stack (dx-compiler & dx-runtime)"
    echo "  --target=<environment_name>    : install specify target DXNN® environment (ex> dx-compiler | dx-runtime)"
    echo "  --ubuntu_version=<version>     : Specify Ubuntu version (default: 20.04)"
      echo "  [--help]                       : Show this help message"

    if [ "$1" == "error" ]; then
        echo "Error: Invalid or missing arguments."
        exit 1
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
            echo "Error: Invalid option '$1'"
            show_help
            exit 1
            ;;
    esac
    shift
done

# usage
if [ -z "$UBUNTU_VERSION" ]; then
    echo "Error: --ubuntu_version ($UBUNTU_VERSION) does not exist."
    show_help "error"
else
    echo "UBUNTU_VERSSION($UBUNTU_VERSION) is set."
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
        echo "[ERROR] Unknown DXNN® environment name: $1"
        exit 1
        ;;
esac

popd
