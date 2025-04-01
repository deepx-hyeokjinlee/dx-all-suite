# DXNN® - DEEPX NPU Software (SDK)

## Prerequisites

### Clone the Main Repository

```
$ git clone --recurse-submodules git@gh.deepx.ai:deepx/dxnn-sdk.git
```

### (Optional) Initialize and Update Submodules in an Already Cloned Repository

```
$ git submodule update --init --recursive
```

### Check Submodule Status

```
$ git submodule status
```

### (Optional) Install Docker & Docker Compose

```
$ ./scripts/install_docker.sh
```

---

# Local Installation

## Install DX-Compiler Environment (dx_com, dx_simulator)

The `DX-Compiler` environment provides prebuilt binary outputs and does not include source code. Each module can be downloaded and installed from a remote server using the following command:

```
$ ./dx-compiler/install.sh
```

When executing the above command:

1. The `dx-com` and `dx-simulator` modules will be downloaded to  
   `../docker_volume/release/dx_com/download/dx_com_M1A_v[VERSION].tar.gz` and  
   `../docker_volume/release/dx_simulator/download/dx_simulator_v[VERSION].tar.gz`, respectively.

2. The downloaded modules will be extracted to  
   `../docker_volume/release/dx_com/dx_com_M1A_v[VERSION]` and  
   `../docker_volume/release/dx_simulator/dx_simulator_v[VERSION]`.  
   Symbolic links will also be created at `./dx-compiler/dx-com` and `./dx-simulator`.

3. If the modules are already installed, running `./dx-compiler/install.sh` again will reuse the existing installations.  
   To force a reinstallation, use the `--force` option:

   ```
   $ ./dx-compiler/install.sh --force
   ```

### Install a Specific Version

To install a specific version, modify the environment variables in `install.sh`:

```
COM_VERSION="1.38.1"        # default
SIM_VERSION="2.14.5"        # default
```

Alternatively, specify the version directly when executing the command:

```
$ ./install.sh --com_version=<version> --sim_version=<version>
```

---

## Install DX-Runtime Environment (`dx_rt_npu_linux_driver`, `dx_rt`, `dx_app`, and `dx_stream`)

The `DX-Runtime` environment includes source code for each module. The repositories are managed as Git submodules under `./dx-runtime`.  
To build and install all modules, run:

```
$ ./dx-runtime/install.sh --all
```

This command will build and install the following modules:  
`dx_rt_npu_linux_driver`, `dx_rt`, `dx_app`, and `dx_stream` (excluding `dx_fw` firmware updates).

### Selective Installation of a Specific Module

You can install a specific module using:

```
$ ./dx-runtime/install.sh --target=<module_name>
```

### Update `dx_fw` (Firmware Image)

The `dx_fw` module does not include source code but provides a `fw.bin` image file.  
To update the firmware using `dxrt-cli`, run:

```
$ dxrt-cli -u ./dx-runtime/dx_fw/m1a/X.X.X/mdot2/fw.bin -u reset
```

Alternatively, you can use:

```
$ ./dx-runtime/install.sh --target=dx_fw
```

**It is recommended to completely shut down and power off the system before rebooting after a firmware update.**

---

# Installation Using Docker

## Install DX-Runtime and DX-Compiler Environment

### Notes

1. When using a Docker environment, the NPU driver must be installed on the host system:

   ```
   $ ./install.sh --target=dx_rt_npu_linux_driver
   ```

2. If `dx_rt` is already installed on the host system and the `service daemon` (`/usr/local/bin/dxrtd`) is running, launching the `DX-Runtime` Docker container will result in an error (`Other instance of dxrtd is running`) and automatic termination.  
   Before starting the container, stop the service daemon on the host system.

3. If another container is already running with the `service daemon` (`/usr/local/bin/dxrtd`), starting a new container will also result in the same error.  
   To run multiple DX-Runtime containers simultaneously, refer to note #4.

4. If you prefer to use the `service daemon` running on the host system instead of inside the container, modify `./docker/Dockerfile` as follows:

   ```
   # ENTRYPOINT [ "/usr/local/bin/dxrtd" ]
   ENTRYPOINT ["tail", "-f", "/dev/null"]
   ```

### Build the Docker Image

```
$ ./docker_build.sh --all --ubuntu_version=24.04
```

This command builds a Docker image with both `dx-compiler` and `dx-runtime` environments.  
You can check the built images using:

```
$ docker images
```

```
REPOSITORY               TAG       IMAGE ID       CREATED          SIZE
dxnn-sdk-compiler        22.04     9b7e6577c526   6 minutes ago    6.56GB
dxnn-sdk-runtime         22.04     1c96c081fdea   16 hours ago     4.02GB
```

#### Selective Docker Image Build for a Specific Environment

```
$ ./docker_build.sh --target=dx-runtime --ubuntu_version=24.04
```

```
$ ./docker_build.sh --target=dx-compiler --ubuntu_version=24.04
```

Use the `--target=<environment_name>` option to build only `dx-runtime` or `dx-compiler`.

### Run the Docker Container

**(Optional) Stop the `dxrt` service daemon before starting a Docker container.**  
(Refer to note #4 for more details.)

```
sudo systemctl stop dxrt.service
```

#### Run a Docker Container with All Environments (`dx_compiler` and `dx_runtime`)

```
$ ./docker_run.sh --all --ubuntu_version=<ubuntu_version>
```

To verify running containers:

```
$ docker ps
```

```
CONTAINER ID   IMAGE                     COMMAND                  CREATED          STATUS          PORTS     NAMES
47837ae2aa4a   dxnn-sdk-runtime:24.04    "/usr/local/bin/dxrt…"   26 minutes ago   Up 26 minutes             dxnn-sdk-runtime-24.04
6c2b63d248d6   dxnn-sdk-compiler:24.04   "tail -f /dev/null s…"   26 minutes ago   Up 26 minutes             dxnn-sdk-compiler-24.04
```

#### Enter the Container

```
$ docker exec -it dxnn-sdk-runtime-<ubuntu_version> bash
```

```
$ docker exec -it dxnn-sdk-container-<ubuntu_version> bash
```

This allows you to enter the `dx-compiler` and `dx-runtime` environments via a bash shell.

#### Check DX-Runtime Installation Inside the Container

```
# dxrt-cli -s
```

Example output:

```
DXRT v2.6.3
=======================================================
* Device 0: M1, Accelerator type
---------------------   Version   ---------------------
* RT Driver version   : v1.3.1
* PCIe Driver version : v1.2.0
-------------------------------------------------------
* FW version          : v1.6.0
--------------------- Device Info ---------------------
* Memory : LPDDR5 5800 MHz, 3.92GiB
* Board  : M.2, Rev 10.0
* PCIe   : Gen3 X4 [02:00:00]

NPU 0: voltage 750 mV, clock 1000 MHz, temperature 29'C
NPU 1: voltage 750 mV, clock 1000 MHz, temperature 28'C
NPU 2: voltage 750 mV, clock 1000 MHz, temperature 28'C
DVFS Disabled
=======================================================
```

---

# Run Sample Application

## dx_app

### Installation Path

1. **On the Host Environment:**
    ```
    $ cd ./dx-runtime/dx_app
    ```
2. **Inside the Docker Container:**
    ```
    $ docker exec -it dxnn-sdk-runtime-<ubuntu_version> bash
    # cd /deepx/dx_app
    ```

### Setup Assets (Precompiled NPU Model and Sample Input Videos)

```
$ ./setup.sh
```

### Run `dx_app`

```
$ ./scripts/run_detector.sh
$ fim ./result-app1.jpg
```

**For more details, refer to `dx_app/README.md`.**

---

## dx_stream

### Installation Path

1. **On the Host Environment:**
    ```
    $ cd ./dx-compiler/dx_stream
    ```
2. **Inside the Docker Container:**
    ```
    $ docker exec -it dxnn-sdk-runtime-<ubuntu_version> bash
    # cd /deepx/dx_stream
    ```

### Setup Assets (Precompiled NPU Model and Sample Input Videos)

```
$ ./setup.sh
```

### Run `dx_stream`

```
$ ./run_demo.sh
```

**For more details, refer to `dx_stream/README.md`.**

---

# Run DX-Compiler

## dx_com

### Installation Path

1. **On the Host Environment:**
    ```
    $ cd ./dx-compiler/dx_com
    ```
2. **Inside the Docker Container:**
    ```
    $ docker exec -it dxnn-sdk-compiler-<ubuntu_version> bash
    # cd /deepx/dx_com
    ```

### Run `dx_com` using Sample onnx input

```
$ make
dx_com/dx_com \
        -m sample/MobileNetV1-1.onnx \
        -c sample/MobileNetV1-1.json \
        -o sample/MobileNetV1-1 
Compiling Model : 100%|███████████████████████████████| 1.0/1.0 [00:06<00:00,  7.00s/model ]

dx_com/dx_com \
        -m sample/ResNet50-1.onnx \
        -c sample/ResNet50-1.json \
        -o sample/ResNet50-1 
Compiling Model : 100%|███████████████████████████████| 1.0/1.0 [00:19<00:00, 19.17s/model ]

dx_com/dx_com \
        -m sample/YOLOV5-1.onnx \
        -c sample/YOLOV5-1.json \
        -o sample/YOLOV5-1 
Compiling Model : 100%|███████████████████████████████| 1.0/1.0 [00:47<00:00, 47.66s/model ]
```

**For more details, refer to `dx_com/README.md`.**

---

## dx_simulator

### Installation Path

1. **On the Host Environment:**
    ```
    $ cd ./dx-compiler/dx_simulator
    ```
2. **Inside the Docker Container:**
    ```
    $ docker exec -it dxnn-sdk-compiler-<ubuntu_version> bash
    (venv-dx-compiler) # cd /deepx/dx_simulator
    ```

### Install Prerequisites

1. **On the Host Environment:**
    ```
    # install prerequisites
    ./scripts/install_prerequisites.sh              ### TODO: error on ubuntu 24.04 (add condition for ubuntu_version)

    # install python
    ./scripts/install_python.sh                     ### TODO: error(install wget, c-compiler) on docker (replace source build to apt install)

    # install dx_simulator
    pip install dx_simulator-xxx-cp38-cp38-linux_x86_64.whl --force-reinstall
    ```

    **temporary**
    ```
    $ \
    echo "Setup dx_simulator..." && \
    echo "Install dependencies..." && \
    UBUNTU_VERSION=$(lsb_release -rs) && \
    echo "*** UBUNTU_VERSION(${UBUNTU_VERSION}) ***" && \
    if [ "$UBUNTU_VERSION" = "24.04" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
              libgl1-mesa-dev libglib2.0-0; \
    elif [ "$UBUNTU_VERSION" = "22.04" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
              libgl1-mesa-dev libglib2.0-0; \
    elif [ "$UBUNTU_VERSION" = "20.04" ] || [ "$UBUNTU_VERSION" = "18.04" ]; then \
      apt-get update && apt-get install -y --no-install-recommends \
              libgl1-mesa-dev libgl1-mesa-glx libglib2.0-0; \
    else \
      echo "Unspported Ubuntu version: $UBUNTU_VERSION" && exit 1; \
    fi && \
    apt-get update && apt-get install -y --no-install-recommends \
        libssl-dev \
        wget \
        openssl \
        build-essential \
        zlib1g-dev \
        patchelf \
        libffi-dev \
        ca-certificates \
        libbz2-dev \
        liblzma-dev \
        libncursesw5-dev \
        libsqlite3-dev \
        tk-dev \
        libgdbm-dev \
        libc6-dev \
        libncurses5-dev \
        libnss3-dev \
        ccache
        
    $ \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get install -y python3.11 python3.11-dev python3.11-venv

    $ python3.11 -m venv /venv-dx-compiler --system-site-packages
    
    $ source /venv-dx-compiler/bin/activate
    (venv-dx-compiler) $ pip install /deepx/dx_simulator/dx_simulator-*-cp311-cp311-linux_x86_64.whl --force-reinstall
    (venv-dx-compiler) $ pip install ultralytics
    ```

2. **Inside the Docker Container:**
    ```
    $ docker exec -it dxnn-sdk-compiler-<ubuntu_version> bash
    (venv-dx-compiler) # cd /deepx/dx_simulator
    (venv-dx-compiler) # pip install /deepx/dx_simulator/dx_simulator-*-cp311-cp311-linux_x86_64.whl --force-reinstall
    (venv-dx-compiler) # pip install ultralytics
    ```

### Run `dx_simulator` using Sample dxnn input
```
(venv-dx-simulator) $ python examples/example_yolov5s.py
(venv-dx-simulator) $ fim examples/yolov5s.jpg
```

**For more details, refer to `dx_simulator/README.md`.**

