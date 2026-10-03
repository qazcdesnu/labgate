# lg commit

사람 신원으로 커밋한다. 타입과 필수 trailer를 물어 메시지를 만들거나, 에이전트가 준비한 초안을 확인해 확정한다.

- 누가: 사람. **터미널에서 직접** 실행한다 (에이전트의 셸에서는 거부된다).
- 언제: 사람의 모든 커밋. task 승인, 게이트 판정, 결정 확정, 에스컬레이션 응답, 계획·사양 변경, 사람이 직접 고친 코드·문서.
- 전제: labgate 0.2 이상으로 만든 프로젝트(spec_version 2 이상) 안. 현재 Git 사용자(`git config user.email`)가 `.lg/identities.json`의 사람 중 하나.

## 형식

```
lg commit [--pending | --no-pending] [--no-tag] [--allow-empty]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `--pending` | — | 초안이 있으면 초안 모드 | 초안 모드를 강제한다. 초안이 없으면 코드 3 |
| `--no-pending` | — | | 초안이 있어도 작성 모드로 간다. 초안 파일은 그대로 둔다 |
| `--no-tag` | — | 꺼짐 | `gate` 승인이어도 tag를 만들지 않는다 |
| `--allow-empty` | — | 꺼짐 | 바뀐 파일 없이 커밋한다. 첫 task 승인처럼 기록만 남기는 커밋에 쓴다 |

## 동작

1. 프로젝트를 확인한다: Git 저장소인지, `.lg/project.yaml`의 spec_version이 지원 범위인지. 커밋 규칙은 프로젝트의 `.lg/hooks/commit-msg`에서 읽는다(규칙을 `lg` 안에 따로 두지 않는다).
2. 표준 입력·출력이 터미널인지, 현재 Git 사용자가 등록된 사람인지 확인한다.
3. 메시지를 준비한다.
   - **초안 모드** (`.lg/pending/COMMIT_MSG`가 있을 때): 초안을 읽는다. stage된 변경이 있어야 하고(`--allow-empty` 제외), 초안이 `Actor: human`이어야 한다.
   - **작성 모드:** 아래 [작성 모드의 질문](#작성-모드의-질문).
4. stage 요약(`git diff --cached --stat`)과 메시지를 보여 주고 **커밋 / 편집기로 수정 / 취소**를 고르게 한다. `gate` 커밋이면 그 Task로 [`lg verify`](lg-verify.md)를 돌려 결과 요약(위반 없음 한 줄, 또는 위반 건수와 커밋, 점검표)을 함께 보여 준다. **막지 않는다**: 위반이 있으면 선택지가 `커밋 (위반 N건 있음)`으로 보일 뿐이다. 검사 자체가 실패해도 커밋 흐름은 계속된다. 편집한 메시지는 커밋 규약을 다시 검사하고, 맞지 않으면 커밋을 고를 수 없다. 편집기는 Git과 같은 규칙으로 고른다(`core.editor`, `GIT_EDITOR`, `VISUAL`, `EDITOR` 순).
5. 커밋한다. 커밋할 때 hook이 작성자 신원까지 다시 검사한다.
6. 정리한다: 초안 모드였으면 초안을 지우고, `.lg/pending/HUMAN_FILES`에서 이번에 커밋된 경로를 뺀다.
7. tag를 만든다: `gate` + `Verdict: approve`면 `gate/<Task>`, `Milestone-Verdict`가 있으면 `milestone/<M>-<verdict>`. `--no-tag`면 만들지 않는다.

자세한 사양: 설계 문서 §18.

## 작성 모드의 질문

| 순서 | 질문 | 언제 |
|---|---|---|
| 1 | 커밋할 파일 (체크박스) | stage된 변경이 없을 때. `--allow-empty`면 묻지 않는다 |
| 2 | 타입 | 항상. 사람이 쓸 수 있는 타입만 보인다: `gate`, `decide`, `plan`, `spec`, `respond`, `exp`, `run`, `result`, `ref`, `log`, `chore` |
| 3 | Task | 타입이 Task를 요구할 때(`gate`, `respond`, `run`, `result`). task 카드 목록에서 고른다. scope는 Task로 정해진다 |
| 3 | Approve (체크박스, 여러 개) | `plan`일 때. 고르지 않으면 생략. 하나만 고르면 scope도 그 Task |
| 3 | scope | 위에서 정해지지 않았을 때. 빈 입력이면 생략 |
| 4 | Verdict | `gate` |
| 4 | Source | `gate`, `decide`, `respond` |
| 4 | Next, Milestone-Verdict | `gate` (둘 다 선택) |
| 4 | Decisions | `decide` |
| 5 | 요약 한 줄 | 항상. 헤더가 72자를 넘으면 다시 묻는다 |

`Actor: human`은 자동으로 넣는다. 본문은 확인 단계의 편집기에서 쓴다.

## 읽고 쓰는 것

- 읽는 것: `.lg/project.yaml`, `.lg/identities.json`, `.lg/hooks/commit-msg`, `.lg/pending/COMMIT_MSG`, task 카드 목록(`plan/milestones/*/tasks/*.md`)
- 쓰는 것: stage(작성 모드에서 고른 파일), 사람 신원의 커밋, tag, `.lg/pending/COMMIT_MSG` 삭제, `.lg/pending/HUMAN_FILES` 갱신

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 커밋 성공 |
| 1 | 예기치 못한 오류 |
| 2 | 터미널이 아님, 등록되지 않은 Git 사용자, labgate 프로젝트가 아님, 지원하지 않는 spec_version, 초안이 사람 커밋용이 아님 |
| 3 | 커밋할 것 없음: 변경 없음, 파일을 고르지 않음, `--pending`인데 초안 없음, 초안은 있는데 stage된 변경 없음 |
| 4 | Git이 커밋을 거부(hook 등). 초안은 남는다. 또는 커밋은 됐지만 tag를 만들지 못함 |
| 130 | 취소를 골랐거나 중단(Ctrl-C). stage와 초안은 그대로 둔다 |

## 예

```bash
# 첫 task 승인: 타입 plan → Approve에서 M0-T0 → 요약 → 커밋
lg commit --allow-empty

# 직접 고친 실험 코드 커밋: 파일 선택 → 타입 exp → 요약 → 커밋
lg commit

# 에이전트가 lg draft로 준비한 초안 확정 (대화로 내린 게이트 판정 등)
lg commit          # 초안이 있으면 자동으로 초안 모드

# 초안은 두고 다른 커밋을 먼저 하기
lg commit --no-pending
```

## 관련 절차

- 에이전트가 초안을 준비하는 절차: `specs/procedures/commit-prep.md`(사람의 변경), `specs/procedures/gate-conversation.md`(대화로 내린 판정)
- 커밋 규약: 생성된 프로젝트의 `specs/git-commit.md`, [project-scripts.md](project-scripts.md#lghookscommit-msg)
- 초안을 만드는 명령: [lg draft](lg-draft.md)

## 알려진 한계

- 터미널 확인은 실수 방지 장치이며 보안 경계가 아니다. 의사 터미널을 만드는 도구로 우회할 수 있다.
- Claude Code 프롬프트에서 `!`로 실행할 때 대화형 입력이 동작하는지는 확인되지 않았다. 별도 터미널에서 실행한다.
