---
id: gate-apply
type: procedure
spec_version: 3
---
# 사람 커밋의 반영

- 시작 조건: `scripts/session-check`가 반영되지 않은 사람 커밋을 알렸을 때, 사람이 판정·결정·응답·승인을 커밋했다고 알렸을 때.
- 끝나는 상태: 반영되지 않은 사람 커밋이 없고(`scripts/apply-human-commits --check`가 빈 결과), 반영 커밋들이 있다.

## 특별 규칙

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|
| G4 (사람 몫의 상태 전이를 하지 않는다) | 사람 커밋이 정한 상태 전이를 커밋한다. 전이는 `scripts/apply-human-commits`가 만든 것만 쓰고, 상태 필드를 직접 편집하지 않는다 |

## 단계

1. 사람 커밋 대기 상태가 아닌지 확인한다(대기 상태면 커밋할 수 없다, G3). 이번 세션에 자기가 바꾼 파일이 있으면 먼저 커밋한다.
2. `scripts/apply-human-commits`를 실행한다. 가장 오래된 반영되지 않은 사람 커밋 하나를 반영하고, 바뀐 파일과 커밋 명령을 출력한다.
3. "반영할 수 없음"(종료 코드 1)이면 아무것도 바뀌지 않았다. 출력된 이유를 사람에게 보고하고 멈춘다.
4. 바뀐 내용을 `git diff`로 확인하고, `STATUS.md`에 다음 할 일을 반영한다(아래 표).
5. 출력된 명령대로 커밋한다: `scripts/agent-commit -F .lg/pending/APPLY_MSG -- <출력된 경로…> STATUS.md`
6. `scripts/apply-human-commits --check`가 빈 결과를 낼 때까지 2–5를 반복한다.
7. 반영한 결과와 다음 할 일을 보고한다.

| 반영한 것 | 다음 할 일 |
|---|---|
| 승인 (`Approve`, `Next`) | 승인된 task 착수 (절차 [task-start](task-start.md)) |
| `approve` (`Next: none`) | 사람의 다음 지시를 기다린다 |
| `revise` | 같은 task 재개. review의 `## 응답`을 읽고 반영 계획을 세운다 |
| `redirect` | 사람의 `plan` 커밋을 기다린다 |
| `respond` | 막혔던 task로 돌아간다 |
| 결정 확정 | 그 결정에 의존하던 작업을 이어 간다 |
