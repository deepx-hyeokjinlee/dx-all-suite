#!/bin/bash

SCRIPT_DIR=$(realpath "$(dirname "$0")")
OUTPUT_DIR="$SCRIPT_DIR/archives"
UBUNTU_VERSION=""

pushd "$SCRIPT_DIR"

# Function to display help message
show_help() {

  echo "Usage: $(basename "$0") --ubuntu_version=<version>"
  echo "Example: $0 --ubuntu_version=20.04"
  echo "Options:"
  echo "  --ubuntu_version <version>     : Specify Ubuntu version (default: 20.04)"
  echo "  [--help]                       : Show this help message"

  if [ "$1" == "error" ]; then
    echo "Error: Invalid or missing arguments."
    exit 1
  fi
  exit 0
}


# parse args
for i in "$@"; do
    case "$1" in
        --ubuntu_version=*)
            UBUNTU_VERSION="${1#*=}"
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
if [ -z "$UBUNTU_VERSION" ]; then
    echo "Error: --ubuntu_version ($UBUNTU_VERSION) does not exist."
    show_help "error"
else
    export UBUNTU_VERSION=${UBUNTU_VERSION}
    echo "UBUNTU_VERSSION($UBUNTU_VERSION) is set."
fi


# Run Docker Container
CMD="docker compose -f docker/docker-compose.yml up -d"
echo "${CMD}"

${CMD}

popd
