---
id: escalate
type: procedure
spec_version: 4
---
# 에스컬레이션

- 시작 조건: [workflow.md](../workflow.md) §7.1의 경우 (Claude Code: `/escalate <Task>`).
- 끝나는 상태: 카드가 `blocked`이고 에스컬레이션 문서와 `review` 커밋이 있다. 사람의 응답을 기다린다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. `specs/templates/review.md`로 `reviews/open/<Task>_esc-NN.md`를 쓴다 (`kind: escalation`): 무엇이 막혔는지, 선택지, 각 선택지의 영향, 추천안.
2. 카드를 `blocked`로 바꾸고, `STATUS.md`의 "막힘"과 "사람 판단 대기"를 갱신한다.
3. `review(<Task>): escalate <요약>` 커밋 (`Actor: agent`, `Task: <Task>`).
4. 사람에게 질문을 요약해 보고하고 멈춘다.
5. 사람의 응답은 `respond` 커밋으로 온다. 대화로 답하면 절차 [gate-conversation](gate-conversation.md), 커밋 이후에는 절차 [gate-apply](gate-apply.md).
