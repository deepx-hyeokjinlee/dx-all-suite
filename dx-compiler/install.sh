#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
pushd "$SCRIPT_DIR"

COM_VERSION="1.38.1"        # default
SIM_VERSION="2.14.5"        # default
ARCHIVE_MODE="n"            # default
ARCHIVE_MODE_ARGS=""        # default
FORCE_ARGS=""

# Function to display help message
show_help() {
  echo "Usage: $(basename "$0") --com_version=<version> --sim_version=<version>"
  echo "Example: $0 [--com_version=$COM_VERSION] [--sim_version=$SIM_VERSION]"
  echo "Options:"
  echo "  [--com_version=<version>]         : Specify dx_com version"
  echo "  [--simulator_version=<version>]   : Specify dx_simulator version"
  echo "  [--archive_mode=<y|n>]            : Set archive mode (default: n)"
  echo "  [--force]                         : Force overwrite if the file already exists"
  echo "  [--help]                          : Show this help message"

  if [ "$1" == "error" ]; then
    echo "Error: Invalid or missing arguments."
    exit 1
  fi
  exit 0
}

# parse args
for i in "$@"; do
    case "$1" in
        --com_version=*)
            COM_VERSION="${1#*=}"
            ;;
        --simulator_version=*)
            SIM_VERSION="${1#*=}"
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
            echo "[ERROR] Unknown option: $1"
            exit 1
            ;;
    esac
    shift
done

# usage
if [ -z "$COM_VERSION" ]; then
    echo "Error: --com_version ($COM_VERSION) does not exist."
    show_help "error"
fi

if [ -z "$SIM_VERSION" ]; then
    echo "Error: --sim_version ($SIM_VERSION) does not exist."
    show_help "error"
fi

if [ "$ARCHIVE_MODE" = "y" ]; then
    echo "[SET ON ARCHIVE_MODE]"
    ARCHIVE_MODE_ARGS="--archive_mode=y"
fi


# install dx-com
INSTALL_COM_CMD="$SCRIPT_DIR/scripts/install_module.sh --module_name=dx_com --file_name=dx_com_M1A --version=$COM_VERSION $ARCHIVE_MODE_ARGS $FORCE_ARGS"
echo "Installing dx-com ..."
echo "$INSTALL_COM_CMD"

$INSTALL_COM_CMD
if [ $? -ne 0 ]; then
    echo "Installing dx-com failed!"
    exit 1
fi

# install dx-sim
INSTALL_SIM_CMD="$SCRIPT_DIR/scripts/install_module.sh --module_name=dx_simulator --version=$SIM_VERSION $ARCHIVE_MODE_ARGS $FORCE_ARGS"
echo "Installing dx-sim ..."
echo "$INSTALL_SIM_CMD"

$INSTALL_SIM_CMD
if [ $? -ne 0 ]; then
    echo "Installing dx-sim failed!"
    exit 1
fi

popd
exit 0
