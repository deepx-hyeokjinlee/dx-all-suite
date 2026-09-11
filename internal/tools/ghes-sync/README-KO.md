# ghes-sync — 미러 → GHES 브랜치 동기화

> 시나리오별 절차: [QUICKGUIDE-KO.md](QUICKGUIDE-KO.md) · [QUICKGUIDE.md](QUICKGUIDE.md)

`ghes-sync.sh`는 private github.com 미러(`github.com/deepx-dhyang/*`)의 작업을 폐쇄망
GHES(`gh.deepx.ai/deepx/*`)로 옮긴다. 설정된 source 브랜치를 fetch → 커밋이 가리키는
submodule pointer 검증 → 같은 이름 브랜치로 **fast-forward push**(force 절대 금지) →
설정된 base(`main`, dx_app/dx_stream은 `dev`)로 PR 생성(또는 기존 PR 재사용). PR merge는 사람이 한다.

GHES에 접근 가능하고 github.com을 *읽을* 수 있는 기계에서 실행한다(github.com push가 막혀 있어도
무관). 두 SCM은 git history를 공유하므로(미러는 GHES에서 clone됨) 일반 `git push`로 충분하고,
도구는 순서와 pointer만 지킨다.

이 디렉터리는 release-excluded인 `internal/` 아래에 있어 공개 `github.com/DEEPX-AI` export에 포함되지 않는다.

## 사전 조건

- bash ≥ 4와 git만 있으면 된다(Git for Windows의 **git bash** 충족: bash 4.4+, git, curl, base64).
  `gh`는 **선택**: 설치되어 있으면 `gh`로, 없으면 dst 토큰 + `curl`로 GHES REST API를 호출해 PR을 만든다.
  둘 다 없으면 브랜치 push는 수행하고 PR은 *경고 후 건너뜀*(exit 0 — 수동으로 열거나 토큰을 넣어 재실행).
- **https 전용.** 폐쇄망 기계에서는 github.com으로 SSH가 안 되므로 `sync.conf`는
  `https://github.com/deepx-dhyang`, `https://gh.deepx.ai/deepx`를 쓴다. `git@…`는 넣지 않는다.
- **자격증명(양쪽 모두 private).** 동등한 두 방식:

  | | src = github.com 미러(읽기) | dst = GHES(push + PR) |
  |---|---|---|
  | 환경변수(실행 단위, 저장 없음) | `GHES_SYNC_SRC_TOKEN`(fallback `GH_TOKEN`) — fine-grained PAT, `deepx-dhyang/*` 5개 repo에 *Contents: Read-only* | `GHES_SYNC_DST_TOKEN`(fallback `GH_ENTERPRISE_TOKEN`, `gh`가 PR 생성에 쓰는 변수와 동일) — `repo`(contents write + pull requests) PAT |
  | credential helper(기계당 1회) | `gh auth login --hostname github.com --with-token < pat.txt && gh auth setup-git --hostname github.com` | `gh auth login --hostname gh.deepx.ai [--with-token < pat.txt] && gh auth setup-git --hostname gh.deepx.ai` |

  환경변수를 쓰면 도구가 호출마다 `git -c http.https://<host>/.extraheader=AUTHORIZATION: basic <base64>`로 토큰을 전달한다 —
  URL·`.git/config`·출력에 남지 않는다(CI workflow와 같은 기법). 자격증명이 전혀 없으면 git은 비밀번호 prompt에서 멈추는데,
  도구가 `GIT_TERMINAL_PROMPT=0`을 설정하므로 인증 힌트와 함께 즉시 실패한다. 폐쇄망 기계에서 `gh auth login`은
  `--with-token`으로 브라우저 없이 가능하고, `https://github.com/login/device`를 열 수 있으면 device/web 흐름도 된다.
- env 토큰과 credential helper가 둘 다 있으면 해당 호출에는 header(env 토큰)가 우선한다.
- **대화형 vs 비대화형.** 터미널(git bash, ssh 세션)에서 토큰 없이 실행하면 git이 직접 묻도록 허용한다:
  Windows의 Git Credential Manager는 브라우저/device 로그인을 띄우고, 일반 git은 터미널에서 user + PAT를 묻는다
  (user는 아무 값, password에 PAT; `git config --global credential.helper manager|store`로 기억 가능).
  PR 단계에서 토큰도 `gh`도 없으면 GHES PAT를 한 번 입력받는다(저장하지 않음). TTY가 없거나 `--non-interactive`,
  `GHES_SYNC_INTERACTIVE=0`(CI)이면 prompt를 차단(`GIT_TERMINAL_PROMPT=0`)하고 자격증명 부재 시 즉시 실패한다 —
  이 경우 PAT를 secret으로 주입한다.

## 빠른 시작

```bash
cd <dx-all-suite>                                   # internal/ 이 있는 checkout
bash internal/tools/ghes-sync/ghes-sync.sh --print-config      # 무엇을 어디로 보낼지
bash internal/tools/ghes-sync/ghes-sync.sh --dry-run           # fetch + 분류, push/gh 명령만 출력
bash internal/tools/ghes-sync/ghes-sync.sh                     # push + PR 보장
bash internal/tools/ghes-sync/ghes-sync.sh --repo dx_app --no-pr   # repo 하나, push만
```

## 설정 — `sync.conf`

```ini
[defaults]
src_host  = https://github.com/deepx-dhyang  # url = <host>/<name>.git — https only
dst_host  = https://gh.deepx.ai/deepx
branch    = feature/dx-agent-dev            # source 브랜치; dst_branch 기본값은 같은 이름
pr_base   = main                            # dst의 PR 대상; "" = 해당 repo PR 없음
mode      = pr                              # pr = push + PR 보장 · push = push만
cache_dir = ${XDG_CACHE_HOME:-~/.cache}/ghes-sync
gitlink_check = strict                      # strict | warn | off

[repo dx_app]           ; 섹션 순서 = 처리 순서 (nested repo 먼저)
pr_base = dev
[repo dx_stream]
pr_base = dev
[repo dx-runtime]
gitlinks = dx_app:dx_app dx_stream:dx_stream         # <repo 이름>:<이 repo 안의 경로>
[repo dx-compiler]
[repo dx-all-suite]
gitlinks = dx-runtime:dx-runtime dx-compiler:dx-compiler
```

repo별 키: `src_url`, `dst_url`(전체 URL이 host+name보다 우선), `src_host`, `dst_host`, `branch`,
`dst_branch`, `pr_base`, `mode`, `gitlinks`. repo 추가 = `[repo NAME]` 섹션 추가(그 repo를 `gitlinks`로
가리키는 parent보다 앞에). 브랜치 매핑 추가 = 해당 섹션에 `branch =`/`dst_branch =`, 또는 별도 설정 파일(`--config other.conf`).

## repo별 동작

| 단계 | 내용 |
|------|------|
| fetch | bare 캐시 `<cache_dir>/<name>.git`에 `src/<branch>`, `dst/<dst_branch>`, `dst/<pr_base>` fetch(URL을 매번 명시 — remote 저장 없음, 자격증명 저장 없음) |
| 분류 | **CREATE**(dst에 브랜치 없음) · **FAST-FORWARD** · **UP-TO-DATE**(no-op) · **DST-AHEAD**(dst가 미러 tip을 포함하고 더 앞섬, 예: merge-update — push할 것 없음, 미러가 뒤처진 상태: `--reverse`로 되가져옴) · **DIVERGED**(양쪽에 서로 없는 커밋 → 해당 repo 실패, push 없음) |
| gitlink 검증 | 새 커밋들의 `gitlinks` 경로(`160000` 항목)가 sub-repo의 동기화된 tip에서 도달 가능해야 함(이 실행에서 처리되지 않은 sub-repo면 dst 현재 상태 기준). `strict`는 parent push 차단, `warn`은 경고 후 push |
| push | `git push <dst> refs/remotes/src/<branch>:refs/heads/<dst_branch>` — ff-only, `--force` 없음; `--tags`면 `refs/tags/*` 추가 |
| 브랜치 갱신(`--update-branch`) | 브랜치를 딴 뒤 dst의 PR base(`pr_base`)가 전진했으면 임시 worktree에서 base를 브랜치에 **merge**(GitHub의 "Update branch"와 동일, rebase 아님 — force push 없음, submodule pointer 유효 유지)하고 merge commit을 ff push. **conflict**면 merge를 abort하고 아무것도 남기지 않음 — 수동으로 해결(아래 *update-branch conflict 해결* 참고). `--dry-run`도 로컬 merge를 수행해 push 없이 conflict를 탐지(남기는 것은 없음). 플래그 없으면 base 전진을 알리기만 함. merge 커밋 identity: `GHES_SYNC_GIT_NAME`/`GHES_SYNC_GIT_EMAIL`, 없으면 git config. 이후 미러는 그 merge commit만큼 뒤처짐 — `--reverse` 참고 |
| PR | `mode = pr`이고 `dst_branch != pr_base`이면 열린 PR 재사용(`gh pr list --head --base`) 또는 커밋 목록을 본문으로 `gh pr create`; base보다 앞선 커밋이 0이면 생성 안 함 |
| 요약 | `repo · action · src · dst-before · dst-after · pr · status` 표; exit 0 / 1(repo 실패) / 2(설정·환경 오류) |

### update-branch conflict 해결 (수동)

깨끗하게 merge되는 경우만 자동이다. conflict가 나면 도구는 abort하고 아무것도 남기거나 push하지 않으므로,
본인 checkout에서 해결한 뒤 도구가 이어받게 한다:

| 위치 | 할 일 | 그다음 |
|---|---|---|
| 폐쇄망(GHES push 가능) | 본인 checkout에서 `git fetch <dst_url> <pr_base> && git merge FETCH_HEAD` → 해결 → commit → `git push <dst_url> HEAD:refs/heads/<branch>`(GHES 브랜치에 ff) | forward sync는 DST-AHEAD 표시; 미러는 `--reverse`로 맞춤 |
| 개발 기계(github.com push 가능) | 미러 checkout에서 같은 merge 후 `git push mirror <branch>` | forward sync가 FAST-FORWARD로 반영 |

conflict를 "고치려고" `--force-with-lease`/`--reset-to-base`를 쓰지 않는다 — 해결 커밋이 사라진다.

## 운용 절차

1. 미러에 작업 push(5 repo 모두 `feature/dx-agent-dev`, nested repo 먼저, 의도치 않은 submodule pointer bump 금지).
2. GHES 측 기계에서 `--dry-run`으로 요약 확인 후 실제 실행.
3. GHES에서 PR 리뷰/merge(`feature/dx-agent-dev → main`, dx_app/dx_stream은 `→ dev`). suite gate(`harness-gate`)와
   sub-repo gate(`subrepo-gate`)가 그 PR에서 실행된다.
4. GHES → 공개 export는 기존 release 절차(rsync + `release-excluded`).

## 역방향 — `--reverse` (GHES → 미러)

GHES 쪽 변경을 미러로 되가져온다: `main`/`dev`의 `dci` bot·merge 커밋, 그리고 `--update-branch`가 PR 브랜치에
추가한 merge commit(이 상태의 미러는 일반 실행에서 **DST-AHEAD**). repo별로 `reverse_branches`(기본: `branch` +
`pr_base` + `main`)의 브랜치를 GHES → 미러로 **fast-forward만** push하며 PR은 만들지 않는다. conf·토큰은 그대로
(`GHES_SYNC_DST_TOKEN` = GHES, `GHES_SYNC_SRC_TOKEN` = 미러 — 이제 *write* 권한 필요).

폐쇄망에서는 github.com push가 막혀 있으므로 **bare 캐시가 운반 매체**이고 두 단계로 나눈다(같은 노트북을
망 간 이동, 또는 `cache_dir`를 push 가능한 기계로 복사):

```bash
# 1) 폐쇄망 — GHES 접근 가능: GHES 브랜치를 캐시로 fetch, push 없음
bash internal/tools/ghes-sync/ghes-sync.sh --reverse --pull-only
# 2) 일반망 — github.com push 가능: 캐시의 GHES 브랜치를 미러에 push (GHES 접근 불필요)
bash internal/tools/ghes-sync/ghes-sync.sh --reverse --push-only
```
`--pull-only`/`--push-only` 없이 `--reverse`만 쓰면 두 단계를 한 번에 수행하며, 양쪽 host가 모두 닿는 곳에서만
의미가 있다. github.com push가 막힌 곳에서는 `cannot reach/push`로 그냥 실패한다.

브랜치별 분류: CREATE · FAST-FORWARD · UP-TO-DATE · **TO-AHEAD**(미러에 GHES가 없는 커밋 존재 — 일반 forward 실행이
push할 것이므로 할 일 없음) · **DIVERGED**(양쪽 모두 전진) → `--force-with-lease`가 없으면 실패, 있으면 사라질
미러 전용 커밋 목록을 출력한 뒤 미러 브랜치를 GHES 브랜치로 덮어쓴다(`--force-with-lease=<branch>:<방금 fetch한 미러 tip>`).
`--force-with-lease`는 `--reverse`와 함께만 허용되며, forward 방향은 절대 force하지 않는다.

### PR이 모두 merge된 뒤 — `--reverse --reset-to-base`

GHES는 PR을 squash merge하므로 `main`/`dev`에는 PR당 새 커밋 1개가 남고, 미러의 `feature/dx-agent-dev`
(원래 커밋들)는 다시는 ff가 될 수 없다. `--reset-to-base`는 repo별로 미러 브랜치를 GHES의 `pr_base`
(`main`, dx_app/dx_stream은 `dev`) tip으로 옮긴다(nested repo 먼저):

```bash
# 폐쇄망                                            # 일반망 (같은 캐시)
ghes-sync.sh --reverse --pull-only                  ghes-sync.sh --reverse --push-only --reset-to-base
```
repo별로 미러 브랜치가 이미 base에 포함되어 있으면(merge commit 방식) 단순 FAST-FORWARD, 아니면 **RESET**:
현재 미러 tip을 먼저 미러의 `backup/<branch>/<YYYYmmdd-HHMMSS>`에 저장하고(`--no-backup`으로 생략), 사라지는
미러 전용 커밋을 나열한 뒤 base tip을 `--force-with-lease=<branch>:<방금 fetch한 미러 tip>`으로 push한다 —
사용자 입장에서는 무조건 덮어쓰기이며, fetch와 push 사이에 누가 미러 브랜치에 push한 경우에만 거부된다(재실행).
`reverse_branches`(`main`/`dev` 자체)도 같은 실행에서 ff로 동기화된다. 끝나면 개발 checkout을 갱신한다:
`git fetch mirror && git reset --hard mirror/feature/dx-agent-dev`(도구가 출력; remote 이름은
`ghes` / `mirror` / `ghcloud` 규칙 — `setup_remotes.sh --rename-origin`으로 적용). `--reset-to-base`는
`--reverse`와 함께만 허용된다.

## 문제 해결

| 증상 | 의미 / 조치 |
|------|-------------|
| `DIVERGED` | GHES 브랜치에 미러가 없는 커밋 존재. 그 브랜치를 미러로 fetch → merge/rebase → 미러 push → 재실행. 도구는 절대 force-push하지 않음. |
| `gitlink … is NOT reachable` | parent가 동기화 브랜치에 없는 sub-repo 커밋을 가리킴(다른 브랜치, 또는 sub-repo가 앞 단계에서 실패). pointer를 고치거나 올바른 sub-repo 브랜치를 먼저 동기화. |
| `PR base 'dev' does not exist on dst` | 설정한 `pr_base`가 GHES에 없음 — `sync.conf` 수정. |
| `gh pr list failed` / 인증 오류 | `gh auth status --hostname gh.deepx.ai` 확인; 브랜치 push 자체는 이미 완료됨. |
| `PR skipped (no gh CLI and no dst token)` | push는 완료. `GHES_SYNC_DST_TOKEN`(curl REST) 설정 또는 `gh` 설치 후 재실행 — 기존 브랜치를 재사용. |
| `REST ... HTTP 401/404` | 토큰에 `repo` scope가 없거나 host 오류: API base는 `https://<host>/api/v3`(GHES) / `https://api.github.com`. |
| `cannot fetch src … auth/network?` / `cannot reach dst …` | private repo 자격증명이 없거나 틀림(사전 조건 참고), 또는 이 기계에서 host 접근 불가. env 토큰은 그 호출에서 credential helper보다 우선. |
| push 시 `GnuTLS recv error (-110)` / `RPC failed` | 일시적 TLS/네트워크 오류. push는 재시도되고(`GHES_SYNC_RETRIES`=3, `GHES_SYNC_RETRY_DELAY`=5초) git stderr가 표시됨. 지속되면 `git config --global http.version HTTP/1.1` 후 재실행(idempotent). |
| `dst probe timed out after 30s` | 이 기계에서 GHES 접근 불가(망 확인). `GHES_SYNC_PROBE_TIMEOUT`(probe, 기본 30초) / `GHES_SYNC_NET_TIMEOUT`(fetch/push, 기본 1800초)로 조정. |
| exit 2 + `unknown key` / `must be listed as an EARLIER [repo]` | 설정 오류 — 메시지에 섹션과 키가 표시됨. |

## 테스트

```bash
python3 -m pytest --rootdir=. internal/tools/ghes-sync/tests -q     # 네트워크 불필요: 로컬 bare repo + fake gh
```
GHES suite gate workflow(`.github/workflows/dx-agent-dev-gate-ghes.yml`, release-excluded)가 별도 step으로 이 테스트를
실행한다. 공개되는 `harness_gate.sh`/`.deepx/` 문서에는 이 디렉터리를 의도적으로 언급하지 않는다.
