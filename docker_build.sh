#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
DX_ALL_DIR=$(realpath -s "${SCRIPT_DIR}")

# color env settings
source ${DX_ALL_DIR}/scripts/color_env.sh

pushd "$SCRIPT_DIR"

OUTPUT_DIR="$SCRIPT_DIR/archives"
UBUNTU_VERSION=""

DXCOM_VER="1.38.1"
# DXSIM_VER=2.14.5
DXSIM_VER="2.14.5_hotfix-1"         # temporary

FILE_DXCOM="archives/dx_com_M1A_v${DXCOM_VER}.tar.gz"
FILE_DXSIM="archives/dx_simulator_v${DXSIM_VER}.tar.gz"

# Function to display help message
show_help() {
    echo "Usage: $(basename "$0") OPTIONS(--all | target=<environment_name>) --ubuntu_version=<version> [--help]"
    echo "Example:1) $0 --all --ubuntu_version=24.04"
    echo "Example 2) $0 --target=dx-compiler --ubuntu_version=24.04"
    echo "Example 3) $0 --target=dx-runtime --ubuntu_version=24.04 --driver_update"
    echo "Options:"
    echo "  --all                          : Install DXNN® Software Stack (dx-compiler & dx-runtime)"
    echo "  --target=<environment_name>    : Install specify target DXNN® environment (ex> dx-compiler | dx-runtime)"
    echo "  --ubuntu_version=<version>     : Specify Ubuntu version (ex> 24.04)"
    echo "  [--driver_update]              : Install 'dx_rt_npu_linux_driver' in the host environment"
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

main() {
    

    # usage
    if [ -z "$UBUNTU_VERSION" ]; then
        show_help "error" "--ubuntu_version ($UBUNTU_VERSION) does not exist."
    else
        echo -e "${TAG_INFO} UBUNTU_VERSSION($UBUNTU_VERSION) is set."
        echo -e "${TAG_INFO} TARGET_ENV($TARGET_ENV) is set."
        echo -e "${TAG_INFO} FILE_DXCOM($FILE_DXCOM) is set."
        echo -e "${TAG_INFO} FILE_DXSIM($FILE_DXSIM) is set."
        if [ "$DRIVER_UPDATE" = "y" ]; then
            echo -e "${TAG_INFO} DRIVER_UPDATE($DRIVER_UPDATE) is set."
        fi
    fi

    case $TARGET_ENV in
        dx-compiler)
            echo "Archiving dx-compiler"
            ./archive_dx-compiler.sh
            docker_build_dx-compiler
            ;;
        dx-runtime)
            echo "Archiving dx-runtime"
            ./archive_dx-runtime.sh
            docker_build_dx-runtime
            if [ "$DRIVER_UPDATE" = "y" ]; then
                install_dx_rt_npu_linux_driver
            fi
            ;;
        all)
            echo "Archiving all DXNN® environments"
            ./archive_dx-compiler.sh
            ./archive_dx-runtime.sh
            docker_build_all
            if [ "$DRIVER_UPDATE" = "y" ]; then
                install_dx_rt_npu_linux_driver
            fi
            ;;
        *)
            echo -e "${TAG_ERROR} Unknown '--target' option '$TARGET_ENV'"
            show_help "error" "${TAG_INFO} (Hint) Please specify either the '--all' option or the '--target=<dx-compiler | dx-runtime>' option."
            ;;
    esac

    # remove archives
    # if [[ -d "$OUTPUT_DIR" ]]; then
    #     echo "Removing archive directory: $OUTPUT_DIR"
    #     rm -rf "$OUTPUT_DIR"
    # fi
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
            ;;
        *)
            show_help "error" "Invalid option '$1'"
            ;;
    esac
    shift
done

main

popd

exit 0
