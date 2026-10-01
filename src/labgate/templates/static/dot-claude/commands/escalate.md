task $ARGUMENTS 에서 에스컬레이션을 제출한다. specs/workflow.md §7을 따른다.
1. specs/templates/review.md 로 reviews/open/$ARGUMENTS_esc-NN.md 를 쓴다 (kind: escalation). 무엇이 막혔는지, 선택지, 각 선택지의 영향, 추천안을 쓴다.
2. 카드 상태를 blocked로, STATUS.md의 "막힘"과 "사람 판단 대기"를 갱신한다.
3. `review($ARGUMENTS): escalate <요약>` 커밋 (Actor: agent, Task: $ARGUMENTS).
4. 사람에게 질문을 요약해 보고하고 멈춘다.
