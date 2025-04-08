# DXNN® - DEEPX NPU 소프트웨어 (SDK) 튜토리얼

## 사전 준비

### DX-All 설치 

`https://github.com/DEEX-AI/dx-all/README.md`를 참고하여 `DXNN® - DEEPX NPU 소프트웨어 (SDK)`를 로컬 환경 또는 도커 컨테이너 환경에 설치합니다.
1. [Local 환경에 직접 설치](README.md#local-installation)
2. [Docker 이미지 빌드 및 컨테이너 실행 환경 구축](README.md#installation-using-docker)


### AI Model Compile(.onnx to .dxnn)


GPU 또는 CPU를 사용하여 구동할 수 있는 AI 모델 파일(.onnx)을 DEEPX NPU로 효율적으로 구동하기 위해서는 변환(최적화 및 양자화) 과정을 필요로 하며, `DX-Compiler`의 `dx_com`을 통해 이러한 변환 과정을 제공합니다.

아래 예시는 `dx_com`을 사용하여 [OSNet ReID](https://arxiv.org/abs/1905.00953) AI 모델()
