# CI/CD Integration Examples

이 문서는 Docker Build Test Suite를 다양한 CI/CD 플랫폼에 통합하는 방법을 제공합니다.

## 목차

- [GitHub Actions](#github-actions)
- [GitLab CI](#gitlab-ci)
- [Jenkins](#jenkins)
- [일반 가이드라인](#일반-가이드라인)

---

## GitHub Actions

### 기본 워크플로우

`.github/workflows/docker-build-test.yml`:

```yaml
name: Docker Build Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  workflow_dispatch:

jobs:
  sanity-check:
    name: Sanity Check
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Run sanity tests
        run: |
          cd internal/tests
          ./test.sh sanity

  docker-build-runtime:
    name: Build dx-runtime
    needs: sanity-check
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, ubuntu-22.04, ubuntu-20.04, ubuntu-18.04, debian-12]
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Test dx-runtime build
        run: |
          cd internal/tests
          ./run_docker_build_tests.sh -v -k "runtime and ${{ matrix.os }}"
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results-runtime-${{ matrix.os }}
          path: internal/tests/reports/

  docker-build-modelzoo:
    name: Build dx-modelzoo
    needs: sanity-check
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, ubuntu-22.04, ubuntu-20.04, ubuntu-18.04, debian-12]
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Test dx-modelzoo build
        run: |
          cd internal/tests
          ./run_docker_build_tests.sh -v -k "modelzoo and ${{ matrix.os }}"
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results-modelzoo-${{ matrix.os }}
          path: internal/tests/reports/

  docker-build-compiler:
    name: Build dx-compiler
    needs: sanity-check
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, ubuntu-22.04, ubuntu-20.04]
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Test dx-compiler build
        run: |
          cd internal/tests
          ./run_docker_build_tests.sh -v -k "compiler and ${{ matrix.os }}"
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results-compiler-${{ matrix.os }}
          path: internal/tests/reports/

  generate-report:
    name: Generate Test Report
    needs: [docker-build-runtime, docker-build-modelzoo, docker-build-compiler]
    runs-on: ubuntu-latest
    if: always()
    
    steps:
      - name: Download all artifacts
        uses: actions/download-artifact@v3
        with:
          path: test-results
      
      - name: Display structure of downloaded files
        run: ls -R test-results
```

### 간소화된 워크플로우 (빠른 검증용)

```yaml
name: Quick Docker Build Check

on:
  pull_request:
    branches: [ main ]

jobs:
  quick-test:
    name: Quick Build Test
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Run sanity tests
        run: |
          cd internal/tests
          ./test.sh sanity
      
      - name: Test one configuration per target
        run: |
          cd internal/tests
          ./run_docker_build_tests.sh -v -k "ubuntu-24.04"
```

---

## GitLab CI

### 기본 파이프라인

`.gitlab-ci.yml`:

```yaml
stages:
  - sanity
  - build-runtime
  - build-modelzoo
  - build-compiler
  - report

variables:
  DOCKER_DRIVER: overlay2
  DOCKER_TLS_CERTDIR: "/certs"

before_script:
  - python3 --version
  - docker --version
  - docker compose version

# Sanity 테스트
sanity-check:
  stage: sanity
  image: ubuntu:24.04
  services:
    - docker:24-dind
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io
    - cd internal/tests
    - ./test.sh sanity
  tags:
    - docker

# dx-runtime 빌드 테스트
.runtime-template: &runtime-template
  stage: build-runtime
  image: ubuntu:24.04
  services:
    - docker:24-dind
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io docker-compose-v2
    - cd internal/tests
    - ./run_docker_build_tests.sh -v -k "runtime and ${OS_VERSION}"
  artifacts:
    when: always
    paths:
      - internal/tests/reports/
    expire_in: 7 days
  tags:
    - docker

runtime-ubuntu-24.04:
  <<: *runtime-template
  variables:
    OS_VERSION: "24.04"

runtime-ubuntu-22.04:
  <<: *runtime-template
  variables:
    OS_VERSION: "22.04"

runtime-ubuntu-20.04:
  <<: *runtime-template
  variables:
    OS_VERSION: "20.04"

runtime-ubuntu-18.04:
  <<: *runtime-template
  variables:
    OS_VERSION: "18.04"

runtime-debian-12:
  <<: *runtime-template
  variables:
    OS_VERSION: "12"
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io docker-compose-v2
    - cd internal/tests
    - ./run_docker_build_tests.sh -v -k "runtime and debian and 12"

# dx-modelzoo 빌드 테스트
.modelzoo-template: &modelzoo-template
  stage: build-modelzoo
  image: ubuntu:24.04
  services:
    - docker:24-dind
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io docker-compose-v2
    - cd internal/tests
    - ./run_docker_build_tests.sh -v -k "modelzoo and ${OS_VERSION}"
  artifacts:
    when: always
    paths:
      - internal/tests/reports/
    expire_in: 7 days
  tags:
    - docker

modelzoo-ubuntu-24.04:
  <<: *modelzoo-template
  variables:
    OS_VERSION: "24.04"

modelzoo-ubuntu-22.04:
  <<: *modelzoo-template
  variables:
    OS_VERSION: "22.04"

modelzoo-ubuntu-20.04:
  <<: *modelzoo-template
  variables:
    OS_VERSION: "20.04"

modelzoo-ubuntu-18.04:
  <<: *modelzoo-template
  variables:
    OS_VERSION: "18.04"

modelzoo-debian-12:
  <<: *modelzoo-template
  variables:
    OS_VERSION: "12"
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io docker-compose-v2
    - cd internal/tests
    - ./run_docker_build_tests.sh -v -k "modelzoo and debian and 12"

# dx-compiler 빌드 테스트
.compiler-template: &compiler-template
  stage: build-compiler
  image: ubuntu:24.04
  services:
    - docker:24-dind
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io docker-compose-v2
    - cd internal/tests
    - ./run_docker_build_tests.sh -v -k "compiler and ${OS_VERSION}"
  artifacts:
    when: always
    paths:
      - internal/tests/reports/
    expire_in: 7 days
  tags:
    - docker

compiler-ubuntu-24.04:
  <<: *compiler-template
  variables:
    OS_VERSION: "24.04"

compiler-ubuntu-22.04:
  <<: *compiler-template
  variables:
    OS_VERSION: "22.04"

compiler-ubuntu-20.04:
  <<: *compiler-template
  variables:
    OS_VERSION: "20.04"

# 테스트 리포트 생성
generate-report:
  stage: report
  image: ubuntu:24.04
  script:
    - echo "All tests completed"
    - ls -R internal/tests/reports/ || true
  artifacts:
    paths:
      - internal/tests/reports/
    expire_in: 30 days
  tags:
    - docker
```

### 간소화된 파이프라인 (MR 검증용)

```yaml
stages:
  - quick-test

quick-build-check:
  stage: quick-test
  image: ubuntu:24.04
  services:
    - docker:24-dind
  script:
    - apt-get update && apt-get install -y python3 python3-venv docker.io docker-compose-v2
    - cd internal/tests
    - ./test.sh sanity
    - ./run_docker_build_tests.sh -v -k "ubuntu-24.04"
  only:
    - merge_requests
  tags:
    - docker
```

---

## Jenkins

### Declarative Pipeline

`Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    environment {
        PYTHON_VERSION = '3.10'
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git submodule update --init --recursive'
            }
        }
        
        stage('Sanity Check') {
            steps {
                dir('internal/tests') {
                    sh './test.sh sanity'
                }
            }
        }
        
        stage('Build Tests') {
            parallel {
                stage('dx-runtime') {
                    stages {
                        stage('Ubuntu 24.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "runtime and ubuntu-24.04"'
                                }
                            }
                        }
                        stage('Ubuntu 22.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "runtime and ubuntu-22.04"'
                                }
                            }
                        }
                        stage('Ubuntu 20.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "runtime and ubuntu-20.04"'
                                }
                            }
                        }
                        stage('Ubuntu 18.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "runtime and ubuntu-18.04"'
                                }
                            }
                        }
                        stage('Debian 12') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "runtime and debian-12"'
                                }
                            }
                        }
                    }
                }
                
                stage('dx-modelzoo') {
                    stages {
                        stage('Ubuntu 24.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "modelzoo and ubuntu-24.04"'
                                }
                            }
                        }
                        stage('Ubuntu 22.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "modelzoo and ubuntu-22.04"'
                                }
                            }
                        }
                        stage('Ubuntu 20.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "modelzoo and ubuntu-20.04"'
                                }
                            }
                        }
                        stage('Ubuntu 18.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "modelzoo and ubuntu-18.04"'
                                }
                            }
                        }
                        stage('Debian 12') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "modelzoo and debian-12"'
                                }
                            }
                        }
                    }
                }
                
                stage('dx-compiler') {
                    stages {
                        stage('Ubuntu 24.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "compiler and ubuntu-24.04"'
                                }
                            }
                        }
                        stage('Ubuntu 22.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "compiler and ubuntu-22.04"'
                                }
                            }
                        }
                        stage('Ubuntu 20.04') {
                            steps {
                                dir('internal/tests') {
                                    sh './run_docker_build_tests.sh -v -k "compiler and ubuntu-20.04"'
                                }
                            }
                        }
                    }
                }
            }
        }
        
        stage('Generate Report') {
            steps {
                dir('internal/tests') {
                    sh './test.sh report'
                }
            }
        }
    }
    
    post {
        always {
            archiveArtifacts artifacts: 'internal/tests/reports/**/*', allowEmptyArchive: true
            
            // Publish HTML reports if using HTML Publisher plugin
            publishHTML([
                allowMissing: false,
                alwaysLinkToLastBuild: true,
                keepAll: true,
                reportDir: 'internal/tests/reports',
                reportFiles: '*.html',
                reportName: 'Docker Build Test Report'
            ])
        }
        
        success {
            echo 'All Docker build tests passed!'
        }
        
        failure {
            echo 'Some Docker build tests failed!'
        }
    }
}
```

### Scripted Pipeline (간소화 버전)

```groovy
node {
    stage('Checkout') {
        checkout scm
        sh 'git submodule update --init --recursive'
    }
    
    stage('Sanity Check') {
        dir('internal/tests') {
            sh './test.sh sanity'
        }
    }
    
    stage('Quick Build Test') {
        dir('internal/tests') {
            sh './run_docker_build_tests.sh -v -k "ubuntu-24.04"'
        }
    }
    
    stage('Archive Results') {
        archiveArtifacts artifacts: 'internal/tests/reports/**/*', allowEmptyArchive: true
    }
}
```

---

## 일반 가이드라인

### 1. 병렬 실행 최적화

빌드 시간을 단축하기 위해 병렬 실행을 권장합니다:

- **Strategy**: OS 버전별로 병렬 실행
- **Job 분리**: runtime, modelzoo, compiler를 별도 job으로 분리
- **실행 순서**: Sanity 테스트 → 병렬 빌드 테스트 → 리포트 생성

### 2. 캐싱 전략

Docker 레이어 캐싱을 활용하여 빌드 시간 단축:

```yaml
# GitHub Actions 예제
- name: Cache Docker layers
  uses: actions/cache@v3
  with:
    path: /tmp/.buildx-cache
    key: ${{ runner.os }}-buildx-${{ github.sha }}
    restore-keys: |
      ${{ runner.os }}-buildx-
```

### 3. 타임아웃 설정

각 빌드에 적절한 타임아웃 설정:

```yaml
# GitHub Actions
timeout-minutes: 45

# GitLab CI
timeout: 45m

# Jenkins
timeout(time: 45, unit: 'MINUTES')
```

### 4. 아티팩트 관리

테스트 결과를 아티팩트로 저장:

- HTML 리포트
- JSON 리포트
- 빌드 로그
- 보관 기간: 7-30일 권장

### 5. 실패 처리

```yaml
# 하나의 빌드 실패가 전체를 중단하지 않도록 설정
strategy:
  fail-fast: false  # GitHub Actions
# 또는
allow_failure: true  # GitLab CI
```

### 6. 알림 설정

빌드 실패 시 알림 설정:

- Slack 통합
- 이메일 알림
- GitHub/GitLab 코멘트

### 7. 스케줄 실행

정기적인 빌드 검증:

```yaml
# GitHub Actions - 매일 자정에 실행
on:
  schedule:
    - cron: '0 0 * * *'

# GitLab CI - 매일 자정에 실행
only:
  - schedules
```

### 8. 리소스 최적화

CI 리소스 사용 최적화:

- **Sanity 먼저**: 빠른 검증 후 실패 시 조기 종료
- **선택적 실행**: PR에서는 변경된 타겟만 테스트
- **우선순위**: 자주 사용되는 OS 버전 우선 실행

---

## 베스트 프랙티스

### 1. PR 워크플로우

Pull Request에서는:
- ✅ Sanity 테스트 필수
- ✅ 최신 OS 버전 (24.04) 빌드 테스트
- ❌ 전체 테스트는 생략 (시간 절약)

### 2. Main/Develop 브랜치

메인 브랜치에서는:
- ✅ 전체 테스트 실행
- ✅ 모든 OS 버전 검증
- ✅ 리포트 생성 및 아카이브

### 3. Release 워크플로우

릴리스 전에는:
- ✅ 전체 테스트 실행
- ✅ 리포트 검토
- ✅ 수동 승인 단계 추가

### 4. 모니터링

CI/CD 성능 모니터링:
- 빌드 시간 추적
- 성공/실패율 모니터링
- 병목 구간 식별

---

## 추가 자료

- [README_DOCKER_BUILD_TESTS.md](README_DOCKER_BUILD_TESTS.md) - 기본 사용법
- [REFERENCE.sh](REFERENCE.sh) - 명령어 퀵 레퍼런스
- [SUMMARY.md](SUMMARY.md) - 프로젝트 개요
