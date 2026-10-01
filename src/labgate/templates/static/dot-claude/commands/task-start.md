task $ARGUMENTS 를 착수한다. specs/workflow.md §5.1을 따른다.
1. 카드 상태가 approved 또는 revise인지 확인한다. 아니면 중단하고 이유를 보고한다.
2. 카드 상태를 in-progress로 바꾸고 updated를 갱신한다.
3. STATUS.md를 갱신한다.
4. scripts/agent-commit 으로 `task($ARGUMENTS): start` 커밋을 만든다 (Actor: agent, Task: $ARGUMENTS).
5. 카드의 완료 기준을 기준으로 이번 세션 작업 계획을 보고한다.
