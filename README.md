# DXNN® - DEEPX NPU Software(SDK) 

## Prerequisites

#### Clone main repository

```
$ git clone --recurse-submodules git@gh.deepx.ai:deepx/dxnn-sdk.git
```

#### (Optional) Initializing and updating submodule in an already cloned repository
```
$ git submodule update --init --recursive
```

#### Check submodule status
```
$ git submodule status
```

#### (Optional) Install Docker & Docker compose
```
$ ./install_docker.sh
```

---

## Local Installation

#### Install All Packages (without fw update)
```
$ ./install.sh --all
```

#### Selective Installation of Specific Packages
```
$ ./install.sh --target <package name>
```
- for update dx_fw
    ```
    $ ./install.sh --target dx_fw
    ```
    It is recommended to shut down the system completely and turn off the power entirely before rebooting after firmware update.


---

## Docker

- When using a Docker environment, the NPU driver must be installed on the HOST system.
    ```
    $ ./install.sh --target dx_rt_npu_linux_driver
    ```

#### Build image

```
$ ./docker_build.sh --ubuntu_version=<ubutnu_version>
```

#### Run continer
- **(Optional) The dxrt service must be stopped before creating a Docker container.**
    ```
    sudo systemctl stop dxrt.service
    ```

- creating a Docker container

    ```
    $ ./docker_run.sh --ubuntu_version=<ubutnu_version>
    ```

- exec container
    ```
    $ docker ps 
    $ docker exec -it dxnn-sdk-runtime-<ubutnu_version> bash
    ```

- check installation
    ```
    # dxrt-cli -s

    DXRT v2.6.3
    =======================================================
    * Device 0: M1, Accelator type
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
    dvfs Disabled
    =======================================================
    ```

---

#### Run Sample Application

- dx_app
    - setup assets(pre-copmpiled NPU model and sample input videos)
    ```
    $ cd /deepx/dx_app
    $ ./setup.sh
    ```

    - run dx-app
    ```
    $ cd /deepx/dx_app
    $ ./scripts/run_detector.sh
    ```

    * You can refer to /deepx/dx_app/README.md for more details.

###### setup assets(pre-copmpiled NPU model and sample input videos)

- dx_stream
    - setup assets(pre-copmpiled NPU model and sample input videos)
    ```
    $ cd /deepx/dx_stream
    $ ./setup.sh
    ```

    - run dx-app
    ```
    $ cd /deepx/dx_stream
    $ ./run_demo.sh
    ```

    * You can refer to /deepx/dx_stream/README.md for more details.
 
