#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")
pushd $SCRIPT_DIR

# install dx-com
INSTALL_COMPILER_CMD="$SCRIPT_DIR/dx-compiler/install.sh --archive_mode=y"
echo "Installing DX-Compiler ..."
echo "$INSTALL_COMPILER_CMD"

$INSTALL_COMPILER_CMD
if [ $? -ne 0 ]; then
    echo "Installing DX-Compiler failed!"
    exit 1
fi

popd
exit 0
