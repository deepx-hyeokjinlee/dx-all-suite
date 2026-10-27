## DX-AllSuite v2.5.0 / 2026-10-23

- DX-Compiler: v2.5.0
    - DX-COM: v2.5.0
    - DX-TRON: Removed
- DX-Runtime: v2.5.0
    - DX_FW: v2.7.6
    - NPU Driver: v2.7.0
    - DX-RT: v3.5.0
    - DX-STREAM: v3.2.0
    - DX-APP: v3.3.0
- DX-ModelZoo: v1.0.0

---

**DX-AllSuite v2.5.0** 릴리즈 노트입니다.

### What's New?
이번 릴리즈는 DEEPX SDK의 설치와 배포 방식에 초점을 맞췄습니다. 사전 빌드된 컨테이너 이미지를 GHCR에 배포하며, DX-Compiler와 DX-Runtime을 `curl | sh` 명령 한 줄 또는 DEEPX apt 저장소로 설치할 수 있고, DX-M1 NPU를 Kubernetes에서 스케줄링할 수 있습니다. Model Zoo 2_5_0 모델은 V9 `.dxnn` container format을 사용하므로 DX-RT v3.5.0과 함께 NPU Driver v2.7.0, DX_FW v2.7.6이 필요하며, 모든 컴포넌트를 함께 업그레이드해야 합니다. 또한 이번 릴리즈부터 Ubuntu 18.04와 DX-TRON 지원을 종료했습니다.

> **Important notice before upgrading**
>
> - **Ubuntu 18.04 지원 종료**: 설치 스크립트, Docker 빌드, DX-Runtime, DX-APP에서 Ubuntu 18.04 지원을 종료했습니다; 호스트를 Ubuntu 20.04 이상으로 업그레이드해야 합니다 (DX-Runtime은 Debian 12 / 13도 지원)
> - **DX-TRON 제거**: DX-Compiler에서 `dx_tron` 설치 타깃, `dxtron` CLI/AppImage, 웹 서버 버전, `run_dxtron_web.sh` / `run_dxtron_appimage.sh`를 포함한 DX-TRON을 제거했습니다; DX-COM Compilation Summary Report(`--export_html`)를 사용하고, `--target=dx_com`으로 설치하며, 남아 있는 DEB 패키지는 `sudo apt-get remove dxtron`으로 제거해야 합니다
> - **지원 환경**: NPU 드라이버와 펌웨어는 NPU가 장착된 bare-metal 호스트에서 지원하며, PCI passthrough를 사용하는 가상 머신은 지원하지 않으므로 DX-Runtime은 물리 호스트에 설치해야 합니다. DX-Compiler와 DX-ModelZoo는 NPU가 필요 없으므로 VM이나 컨테이너에서도 실행할 수 있습니다

#### New: Simplified Installation & Deployment
**Highlights**
- **GHCR 사전 빌드 컨테이너 이미지** — `ghcr.io/deepx-ai/dx-runtime` (`rt`, `rt-app`, `rt-stream`, `rt-app-stream`, `latest`; `linux/amd64`, `linux/arm64`), `ghcr.io/deepx-ai/dx-compiler` (`latest`; `linux/amd64`), `ghcr.io/deepx-ai/dx-modelzoo` (`latest`; `linux/amd64`)를 각각 고정 버전 태그와 함께 배포하여, `docker_build.sh`를 실행하는 대신 이미지를 pull할 수 있게 했습니다; 레지스트리 경로에는 소문자 `deepx-ai`를 사용해야 합니다 (`docker/README.md` 참고)
- **원라인 설치와 DEEPX apt 저장소** — 레포지토리를 clone하지 않고 설치할 수 있도록 DX-Compiler와 DX-Runtime에 `oneline-install.sh`를 추가했으며, `DX_VERSION`(DX-Compiler) 또는 `DX_RT_VERSION` / `DX_DRIVER_VERSION` / `DX_FW_VERSION`(DX-Runtime)으로 버전을 고정하고 `oneline-uninstall.sh`로 제거할 수 있습니다; DX-Runtime 원라인 설치는 NPU 드라이버, DX-RT, 펌웨어를 포함하며, DX-APP과 DX-STREAM은 기존 설치 가이드를 사용합니다
    ```bash
    # DX-Compiler (x86_64 Host PC)
    curl -fsSL https://raw.githubusercontent.com/DEEPX-AI/dx-compiler/main/oneline-install.sh | sh

    # DX-Runtime (target device: NPU driver + DX-RT + firmware)
    curl -fsSL https://raw.githubusercontent.com/DEEPX-AI/dx-runtime/main/oneline-install.sh | sh
    ```
    NPU 드라이버(`dxrt-driver-dkms`)와 DX-RT(`libdxrt-bin`)를 설치할 수 있는 DEEPX apt 저장소를 추가했습니다:
    ```bash
    wget -O - https://apt.releases.deepx.ai/gpg | sudo gpg --dearmor -o /usr/share/keyrings/deepx-archive-keyring.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/deepx-archive-keyring.gpg] https://apt.releases.deepx.ai $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") main" | sudo tee /etc/apt/sources.list.d/deepx.list

    sudo apt update
    sudo apt install dxrt-driver-dkms
    sudo apt install libdxrt-bin
    ```
- **DX-M1 Kubernetes 지원** — `dx-npu` Helm chart와 `dx-k8s-device-plugin` 서브모듈을 추가했습니다; `deepx.ai/dx-m1`을 스케줄링 가능한 리소스로 등록하고(`deepx.ai/dx-m1: 1`로 요청), CDI로 `/dev/dxrtN`과 호스트 라이브러리를 주입하며, node-feature-discovery로 NPU 노드에 라벨을 붙입니다; `helm install dx-npu oci://ghcr.io/deepx-ai/charts/dx-npu -n dx-system --create-namespace --set nfd.enabled=true`로 설치합니다 (`docs/source/06_Kubernetes_Quickstart.md`, `deploy/k8s/README.md` 참고)

#### **Additional Improvements**
- **DX-COM 연산자 지원 확대** — 3D `Conv` / `ConvTranspose`(5D 입력), (batched) 행렬 곱으로 환원되는 2-입력 `Einsum` 수식, 2-D `Gather` 인덱스의 NPU 지원을 추가했습니다; `qmaster` 설정의 `task_type` 블록으로 segmentation QAT를 추가했습니다
- **DX-RT 처리량 튜닝과 latency 가시성** — I/O 버퍼 수를 자동 튜닝하는 `dxrun --max-throughput`과 C++, C, Python용 E2E Response Time(`GetE2EResponseTime()`) 및 Core Latency(`GetCoreLatency*`) API를 추가했습니다
- **DX-APP의 DX Model Zoo 모델 147종** — RT-DETR, YOLOv12, YOLOv13, anomaly detection, image matting, CLIP retrieval을 포함한 147개 모델을 등록하고, `--check`, `--list-models`, `--report` 옵션을 지원하는 `multi_model_graph_sync` / `multi_model_graph_async` 러너를 추가했습니다
- **DX-STREAM의 DX-H1 V-NPU 가속** — `dxvnpudec`, `dxvnpuenc`, `dxinfer`를 통한 하드웨어 가속 디코딩, 인코딩, 변환, 전처리, 추론을 추가했습니다 (`./build.sh --dxvnpu`)

#### Breaking Changes & Deprecations
- **DX-COM**: `pre_optimize` pass 이름을 `yolo_postprocess` → `yolo_dfl_postprocess`, `yolo26_postprocess` → `yolo_no_dfl_postprocess`로 변경했습니다; YOLO pass는 이제 `task`(`base` / `seg` / `pose`)가 필수이며 `input_height` / `input_width`를 지정하면 `ValueError`가 발생하므로 기존 설정을 수정해야 합니다
- **DX-COM**: Python QAT 인자 `quantization_mode`, `qat_config`, `qat_skip_training`, `qat_resume_from_checkpoint`를 `QMasterConfig`를 받는 단일 `qmaster` 인자로 대체했습니다; `dx_com.compile()`이 keyword 인자를 받도록 변경했습니다; `quantization_device`는 폐기되어 `UserWarning`과 함께 무시되므로 제거하고, `--use_gpu` / `use_gpu`와 `CUDA_VISIBLE_DEVICES`로 디바이스를 선택해야 합니다
- **DX-ModelZoo**: compile YAML 키 `compile.quantization`을 `compile.calibration`으로 변경하고 공개 CLI 옵션 `--use-gpu`를 제거했습니다; 사용자 정의 compile YAML 파일을 수정해야 합니다
- **DX-RT**: 최소 요구 버전을 Linux Driver 2.7.0, Linux PCIe Driver 2.7.0, Windows PCIe Driver 2.0.1, Firmware 2.7.6으로 상향했습니다; DX-RT와 함께 NPU Driver와 DX_FW도 업그레이드해야 합니다
- **DX-RT**: `GetLatency*`가 E2E Response Time을 반환하도록 재정의했습니다; buffer pool 및 queue 대기 시간을 제외한 latency를 측정하려면 `GetCoreLatency*` (C++), `dxrt_engine_get_core_latency*` (C), `get_core_latency*` (Python)로 전환해야 합니다
- **DX-RT**: `dx_engine`의 major.minor 버전이 `libdxrt.so`와 다르면 `import dx_engine`이 `RuntimeError`를 발생시키는 버전 체크를 추가했습니다; `DX_ENGINE_SKIP_VERSION_CHECK=1`로 우회할 수 있습니다
- **DX-RT**: C++/CLI `csharp_package`를 제거했습니다; `examples/csharp/README.md`를 참고하여 P/Invoke로 C API를 호출해야 합니다
- **DX-APP**: 태스크 디렉터리, 실행 파일, 빌드 타깃, Python 스크립트 이름을 변경하고(예: `yolov9s_sync` → `yolov9-s_640x640_sync`), `add_model.sh`가 첫 번째 인자로 variant(`.dxnn` stem)를 받도록 변경했습니다; 이전 이름이나 인자를 사용하는 스크립트를 수정해야 합니다
- **DX-STREAM**: SCRFD500M PPU와 YOLOv5Pose PPU 데모를 제거하고 V3 DSP / RGA 커널을 선택형 백엔드 플러그인으로 분리했습니다; 제거된 데모를 호출하는 스크립트를 수정하고, V3 DSP 가속을 유지하려면 `./build.sh --dxv3`로 빌드해야 합니다

### Key Updates
**Performance & Efficiency**
- **DX_FW**: NPU 파워 게이팅으로 절전 모드를 강화했습니다
- **DX-RT**: NEON/SSE4.1 커널 기반 SIMD float32 → int8 입력 양자화를 추가하여 DMA 쓰기 시간을 줄였습니다
- **NPU Driver**: 드라이버 probe 시 EP PCIe 디바이스 태스크 주기를 변경했습니다
- **DX-RT**: `dxcli` 버전 출력을 `version (build: hash)` 형식으로 변경하고, `dxtop`에 DDR 타입을 추가했으며, 대기 중 실패한 Windows 드라이버 요청을 오류로 보고하고, Windows `dxrtd` named pipe가 원격 클라이언트를 거부하도록 제한했습니다
- **DX-APP**: `scripts/extract_model_package.sh`가 추출 대상 모델이 의존하는 `common/` 파일만 복사하도록 변경했습니다 (`--no-prune`으로 전체 복사 유지); model-zoo manifest를 `2_5_0` URL 계층으로 이전했습니다
- **DX-STREAM / DX-APP**: DX-STREAM 샘플 모델을 DX-COM v2.5.0 빌드로 갱신했습니다; EfficientNet-Lite0 샘플을 256x256에서 224x224로 전환했습니다
- **DX-ModelZoo**: PPU 및 pre-optimized 모델 설정 구조를 재편했습니다; DXNN 다운로드 경로를 최신 버전 기준으로 표준화했습니다; compile profile 파라미터를 `dx_com.compile()`에 전달하도록 했습니다

**Stability & Fixes**
- **DX_FW**: LPDDR5X clear 로직과 mailbox ACK starvation을 수정했습니다; HW op-timeout을 NPU hang으로 보고하도록 하고, HW 타임아웃(2s)을 SW 타임아웃(3s)보다 짧게 설정했습니다
- **NPU Driver**: 사용자 버퍼 unmap 시 발생하던 지연 급증을 수정했습니다
- **DX-RT**: 빈 PPU 출력에서의 segfault, `ServiceDevice` 종료 시 deadlock과 heap 손상, `dxrtd` NPU 메모리 누수와 Windows 서비스 크래시, Windows에서의 `find_package(dxrt)` 실패를 수정했습니다; 추론이 한 번도 성공하지 않으면 `dxrun`이 오류로 종료하도록 수정했습니다
- **DX-STREAM**: OC-SORT의 관측 이력, association/GIoU 처리, momentum 가중치, tracker 설정 복구를 수정했습니다
- **DX-APP**: Python 및 C++ 예제와 결과가 다르던 `dx_postprocess`(`ClassificationPostProcess`, `VitPosePostProcess`, DAMO-YOLO 및 NanoDet NMS, CenterPose)를 수정했습니다; Python postprocessor가 `score_threshold`를 무시하던 문제를 수정했습니다; async 러너에서 공유 postprocessor를 동시에 호출하던 문제를 수정했습니다
- **DX-Compiler**: `--python_version`을 지정하지 않으면 `install.sh`가 OS 기본 `python3`를 사용하도록 수정했습니다; `uninstall.sh`가 남아 있는 `dx_tron/` 디렉터리를 제거하도록 수정했습니다
- **DX-ModelZoo**: 데이터셋 구조, 파일, 라벨 검증을 강화했습니다; YAML 메타데이터와 compile 설정의 일관성을 개선했습니다
- **DX-Runtime(installer)**: `scripts/install_python_and_venv.sh`가 Ubuntu 26.04를 인식하도록 수정했습니다

**New Features & Tools**
- **DX-COM**: `--use_gpu`, `--verbose` CLI 플래그(및 Python 인자 `use_gpu` / `verbose`), 공개 `QMasterConfig` 객체, `pre_optimize` `task` 키를 통한 pose 및 segmentation 후처리, `rtmdet_postprocess` pass를 추가했습니다
- **DX-Compiler**: `install.sh`에 uv 기반 설치(`--uv=true|false`)를 추가했으며, uv가 없으면 pip를 사용합니다
- **DX-AllSuite**: Ubuntu 기반 이미지용 `docker_run.sh` GPU 옵션을 추가했습니다: `nvidia-container-toolkit`을 사용하는 dx-compiler / dx-modelzoo용 `--nvidia_gpu`(`--cuda_version`, 기본값 `12.8.1`), `/dev/dri`를 사용하는 dx-runtime VA-API 가속용 `--intel_gpu_hw_acc`
- **DX-RT**: V9 `.dxnn` 파싱, 디바이스 제거 오류 코드, 엔진별 `showModelInfo`, 팬 제어 모드, `SLT` / `VNPU` 보드 타입, H1M FCT/OTP 인증, C# 사용 가이드, Authenticode 서명 가이드를 추가했습니다
- **DX_FW**: EQ 실패 복구, H1/H1M VNPU 수동 팬 제어, PCIe 메시지 API를 추가했습니다
- **DX-STREAM**: zero-copy DMA-BUF import를 지원하는 `gstdxstream-gles` 변환 백엔드를 추가했습니다; `run_demo.sh`에 Raspberry Pi 카메라 파이프라인(`libcamerasrc`)과 YOLO26 depth estimation 파이프라인을 추가했습니다
- **DX-APP**: person re-id, image retrieval, visual place recognition용 샘플 갤러리와 `RTDETRPostProcess`, `CLIPTextPostProcess`를 포함한 `dx_postprocess` 클래스 8종(50 → 58)을 추가했습니다
- **DX-ModelZoo**: YOLO26 depth, pose, classification, segmentation, PaddlePaddle, CLIP 이미지/텍스트 인코더, anomaly detection, person re-id 모델을 추가했습니다; MVTec AD 평가, 데이터셋 무결성 및 모델 입력 계약 검증, CLIP 임베딩 생성 및 캐싱을 추가했습니다

### Known Issues
- **DX-Runtime(installer)**: `oneline-install.sh`는 아티팩트 체크섬을 검증하지 않으며, 각 컴포넌트가 독립된 `main` 브랜치를 따르므로 설치된 조합이 함께 검증되지 않았을 수 있습니다. Workaround: `DX_RT_VERSION`, `DX_DRIVER_VERSION`, `DX_FW_VERSION`으로 버전을 고정하거나 `install.sh`를 사용합니다

---
