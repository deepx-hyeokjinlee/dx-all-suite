# pr-review-apply — GHES PR에 달린 봇 코드리뷰 처리

> English: [README.md](README.md) · skill `dx-internal-pr-review-apply`
> (`.deepx/skills/dx-internal-pr-review-apply/`)가 이 도구를 구동. 의도적으로 로컬 전용: 개발자가 자기 PC에서
> 자기 agent로 실행한다. CI 판은 없다(workflow run은 항목별 질문을 할 수 없고 runner에 agent CLI + 모델 접근이 필요).

폐쇄망 GHES(`gh.deepx.ai/deepx/*`)에 PR이 열리면 n8n 자동화가 리뷰를 수행하고 봇 계정 **`dci`** 가
요약 comment와 inline review thread를 남긴다. 이 도구는 그 리뷰를 thread별 결정 기록으로 바꾸고 루프를 닫는다:

```
fetch ──> show ──> decide (thread별, 사람이 결정) ──> [수정 + commit 1개] ──> commit-ref
      ──> replies (미리보기) ──> publish (thread reply + reviewer dci 재요청)
```

**판단** — 수정 제안인지 칭찬인지, 적용할지 말지 — 는 skill을 실행하는 agent가 개발자와 함께
thread 본문과 현재 코드를 읽고 내린다. 도구는 이모지나 헤더로 분류하지 않는다(봇의 표식은 일정하지 않다).

## 입력 두 가지

| 소스 | 명령 | 언제 |
|---|---|---|
| 저장한 PR 페이지(`.mhtml`, Chrome "다른 이름으로 저장 → 웹페이지, 단일 파일") | `fetch --mhtml <file>` | 개발 PC가 GHES에 닿지 않을 때(보통의 경우) |
| GHES REST API | `fetch --pr https://gh.deepx.ai/deepx/<repo>/pull/<n>` | token 또는 로그인된 `gh`가 있을 때 |

Token 우선순위(ghes-sync와 동일): `GHES_SYNC_DST_TOKEN` > `GH_ENTERPRISE_TOKEN` > `GHES_TOKEN` > `GH_TOKEN`;
모두 없으면 PATH의 `gh`로 `gh api`를 쓴다.

## 명령

```bash
T=internal/tools/pr-review-apply/pr_review_apply.py
python3 $T fetch  --mhtml ~/Downloads/pr91.mhtml          # 또는 fetch --pr <url>
python3 $T show   [--pending]                             # 전체 thread + 결정 상태
python3 $T decide --id r18833 --apply     --note "url 유도 실패를 로그로 남기고 exit 3"
python3 $T decide --id r18829 --skip      --note "출력이 의도적으로 한국어 — 안내 한 줄 추가"
python3 $T decide --id r18845 --defer     --note "후속 정리"
python3 $T decide --id r18847 --no-action --note "칭찬"            # 이 항목에는 reply를 보내지 않음
python3 $T commit-ref --sha "$(git rev-parse HEAD)"        # 수정 commit 1개를 모든 apply 항목에 기록
python3 $T replies                                         # reply 본문 미리보기
python3 $T publish --pr <url> [--retrigger rerequest|comment|both|none] [--dry-run]
python3 $T publish --queue                                 # 오프라인: publish-queue.json + replies.md 생성
python3 $T publish --queue-file .dx-pr-review/<owner>-<repo>-<n>/publish-queue.json   # GHES 접근 가능한 PC에서
python3 $T probe-bot --pr <url>                            # 어떤 재트리거가 봇에 닿는지(repo admin 필요)
```

상태는 `.dx-pr-review/<owner>-<repo>-<n>/`(gitignore)에 둔다: `review.json`(파싱한 리뷰),
`decisions.json`(`apply|skip|defer|no-action`, note, commit, `published_at`), `publish-queue.json`,
`replies.md`. 모든 reply는 `<!-- dx-pr-review-apply r<id> -->`로 시작하므로 재실행해도 두 번 달리지 않는다.

## 리뷰 봇 재트리거

봇은 PR이 열릴 때 돈다. 이후 push로는 **다시 돌지 않는다.** 다시 돌게 하는 방법:

| `--retrigger` | 전송 내용 | 비고 |
|---|---|---|
| `rerequest` (기본) | `POST …/pulls/<n>/requested_reviewers {"reviewers":["dci"]}` | UI의 "Re-request review" 버튼과 같은 webhook(`pull_request.review_requested`) |
| `comment` | `POST …/issues/<n>/comments` + `--comment-text` | n8n이 `issue_comment`를 구독할 때만 유효 |
| `both` | 둘 다 | |

`probe-bot`은 repo webhook(admin token)을 읽어 n8n hook이 둘 중 무엇을 받을 수 있는지 알려준다.
admin 권한이 없으면 `rerequest`를 유지한다. `ghes-sync.sh`가 실제 push마다 재요청을 대신할 수 있다
(`sync.override.conf`의 `reviewers = dci` 또는 `--reviewers dci`).

## 폐쇄망 흐름

```
개발 PC (GHES 불가)               mirror (github.com)        폐쇄망 PC                        GHES
fetch --mhtml ─ decide ─ 수정 ─ commit ─ push ─────────────> ghes-sync.sh ───────────────> PR 갱신,
publish --queue  ──(.dx-pr-review/<dir>/ 복사)─────────────> publish --queue-file ────────> reply + dci 재요청
```

저쪽에 도구가 없을 때의 대안: `replies.md`를 thread에 붙여넣고 "Re-request review"를 누른다.

## 테스트

```bash
cd internal/tools/pr-review-apply && python3 -m pytest tests -q
# fixture: tests/fixtures/pr91.mhtml (실제 페이지 축약본, thread 10개) — tests/make_fixture.py <full.mhtml> <out> 로 재생성
```
