# ghes-sync — 시나리오별 빠른 가이드

도구는 작업 checkout을 읽지 않는다. 자기 **bare 캐시**(`~/.cache/ghes-sync/<repo>.git`)와 `sync.conf`의 두 remote만 다룬다:
**src** = github.com 미러(`deepx-dhyang/*`), **dst** = 폐쇄망 GHES(`gh.deepx.ai/deepx/*`).
아래에서 "폐쇄망" = GHES에 접근되고 github.com은 *읽기만* 되는 기계, "일반망" = github.com에 push 가능한 기계(보통 개발 PC).
상세는 [README-KO.md](README-KO.md).

항상 `--dry-run`으로 먼저 실행한다. fetch·판정까지 실제로 수행하고 push/PR은 명령만 출력한다.

---

## 시나리오 1 — 미러 → GHES (평소 개발 흐름)

| 단계 | 어디서 | 명령 / 작업 |
|---|---|---|
| 1 | 개발 PC | 작업을 commit하고 미러에 push, nested repo 먼저: dx_app / dx_stream → dx-runtime → dx-compiler → dx-all-suite 순으로 `git push origin feature/dx-agent-dev`. 의도하지 않은 submodule pointer bump 금지. |
| 2 | 폐쇄망 | `bash internal/tools/ghes-sync/ghes-sync.sh --dry-run` — repo별 `CREATE` / `FAST-FORWARD` / `UP-TO-DATE`와 PR 계획 확인. |
| 3 | 폐쇄망 | `bash internal/tools/ghes-sync/ghes-sync.sh` — 미러 브랜치 fetch → submodule pointer 검증 → 같은 이름 브랜치를 GHES에 ff push → `pr_base`(`main`, dx_app/dx_stream은 `dev`)로 PR 생성(열린 PR 있으면 재사용). 제목 `ci: sync <repo> <branch> -> <base> (N commits)`. |
| 4 | GHES UI | PR 리뷰/merge. suite gate(`harness-gate`)와 sub-repo gate(`subrepo-gate`)가 PR에서 실행된다. |

자격증명: `GHES_SYNC_SRC_TOKEN`(github.com PAT, 읽기) + `GHES_SYNC_DST_TOKEN` 또는 `GH_ENTERPRISE_TOKEN`(GHES PAT, repo scope),
또는 `gh auth login --hostname <host> --with-token` + `gh auth setup-git`. 토큰 없이 대화형 터미널이면 git / Git Credential
Manager prompt가 허용되고, CI에서는 `--non-interactive`.

**변형**
- 브랜치를 딴 뒤 GHES base가 전진해(다른 PR merge) 브랜치를 최신으로 맞추려면 `--update-branch`. 깨끗한 merge는 자동 push
  (merge commit, rebase/force 없음). **conflict는 abort** — 본인 checkout에서 수동 해결: `git fetch <dst_url> <pr_base> && git merge FETCH_HEAD`
  → 해결 → commit → 폐쇄망이면 `git push <dst_url> HEAD:refs/heads/<branch>`(ff), 개발 PC면 미러 push 후 forward 재실행(FAST-FORWARD).
  conflict에 `--force-with-lease`/`--reset-to-base`는 쓰지 않는다.
- 일부 repo만: `--repo dx_app --repo dx-runtime`. PR 없이 push만: `--no-pr`. 태그: `--tags`.
- 요약의 `DST-AHEAD` = GHES에 미러가 없는 커밋이 있음(예: merge-update 커밋) — push할 것 없음, 시나리오 3으로 미러를 맞춤.
- `DIVERGED` = 양쪽에 서로 없는 커밋. 어느 쪽이 옳은지 결정: 미러 → 미러 checkout에서 merge/rebase 후 재실행, GHES → 시나리오 2/3에서
  `--reset-to-base` / `--force-with-lease`.

---

## 시나리오 2 — PR merge 후 GHES → 미러 (`--reverse --reset-to-base`)

GHES는 squash merge라 `main`/`dev`에 PR당 새 커밋 1개가 남고, 미러의 `feature/dx-agent-dev`는 다시는 ff가 안 된다.
이 시나리오는 미러 feature 브랜치를 GHES 통합 브랜치 tip으로 옮기고 `main`/`dev` 자체도 동기화한다.

| 단계 | 어디서 | 명령 / 작업 |
|---|---|---|
| 2.1 | 폐쇄망 | `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --pull-only` — repo별 GHES `feature/dx-agent-dev`, `pr_base`(`main`/`dev`), `main`을 캐시에 fetch. push 없음. 요약 행은 `FETCHED`. |
| 2.2 | — | 캐시를 일반망으로 반출/반입: 같은 노트북을 옮기거나 `~/.cache/ghes-sync/` 디렉터리를 복사(bare repo, 용량 ≈ repo 크기). checkout은 옮길 필요 없음. |
| 2.3 | 일반망 | `bash internal/tools/ghes-sync/ghes-sync.sh --reverse --push-only --reset-to-base --dry-run` — 계획 확인: repo별 `main`/`dev`(ff) 행과 `<repo>:feature/dx-agent-dev<=<pr_base>` 행이 `RESET`(base가 이미 브랜치를 포함하면 `FAST-FORWARD`), 사라질 미러 전용 커밋 목록. 이상 없으면 `--dry-run` 없이 실행. RESET은 먼저 `backup/feature/dx-agent-dev/<YYYYmmdd-HHMMSS>`를 미러에 push한 뒤(`--no-backup`으로 생략) 브랜치를 덮어쓴다(내부적으로 `--force-with-lease`; 그 사이 누가 미러 브랜치에 push했을 때만 거부 → 재실행). |
| 2.4 | 일반망(개발 checkout) | `git fetch origin && git checkout feature/dx-agent-dev && git reset --hard origin/feature/dx-agent-dev`(로컬 변경은 먼저 stash/commit). sub-repo도 각 디렉터리에서 동일하게(nested 먼저), suite pointer가 움직였으면 `git submodule update --init`. `main`/`dev`를 추적 중이면 `git pull --ff-only`. |

이후 forward `--dry-run`은 전부 `UP-TO-DATE`가 되어야 한다(GHES feature 브랜치는 보통 merge 시 삭제됨; 남아 있으면
`DST-AHEAD`/`DIVERGED`로 보일 수 있으나 새 작업을 push하기 전까지는 무해).

`--reset-to-base` / `--force-with-lease`는 `--reverse`와 함께만 허용되며 forward 방향은 절대 force하지 않는다.

---

## 시나리오 3 — GHES → 미러, 같은 이름 브랜치만 (`--reverse`)

history 재작성 없이 GHES 쪽에만 커밋이 생겼을 때: `main`의 `dci` bot bump, feature 브랜치의 merge-update 커밋(forward에서 `DST-AHEAD`),
release 커밋 등.

| 단계 | 어디서 | 명령 |
|---|---|---|
| 3.1 | 폐쇄망 | `ghes-sync.sh --reverse --pull-only` |
| 3.2 | — | `~/.cache/ghes-sync/` 반출·반입 |
| 3.3 | 일반망 | `ghes-sync.sh --reverse --push-only` — 브랜치별 `CREATE` / `FAST-FORWARD` / `UP-TO-DATE` / `TO-AHEAD`(미러가 앞섬: 할 일 없음, forward가 push함) |
| 3.4 | 개발 checkout | 해당 브랜치에서 `git pull --ff-only` |

여기서 `DIVERGED`는 양쪽이 모두 움직인 것. GHES가 옳으면(예: 해결한 브랜치를 GHES에 force-push한 경우) 3.3에 `--force-with-lease`를
붙여 재실행: 미러 전용 커밋을 나열한 뒤 미러 브랜치를 덮어쓴다. **sub-repo** 브랜치가 재작성됐다면 parent repo의 submodule pointer도
새 커밋으로 bump해야 하며, 아니면 forward의 gitlink 검증이 parent를 막는다.

---

## 시나리오 4 — 무언가 red일 때

| 증상 | 의미 / 조치 |
|---|---|
| `cannot fetch src … auth/network?` / `cannot reach dst` | PAT가 없거나 틀림, 또는 이 기계에서 host 접근 불가. github.com push가 막힌 곳에서 `--reverse --push-only`를 돌리면 이렇게 실패하는 것이 정상 — 2.3/3.3은 일반망에서. |
| `dst probe timed out after 30s` | 여기서 GHES 접근 불가(망 확인). `GHES_SYNC_PROBE_TIMEOUT` / `GHES_SYNC_NET_TIMEOUT`으로 조정. |
| `gitlink … is NOT reachable` | parent repo가 동기화 브랜치에 없는 sub-repo 커밋을 가리킴. pointer를 고치거나 올바른 sub-repo 브랜치를 먼저 동기화(nested repo는 항상 먼저 처리됨). |
| `PR skipped (no gh CLI and no dst token)` | 브랜치는 push됨. `GHES_SYNC_DST_TOKEN`(curl REST) 설정 또는 `gh` 설치 후 재실행 — 열린 PR 재사용. |
| `merge CONFLICT`(`--update-branch`) | 수동 해결(시나리오 1 변형). push된 것도 남은 것도 없음. |
| sub-repo gate: `suite/.deepx/tools/scripts/subrepo_check.sh: No such file` | 그 sub-repo 통합 브랜치의 gate가 구버전. 현재 gate는 suite 브랜치를 180초 기다리고 옛 suite는 명확히 거부함. gate workflow PR을 해당 sub-repo의 `main`/`dev`에 merge. |
| dx_app/dx_stream 작업이 `dev`에 있는 동안 suite `main` push run이 red | 예상된 상태. How-to-fix step이 `submodule_refs='dx_app=dev dx_stream=dev'` run을 dispatch(또는 실행 방법 안내). |

Exit code: `0` 모두 OK · `1` repo/브랜치 중 하나 이상 실패 · `2` 사용법/설정/환경 오류.
