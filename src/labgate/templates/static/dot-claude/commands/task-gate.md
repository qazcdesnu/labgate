task $ARGUMENTS 의 게이트 요청을 제출한다. specs/workflow.md §5.4와 specs/doc-types/review.spec.md를 따른다.
1. 완료 기준을 하나씩 점검한다. 충족하지 못한 기준이 있으면 게이트 대신 계속 작업할지 사용자에게 묻는다.
2. task 결과 문서(results/<M>/$ARGUMENTS_result.md)를 쓴다.
3. specs/templates/review.md 로 reviews/open/$ARGUMENTS_gate-NN.md 를 쓴다 (kind: gate).
4. 카드 상태를 in-review로, STATUS.md의 "사람 판단 대기"에 항목을 추가한다.
5. `review($ARGUMENTS): request gate` 커밋 (Actor: agent, Task: $ARGUMENTS, Review: <review id>).
6. 사람에게 무엇을 판정해야 하는지 요약해 보고하고 멈춘다.
