---
id: session-start
type: procedure
spec_version: 2
---
# 세션 시작

- 시작 조건: 세션을 시작할 때 (Claude Code: `/session-start`).
- 푸는 일반 규칙: 6번 중 `.lg/` 수정 금지 — 사람이 이미 커밋한 초안 파일(`.lg/pending/COMMIT_MSG`)을 지우는 것 (2단계).
- 끝나는 상태: 이번 세션에 할 일이 정해지고 사람에게 보고되었다.

## 단계

1. `scripts/session-check`를 실행한다. Claude Code에서는 세션 시작 hook이 이미 실행해 출력이 맥락에 있으므로 그 출력을 쓴다.
2. 출력이 "사람 커밋 대기 상태"이면: `git log`에 초안 첫 줄과 같은 헤더의 사람 커밋이 있는지 확인한다. 있으면(사람이 `git commit`으로 직접 커밋한 경우) 초안 파일을 지우고 계속한다. 없으면 사람에게 터미널에서 `lg commit` 실행을 요청하고, 아래 읽기 단계(4, 5, 7–9)만 한 뒤 보고하고 멈춘다.
3. 출력이 "커밋되지 않은 사람의 변경"이면 절차 [commit-prep](commit-prep.md)의 1단계(선택지 제시)를 한다. 사람이 답할 때까지는 아래 읽기 단계(4, 5, 7–9)만 하고 보고한다.
4. `STATUS.md`를 읽는다.
5. 현재 task 카드(`plan/milestones/<M>/tasks/<Task>.md`)를 읽는다. 상태가 `approved`, `in-progress`, `revise` 중 하나가 아니면 작업하지 않고 STATUS에 이유를 적은 뒤 절차 [session-close](session-close.md)로 간다.
6. 반영되지 않은 사람의 `gate`·`respond` 커밋이 있으면(review 문서가 `reviews/open/`에 남아 있거나, 카드·결정 상태가 커밋 trailer와 다르면) 절차 [gate-apply](gate-apply.md)를 먼저 한다.
7. 카드에 연결된 결정(`decisions/`)과 `references/<M>/task-map.md`를 읽는다.
8. `logs/`의 최근 일지 1–2개를 읽는다.
9. 이번 세션에 쓸 문서 유형의 사양(`specs/doc-types/`)을 읽는다.
10. 3–5줄로 보고한다: 사람 커밋 대기 상태나 사람의 변경(있으면 먼저), 현재 task와 상태, 반영한 사람 응답, 이번 세션에 할 일.
