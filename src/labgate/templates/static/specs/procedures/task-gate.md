---
id: task-gate
type: procedure
spec_version: 6
---
# 게이트 요청

- 시작 조건: task의 완료 기준을 모두 충족했다고 판단할 때 (Claude Code: `/task-gate <Task>`).
- 끝나는 상태: 카드가 `in-review`이고 게이트 요청 문서와 `review` 커밋이 있다. 이 task에서는 더 작업하지 않는다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. 완료 기준을 하나씩 점검한다. 충족한 기준은 카드의 `## 완료 기준`에서 `- [x]`로 바꾼다. 충족하지 못한 기준이 있으면 게이트 대신 계속 작업할지 사람에게 묻는다.
2. task 결과 문서 `results/<M>/<Task>_result.md`를 쓴다. 마일스톤의 마지막 task면 마일스톤 보고 `results/<M>/report.md`와 Go/No-go 근거도 쓴다 ([workflow.md](../workflow.md) §8).
3. `lg`가 설치되어 있으면 지금까지의 작업을 커밋한 뒤 `lg verify --task <Task>`를 실행한다(읽기만 한다). 위반이 있으면 고칠 수 있는 것은 고치고, 이미 커밋되어 고칠 수 없는 것은 요청서의 "예상과 달랐던 점"에 적는다.
4. `specs/templates/review.md`로 `reviews/open/<Task>_gate-NN.md`를 쓴다 (`kind: gate`, [review.spec.md](../doc-types/review.spec.md)).
5. 카드를 `in-review`로 바꾸고, `STATUS.md`의 "사람 판단 대기"에 항목을 추가한다.
6. `review(<Task>): request gate` 커밋 (`Actor: agent`, `Task: <Task>`, `Review: <review id>`).
7. 사람에게 무엇을 판정해야 하는지 요약해 보고하고 멈춘다. 판정하는 방법을 끝에 쓴다: 터미널에서 `lg answer <review id>` (요청서에 직접 쓰거나 대화로 판정해도 된다).
