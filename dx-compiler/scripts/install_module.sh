#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
COMPILER_PATH=$(realpath -s "${SCRIPT_DIR}/..")
DX_AS_PATH=$(realpath -s "${COMPILER_PATH}/..")

VERSION=""      # default
MODULE_NAME=""
ARCHIVE_MODE=""
FORCE_ARGS=""

# Function to display help message
show_help() {
  echo "Usage: $(basename "$0") --module_name=<module name> [--file_name=dx_com_M1A] --version=<version> "
  echo "Example: $0 --module_name=dx_com --file_name=dx_com_M1A --version=1.38.1"
  echo "Options:"
  echo "  --module_name=<module name>  : Specify module (dx_com | dx_simulator)"
  echo "  [--file_name=<file_name>]    : Specify file name (ex> dx_com_M1A, skip if it matches the module name)"
  echo "  --version=<version>          : Specify version"
  echo "  [--force]                    : Force overwrite if the file already exists"
  echo "  [--help]                     : Show this help message"

  if [ "$1" == "error" ]; then
    echo "Error: Invalid or missing arguments."
    exit 1
  fi
  exit 0
}

# parse args
for i in "$@"; do
    case "$1" in
        --module_name=*)
            MODULE_NAME="${1#*=}"
            ;;
        --file_name=*)
            FILE_NAME="${1#*=}"
            ;;
        --version=*)
            VERSION="${1#*=}"
            ;;
        --archive_mode=*)
            ARCHIVE_MODE="${1#*=}"
            ;;
        --force)
            FORCE_ARGS="--force"
            ;;
        --help)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

# usage
if [ -z "$VERSION" ]; then
    echo "Error: --version ($VERSION) does not exist."
    show_help "error"
fi

if [ -z "$MODULE_NAME" ]; then
    echo "Error: --module_name ($MODULE_NAME) does not exist."
    show_help "error"
fi

if [ -z "$FILE_NAME" ]; then
    FILE_NAME="$MODULE_NAME"        # default
fi

BASE_URL="https://sdk.deepx.ai/"

# default value
SOURCE_PATH="release/${MODULE_NAME}/${FILE_NAME}_v${VERSION}.tar.gz"
OUTPUT_DIR="${COMPILER_PATH}/${MODULE_NAME}"
EXTRACT_ARGS="--extract"
if [ "$ARCHIVE_MODE" = "y" ]; then
    OUTPUT_DIR="${DX_AS_PATH}/archives"
    EXTRACT_ARGS=""
fi

SYMLINK_TARGET_PATH="${DX_AS_PATH}/workspace/release/${MODULE_NAME}"
SYMLINK_ARGS="--symlink_target_path=$SYMLINK_TARGET_PATH"

GET_RES_CMD="${DX_AS_PATH}/scripts/get_resource.sh --src_path=$SOURCE_PATH --output=$OUTPUT_DIR $EXTRACT_ARGS $SYMLINK_ARGS $FORCE_ARGS"
echo "Get Resources from remote server ..."
echo "$GET_RES_CMD"

$GET_RES_CMD
if [ $? -ne 0 ]; then
    echo "Get resource failed!"
    exit 1
fi

exit 0
