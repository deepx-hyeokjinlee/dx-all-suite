# ghes-sync — 시나리오별 빠른 가이드

도구는 작업 checkout을 읽지 않는다. 자기 **bare 캐시**(`~/.cache/ghes-sync/<repo>.git`)와 `sync.conf`의 두 remote만 다룬다:
**src** = github.com 미러(`{DEEPX-MIRROR-ORG}/*`), **dst** = 폐쇄망 GHES(`gh.deepx.ai/deepx/*`).
아래에서 "폐쇄망" = GHES에 접근되고 github.com은 *읽기만* 되는 기계, "일반망" = github.com에 push 가능한 기계(보통 개발 PC).
상세는 [README-KO.md](README-KO.md).

항상 `--dry-run`으로 먼저 실행한다. fetch·판정까지 실제로 수행하고 push/PR은 명령만 출력한다.

## remote 네이밍 규칙 (개발 checkout)

| remote | URL | 역할 |
|---|---|---|
| `ghes` | `https://gh.deepx.ai/deepx/<repo>.git` | 폐쇄망 SCM (원천) |
| `mirror` | `https://github.com/{DEEPX-MIRROR-ORG}/<repo>.git` | sync 도구가 읽고 쓰는 private 미러 |
| `ghcloud` | `https://github.com/DEEPX-AI/<repo>.git` | 공개 채널 — `ghcloud_url`을 설정한 repo **전용**(현재: `dx_fw`) |

공개 채널은 보통 GHES release export로 만들어지는 것이라 개발용 remote가 아니다. 그것이 실제 소스인
유일한 repo는 시나리오 5 참고.
suite와 4개 harness sub-repo에 한 번에 적용한다(idempotent; `--rename-origin`은 두 URL 중 하나와 같은
`origin`을 그 이름으로 바꿈; `--dry-run`은 계획만 출력):
```bash
bash internal/tools/ghes-sync/setup_remotes.sh --rename-origin
```
아래 모든 명령은 이 이름을 쓴다. remote URL에 토큰을 넣지 말 것 — credential helper 또는
`GHES_SYNC_*_TOKEN`을 쓴다. URL 속 PAT는 `.git/config`, `git remote -v` 출력, 붙여 넣은 로그에 그대로 남는다.

---

## 시나리오 1 — 미러 → GHES (평소 개발 흐름)

| 단계 | 어디서 | 명령 / 작업 |
|---|---|---|
| 1 | 개발 PC | 작업을 commit하고 미러에 push, nested repo 먼저: dx_app / dx_stream → dx-runtime → dx-compiler → dx-all-suite 순으로 `git push mirror feature/dx-agent-dev`. 의도하지 않은 submodule pointer bump 금지. |
| 2 | 폐쇄망 | `bash internal/tools/ghes-sync/ghes-sync.sh --dry-run` — repo별 `CREATE` / `FAST-FORWARD` / `UP-TO-DATE`와 PR 계획 확인. |
| 3 | 폐쇄망 | `bash internal/tools/ghes-sync/ghes-sync.sh` — 미러 브랜치 fetch → submodule pointer 검증 → 같은 이름 브랜치를 GHES에 ff push → `pr_base`(`main`, dx_app/dx_stream은 `dev`)로 PR 생성(열린 PR 있으면 재사용). 제목 `ci: sync <repo> <branch> -> <base> (N commits)`. |
| 4 | GHES UI | PR 리뷰/merge. suite gate(`harness-gate`)와 sub-repo gate(`subrepo-gate`)가 PR에서 실행된다. |

자격증명: `GHES_SYNC_SRC_TOKEN`(github.com PAT, 읽기) + `GHES_SYNC_DST_TOKEN` 또는 `GH_ENTERPRISE_TOKEN` 또는 `GHES_TOKEN`(GHES PAT, repo scope),
또는 `gh auth login --hostname <host> --with-token` + `gh auth setup-git --hostname <host>`. 도구는 절대 묻지 않는다:
둘 다 없는 host는 첫 fetch 전에 정확한 해결 명령과 함께 실패한다. 첫 실행 전 `cp internal/tools/ghes-sync/sync.override.conf.example internal/tools/ghes-sync/sync.override.conf` 후
그 파일에 `src_host`(본인 미러 org)와 `branch`(본인 feature 브랜치)를 설정한다 — gitignore 대상이며 공유 `sync.conf` 위에 덮어씌워진다.
`sync.conf`의 두 키는 의도적으로 비어 있고, 채우지 않으면(또는 `GHES_SYNC_SRC_HOST` / `GHES_SYNC_BRANCH` export) 시작을 거부한다.

**변형**
- 브랜치를 딴 뒤 GHES base가 전진해(다른 PR merge) 브랜치를 최신으로 맞추려면 `--update-branch`. 깨끗한 merge는 자동 push
  (merge commit, rebase/force 없음). **conflict는 abort** — 본인 checkout에서 수동 해결: `git fetch ghes <pr_base> && git merge ghes/<pr_base>`
  → 해결 → commit → 폐쇄망이면 `git push ghes HEAD:refs/heads/<branch>`(ff), 개발 PC면 `git push mirror feature/dx-agent-dev` 후 forward 재실행(FAST-FORWARD).
  conflict에 `--force-with-lease`/`--reset-to-base`는 쓰지 않는다.
- 일부 repo만: `--repo dx_app --repo dx-runtime`. PR 없이 push만: `--no-pr`. 태그: `--tags`.
- push 뒤 리뷰 봇 다시 돌리기: `--reviewers dci` (또는 `sync.override.conf`에 `reviewers = dci`). 봇은 PR이 열릴 때만 리뷰하고 이후 push에는 돌지 않는다; reviewer 재요청이 봇을 깨운다. 리뷰 항목 처리는 `internal/tools/pr-review-apply/README-KO.md` 참고.
- 요약의 `DST-AHEAD` = GHES에 미러가 없는 커밋이 있음(예: merge-update 커밋) — push할 것 없음, 시나리오 3으로 미러를 맞춤.
- `DIVERGED` = 양쪽에 서로 없는 커밋. 어느 쪽이 옳은지 결정: 미러 → 미러 checkout에서 merge/rebase 후 재실행, GHES → 시나리오 2/3에서
  `--reset-to-base` / `--force-with-lease`.

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
| 이후 미러 상태 | 변화 없음 — 다음 forward 실행은 `UP-TO-DATE` | GHES가 merge commit만큼 앞섬(`DST-AHEAD`) — github.com push 가능한 곳에서 `--reverse`(시나리오 3)로 되가져와야 미러가 맞춰짐 |
| 쓰는 경우 | 대부분 | (1) PR 화면에 conflict가 뜰 때, (2) branch protection이 "branches up to date before merging"을 요구할 때, (3) merge 전에 브랜치+base 상태로 gate를 돌려 보고 싶을 때 |

GHES PR 화면의 **Update branch** 버튼은 `--update-branch`와 같은 일을 한다(GHES 브랜치에 merge commit 추가). 어느 쪽을 쓰든
그 뒤 미러가 뒤처지므로 시나리오 3(`--reverse`)으로 마무리한다. 권장 순서: 플래그 없이 실행 → PR 확인 → conflict가 뜬
repo만 `--update-branch --repo <name>`.

---

## 시나리오 2 — PR merge 후 GHES → 미러 (`--reverse --reset-to-base`)

GHES는 squash merge라 `main`/`dev`에 PR당 새 커밋 1개가 남고, **양쪽** `feature/dx-agent-dev` — 미러의 것과 GHES에 남은
것 — 모두 base와 diverged 상태가 된다. `--reset-to-base`는 둘을 모두 base tip으로 옮기고(GHES 쪽은 GHES 접근 가능한 곳에서,
미러 쪽은 github.com push 가능한 곳에서) `main`/`dev` 자체도 동기화한다.

| 단계 | 어디서 | 명령 / 작업 |
|---|---|---|
| 2.1 | 폐쇄망 | `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --pull-only --reset-to-base --dry-run` 확인 후 `--dry-run` 없이 실행 — repo별 GHES `pr_base`(`main`/`dev`), `main`을 캐시에 fetch(행 `FETCHED`)하고 **GHES feature 브랜치를 reset**: 행 `<repo>:feature/dx-agent-dev<=<pr_base>@GHES` — merge 전 옛 브랜치가 남아 있으면 `RESET`(tip을 먼저 GHES `backup/feature/dx-agent-dev/<ts>`에 저장, GHES에만 있는 커밋 목록 출력, 그 tip이 head인 merged PR이 있는지 확인 — dst token이 있으면 REST, 아니면 `gh`; 둘 다 없으면 직접 확인하라는 안내만), merge 시 삭제되어 없으면 `CREATE`(base tip으로 재생성), 이미 같으면 `UP-TO-DATE`. 내부적으로 `--force-with-lease`; 이 단계에서 미러에는 아무것도 push하지 않는다. |
| 2.2 | — | 캐시를 일반망으로 반출/반입: 같은 노트북을 옮기거나 `~/.cache/ghes-sync/` 디렉터리를 복사(bare repo, 용량 ≈ repo 크기). checkout은 옮길 필요 없음. |
| 2.3 | 일반망 | **이 단계 전에 미러 `feature/dx-agent-dev`의 미러 전용 커밋이 모두 GHES에 반영(cherry-pick/merge)되었는지 확인** — RESET은 그 커밋들을 브랜치에서 제거한다(`backup/…`에는 남음). `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --push-only --reset-to-base --dry-run` — 계획 확인: repo별 `main`/`dev`(ff) 행과 `<repo>:feature/dx-agent-dev<=<pr_base>` 행이 `RESET`(base가 이미 브랜치를 포함하면 `FAST-FORWARD`), 사라질 미러 전용 커밋 목록. 이상 없으면 `--dry-run` 없이 실행. RESET은 먼저 `backup/feature/dx-agent-dev/<YYYYmmdd-HHMMSS>`를 미러에 push한 뒤(`--no-backup`으로 생략) 브랜치를 덮어쓴다(내부적으로 `--force-with-lease`; 그 사이 누가 미러 브랜치에 push했을 때만 거부 → 재실행). |
| 2.4 | 일반망(개발 checkout) | `git fetch mirror && git checkout feature/dx-agent-dev && git reset --hard mirror/feature/dx-agent-dev`(로컬 변경은 먼저 stash/commit). sub-repo도 각 디렉터리에서 동일하게(nested 먼저) — suite pointer가 sub-repo tip과 같아졌으므로 `git submodule update`도 된다. `main`/`dev`를 추적 중이면 `git pull --ff-only mirror main`(또는 `dev`). |

이후 forward `--dry-run`은 전부 `UP-TO-DATE`가 되어야 한다: 양쪽 feature 브랜치가 base tip에 있으므로 다음 실제 커밋은
`FAST-FORWARD`로 올라간다. (2.1이 GHES 쪽도 reset하기 전에는 GHES에 남은 옛 브랜치가 여기서 `DST-AHEAD`/`DIVERGED`로 보여
손으로 지워야 했다.) reverse 요약의 `@GHES` 행은 `ghes` 열이 base tip, `mirror-before/after`가 GHES 브랜치의 전/후 — GHES만 다루는 행이다.

`--reset-to-base` / `--force-with-lease`는 `--reverse`와 함께만 허용되며 forward 방향은 절대 force하지 않는다.

---

**`main`/`dev`도 같은 실행에서 동기화된다.** `reverse_branches` 기본값이 *branch + pr_base + main*이므로 `--reverse`
(`--reset-to-base` 유무와 무관)는 미러의 `main`·`dev`도 GHES로 ff한다 — 별도 단계 불필요. `main`/`dev` 행의
`TO-AHEAD`는 미러에 GHES가 없는 커밋이 있다는 뜻이고 도구는 건드리지 않는다(forward는 feature만 동기화). 먼저 이유를
확인한다(`git log ghes/main..mirror/main`): GHES가 되감긴 것이고 GHES가 옳으면 `--force-with-lease`로 재실행, 미러에
진짜 작업이 있으면 먼저 GHES에 올린다.

### `--reverse`가 repo별로 맞추는 브랜치

`--reverse`는 **같은 이름** 브랜치를 GHES → 미러로 push한다. 대상은 `reverse_branches`가 있으면 그 목록, 없으면
**`branch` + `pr_base` + `main`**(중복 제거). `--reset-to-base`는 여기에 "GHES `pr_base` → 미러 `branch`" 한 행을
추가하고, 대신 `branch`의 같은-이름 동기화는 *건너뛴다*(곧 덮어쓸 대상이므로). `branch = feature/X`일 때:

| repo | `pr_base` | `--reverse`만 (같은 이름 → 같은 이름) | `--reset-to-base` 추가 |
|---|---|---|---|
| dx_app, dx_stream | dev | `feature/X`, `dev`, `main` | 미러 `feature/X` ← GHES `dev` (`feature/X` 같은-이름 동기화는 생략) |
| dx-runtime, dx-compiler, dx-all-suite | main | `feature/X`, `main` | 미러 `feature/X` ← GHES `main` |

repo별 헤더 로그가 이것을 그대로 보여 준다: `같은 이름으로 sync: dev main | reset: mirror feature/X <= GHES dev`.
`reverse_branches`는 `[defaults]`(모든 repo)와 `[repo NAME]` 섹션(그 repo만, defaults보다 우선) 어디에나 둘 수 있고,
쓰지 않으면 위 표가 기본이다.

## 시나리오 3 — GHES → 미러, 같은 이름 브랜치만 (`--reverse`)

history 재작성 없이 GHES 쪽에만 커밋이 생겼을 때: `main`의 `dci` bot bump, feature 브랜치의 merge-update 커밋(forward에서 `DST-AHEAD`),
release 커밋 등.

| 단계 | 어디서 | 명령 |
|---|---|---|
| 3.1 | 폐쇄망 | `ghes-sync.sh --reverse --pull-only` |
| 3.2 | — | `~/.cache/ghes-sync/` 반출·반입 |
| 3.3 | 일반망 | `ghes-sync.sh --reverse --push-only` — 브랜치별 `CREATE` / `FAST-FORWARD` / `UP-TO-DATE` / `TO-AHEAD`(미러가 앞섬: 할 일 없음, forward가 push함) |
| 3.4 | 개발 checkout | 해당 브랜치에서 `git pull --ff-only mirror <branch>` |

여기서 `DIVERGED`는 양쪽이 모두 움직인 것. GHES가 옳으면(예: 해결한 브랜치를 GHES에 force-push한 경우) 3.3에 `--force-with-lease`를
붙여 재실행: 미러 전용 커밋을 나열한 뒤 미러 브랜치를 덮어쓴다. **sub-repo** 브랜치가 재작성됐다면 parent repo의 submodule pointer도
새 커밋으로 bump해야 하며, 아니면 forward의 gitlink 검증이 parent를 막는다.

---

## 시나리오 4 — 무언가 red일 때

메시지는 터미널 언어로 나온다(한국어 locale → 국문, 그 외 영문; `--lang ko|en` 또는 `GHES_SYNC_LANG`으로 강제).
아래 표는 국문 문구를, [QUICKGUIDE.md](QUICKGUIDE.md)는 영문 문구를 인용한다. action 단어·환경변수·git 명령은 두 언어에서 같다.

| 증상 | 의미 / 조치 |
|---|---|
| push 시 `GnuTLS recv error (-110)` / `RPC failed` / `early EOF` | 이 기계와 github.com 사이의 일시적 TLS/네트워크 문제(Debian GnuTLS git을 쓰는 Orange Pi에서 관찰). 도구는 push를 3회 재시도(`GHES_SYNC_RETRIES`, `GHES_SYNC_RETRY_DELAY`)하고 git의 실제 에러를 출력한다. 계속 실패하면 `git config --global http.version HTTP/1.1`(및 `http.postBuffer 524288000`) 후 **같은 명령을 다시 실행** — 모든 단계는 idempotent: 끝난 행은 UP-TO-DATE, 기존 백업은 재사용. |
| `mirror(to) / GHES(from) 에 접근할 수 없음 — git: Authentication failed … — GH_TOKEN 의 token이 REJECTED` | 도구가 사용한 토큰(메시지에 이름 표시)이 거부됨: revoke/만료(예: 유출 후 폐기), org 불일치, 미러 repo에 `Contents` 권한 없음. 새 PAT 발급; `GHES_SYNC_SRC_TOKEN`이 `GH_TOKEN`보다, `GHES_SYNC_DST_TOKEN`이 `GH_ENTERPRISE_TOKEN`보다 우선 — 어느 것이 export되어 있는지 확인. |
| `… 접근할 수 없음 — git: Could not resolve host / unable to access — NETWORK 문제` | 인증이 아닌 네트워크 문제: 이 기계에서 host에 닿지 않음(망, proxy, DNS). |
| `probe N/3 회 실패 — 일시적 network/TLS 오류 … 재시도` | `ls-remote` probe의 일시적 TLS 오류(GnuTLS -110). probe도 재시도되며(`GHES_SYNC_RETRIES`=3, `GHES_SYNC_RETRY_DELAY`=5초) 마지막까지 실패하면 `N회 시도 후에도 실패 — … NETWORK`로 FAIL. 인증 문제가 아님. |
| `src […] 를 fetch 할 수 없음` / `dst(GHES) 에 접근할 수 없음` | PAT가 없거나 틀림, 또는 이 기계에서 host 접근 불가. github.com push가 막힌 곳에서 `--reverse --push-only`를 돌리면 이렇게 실패하는 것이 정상 — 2.3/3.3은 일반망에서. |
| `probe timeout (30초, GHES_SYNC_PROBE_TIMEOUT 초과)` | 여기서 GHES 접근 불가(망 확인). `GHES_SYNC_PROBE_TIMEOUT` / `GHES_SYNC_NET_TIMEOUT`으로 조정. |
| sub-repo PR이 squash merge된 직후, 미러에 NEW feature 브랜치가 있는데 `DIVERGED` | GHES에 merge 전 `feature/<X>`가 남아 있음(merge는 브랜치를 지우지 않음). 재구성된 미러 브랜치와 공통 조상이 없고, 내용은 이미 `main`/`dev`에 있으므로 GHES에서 삭제(`git push ghes --delete feature/<X>` 또는 GHES UI) 후 재실행 — CREATE로 바뀐다. |
| `gitlink … NOT reachable` | parent repo가 동기화 브랜치에 없는 sub-repo 커밋을 가리킴. pointer를 고치거나 올바른 sub-repo 브랜치를 먼저 동기화(nested repo는 항상 먼저 처리됨). |
| `PR 생성 SKIP (gh CLI 없음, dst token 없음)` | 브랜치는 push됨. 도구가 읽는 변수는 `GHES_SYNC_DST_TOKEN`, `GH_ENTERPRISE_TOKEN`, `GHES_TOKEN` 셋뿐 — 다른 이름의 변수는 보이지 않음. 그중 하나를 export(curl REST) 또는 `gh` 설치 후 재실행 — 열린 PR 재사용. |
| `cache 정리: GHES 에서 삭제된 브랜치의 옛 사본 제거 — …` | 정보성: GHES에 이미 없는 브랜치(squash-merge 후 삭제)의 `refs/remotes/dst/<branch>`가 bare cache에 남아 있어 제거함 — DIVERGED로 오판되지 않게 하는 조치. |
| `merge CONFLICT`(`--update-branch`) | 수동 해결(시나리오 1 변형). push된 것도 남은 것도 없음. |
| sub-repo gate: `suite/.deepx/tools/scripts/subrepo_check.sh: No such file` | 그 sub-repo 통합 브랜치의 gate가 구버전. 현재 gate는 suite 브랜치를 180초 기다리고 옛 suite는 명확히 거부함. gate workflow PR을 해당 sub-repo의 `main`/`dev`에 merge. |
| dx_app/dx_stream 작업이 `dev`에 있는 동안 suite `main` push run이 red | 예상된 상태. How-to-fix step이 `submodule_refs='dx_app=dev dx_stream=dev'` run을 dispatch(또는 실행 방법 안내). |

Exit code: `0` 모두 OK · `1` repo/브랜치 중 하나 이상 실패 · `2` 사용법/설정/환경 오류.

---

## 시나리오 5 — `dx_fw`: 필요한 내용이 공개 채널에만 있을 때

`dx_fw`의 소스는 GHES에 있지만, 실제로 굽는 `fw.bin`은 `github.com/DEEPX-AI/dx_fw`에만 올라온다.
어느 쪽을 미러링해도 틀리므로 이 repo는 `sync.conf`에서 `sync = off`이고, sync 실행에는
`SKIPPED (sync=off)` 한 줄로만 나온다.

```bash
bash internal/tools/ghes-sync/setup_remotes.sh --checkout-ghcloud
git -C dx-runtime/dx_fw log --oneline -1           # 공개 채널의 tip
```

(새로 clone한 경우 디렉터리는 아직 비어 있고 — `submodule update --init`이 건너뛴다 — 같은 명령이 그
자리에 clone해 준다.)

`dx-runtime`에 적용되는 것(local config 전용 — `.gitmodules`는 GHES repo 소유):

| 설정 | 이유 |
|---|---|
| `submodule.dx_fw.url` → ghcloud | mirror org에는 clone할 `dx_fw` repo가 없다 |
| `submodule.dx_fw.update = none` | 기록된 gitlink가 공개 history에 없는 GHES commit이라, `git submodule update --init`이 전체 실패하지 않고 건너뛰어야 한다 |
| `submodule.dx_fw.ignore = all` | 체크아웃된 내용이 gitlink와 다른 것이 **의도된 상태**다 |

GHES 소스로 되돌리려면 `git -C dx-runtime config --unset-all submodule.dx_fw.url`(`.update`/`.ignore`도)
실행 후 `git -C dx-runtime/dx_fw checkout ghes-main`. 그 checkout의 `ghes` remote는 그대로 두므로 두
history를 나란히 쓸 수 있다.

