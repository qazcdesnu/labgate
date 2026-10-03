# 에이전트와 하루 작업하기

- 언제: 에이전트에게 승인된 task를 맡길 때 (매 세션)
- 결과: 에이전트 커밋들, 작업 일지(`logs/`), 갱신된 `STATUS.md`. task가 끝나면 게이트 요청서(`reviews/open/`)

## 순서

| # | 터미널 | 할 일 |
|---|---|---|
| 1 | B | `/session-start` — 에이전트가 상태를 점검하고 오늘 할 일을 3–5줄로 보고한다 |
| 2 | B | 보고를 읽는다. 사람의 변경이나 사람 커밋 대기 상태가 있다고 하면 그것부터 처리한다 ([edit-yourself.md](edit-yourself.md)) |
| 3 | B | task가 `approved`이고 아직 시작 전이면 `/task-start <Task>` (예: `/task-start M0-T0`). 이미 진행 중이면 "계속해"로 충분하다 |
| 4 | B | 에이전트가 일한다. 중간에 질문하면 답한다. 범위·예산을 넘거나 판단이 필요하면 에이전트가 스스로 멈추고 에스컬레이션한다 ([respond-escalation.md](respond-escalation.md)) |
| 5 | A | 중간중간 확인: `git log --oneline -10`, `cat STATUS.md` |
| 6 | B | task가 끝나면 에이전트가 `/task-gate <Task>`로 게이트 요청서를 내고 멈춘다. 직접 지시해도 된다 |
| 7 | A·B | 판정한다 ([judge-gate.md](judge-gate.md)) |
| 8 | B | 그만할 때 `/session-close` — 일지와 STATUS를 남기고 커밋한다 |

세션 도중에는 코드·문서를 직접 고치지 않는 것이 좋다. 고쳤다면 에이전트에게 어떤 파일을 고쳤는지 알린다([edit-yourself.md](edit-yourself.md)).

## 확인

```bash
git log --format='%h %an | %s' -10    # 에이전트 커밋은 research-agent(설정한 이름), 사람 커밋은 나
git status --short                     # 세션 종료 뒤에는 비어 있어야 한다 (예외: 내 변경, 사람 커밋 대기)
ls reviews/open/                       # 판정을 기다리는 요청서
```

`STATUS.md`의 "사람 판단 대기"에 내가 할 일이 모여 있다.

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| 에이전트가 "카드가 approved가 아니라 작업할 수 없다"며 멈춤 | 승인 커밋이 카드에 반영되지 않았다. "커밋 `<해시>`로 승인됐으니 카드에 반영하고 진행해"라고 알린다 ([approve-task.md](approve-task.md)) |
| 에이전트가 커밋하지 않고 "사람 커밋 대기 상태"라고 함 | 초안이 확정을 기다린다. 터미널 A에서 `lg commit` |
| 세션 시작 때 "커밋되지 않은 사람의 변경"이 나옴 | 내 변경이 남아 있다 ([edit-yourself.md](edit-yourself.md)) |
| 슬래시 명령이 없음 | Claude Code를 프로젝트 폴더 밖에서 열었다. 프로젝트 폴더에서 다시 연다 |
| 에이전트가 `git commit`을 시도하다 막힘 | 정상이다. 에이전트는 `scripts/agent-commit`만 쓴다 |

## 에이전트는 무엇을 하나

- 세션 시작: `specs/procedures/session-start.md` (Claude Code는 시작할 때 `scripts/session-check`가 자동 실행)
- 착수: `specs/procedures/task-start.md`
- 게이트 요청: `specs/procedures/task-gate.md`
- 세션 종료: `specs/procedures/session-close.md`
