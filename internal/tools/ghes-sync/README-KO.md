# ghes-sync — 미러 → GHES 브랜치 동기화

> 시나리오별 절차: [QUICKGUIDE-KO.md](QUICKGUIDE-KO.md) · [QUICKGUIDE.md](QUICKGUIDE.md)

`ghes-sync.sh`는 private github.com 미러(`github.com/{DEEPX-MIRROR-ORG}/*`)의 작업을 폐쇄망
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
  `https://github.com/{DEEPX-MIRROR-ORG}`, `https://gh.deepx.ai/deepx`를 쓴다. `git@…`는 넣지 않는다.
- **자격증명(양쪽 모두 private).** 동등한 두 방식:

  | | src = github.com 미러(읽기) | dst = GHES(push + PR) |
  |---|---|---|
  | 환경변수(실행 단위, 저장 없음) | `GHES_SYNC_SRC_TOKEN`(fallback `GH_TOKEN`) — fine-grained PAT, `{DEEPX-MIRROR-ORG}/*` 5개 repo에 *Contents: Read-only* | `GHES_SYNC_DST_TOKEN`(fallback `GH_ENTERPRISE_TOKEN`, 그 다음 `GHES_TOKEN`; `gh`가 PR 생성에 쓰는 변수와 동일) — `repo`(contents write + pull requests) PAT |
  | credential helper(기계당 1회) | `gh auth login --hostname github.com --with-token < pat.txt && gh auth setup-git --hostname github.com` | `gh auth login --hostname gh.deepx.ai [--with-token < pat.txt] && gh auth setup-git --hostname gh.deepx.ai` |

  환경변수를 쓰면 도구가 호출마다 `git -c http.https://<host>/.extraheader=AUTHORIZATION: basic <base64>`로 토큰을 전달한다 —
  URL·`.git/config`·출력에 남지 않는다(CI workflow와 같은 기법). 자격증명이 전혀 없으면 git은 비밀번호 prompt에서 멈추는데,
  도구가 `GIT_TERMINAL_PROMPT=0`을 설정하므로 인증 힌트와 함께 즉시 실패한다. 폐쇄망 기계에서 `gh auth login`은
  `--with-token`으로 브라우저 없이 가능하고, `https://github.com/login/device`를 열 수 있으면 device/web 흐름도 된다.
- env 토큰과 credential helper가 둘 다 있으면 해당 호출에는 header(env 토큰)가 우선한다.
- **비대화형 전용.** 도구는 절대 묻지 않는다(`GIT_TERMINAL_PROMPT=0`, PAT prompt 없음) — 대화형 로그인은 실제로 안정적으로
  인증되지 않았다. host에 접근하기 전에 **자격증명 preflight**를 수행한다: 해당 쪽 토큰 env가 없으면 git credential helper에
  묻고(`git credential fill`, prompt 없음), 응답이 없으면 env 변수 이름과
  `gh auth login --hostname <host> --with-token && gh auth setup-git --hostname <host>`를 힌트로 출력하며 즉시 실패한다.
  CI에서는 PAT를 secret으로 주입한다.

## 빠른 시작

```bash
cd <dx-all-suite>                                   # internal/ 이 있는 checkout
bash internal/tools/ghes-sync/ghes-sync.sh --print-config      # 무엇을 어디로 보낼지
bash internal/tools/ghes-sync/ghes-sync.sh --dry-run           # fetch + 분류, push/gh 명령만 출력
bash internal/tools/ghes-sync/ghes-sync.sh                     # push + PR 보장
bash internal/tools/ghes-sync/ghes-sync.sh --repo dx_app --no-pr   # repo 하나, push만
bash internal/tools/ghes-sync/ghes-sync.sh --reviewers dci          # + push가 들어간 PR마다 리뷰 봇 재요청
```

## 설정 — `sync.conf` + `sync.override.conf`

`sync.conf`는 commit되어 공유되는 파일이다. **개인 값을 여기에 넣지 말 것**(계속 `git status`에 남는다). 옆의
`sync.override.conf`에 넣는다 — gitignore 대상, 같은 INI 형식, `sync.conf` 위에 덮어씀:

```bash
cp internal/tools/ghes-sync/sync.override.conf.example internal/tools/ghes-sync/sync.override.conf
# 그 파일에서 src_host(본인 미러 org)와 branch(본인 feature 브랜치)를 설정
```
두 키는 `sync.conf`에서 의도적으로 비어 있다. 설정되기 전(override 파일, `--override FILE`, 또는
`GHES_SYNC_SRC_HOST` / `GHES_SYNC_BRANCH` env)까지 도구는 exit 2와 힌트로 멈춘다. `--print-config`가 적용된 override 파일을 보여 준다.


```ini
[defaults]
src_host  =                                 # 필수 — 본인 private 미러 org, 예: https://github.com/{DEEPX-MIRROR-ORG}
                                            # (https 전용; 또는 export GHES_SYNC_SRC_HOST). 비어 있으면 exit 2 + 힌트
dst_host  = https://gh.deepx.ai/deepx
branch    =                                 # 필수 — 본인 feature 브랜치, 예: feature/my-topic
                                            # (또는 export GHES_SYNC_BRANCH); dst_branch 기본값은 같은 이름
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
| reviewers (`reviewers = dci` / `--reviewers dci`) | 브랜치가 실제로 움직인 push(CREATE / FAST-FORWARD) 뒤 PR이 있거나 생성되면 그 reviewer를 (재)요청(`gh pr edit --add-reviewer` 또는 REST `POST …/requested_reviewers`). GHES 리뷰 봇(`dci`, n8n)은 PR이 열릴 때만 돌고 이후 push에는 **돌지 않는다** — reviewer 재요청이 봇을 다시 깨운다(UI의 "Re-request review" 버튼과 같은 webhook). 설정이 없으면 off; 실패는 warning이며 sync 자체는 성공. 리뷰 결과 처리는 `internal/tools/pr-review-apply` 참고 |
| 요약 | `repo · action · src · dst-before · dst-after · pr · status` 표 — 셀은 ASCII만 써서 열이 어긋나지 않음; `status`는 `OK` / `FAIL`이고 `[n]`은 표 아래의 번호 붙은 설명을 가리킴(긴 설명은 표 안에 넣지 않음); exit 0 / 1(repo 실패) / 2(설정·환경 오류) |
| 출력 형식 | 메시지는 출력 언어를 따름(*출력 언어* 절 참고: 한국어 locale이면 국문, 그 외 영문; action 이름·환경변수·git 명령 같은 기술 용어는 두 언어에서 동일). repo별 줄은 `[ghes-sync] <repo(:branch)>  │ 메시지` 형식으로, repo key를 실행마다 한 폭으로 맞춰 `│` 열이 정렬됨; `▶`는 repo 시작, `WARNING:` / `FAIL:`은 문제 표시 |


### base가 전진했을 때: 기본 실행 vs `--update-branch`

브랜치를 딴 뒤 GHES의 `pr_base`(`main` / `dev`)에 새 커밋이 들어오면(그 사이 merge된 다른 PR, dci bump 등) 아래 줄이 나온다:

```
[ghes-sync] dx_stream    │ base 'dev' 에 feature/dx-agent-dev 가 없는 새 commit 2 개 — PR 이 base 와 최신 상태가 아닙니다; --update-branch 로 재실행하면 base 를 브랜치에 merge 합니다
```

이것은 **실패가 아니라 안내**다: push와 PR 생성은 그대로 진행된다. `--update-branch`는 선택 사항이다.

| | 기본 (플래그 없음) | `--update-branch` |
|---|---|---|
| GHES에 올라가는 것 | 미러 브랜치 **그대로** (미러 == GHES 브랜치) | 미러 브랜치 + **merge commit 1개** (`Merge <base> into <branch> (ghes-sync --update-branch)`) — base를 브랜치에 merge; rebase·force push 없음 |
| base가 전진한 경우 | 안내만 출력. PR은 생성되고 GHES가 merge 시점에 현재 base와 합친다(test-merge) — conflict가 없으면 그대로 merge 가능 | 도구가 먼저 merge하므로 PR 브랜치 자체가 base를 포함. **conflict면 아무것도 push하지 않고** 수동 절차를 안내 |
| conflict를 알게 되는 시점 | PR 화면("This branch has conflicts") | 실행 즉시 — `--dry-run --update-branch`로 push 없이 사전 확인 |
| PR의 CI | `pull_request` CI는 GHES의 test-merge에서 돌아가므로 base 변경분 포함 | 브랜치 tip에 base가 들어 있어 `push` CI도 포함 |
| 이후 미러 상태 | 변화 없음 — 다음 forward 실행은 `UP-TO-DATE` | GHES가 merge commit만큼 앞섬(`DST-AHEAD`) — github.com push 가능한 곳에서 `--reverse`(아래 *역방향* 참고)로 되가져와야 미러가 맞춰짐 |
| 쓰는 경우 | 대부분 | (1) PR 화면에 conflict가 뜰 때, (2) branch protection이 "branches up to date before merging"을 요구할 때, (3) merge 전에 브랜치+base 상태로 gate를 돌려 보고 싶을 때 |

GHES PR 화면의 **Update branch** 버튼은 `--update-branch`와 같은 일을 한다(GHES 브랜치에 merge commit 추가). 어느 쪽을 쓰든
그 뒤 미러가 뒤처지므로 `--reverse`로 마무리한다. 권장 순서: 플래그 없이 실행 → PR 확인 → conflict가 뜬
repo만 `--update-branch --repo <name>`.

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
의미가 있다. github.com push가 막힌 곳에서는 `접근할 수 없음` / `push 실패`로 그냥 실패한다.

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
ghes-sync.sh --reverse --pull-only --reset-to-base  ghes-sync.sh --reverse --push-only --reset-to-base
```
repo별로 미러 브랜치가 이미 base에 포함되어 있으면(merge commit 방식) 단순 FAST-FORWARD, 아니면 **RESET**:
현재 미러 tip을 먼저 미러의 `backup/<branch>/<YYYYmmdd-HHMMSS>`에 저장하고(`--no-backup`으로 생략), 사라지는
미러 전용 커밋을 나열한 뒤 base tip을 `--force-with-lease=<branch>:<방금 fetch한 미러 tip>`으로 push한다 —
사용자 입장에서는 무조건 덮어쓰기이며, fetch와 push 사이에 누가 미러 브랜치에 push한 경우에만 거부된다(재실행).
`reverse_branches`(`main`/`dev` 자체)도 같은 실행에서 ff로 동기화된다. 끝나면 개발 checkout을 갱신한다:
`git fetch mirror && git reset --hard mirror/feature/dx-agent-dev`(도구가 출력; remote 이름은
`ghes` / `mirror` 규칙 — `setup_remotes.sh --rename-origin`으로 적용).

**GHES 쪽도 함께.** 그 실행에서 GHES에 접근 가능하면(`--pull-only` 포함) `--reset-to-base`는 squash merge로 diverged된
GHES feature 브랜치도 reset한다: 옛 tip을 GHES `backup/<branch>/<ts>`에 저장하고, 그 head의 merged PR을 조회(dst token이
있으면 REST, 아니면 `gh`; 없거나 클라이언트가 없으면 경고만)한 뒤 GHES `<branch>` := `<pr_base>` tip을 `--force-with-lease`로
push한다 — 행 `<repo>:<branch><=<pr_base>@GHES`(GHES가 merge 시 브랜치를 지웠으면 `CREATE`). 따라서 폐쇄망 단계는
`--reverse --pull-only --reset-to-base`, 일반망 단계는 `--reverse --push-only --reset-to-base`이고, 다음 forward는 양쪽 모두 `UP-TO-DATE`다.

`--reset-to-base`는 `--reverse`와 함께만 허용된다.

## 출력 언어

메시지는 국문 또는 영문으로 출력된다. 선택 순서: `--lang ko|en` > `GHES_SYNC_LANG` > 터미널 locale(`LC_ALL` >
`LC_MESSAGES` > `LANG`; 값이 `ko`로 시작하면 국문, 그 외 — `C`나 미설정 포함 — 영문). 다른 값은 exit 2. action 단어
(`CREATE`, `FAST-FORWARD`, `DST-AHEAD`, `DIVERGED`, `DRY-RUN`, `FAIL`, `WARNING`, `SKIPPED`), 환경변수/옵션 이름, git 명령은
두 언어에서 같으므로 이를 grep하는 스크립트는 그대로 동작한다; `--help`도 같은 선택을 따른다. 이 문서의 예시는 국문
메시지를, [README.md](README.md)는 영문 메시지를 인용한다.

```bash
bash internal/tools/ghes-sync/ghes-sync.sh --lang en --dry-run     # locale과 무관하게 영문
GHES_SYNC_LANG=ko bash internal/tools/ghes-sync/ghes-sync.sh       # locale과 무관하게 국문
```

## 문제 해결

| 증상 | 의미 / 조치 |
|------|-------------|
| `DIVERGED` | GHES 브랜치에 미러가 없는 커밋 존재. 그 브랜치를 미러로 fetch → merge/rebase → 미러 push → 재실행. 도구는 절대 force-push하지 않음. |
| `gitlink … NOT reachable` | parent가 동기화 브랜치에 없는 sub-repo 커밋을 가리킴(다른 브랜치, 또는 sub-repo가 앞 단계에서 실패). pointer를 고치거나 올바른 sub-repo 브랜치를 먼저 동기화. |
| `PR base 'dev' does not exist on dst` | 설정한 `pr_base`가 GHES에 없음 — `sync.conf` 수정. |
| `gh pr list failed` / 인증 오류 | `gh auth status --hostname gh.deepx.ai` 확인; 브랜치 push 자체는 이미 완료됨. |
| `PR 생성 SKIP (gh CLI 없음, dst token 없음)` | push는 완료. `GHES_SYNC_DST_TOKEN` / `GH_ENTERPRISE_TOKEN` / `GHES_TOKEN`(curl REST) 설정 또는 `gh` 설치 후 재실행 — 기존 브랜치를 재사용. |
| `REST ... HTTP 401/404` | 토큰에 `repo` scope가 없거나 host 오류: API base는 `https://<host>/api/v3`(GHES) / `https://api.github.com`. |
| `src […] 를 fetch 할 수 없음` / `dst(GHES) 에 접근할 수 없음 — git: … — … REJECTED / NETWORK` | private repo 자격증명이 없거나 틀림(사전 조건 참고), 또는 이 기계에서 host 접근 불가. env 토큰은 그 호출에서 credential helper보다 우선. |
| push 시 `GnuTLS recv error (-110)` / `RPC failed` | 일시적 TLS/네트워크 오류. push는 재시도되고(`GHES_SYNC_RETRIES`=3, `GHES_SYNC_RETRY_DELAY`=5초) git stderr가 표시됨. 지속되면 `git config --global http.version HTTP/1.1` 후 재실행(idempotent). |
| `probe N/3 회 실패 — 일시적 network/TLS 오류` | `ls-remote` probe의 일시적 TLS 오류(GnuTLS -110 등); push처럼 probe도 재시도(`GHES_SYNC_RETRIES`). 마지막 시도까지 실패해야 repo가 FAIL이 되고, 메시지에 `N회 시도 후에도 실패`가 붙음. |
| `cache 정리: … 삭제된 브랜치의 옛 사본 제거 — <branches>` | 정보성: 원격에서 삭제된 브랜치(예: squash-merge 후 지운 feature 브랜치)를 bare cache에서 제거해 DIVERGED로 오판되지 않게 함. |
| `probe timeout (30초, GHES_SYNC_PROBE_TIMEOUT 초과)` | 이 기계에서 GHES 접근 불가(망 확인). `GHES_SYNC_PROBE_TIMEOUT`(probe, 기본 30초) / `GHES_SYNC_NET_TIMEOUT`(fetch/push, 기본 1800초)로 조정. |
| exit 2 + `unknown key` / `must be listed as an EARLIER [repo]` | 설정 오류 — 메시지에 섹션과 키가 표시됨. |

## 테스트

```bash
python3 -m pytest --rootdir=. internal/tools/ghes-sync/tests -q     # 네트워크 불필요: 로컬 bare repo + fake gh
```
GHES suite gate workflow(`.github/workflows/dx-agent-dev-gate-ghes.yml`, release-excluded)가 별도 step으로 이 테스트를
실행한다. 공개되는 `harness_gate.sh`/`.deepx/` 문서에는 이 디렉터리를 의도적으로 언급하지 않는다.
