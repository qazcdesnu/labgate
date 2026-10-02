---
id: workflow
type: spec
spec_version: 1
status: complete
---
# 워크플로우

## 1. 원칙

1. **Task는 승인 게이트 사이의 작업 단위다.** 에이전트는 승인된 task 범위 안에서 자율적으로 일하고, 경계에서 사람이 판정한다.
2. **사실의 원본은 Git 커밋이다.** 특히 사람의 판정·확정은 사람 신원의 커밋(trailer 포함)이 원본이다. 문서의 상태 필드는 이를 반영한 것이며, 둘이 다르면 커밋이 우선한다.
3. **이력은 `main` 하나로 선형이다.** 게이트 지점은 tag로 표시한다. 워크트리 브랜치는 실험 격리용 임시 브랜치이며 `main`에 병합·cherry-pick하지 않는다 ([AGENTS.md](../AGENTS.md)).

## 2. 역할

| 주체 | 하는 일 |
|---|---|
| 사람 | task 승인, 게이트 판정, 에스컬레이션 응답, 결정 확정, 계획·사양 변경, tag 생성. 필요하면 코드·문서를 직접 고치고 사람 신원으로 커밋 (§4.1) |
| 에이전트 | 승인된 task 수행, 문서·코드·실행 기록 작성, 결정·계획·사양 변경 제안, 게이트 요청, 에스컬레이션, 사람 커밋의 결과를 문서에 반영 |

## 3. Task 상태 기계

```
draft ──▶ approved ──▶ in-progress ──▶ in-review ──┬──▶ closed
                          │   ▲                    ├──▶ revise ──▶ in-progress
                          ▼   │                    └──▶ redirected
                         blocked
```

| 전이 | 주체 | 기록하는 커밋 |
|---|---|---|
| `draft → approved` | 사람 | 이전 task의 `gate` 커밋 `Next:`, 또는 `plan` 커밋 `Approve:` |
| `approved → in-progress` | 에이전트 | `task` |
| `in-progress → blocked` | 에이전트 | `review` (에스컬레이션 제출) |
| `blocked → in-progress` | 에이전트 | `task` (사람의 `respond` 커밋 이후에만) |
| `in-progress → in-review` | 에이전트 | `review` (게이트 요청 제출) |
| `in-review → closed / revise / redirected` | 사람 | `gate` (`Verdict:`) |
| `revise → in-progress` | 에이전트 | `task` |

- `redirected`는 끝 상태다. 대체 계획은 사람의 `plan` 커밋으로 반영한다.
- 카드의 `status` 필드는 사람이 해당 커밋에서 직접 바꾸거나, 에이전트가 다음 커밋에서 반영한다.

마일스톤 상태: `planned → active`는 그 마일스톤 T0의 게이트 승인 시(T0 동안에는 `planned`이므로 에이전트가 목표·기준 초안을 쓸 수 있다), `active → closed`는 마지막 task의 `gate` 커밋에 `Milestone-Verdict:`가 있을 때.

## 4. 세션 절차

시작·종료 절차는 [AGENTS.md](../AGENTS.md)에 있다. 모든 세션은 깨끗한 작업 트리로 끝난다. 예외는 둘이다: 사람 커밋 대기 상태(§6.2)와 커밋되지 않은 사람의 변경(§4.1).

### 4.1 사람의 변경

사람도 코드·문서를 직접 고칠 수 있다. 사람의 변경은 사람 신원으로 커밋하며, 공통 타입(`exp`, `run`, `result`, `ref`, `log`, `chore`)을 쓸 수 있다 ([git-commit.md](git-commit.md) §3).

에이전트는 사람의 변경을 다음처럼 다룬다.

1. 세션 시작 때 `git status`에 나오는 커밋되지 않은 변경은 사람의 변경으로 본다. 이전 세션은 깨끗하게 끝나기 때문이다. 단, 사람 커밋 대기 상태의 stage된 변경은 §6.2를 따른다. 출처가 불확실하면 사람에게 묻는다.
2. 사람의 변경은 stage·커밋·되돌리기(`git restore`, `git checkout --`, `git stash`)를 하지 않는다. 자기 변경은 파일 경로를 지정해 stage한다(`git add -A`, `git add .`, `git add -u`, `scripts/agent-commit -a` 금지).
3. 사람의 변경이 있는 파일을 고쳐야 하면 고치기 전에 사람에게 커밋을 요청한다. 한 파일에 두 주체의 변경이 섞이면 어느 신원으로도 정확히 커밋할 수 없다.
4. 세션 종료 시 사람의 변경은 그대로 두고, 남은 파일 목록을 보고한다.
5. 사람이 요청하면 사람 변경의 커밋을 준비한다. 자기 변경을 먼저 커밋해 둔 뒤, 사람의 변경을 stage하고 `Actor: human` 메시지 초안을 `.lg/pending/COMMIT_MSG`에 쓴다. 사람에게 `git diff --cached` 확인과 다음 명령 실행을 요청하고 멈춘다:
   `git commit -F .lg/pending/COMMIT_MSG && rm .lg/pending/COMMIT_MSG`
   이후는 §6.2의 "사람 커밋 대기 상태"와 같다.

## 5. Task 실행

### 5.1 착수

1. 카드가 `approved` 또는 `revise`인지 확인한다.
2. 카드 `status`를 `in-progress`로 바꾸고 STATUS를 갱신해 `task(<Task>): start` 커밋.
3. `revise`에서 시작하는 경우, 해당 gate review의 `## 응답`을 먼저 반영한다.

### 5.2 진행

- 작업 단위마다 알맞은 타입으로 커밋한다 (`exp`, `run`, `result`, `ref`, `task` …).
- 새로운 결정이 필요하면 `decisions/`에 `proposed`로 쓰고 `propose` 커밋한다. 확정은 하지 않는다.
- 실행은 카드의 자원 예산 안에서만 한다. 실행마다 run-record를 남긴다.

### 5.3 에스컬레이션이 필요한 경우

§7을 따른다.

### 5.4 완료와 게이트 요청

1. 완료 기준을 하나씩 점검한다.
2. task 결과 문서 `results/<M>/<Task>_result.md`를 쓴다.
3. `reviews/open/<Task>_gate-NN.md`를 쓴다 (`kind: gate`, [review.spec.md](doc-types/review.spec.md)).
4. 카드를 `in-review`로, STATUS의 "사람 판단 대기"에 추가.
5. `review(<Task>): request gate` 커밋. 이후 이 task에서 작업하지 않는다.

## 6. 게이트 절차

### 6.1 문서 경로 (사람이 직접 작성)

1. 사람이 review 문서의 `## 응답`을 작성하고 frontmatter `verdict`, `source: document`, `status: answered`, `answered`를 채운다.
2. 필요하면 같은 커밋에서 카드 `status`, 결정 `status`, 다음 task 카드 `status: approved`를 바꾼다.
3. 사람 신원으로 `gate(<Task>): <verdict>…` 커밋 ([git-commit.md](git-commit.md) §4).
4. 승인이면 tag: `git tag gate/<Task>`.

### 6.2 대화 경로 (사람이 대화로 판정)

1. 에이전트가 사람의 발언을 그대로 반영해 `## 응답`을 작성하고 `verdict`, `source: conversation`, `status: answered`를 채운다. 사람이 말하지 않은 내용을 추가하지 않는다.
2. 에이전트가 관련 변경(카드·결정 상태 등)을 stage하고, 커밋 메시지 초안을 `.lg/pending/COMMIT_MSG`에 쓴다. `.lg/pending/`은 Git에서 제외되며, 에이전트가 쓸 수 있는 `.lg/` 안의 유일한 위치다.
3. 에이전트는 사람에게 `git diff --cached` 확인과 다음 명령 실행을 요청하고 멈춘다 (tag는 `approve`일 때만):
   `git commit -F .lg/pending/COMMIT_MSG && rm .lg/pending/COMMIT_MSG && git tag gate/<Task>`
4. 사람이 확인 후 실행한다. 내용이 다르면 수정 후 커밋한다.

같은 방식이 `decide`, `respond` 커밋의 대화 경로에도 적용된다.

**사람 커밋 대기 상태.** `.lg/pending/COMMIT_MSG`가 있는 동안 stage된 변경은 사람의 커밋을 기다리는 것이다. 이 상태에서 에이전트는:

- 어떤 커밋도 하지 않는다 (stage된 변경이 에이전트 커밋에 섞이기 때문). 세션 종료 시에도 `log` 커밋을 하지 않고, 작업 트리가 깨끗하지 않은 채로 끝내며 그 이유를 보고한다 (§4 "깨끗한 작업 트리"의 유일한 예외).
- 세션 시작 시 이 파일이 있으면, `git log`에 그 메시지로 된 사람 커밋이 이미 있는지 확인한다. 있으면 파일을 지우고 §6.3으로 간다. 없으면 사람에게 커밋 실행을 다시 요청하고 다른 작업을 하지 않는다.

### 6.3 판정 후 정리 (에이전트)

다음 세션에서 에이전트가 사람의 `gate` 커밋을 확인하고:

1. review 문서를 `reviews/closed/`로 옮기고(`git mv`) `status: closed`.
2. 카드·결정·마일스톤 문서의 상태 필드가 커밋 trailer와 다르면 맞춘다.
3. 카드의 "게이트 이력"에 판정과 커밋 해시를 추가한다.
4. STATUS 갱신 후 `log(<Task>): apply gate <해시>` 커밋.

### 6.4 판정별 다음 단계

| Verdict | 카드 | 다음 |
|---|---|---|
| `approve` | `closed` | `Next:`의 task가 `approved`. 없으면(`none`) 사람의 다음 지시 대기 |
| `revise` | `revise` | 같은 task 재개. 다음 게이트 요청은 `gate-NN`의 번호를 올린다 |
| `redirect` | `redirected` | 사람의 `plan` 커밋을 기다린다 |

## 7. 에스컬레이션

### 7.1 해야 하는 경우

- 승인된 범위 밖의 작업이 필요할 때
- 결과가 확정되지 않은 결정에 크게 좌우될 때
- 자원 예산을 넘어야 할 때
- 완료 기준 자체가 잘못되었거나 달성 불가능하다고 판단될 때
- 사양·규칙끼리 충돌할 때

### 7.2 절차

1. `reviews/open/<Task>_esc-NN.md` (`kind: escalation`): 상황, 선택지, 영향, 추천안.
2. 카드 `blocked`, STATUS 갱신, `review(<Task>): escalate …` 커밋.
3. 사람이 응답하고 `respond(<Task>): …` 커밋 (§6.1 또는 §6.2와 같은 방식, `Verdict` 없음).
4. 에이전트가 응답을 반영해 `in-progress`로 돌아가고, 문서를 `closed/`로 옮긴다.

## 8. 마일스톤 착수와 종료

- **착수:** 모든 마일스톤은 T0(착수 계획)으로 시작한다. T0의 게이트에서 사람이 task 분해를 승인하면 `Next: <M>-T1`, 마일스톤은 `active`.
- **종료:** 마지막 task의 게이트 요청에 마일스톤 보고(`results/<M>/report.md`)와 Go/No-go 근거를 포함한다. 사람의 `gate` 커밋에 `Milestone-Verdict:`를 넣고 tag `milestone/<M>-<go|nogo|conditional>`을 만든다. 다음 마일스톤 T0의 승인도 같은 커밋 `Next:`로 한다.
- 마일스톤 종료 게이트에서는 해당 결과를 `paper/` 초안에 반영하는 것을 마일스톤 보고의 일부로 한다.

## 9. 계획·사양 변경

- 에이전트는 변경안을 `notes/` 또는 해당 문서의 제안 섹션에 쓰고 `propose` 커밋한다.
- 사람이 `plan`(로드맵·마일스톤) 또는 `spec`(사양·AGENTS 등) 커밋으로 확정한다.

## 10. 규칙 위반과 실수

- 잘못된 커밋은 사람이 `git revert`로 되돌린다. 이력은 재작성하지 않는다.
- `--no-verify`는 사람만, 긴급할 때만 쓰고 이유를 다음 커밋 본문에 남긴다.
