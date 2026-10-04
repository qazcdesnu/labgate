---
id: session-start
type: procedure
spec_version: 7
---
# 세션 시작

- 시작 조건: 세션을 시작할 때 (Claude Code: `/session-start`).
- 끝나는 상태: 이번 세션에 할 일이 정해지고 사람에게 보고되었다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. `scripts/session-check`의 출력을 확인한다. Claude Code에서는 세션 시작 hook이 이미 실행해 출력이 맥락에 있다. 다른 도구에서는 직접 실행한다.
2. "사람 커밋 대기 상태"가 있으면: 사람에게 터미널에서 `lg commit` 실행을 요청하고, 아래 읽기 단계(5, 6, 8–10)만 한 뒤 보고하고 멈춘다.
3. "커밋되지 않은 사람의 변경"이 있으면: 절차 [commit-prep](commit-prep.md)의 1단계(선택지 제시)를 한다. 사람이 답할 때까지는 아래 읽기 단계(5, 6, 8–10)만 한다.
4. "반영되지 않은 사람 커밋"이 있으면: 절차 [gate-apply](gate-apply.md)를 먼저 한다. 카드 상태는 반영한 뒤에 판단한다.
5. `STATUS.md`를 읽는다.
6. 현재 task 카드(`plan/milestones/<M>/tasks/<Task>.md`)를 읽는다.
7. 카드 상태가 `approved`, `in-progress`, `revise` 중 하나가 아니면 작업하지 않고 STATUS에 이유를 적은 뒤 절차 [session-close](session-close.md)로 간다.
8. 카드에 연결된 결정(`decisions/`)과 `references/<M>/task-map.md`를 읽는다.
9. `logs/`의 최근 일지 1–2개를 읽는다.
10. 이번 세션에 쓸 문서 유형의 사양(`specs/doc-types/`)을 읽는다.
11. 3–5줄로 보고한다: 사람 커밋 대기 상태나 사람의 변경(있으면 먼저), 반영한 사람 커밋, 현재 task와 상태, 이번 세션에 할 일.
