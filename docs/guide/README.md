# 사용자 작업 설명서

사람이 하는 일을 상황별로, 처음부터 끝까지 따라 할 수 있게 정리했다. 명령의 세부(옵션, 종료 코드)는 [명령 설명서](../cli/README.md)에 있다.

이 설명서에서 **터미널 A**는 사람이 `lg` 명령을 치는 곳, **터미널 B**는 Claude Code(에이전트)가 일하는 곳이다. 둘 다 같은 프로젝트 폴더에서 연다.

## 지금 무엇을 하려는가

| 하려는 일 | 문서 |
|---|---|
| labgate를 설치하고 프로젝트를 만든다, 클론한 프로젝트를 설정한다 | [setup.md](setup.md) |
| 에이전트와 하루 작업을 한다 (세션 시작부터 끝까지) | [daily-loop.md](daily-loop.md) |
| task를 승인한다 (첫 task, 다음 task) | [approve-task.md](approve-task.md) |
| 에이전트의 게이트 요청을 판정한다 | [judge-gate.md](judge-gate.md) |
| 에이전트의 에스컬레이션(질문)에 답한다 | [respond-escalation.md](respond-escalation.md) |
| 코드·문서를 내가 직접 고쳤다 | [edit-yourself.md](edit-yourself.md) |
| 로드맵·마일스톤·사양을 바꾼다, 결정을 확정한다 | [change-plan.md](change-plan.md) |
| 잘못된 것을 바로잡는다 (커밋, 초안, 멈춘 에이전트) | [mistakes.md](mistakes.md) |
| labgate를 업데이트한다 | [upgrade.md](upgrade.md) |

## 사람이 하는 일과 에이전트가 하는 일

| 사람 (터미널 A) | 에이전트 (터미널 B) |
|---|---|
| task 승인, 게이트 판정, 에스컬레이션 응답, 결정 확정, 계획·사양 변경 | 승인된 task 수행, 문서·코드·실행 기록 작성 |
| 사람 신원의 커밋: `lg commit` | 에이전트 신원의 커밋: `scripts/agent-commit` |
| 직접 고친 코드·문서의 커밋 | 사람 커밋의 초안 준비: `lg draft` |
| tag (`lg commit`이 자동) | 사람 커밋의 결과를 문서 상태에 반영 |

## 사람에서 에이전트로 넘어가는 지점

사람이 무언가를 커밋하면 에이전트가 그 결과를 이어받는다. 각 지점에서 에이전트가 무엇을 하는지는 해당 문서의 "에이전트는 무엇을 하나"에 있다.

| # | 사람이 남기는 것 | 에이전트가 이어받아 하는 일 | 문서 |
|---|---|---|---|
| H1 | `plan` 커밋 + `Approve: <Task>` | 카드를 `approved`로 반영하고 착수 | [approve-task.md](approve-task.md) |
| H2 | `gate` 커밋 (`Verdict`, `Next`, `Milestone-Verdict`) | review 닫기, 카드·다음 카드·마일스톤 상태 반영 | [judge-gate.md](judge-gate.md) |
| H3 | `respond` 커밋 | review 닫기, 카드 `blocked → in-progress`, 작업 재개 | [respond-escalation.md](respond-escalation.md) |
| H4 | `decide` 커밋 | 결정 문서 상태 반영 | [change-plan.md](change-plan.md) |
| H5 | `plan`·`spec` 커밋 (계획·사양 변경) | 바뀐 계획·사양을 다음 작업부터 따름 | [change-plan.md](change-plan.md) |
| H6 | 커밋하지 않은 사람의 변경 | 세션 시작 때 감지, 작업 전에 정리 요청 | [edit-yourself.md](edit-yourself.md) |
| H7 | 대화로 전한 판정·결정·응답 | 문서에 반영하고 `lg draft`로 초안, 사람의 `lg commit` 대기 | [judge-gate.md](judge-gate.md) |

H1–H4의 상태 반영은 `scripts/apply-human-commits`가 한다(spec_version 3 이상). 에이전트는 결과를 확인하고 커밋하며, 반영 커밋은 `Applies: <사람 커밋 해시>`로 어떤 사람 커밋을 반영했는지 남긴다. spec_version 2 프로젝트에는 이 도구가 없어서, H1(`plan`의 `Approve`)과 H4(`decide`)의 반영은 에이전트의 판단에 기댄다. `lg upgrade`로 올리면 도구가 생긴다([upgrade.md](upgrade.md)).
