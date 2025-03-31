#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
pushd "$SCRIPT_DIR"

OUTPUT_DIR="$SCRIPT_DIR/archives"
UBUNTU_VERSION=""

FILE_DXCOM=archives/dx_com_M1A_v1.38.1.tar.gz
FILE_DXSIM=archives/dx_simulator_v2.14.5.tar.gz

# Function to display help message
show_help() {
    echo "Usage: $(basename "$0") OPTIONS(--all | target=<environment_name>) --ubuntu_version=<version> [--help]"
    echo "Example:1) $0 --all --ubuntu_version=24.04"
    echo "Example 2) $0 --target=dx-compiler --ubuntu_version=24.04"
    echo "Example 2) $0 --target=dx-runtime --ubuntu_version=24.04 --driver_update"
    echo "Options:"
    echo "  --all                          : Install DXNN® Software Stack (dx-compiler & dx-runtime)"
    echo "  --target=<environment_name>    : Install specify target DXNN® environment (ex> dx-compiler | dx-runtime)"
    echo "  --ubuntu_version=<version>     : Specify Ubuntu version (ex> 24.04)"
    echo "  [--driver_update]              : Install 'dx_rt_npu_linux_driver' in the host environment"
    echo "  [--help]                       : Show this help message"

    if [ "$1" == "error" ]; then
        echo "Error: Invalid or missing arguments."
        exit 1
    fi
    exit 0
}

docker_build_all() 
{
    # Build Docker image
    export COMPOSE_BAKE=true
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    export FILE_DXCOM=${FILE_DXCOM}
    export FILE_DXSIM=${FILE_DXSIM}
    CMD="docker compose -f ./docker/docker-compose.yml build"
    echo "${CMD}"

    ${CMD}
}

docker_build_dx-compiler() 
{
    # Build Docker image
    export COMPOSE_BAKE=true
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    export FILE_DXCOM=${FILE_DXCOM}
    export FILE_DXSIM=${FILE_DXSIM}
    CMD="docker compose -f ./docker/docker-compose.yml build dxnn-sdk-compiler"
    echo "${CMD}"

    ${CMD}
}

docker_build_dx-runtime() 
{
    # Build Docker image
    export COMPOSE_BAKE=true
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    CMD="docker compose -f ./docker/docker-compose.yml build dxnn-sdk-runtime"
    echo "${CMD}"

    ${CMD}
}

install_dx_rt_npu_linux_driver() 
{
    CMD="./dx-runtime/install.sh --target=dx_rt_npu_linux_driver"
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
        --driver_update)
            DRIVER_UPDATE=y
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
    echo "TARGET_ENV($TARGET_ENV) is set."
    echo "FILE_DXCOM($FILE_DXCOM) is set."
    echo "FILE_DXSIM($FILE_DXSIM) is set."
    if [ "$DRIVER_UPDATE" = "y" ]; then
        echo "DRIVER_UPDATE($DRIVER_UPDATE) is set."
    fi
fi

case $TARGET_ENV in
    dx-compiler)
        echo "Installing dx-compiler"
        ./archive_dx-compiler.sh
        docker_build_dx-compiler
        ;;
    dx-runtime)
        echo "Installing dx-runtime"
        ./archive_dx-runtime.sh
        docker_build_dx-runtime
        if [ "$DRIVER_UPDATE" = "y" ]; then
            install_dx_rt_npu_linux_driver
        fi
        ;;
    all)
        echo "Installing all DXNN® environments"
        ./archive_dx-compiler.sh
        ./archive_dx-runtime.sh
        docker_build_all
        if [ "$DRIVER_UPDATE" = "y" ]; then
            install_dx_rt_npu_linux_driver
        fi
        ;;
    *)
        echo "[ERROR] Unknown DXNN® environment name: $1"
        exit 1
        ;;
esac

# remove archives
# if [[ -d "$OUTPUT_DIR" ]]; then
#     echo "Removing archive directory: $OUTPUT_DIR"
#     rm -rf "$OUTPUT_DIR"
# fi

popd
