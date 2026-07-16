# DX Benchmark — YOLO26 하드웨어 벤치마크 도구

## [section:overview,소개,benchmark,벤치마크] DX Benchmark 개요

DX Benchmark (포트 8097)는 **YOLO26 계열 모델의 NPU 하드웨어별 성능을 측정·비교하는 도구**입니다.
- **모델 크기별 비교**: n (Nano), s (Small), m (Medium), l (Large)
- **E2E 파이프라인 성능**: 전처리→추론→후처리 전 구간 FPS/Latency 측정
- **Multi-Stream 용량 테스트**: 30fps 유지 가능한 최대 스트림 수 측정
- **Version Trend**: 소프트웨어 버전별 성능 추이 비교

### 지원 하드웨어
| 보드 | 설명 |
|------|------|
| AI Box (DX-AIPlayer-N97) | DEEPX M1 NPU 탑재 미니 PC |
| ROCK5B+ | Rockchip RK3588 + DEEPX M1 |
| OrangePi5+ | Rockchip RK3588 + DEEPX M1 |
| Raspberry Pi 5 | BCM2712 + DEEPX M1 |
| BIOSTAR | DEEPX H1 NPU 탑재 산업용 보드 |
| i7-14700K | Intel 데스크톱 + DEEPX M1 PCIe |

## [section:run,실행,runner,test] 벤치마크 실행

### Run 탭 사용법
1. **Preflight Check** — 드라이버, 디바이스 파일, 모델 존재 여부 자동 확인
2. **Task 선택** — Detection / Classification
3. **Size 선택** — n / s / m / l (동시 복수 선택 가능)
4. **ORT 모드** — ONNX Runtime 사용 여부
5. **Run Benchmark** 클릭 → 실시간 로그 출력
6. 완료 후 자동으로 `results/<hw_id>/<run_id>/` 에 저장

### 측정 항목
- **Model FPS / Latency**: 추론 모델 단독 성능
- **E2E FPS**: 전처리→추론→후처리 전체 파이프라인
- **Multi-Stream Capacity**: 30fps 기준 최대 병렬 스트림 수

## [section:dashboard,대시보드,chart,차트] Dashboard 탭

### Overview 차트
- **좌축 (막대)**: FPS (Model Throughput / E2E FPS)
- **우축 (다이아몬드)**: Latency (ms)
- 하드웨어별 비교, 클릭 시 상세 정보 펼침

### E2E FPS by Size 차트
- 모델 크기(n/s/m/l)별 그룹 막대 차트
- Max Channel 배지 표시 (보라색)

### Version Trend 탭
- 소프트웨어 버전별 성능 추이 라인 차트
- 스냅샷 데이터 필요 (results 폴더에 복수 run_id 존재 시)

## [section:result,결과,results,report] Results 탭

### 결과 탐색
1. **하드웨어 선택** → 해당 보드의 실행 목록 표시
2. **Run 선택** → 상세 결과 (환경정보, 모델 성능, 파이프라인 성능)
3. **REPORT.md** — 자동 생성된 마크다운 리포트 뷰어

## [section:settings,설정,config] Settings 탭

### 설정 항목
- **Model Directory**: YOLO26 모델 파일 경로
- **Video Directory**: 벤치마크 입력 영상 경로
- **Results Directory**: 결과 저장 경로
- **Cooldown Threshold**: 열 관리 온도 임계값 (°C)
- **Wait Interval**: 쿨다운 대기 간격 (초)
- **Iterations**: 벤치마크 반복 횟수
- **Warmup Runs**: 워밍업 실행 횟수
- **FPS Threshold**: 최소 FPS 기준값

## [section:troubleshoot,문제,error,에러] 문제 해결

### Preflight Check 실패
- **NPU 드라이버 미설치**: `dxnn-driver` 패키지 설치 필요
- **디바이스 파일 없음**: `/dev/dxnn*` 파일이 없으면 드라이버 로드 확인
- **모델 파일 없음**: Settings에서 올바른 모델 경로 설정

### 결과 없음 (No data)
- `results/` 폴더가 비어 있으면 Dashboard에 "No data" 표시
- Run 탭에서 벤치마크를 한 번 이상 실행해야 합니다

### 차트가 안 보임
- 브라우저 콘솔에서 JavaScript 에러 확인
- dataset.json 파일이 올바르게 생성되었는지 확인
