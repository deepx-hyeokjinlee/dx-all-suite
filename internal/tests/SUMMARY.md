# Docker Build Test Suite - 프로젝트 요약

## 📋 개요

dx-all-suite의 Docker 이미지 빌드를 자동으로 검증하는 pytest 기반 테스트 스위트입니다.

**목적**: 13개의 Docker 이미지 빌드 구성이 모두 정상적으로 빌드되는지 자동 검증

## 🎯 테스트 범위

### 빌드 타겟 (3개)
- **dx-runtime**: 런타임 환경
- **dx-modelzoo**: 모델 저장소
- **dx-compiler**: 컴파일러

### OS 구성 (13개 조합)

| 타겟 | Ubuntu 24.04 | Ubuntu 22.04 | Ubuntu 20.04 | Ubuntu 18.04 | Debian 12 | 합계 |
|------|:------------:|:------------:|:------------:|:------------:|:---------:|:----:|
| dx-runtime | ✅ | ✅ | ✅ | ✅ | ✅ | 5 |
| dx-modelzoo | ✅ | ✅ | ✅ | ✅ | ✅ | 5 |
| dx-compiler | ✅ | ✅ | ✅ | ❌ | ❌ | 3 |
| **합계** | **3** | **3** | **3** | **2** | **2** | **13** |

> **Note**: dx-compiler는 Ubuntu만 지원

### 테스트 구성
- **Sanity 테스트**: 4개 (환경 검증)
- **Build 테스트**: 13개 (실제 빌드)
- **총 테스트**: 17개

## 📁 파일 구조

```
internal/tests/
├── 🐍 test_docker_build.py              # 메인 테스트 파일 (pytest)
├── 🔧 run_docker_build_tests.sh         # 테스트 실행 스크립트
├── ⚡ test.sh                           # 간편 명령어 래퍼
├── 📖 REFERENCE.sh                      # 빠른 참조 가이드
├── 📚 README_DOCKER_BUILD_TESTS.md      # 상세 사용 가이드
├── 🔄 CI_CD_EXAMPLES.md                 # CI/CD 통합 예제
├── 📝 SUMMARY.md                        # 이 문서
├── 📦 requirements.txt                  # Python 의존성 (자동 생성)
├── 🐍 venv/                             # Python 가상환경 (자동 생성)
└── 📊 reports/                          # 테스트 리포트 (자동 생성)
```

## 🚀 빠른 시작

### 1단계: Sanity 체크 (5초)
```bash
cd internal/tests
./test.sh sanity
```

### 2단계: 특정 타겟 테스트
```bash
./test.sh runtime      # dx-runtime만 (약 2.5시간)
./test.sh modelzoo     # dx-modelzoo만 (약 2.5시간)
./test.sh compiler     # dx-compiler만 (약 1.5시간)
```

### 3단계: 전체 테스트
```bash
./test.sh all          # 모든 테스트 (약 6-8시간)
```

## 💡 주요 명령어

### 기본 명령어
```bash
./test.sh sanity           # ⚡ 빠른 검증 (5초)
./test.sh all              # 🔥 전체 테스트 (6-8시간)
./test.sh list             # 📋 테스트 목록
./test.sh help             # ❓ 도움말
```

### 타겟별 실행
```bash
./test.sh runtime          # dx-runtime 테스트
./test.sh modelzoo         # dx-modelzoo 테스트
./test.sh compiler         # dx-compiler 테스트
```

### OS별 실행
```bash
./test.sh ubuntu           # Ubuntu 전체
./test.sh debian           # Debian 전체
./test.sh ubuntu-24.04     # Ubuntu 24.04만
./test.sh ubuntu-22.04     # Ubuntu 22.04만
./test.sh ubuntu-20.04     # Ubuntu 20.04만
./test.sh ubuntu-18.04     # Ubuntu 18.04만
./test.sh debian-12        # Debian 12만
```

### 리포트 생성
```bash
./test.sh report           # 📊 HTML 리포트
./test.sh json             # 📄 JSON 리포트
```

## 🎨 사용 예시

### 예시 1: 개발 중 빠른 검증
```bash
# PR 전에 sanity + 최신 버전만 테스트
./test.sh sanity && ./test.sh ubuntu-24.04
```

### 예시 2: 특정 타겟 집중 테스트
```bash
# runtime 관련 코드 수정 후
./test.sh runtime -v
```

### 예시 3: 릴리스 전 전체 검증
```bash
# 리포트 생성과 함께 전체 테스트
./test.sh report
```

### 예시 4: 특정 OS 버전만
```bash
# Ubuntu 24.04와 Debian 12만 테스트
./run_docker_build_tests.sh -k "24.04 or 12"
```

## 📊 예상 실행 시간

| 테스트 유형 | 테스트 수 | 예상 시간 | 용도 |
|------------|----------|----------|------|
| Sanity | 4 | ~5초 | 환경 검증 |
| 단일 빌드 | 1 | ~10-15분 | 개별 테스트 |
| Runtime | 5 | ~2.5시간 | 타겟별 검증 |
| Modelzoo | 5 | ~2.5시간 | 타겟별 검증 |
| Compiler | 3 | ~1.5시간 | 타겟별 검증 |
| **전체** | **17** | **~6-8시간** | **완전한 검증** |

> **Note**: 시간은 캐시 상태와 시스템 성능에 따라 달라질 수 있습니다.

## 🔍 테스트 세부 정보

### Sanity 테스트 (4개)
환경 및 전제 조건 검증:

1. ✅ `test_docker_build_script_exists` - docker_build.sh 스크립트 존재 확인
2. ✅ `test_docker_command_available` - docker 명령어 사용 가능 확인
3. ✅ `test_docker_compose_command_available` - docker compose 사용 가능 확인
4. ✅ `test_project_structure` - 필수 디렉토리 구조 확인

### Build 테스트 (13개)
실제 Docker 이미지 빌드 검증:

**dx-runtime (5개)**
- ✅ `test_docker_build[dx-runtime-ubuntu-24.04]`
- ✅ `test_docker_build[dx-runtime-ubuntu-22.04]`
- ✅ `test_docker_build[dx-runtime-ubuntu-20.04]`
- ✅ `test_docker_build[dx-runtime-ubuntu-18.04]`
- ✅ `test_docker_build[dx-runtime-debian-12]`

**dx-modelzoo (5개)**
- ✅ `test_docker_build[dx-modelzoo-ubuntu-24.04]`
- ✅ `test_docker_build[dx-modelzoo-ubuntu-22.04]`
- ✅ `test_docker_build[dx-modelzoo-ubuntu-20.04]`
- ✅ `test_docker_build[dx-modelzoo-ubuntu-18.04]`
- ✅ `test_docker_build[dx-modelzoo-debian-12]`

**dx-compiler (3개)**
- ✅ `test_docker_build[dx-compiler-ubuntu-24.04]`
- ✅ `test_docker_build[dx-compiler-ubuntu-22.04]`
- ✅ `test_docker_build[dx-compiler-ubuntu-20.04]`

## 🛠 기술 스택

- **테스트 프레임워크**: pytest 7.4.3+
- **리포팅**: pytest-html, pytest-json-report
- **언어**: Python 3.8+, Bash
- **필수 도구**: Docker, Docker Compose
- **플랫폼**: Ubuntu/Debian Linux

## 📚 문서

| 문서 | 설명 |
|------|------|
| [README_DOCKER_BUILD_TESTS.md](README_DOCKER_BUILD_TESTS.md) | 📘 상세 사용 가이드 |
| [CI_CD_EXAMPLES.md](CI_CD_EXAMPLES.md) | 🔄 CI/CD 통합 예제 |
| [REFERENCE.sh](REFERENCE.sh) | 📖 명령어 퀵 레퍼런스 |
| [SUMMARY.md](SUMMARY.md) | 📝 이 문서 (프로젝트 개요) |

## 🔧 고급 사용법

### pytest 직접 사용
```bash
# 가상환경 활성화
source ./venv/bin/activate

# 다양한 필터링
pytest -v                              # 전체 실행
pytest -k "runtime and ubuntu"         # 조건 필터
pytest -m sanity                       # 마커 필터
pytest --collect-only                  # 테스트 목록만
pytest -x                              # 첫 실패시 중단
pytest -v -s                           # 상세 출력

# 비활성화
deactivate
```

### 커스텀 필터링
```bash
# AND 조건
./run_docker_build_tests.sh -k "runtime and ubuntu and 24.04"

# OR 조건
./run_docker_build_tests.sh -k "runtime or compiler"

# NOT 조건
./run_docker_build_tests.sh -k "not debian"

# 복합 조건
./run_docker_build_tests.sh -k "(runtime or modelzoo) and ubuntu and not 18.04"
```

## 🚨 문제 해결

### 일반적인 문제

#### 1. pytest를 찾을 수 없음
```bash
rm -rf ./venv
./run_docker_build_tests.sh --collect-only
```

#### 2. Docker 권한 에러
```bash
sudo usermod -aG docker $USER
# 로그아웃 후 다시 로그인
```

#### 3. 빌드 타임아웃
`test_docker_build.py`에서 타임아웃 조정:
```python
TEST_TIMEOUT = 3600  # 60분으로 증가
```

#### 4. 가상환경 문제
```bash
rm -rf ./venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 🔄 CI/CD 통합

이 테스트 스위트는 다음 CI/CD 플랫폼과 통합 가능:

- ✅ GitHub Actions
- ✅ GitLab CI
- ✅ Jenkins
- ✅ 기타 (표준 pytest 호환)

상세 예제는 [CI_CD_EXAMPLES.md](CI_CD_EXAMPLES.md) 참조.

### CI/CD 권장 전략

**Pull Request**:
- ✅ Sanity 테스트
- ✅ 최신 OS 버전 (24.04) 빌드
- ❌ 전체 테스트 (시간 절약)

**Main/Develop Branch**:
- ✅ 전체 테스트 실행
- ✅ 리포트 생성
- ✅ 아티팩트 보관

**Release**:
- ✅ 전체 테스트 실행
- ✅ 수동 승인 단계
- ✅ 상세 리포트 검토

## 📈 테스트 커버리지

| 카테고리 | 커버리지 |
|---------|---------|
| 빌드 타겟 | 3/3 (100%) |
| Ubuntu 버전 | 4/4 (100%) |
| Debian 버전 | 1/1 (100%) |
| 전체 조합 | 13/13 (100%) |

## 🎯 프로젝트 목표

1. ✅ **자동화**: 수동 빌드 검증 제거
2. ✅ **일관성**: 모든 OS 버전에서 동일한 검증
3. ✅ **신뢰성**: 빌드 실패 조기 발견
4. ✅ **효율성**: CI/CD 파이프라인 통합
5. ✅ **문서화**: 명확한 사용법 제공

## 🤝 기여 가이드

테스트 추가 또는 개선 시:

1. 새 OS 버전 추가는 `test_docker_build.py`의 `@pytest.mark.parametrize` 수정
2. 새 타겟 추가는 동일한 parametrize에 추가
3. 테스트 실행 확인: `./test.sh sanity && ./test.sh list`
4. 문서 업데이트: README.md, SUMMARY.md 등

## 📞 지원

- 📖 문서: [README_DOCKER_BUILD_TESTS.md](README_DOCKER_BUILD_TESTS.md)
- 📋 퀵 레퍼런스: [REFERENCE.sh](REFERENCE.sh)
- 🔄 CI/CD 가이드: [CI_CD_EXAMPLES.md](CI_CD_EXAMPLES.md)

