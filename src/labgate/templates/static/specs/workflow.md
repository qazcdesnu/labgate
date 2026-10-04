---
id: workflow
type: spec
spec_version: 7
status: complete
---
# 워크플로우

## 1. 원칙

1. **Task는 승인 게이트 사이의 작업 단위다.** 에이전트는 승인된 task 범위 안에서 자율적으로 일하고, 경계에서 사람이 판정한다.
2. **사실의 원본은 Git 커밋이다.** 사람의 판정·확정은 사람 신원의 커밋(trailer 포함)이 원본이고, 문서의 상태 필드는 그것을 반영한다([AGENTS.md](../AGENTS.md) P1).
3. **이력은 `main` 하나로 선형이다.** 게이트 지점은 tag로 표시한다. 워크트리 브랜치는 실험 격리용 임시 브랜치이며 `main`에 병합·cherry-pick하지 않는다 ([AGENTS.md](../AGENTS.md)).
4. **규칙의 층과 우선순위는 [AGENTS.md](../AGENTS.md) 0절에 있다.** 불변 원칙은 예외가 없고, 적용할 때는 task 카드, 절차의 특별 규칙([procedures/](procedures/)), 일반 규칙 순으로 구체적인 것이 먼저다. 이 문서는 상태 기계와 게이트를 정한다.

## 2. 역할

| 주체 | 하는 일 |
|---|---|
| 사람 | task 승인, 게이트 판정, 에스컬레이션 응답, 결정 확정, 계획·사양 변경, tag 생성. 필요하면 코드·문서를 직접 고치고 사람 신원으로 커밋 (§4) |
| 에이전트 | 승인된 task 수행, 문서·코드·실행 기록 작성, 결정·계획·사양 변경 제안, 게이트 요청, 에스컬레이션, 사람 커밋의 초안 준비, 사람 커밋의 결과를 문서에 반영 |

## 3. Task 상태 기계

```
draft ──▶ approved ──▶ in-progress ──▶ in-review ──┬──▶ closed
                          │   ▲                    ├──▶ revise ──▶ in-progress
                          ▼   │                    └──▶ redirected
                         blocked
```

| 전이 | 주체 | 기록하는 커밋 |
|---|---|---|
| `draft → approved` | 사람 | 이전 task의 `gate` 커밋 `Next:`, 또는 `plan` 커밋 `Approve:` (반영: `gate-apply`) |
| `approved → in-progress` | 에이전트 | `task` |
| `in-progress → blocked` | 에이전트 | `review` (에스컬레이션 제출) |
| `blocked → in-progress` | 에이전트 | `task` (사람의 `respond` 커밋 이후에만) |
| `in-progress → in-review` | 에이전트 | `review` (게이트 요청 제출) |
| `in-review → closed / revise / redirected` | 사람 | `gate` (`Verdict:`) |
| `revise → in-progress` | 에이전트 | `task` |

- `redirected`는 끝 상태다. 대체 계획은 사람의 `plan` 커밋으로 반영한다.
- 사람이 기록하는 전이는 사람이 해당 커밋에서 직접 바꾸거나, 에이전트가 `scripts/apply-human-commits`로 반영한다(절차 [gate-apply](procedures/gate-apply.md)). 반영 커밋은 `Applies:` trailer로 사람 커밋을 가리킨다.

마일스톤 상태: `planned → active`는 그 마일스톤 T0의 게이트 승인 시(T0 동안에는 `planned`이므로 에이전트가 목표·기준 초안을 쓸 수 있다), `active → closed`는 마지막 task의 `gate` 커밋에 `Milestone-Verdict:`가 있을 때.

## 4. 사람의 커밋

### 4.1 사람의 변경

사람도 코드·문서를 직접 고칠 수 있다. 사람의 변경은 사람 신원으로 커밋하며, 공통 타입(`exp`, `run`, `result`, `ref`, `log`, `chore`)을 쓸 수 있다 ([git-commit.md](git-commit.md) §3). 커밋은 터미널에서 `lg commit`으로 하거나 `git commit`으로 한다.

사람의 변경은 에이전트 작업보다 먼저 커밋한다. 세션 시작 때 커밋되지 않은 변경은 사람의 변경으로 본다(`scripts/session-check`가 알리고 `.lg/pending/HUMAN_FILES`에 기록한다). 에이전트는 그것을 건드리지 않고 사람에게 정리를 요청한다 (절차 [commit-prep](procedures/commit-prep.md)). 세션 도중에는 직접 수정하지 않는다. 했다면 에이전트에게 알린다.

### 4.2 사람 커밋 대기 상태

에이전트가 사람 커밋을 준비하면(`lg draft`) stage된 변경과 `.lg/pending/COMMIT_MSG`가 남는다. 사람이 `lg commit`으로 확인·확정할 때까지 에이전트는 어떤 커밋도 하지 않는다.

### 4.3 깨끗한 작업 트리

모든 세션은 깨끗한 작업 트리로 끝난다. 예외는 사람 커밋 대기 상태의 stage된 변경과 커밋되지 않은 사람의 변경뿐이다.

## 5. Task 진행

- 착수와 게이트 요청: 절차 [task-start](procedures/task-start.md), [task-gate](procedures/task-gate.md).
- 작업 단위마다 알맞은 타입으로 커밋한다 (`exp`, `run`, `result`, `ref`, `task` …).
- 새로운 결정이 필요하면 `decisions/`에 `proposed`로 쓰고 `propose` 커밋한다. 확정은 하지 않는다.
- 실행은 카드의 자원 예산 안에서만 한다. 실행마다 run-record를 남긴다.

## 6. 게이트

### 6.1 문서 경로 (사람이 직접 작성)

1. 사람이 review 문서의 `## 응답`을 작성하고 frontmatter `verdict`, `source: document`, `status: answered`, `answered`를 채운다.
2. 필요하면 같은 커밋에서 카드 `status`, 결정 `status`, 다음 task 카드 `status: approved`를 바꾼다.
3. `lg commit`으로 `gate(<Task>): <verdict>…` 커밋을 만든다 ([git-commit.md](git-commit.md) §4). 승인이면 `lg commit`이 tag `gate/<Task>`도 만든다. `git commit`으로 했다면 `git tag gate/<Task>`.

### 6.2 대화 경로 (사람이 대화로 판정)

절차 [gate-conversation](procedures/gate-conversation.md). 에이전트가 사람의 발언을 review의 `## 응답`에 옮기고 초안을 준비하면(`lg draft`), 사람이 `lg commit`으로 확인·확정한다. 상태 전이는 이 단계에서 하지 않고, 사람이 커밋한 뒤 §6.3으로 반영한다. 같은 방식이 `decide`, `respond`에도 적용된다.

### 6.3 판정 후 정리

절차 [gate-apply](procedures/gate-apply.md). 사람의 커밋 이후 `scripts/apply-human-commits`가 review 문서를 닫고 상태 필드를 커밋 trailer에 맞추며, 에이전트가 그 결과를 커밋한다. 문서 경로와 대화 경로가 같은 반영 경로를 쓴다.

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

### 7.2 진행

에이전트는 절차 [escalate](procedures/escalate.md)로 제출하고 멈춘다. 사람은 `respond(<Task>): …` 커밋으로 응답한다(§6.1 또는 §6.2와 같은 방식, `Verdict` 없음). 에이전트는 절차 [gate-apply](procedures/gate-apply.md)로 반영하고 작업으로 돌아간다.

## 8. 마일스톤 착수와 종료

- **착수:** 모든 마일스톤은 T0(착수 계획)으로 시작한다. T0의 게이트에서 사람이 task 분해를 승인하면 `Next: <M>-T1`, 마일스톤은 `active`.
- **종료:** 마지막 task의 게이트 요청에 마일스톤 보고(`results/<M>/report.md`)와 Go/No-go 근거를 포함한다. 사람의 `gate` 커밋에 `Milestone-Verdict:`를 넣고 tag `milestone/<M>-<go|nogo|conditional>`을 만든다(`lg commit`은 자동). 다음 마일스톤 T0의 승인도 같은 커밋 `Next:`로 한다.
- 마일스톤 종료 게이트에서는 해당 결과를 `paper/`(제안서 프로젝트는 `deliverables/`) 초안에 반영하는 것을 마일스톤 보고의 일부로 한다.

## 9. 계획·사양 변경

- 에이전트는 변경안을 `notes/` 또는 해당 문서의 제안 섹션에 쓰고 `propose` 커밋한다.
- 사람이 `plan`(로드맵·마일스톤) 또는 `spec`(사양·AGENTS 등) 커밋으로 확정한다.

## 10. 규칙 위반과 실수

- 잘못된 커밋은 사람이 `git revert`로 되돌린다. 이력은 재작성하지 않는다.
- `--no-verify`는 사람만, 긴급할 때만 쓰고 이유를 다음 커밋 본문에 남긴다.
