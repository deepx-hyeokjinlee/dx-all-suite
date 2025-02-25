#!/bin/bash
SCRIPT_DIR=$(realpath "$(dirname "$0")")

function help()
{
    echo "./install.sh"
    echo "    --help     show this help"
    echo "    --all      install all dxnn library (without firmware)"
    echo "    --target   install target dxnn package [ dx_fw, dx_rt_npu_linux_driver, dx_rt, dx_app, dx_stream ]"
}

function install_dx_rt_npu_linux_driver()
{
    sudo apt update && sudo apt-get -y install pciutils kmod build-essential make linux-headers-6.11.0-17-generic
    cd $SCRIPT_DIR/dx-runtime/dx_rt_npu_linux_driver/modules
    sudo ./build.sh -c uninstall
    ./build.sh
    sudo ./build.sh -c install
    sudo modprobe dx_dma
    lsmod | grep dx
}

function install_dx_rt()
{
    cd $SCRIPT_DIR/dx-runtime/dx_rt
    sudo ./install.sh --dep
    sudo ./build.sh --clean
    dxrt-cli -s
}

function install_dx_app()
{
    cd $SCRIPT_DIR/dx-runtime/dx_app
    sudo ./install.sh --all
    sudo ./build.sh --clean
}

function install_dx_stream()
{
    cd $SCRIPT_DIR/dx-runtime/dx_stream
    sudo ./install.sh
    sudo ./build.sh --install
    gst-inspect-1.0 dxstream
}

function install_dx_fw()
{
    if [ ! -f "$SCRIPT_DIR/dx-runtime/dx_fw/m1a/latest/mdot2/fw.bin" ]; then
        echo "Error: firmware file not found!"
        exit 1
    fi
    if ! command -v dxrt-cli &> /dev/null; then
        echo "Error: 'dxrt-cli' not found!"
        exit 1
    fi
    dxrt-cli -g $SCRIPT_DIR/dx-runtime/dx_fw/m1a/latest/mdot2/fw.bin
    dxrt-cli -u $SCRIPT_DIR/dx-runtime/dx_fw/m1a/latest/mdot2/fw.bin -u reset
    echo "It is recommended to power off completely and reboot after the firmware update."
}

target_package=all

case "$1" in
    --help)  help; exit 0;;
    --all) target_package=all;;
    --target)
        target_package="${2,,}"
        ;;
    *)
    echo "Error: Invalid option '$1'"
    help
    exit 1
    ;;
esac

echo "PATH : $SCRIPT_DIR"
echo "Start Installation Target Package : $target_package"

case $target_package in
    dx_rt_npu_linux_driver)
        install_dx_rt_npu_linux_driver
        ;;
    dx_rt)
        install_dx_rt
        ;;
    dx_app)
        install_dx_app
        ;;
    dx_stream)
        install_dx_stream
        ;;
    dx_fw)
        install_dx_fw
        ;;
    all)
        install_dx_rt_npu_linux_driver
        install_dx_rt
        install_dx_app
        install_dx_stream
        ;;
    *)
        echo "Error: Invalid target package '$target_package'"
        exit 1
        ;;
esac
