---
id: gate-apply
type: procedure
spec_version: 2
---
# 판정 후 정리

- 시작 조건: 사람의 `gate`·`respond` 커밋이 있는데 문서가 아직 반영하지 않았을 때 (세션 시작 시 확인, 절차 `gate-conversation` 이후).
- 푸는 일반 규칙: 6번 — 카드·결정·마일스톤 문서의 상태 필드를 사람 커밋의 trailer에 맞추는 것.
- 끝나는 상태: review 문서가 `reviews/closed/`에 있고, 상태 필드가 커밋과 같으며, 반영 커밋이 있다.

## 단계

1. review 문서를 `reviews/closed/`로 옮기고(`git mv`) `status: closed`로 바꾼다.
2. 카드·결정·마일스톤 문서의 상태 필드가 커밋 trailer와 다르면 맞춘다 ([workflow.md](../workflow.md) §6.4, §8).
3. 카드의 "게이트 이력"에 판정과 커밋 해시를 추가한다.
4. `STATUS.md`를 갱신하고 커밋한다.
   - `gate`: `log(<Task>): apply gate <해시>`
   - `respond`: 카드를 `in-progress`로 바꾸고 `task(<Task>): resume after response <해시>`
