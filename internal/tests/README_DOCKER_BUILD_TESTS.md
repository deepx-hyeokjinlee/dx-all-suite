# Docker Build Test Suite

Docker 이미지 빌드를 자동으로 검증하는 pytest 기반 테스트 스위트입니다.

## 개요

이 테스트 스위트는 다음 Docker 이미지 빌드를 검증합니다:

- **dx-runtime**: Ubuntu 24.04, 22.04, 20.04, 18.04, Debian 12 (5개 테스트)
- **dx-modelzoo**: Ubuntu 24.04, 22.04, 20.04, 18.04, Debian 12 (5개 테스트)
- **dx-compiler**: Ubuntu 24.04, 22.04, 20.04 (3개 테스트)

**총 13개의 빌드 테스트 + 4개의 Sanity 테스트 = 17개 테스트**

## 파일 구조

```
internal/tests/
├── test_docker_build.py              # 메인 pytest 테스트 파일
├── run_docker_build_tests.sh         # 테스트 실행 스크립트
├── test.sh                           # 간편 명령어 래퍼
├── REFERENCE.sh                      # 빠른 참조 가이드
├── README_DOCKER_BUILD_TESTS.md      # 이 문서
├── CI_CD_EXAMPLES.md                 # CI/CD 통합 예제
├── SUMMARY.md                        # 프로젝트 개요
├── requirements.txt                  # Python 의존성 (자동 생성)
├── venv/                             # Python 가상환경 (자동 생성)
└── reports/                          # 테스트 리포트 (자동 생성)
```

## 빠른 시작

### 1. Sanity 테스트만 실행 (빠른 검증)

```bash
cd internal/tests
./test.sh sanity
```

### 2. 전체 테스트 실행

```bash
./test.sh all
```

### 3. 특정 타겟만 테스트

```bash
./test.sh runtime      # dx-runtime만
./test.sh modelzoo     # dx-modelzoo만
./test.sh compiler     # dx-compiler만
```

## 상세 사용법

### test.sh 명령어

`test.sh`는 일반적인 테스트 시나리오를 위한 간편한 래퍼입니다:

```bash
# 기본 사용법
./test.sh <command> [additional_args...]

# 사용 가능한 명령어
./test.sh sanity           # Sanity 테스트만
./test.sh all              # 모든 테스트
./test.sh runtime          # dx-runtime 테스트
./test.sh modelzoo         # dx-modelzoo 테스트
./test.sh compiler         # dx-compiler 테스트
./test.sh ubuntu           # Ubuntu 이미지만
./test.sh debian           # Debian 이미지만
./test.sh ubuntu-24.04     # Ubuntu 24.04만
./test.sh ubuntu-22.04     # Ubuntu 22.04만
./test.sh ubuntu-20.04     # Ubuntu 20.04만
./test.sh ubuntu-18.04     # Ubuntu 18.04만
./test.sh debian-12        # Debian 12만
./test.sh list             # 테스트 목록 출력
./test.sh report           # HTML 리포트 생성
./test.sh json             # JSON 리포트 생성
./test.sh help             # 도움말
```

### run_docker_build_tests.sh 명령어

더 세밀한 제어가 필요한 경우 직접 사용:

```bash
# 기본 사용법
./run_docker_build_tests.sh [pytest_args...]

# 예제
./run_docker_build_tests.sh -v                    # Verbose 출력
./run_docker_build_tests.sh -k "runtime"          # 특정 테스트
./run_docker_build_tests.sh --collect-only        # 테스트 목록만
./run_docker_build_tests.sh -x                    # 첫 실패시 중단
./run_docker_build_tests.sh -v -s                 # 상세 출력 + stdout
```

### pytest 직접 사용

가상환경을 직접 활성화하여 pytest를 사용할 수도 있습니다:

```bash
# 가상환경 활성화
source ./venv/bin/activate

# pytest 직접 실행
pytest -v
pytest -k "runtime and ubuntu"
pytest --collect-only
pytest -v --tb=short

# 완료 후 비활성화
deactivate
```

## 테스트 필터링

### 키워드로 필터링 (-k 옵션)

```bash
# 특정 타겟만
./run_docker_build_tests.sh -k "runtime"
./run_docker_build_tests.sh -k "modelzoo"
./run_docker_build_tests.sh -k "compiler"

# 특정 OS만
./run_docker_build_tests.sh -k "ubuntu"
./run_docker_build_tests.sh -k "debian"

# 특정 버전만
./run_docker_build_tests.sh -k "24.04"
./run_docker_build_tests.sh -k "22.04"

# 조합 (AND)
./run_docker_build_tests.sh -k "runtime and ubuntu"
./run_docker_build_tests.sh -k "runtime and 24.04"

# 조합 (OR)
./run_docker_build_tests.sh -k "runtime or compiler"

# 제외 (NOT)
./run_docker_build_tests.sh -k "not debian"
./run_docker_build_tests.sh -k "ubuntu and not 18.04"
```

### 마커로 필터링 (-m 옵션)

```bash
# Sanity 테스트만
./run_docker_build_tests.sh -m sanity

# Sanity 테스트 제외
./run_docker_build_tests.sh -m "not sanity"
```

## 리포트 생성

### HTML 리포트

```bash
# test.sh 사용 (권장)
./test.sh report

# 직접 지정
./run_docker_build_tests.sh --html=report.html --self-contained-html
```

생성 위치: `internal/tests/reports/test_report_<timestamp>.html`

### JSON 리포트

```bash
# test.sh 사용 (권장)
./test.sh json

# 직접 지정
./run_docker_build_tests.sh --json-report --json-report-file=report.json
```

생성 위치: `internal/tests/reports/test_report_<timestamp>.json`

## 실행 예제

### 예제 1: 빠른 검증

```bash
# Sanity 테스트만 실행 (약 5초 소요)
./test.sh sanity
```

### 예제 2: 특정 타겟 테스트

```bash
# dx-runtime만 테스트 (약 2.5시간 소요)
./test.sh runtime -v
```

### 예제 3: 특정 OS 버전 테스트

```bash
# Ubuntu 24.04만 테스트
./test.sh ubuntu-24.04 -v
```

### 예제 4: 리포트와 함께 전체 테스트

```bash
# 전체 테스트 + HTML 리포트 생성
./test.sh report
```

### 예제 5: 첫 실패시 중단

```bash
# 실패하면 즉시 중단
./run_docker_build_tests.sh -x -v
```

## 테스트 구조

### Sanity 테스트 (4개)

빌드 전 환경 검증:

1. `test_docker_build_script_exists` - docker_build.sh 존재 확인
2. `test_docker_command_available` - docker 명령어 확인
3. `test_docker_compose_command_available` - docker compose 확인
4. `test_project_structure` - 프로젝트 구조 확인

### Build 테스트 (13개)

실제 Docker 이미지 빌드:

**dx-runtime (5개)**
- `test_docker_build[dx-runtime-ubuntu-24.04]`
- `test_docker_build[dx-runtime-ubuntu-22.04]`
- `test_docker_build[dx-runtime-ubuntu-20.04]`
- `test_docker_build[dx-runtime-ubuntu-18.04]`
- `test_docker_build[dx-runtime-debian-12]`

**dx-modelzoo (5개)**
- `test_docker_build[dx-modelzoo-ubuntu-24.04]`
- `test_docker_build[dx-modelzoo-ubuntu-22.04]`
- `test_docker_build[dx-modelzoo-ubuntu-20.04]`
- `test_docker_build[dx-modelzoo-ubuntu-18.04]`
- `test_docker_build[dx-modelzoo-debian-12]`

**dx-compiler (3개)**
- `test_docker_build[dx-compiler-ubuntu-24.04]`
- `test_docker_build[dx-compiler-ubuntu-22.04]`
- `test_docker_build[dx-compiler-ubuntu-20.04]`

## 예상 실행 시간

- **Sanity 테스트**: ~5초
- **단일 빌드 테스트**: ~10-15분 (첫 빌드) / ~5-10분 (캐시 사용)
- **전체 테스트**: ~2-4시간 (병렬 실행 없이)

## 문제 해결

### pytest를 찾을 수 없음

```bash
# 가상환경 재생성
rm -rf ./venv
./run_docker_build_tests.sh --collect-only
```

### Docker 권한 에러

```bash
# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
# 로그아웃 후 다시 로그인
```

### 테스트 타임아웃

각 빌드는 기본 30분 타임아웃이 설정되어 있습니다. 필요시 `test_docker_build.py`에서 `TEST_TIMEOUT` 값을 조정하세요.

```python
TEST_TIMEOUT = 1800  # 30분 (초 단위)
```

### 가상환경 문제

```bash
# 가상환경 완전 삭제 후 재생성
rm -rf ./venv
./run_docker_build_tests.sh --collect-only
```

## CI/CD 통합

CI/CD 파이프라인에 통합하는 방법은 [CI_CD_EXAMPLES.md](CI_CD_EXAMPLES.md)를 참조하세요.

주요 CI 플랫폼 예제 포함:
- GitHub Actions
- GitLab CI
- Jenkins

## 추가 정보

- **빠른 참조**: [REFERENCE.sh](REFERENCE.sh) - 모든 명령어 퀵 레퍼런스
- **프로젝트 개요**: [SUMMARY.md](SUMMARY.md) - 전체 프로젝트 요약
- **CI/CD 예제**: [CI_CD_EXAMPLES.md](CI_CD_EXAMPLES.md) - CI/CD 통합 가이드

## 라이선스

이 테스트 스위트는 dx-all-suite 프로젝트의 일부입니다.
