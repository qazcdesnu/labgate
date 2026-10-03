---
id: task-start
type: procedure
spec_version: 5
---
# Task 착수

- 시작 조건: 승인된 task를 착수할 때 (Claude Code: `/task-start <Task>`).
- 끝나는 상태: 카드가 `in-progress`이고 `task(<Task>): start` 커밋이 있다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. 카드 상태가 `approved` 또는 `revise`인지 확인한다. `draft`이고 `scripts/apply-human-commits --check`에 이 task의 승인이 있으면 절차 [gate-apply](gate-apply.md)를 먼저 한다. 그 밖에는 중단하고 이유를 보고한다.
2. `revise`에서 시작하면 해당 gate review의 `## 응답`을 먼저 읽고 반영 계획을 세운다.
3. 카드 `status`를 `in-progress`로 바꾸고 `updated`를 갱신한다.
4. `STATUS.md`를 갱신한다.
5. `scripts/agent-commit`으로 `task(<Task>): start` 커밋을 만든다 (`Actor: agent`, `Task: <Task>`).
6. 카드의 완료 기준을 기준으로 이번 세션 작업 계획을 보고한다.
