# 프로젝트 스크립트

`lg init`이 생성된 프로젝트 안에 만드는 실행 파일 네 개. 모두 Python 표준 라이브러리(Python 3.9 이상)와 `bash`만 쓰므로 `lg`가 설치되어 있지 않아도 동작한다.

| 파일 | 누가 실행 | 하는 일 |
|---|---|---|
| `scripts/agent-commit` | 에이전트 | 에이전트 신원으로 커밋 |
| `scripts/session-check` | 에이전트 (Claude Code는 hook이 자동) | 세션 시작 점검: 이미 커밋된 초안 정리, 대기 상태·반영되지 않은 사람 커밋·사람의 변경 알림 |
| `scripts/apply-human-commits` | 에이전트 | 사람 커밋의 결과를 상태 필드에 반영 (커밋하지 않음) |
| `.lg/hooks/commit-msg` | Git (모든 커밋) | 커밋 규약과 작성자 신원 검사 |

## scripts/agent-commit

에이전트 신원으로 커밋한다. 에이전트는 `git commit` 대신 이것만 쓴다.

```
scripts/agent-commit -m "<헤더>" -m "<trailer 블록>"
scripts/agent-commit -F <메시지 파일>
```

- `.lg/identities.json`의 `agent` 이름·이메일을 작성자와 커미터로 정하고 `git commit`에 나머지 인자를 그대로 넘긴다.
- 메시지를 여러 `-m`으로 줄 때는 마지막 `-m`이 trailer 블록이 되게 한다(각 `-m`은 빈 줄로 구분된 문단이 된다).
- **거부하는 옵션** (코드 2): `--no-verify`, `-n`(검사 우회), `--author`, `--author=…`(작성자를 사람으로 바꿀 수 있음), `-a`, `--all`(사람의 미커밋 변경까지 커밋함). `-am`, `-nm`처럼 묶인 짧은 옵션도 거부한다. 값을 받는 옵션(`-m`, `-F`, `-C`, `-c`, `-t`)의 값은 검사하지 않으므로, 메시지가 `-a`로 시작해도 괜찮다.
- 나머지 종료 코드는 `git commit`의 것이다(hook이 거부하면 1).

```bash
scripts/agent-commit -m "task(M0-T0): start initial planning" -m "Actor: agent
Task: M0-T0"
```

## scripts/session-check

세션을 시작할 때 실행한다. Claude Code에서는 `.claude/settings.json`의 SessionStart hook이 새 세션, 재개, `/clear`, compact 때마다 자동으로 실행하고, 출력이 에이전트의 맥락에 들어간다. 다른 도구에서는 에이전트가 절차 `session-start`의 첫 단계로 실행한다.

```
scripts/session-check
```

순서대로 확인하고, 해당하는 것을 모두 출력한다.

| # | 확인 | 출력 | 파일 |
|---|---|---|---|
| 1 | Git 저장소가 아님 | 없음 (끝) | — |
| 2 | 초안(`.lg/pending/COMMIT_MSG`)과 같은 메시지의 사람 커밋이 최근 20개 안에 있음 (`lg commit` 대신 `git commit -F`로 확정한 경우) | 초안을 정리했다는 안내 | 초안 삭제 |
| 3 | 초안이 남아 있음 (사람 커밋 대기 상태) | 대기 상태 안내 (4–6은 하지 않음) | — |
| 4 | 지난 반영 (`scripts/apply-human-commits --tidy`): 커밋됐으면 정리, 아니면 "반영했지만 커밋하지 않음" | 정리 안내, 또는 커밋 명령 안내 (5는 하지 않음) | `APPLY_MSG`·`APPLY_PATHS` 삭제 |
| 5 | 반영되지 않은 사람 커밋 (`scripts/apply-human-commits --check`) | 커밋 목록과 절차 `gate-apply` 안내 | — |
| 6 | 커밋되지 않은 변경 (커밋 대기 중인 반영의 경로는 뺌) | 사람의 변경 안내와 파일 목록(20개까지, 넘으면 "외 N개") | `.lg/pending/HUMAN_FILES`에 전체 목록. 깨끗하면 이 파일을 지움 |

- 세션 시작 시점의 커밋되지 않은 변경은 사람의 변경으로 본다. 이전 세션은 깨끗한 작업 트리로 끝나기 때문이다.
- 새 파일도 포함하고, 이름 바꾸기는 새 경로와 이전 경로를 모두 기록한다.
- 종료 코드는 항상 0이다(알리기만 한다).
- `lg draft`를 경로 없이 실행하면 이 목록의 경로만 stage한다.

## scripts/apply-human-commits

사람 커밋의 trailer가 정한 상태 전이를 문서의 상태 필드에 반영한다. **커밋하지 않는다.** 에이전트가 결과를 확인하고 `scripts/agent-commit`으로 커밋한다. 에이전트는 상태 필드를 손으로 고치지 않고 이 도구만 쓴다(절차 `gate-apply`).

```
scripts/apply-human-commits            # 가장 오래된 반영되지 않은 사람 커밋 하나를 반영
scripts/apply-human-commits --check    # 바꾸지 않고 반영되지 않은 사람 커밋을 나열
scripts/apply-human-commits --tidy     # 지난 반영의 커밋 여부 (session-check가 쓴다)
scripts/apply-human-commits --preview  # 표준 입력의 커밋 메시지가 반영되면 생길 변화. 쓰지 않는다 (lg answer가 쓴다, spec_version 5)
```

**반영 대상:** 사람이 작성한 `gate`, `respond`, `decide` 커밋과 `Approve`가 있는 `plan` 커밋 중, 뒤의 어떤 커밋의 `Applies` trailer에도 그 해시가 없는 것. 오래된 것부터 하나씩 반영한다.

| 사람 커밋 | 반영 |
|---|---|
| `plan` + `Approve: T` | 카드 T `draft → approved` |
| `gate` + `Verdict` | 카드 `in-review → closed / revise / redirected`, 게이트 이력 한 줄, review를 `reviews/closed/`로 |
| `gate` + `Next: T` | 카드 T `draft → approved` |
| `gate` approve, Task가 `<M>-T0` | 마일스톤 `planned → active` |
| `gate` + `Milestone-Verdict` | 마일스톤 `active → closed` |
| `respond` | 카드 `blocked → in-progress`, esc review를 `reviews/closed/`로 |
| `decide`, 또는 `gate` + `Decisions` | 결정 `proposed / discussing → confirmed`, 결정 목록의 상태와 확정 커밋 |

- 카드가 바뀌면 마일스톤 문서의 "Task 목록" 표에서 그 행의 상태도 바꾼다. 마일스톤이 바뀌면 `plan/roadmap.md`의 "마일스톤" 표에서 그 행의 상태도 바꾼다(spec_version 5, 절차 `gate-apply`의 G6 특별 규칙).
- 이미 목표 상태이거나 그 뒤의 상태면 건너뛴다(예: 승인됐는데 이미 `in-progress`). 이때도 반영 커밋은 만들어 `Applies`를 남긴다. 바꿀 파일이 없으면 출력이 그 이유를 알려 준다: 반영 여부는 `Applies`로만 판별하고 `Refs` 같은 다른 trailer는 기록으로 보지 않는다.
- 한 커밋의 전이 중 하나라도 할 수 없으면(카드가 출발 상태가 아님, 문서 없음) **아무것도 바꾸지 않는다.**
- 지난 반영이 아직 커밋되지 않았으면 새로 반영하지 않고(코드 2) 그 커밋 명령을 안내한다.
- `--preview`는 아직 커밋하지 않은 사람 커밋 메시지 하나를 표준 입력으로 받아, 반영 계획을 `미리보기: <헤더>`와 바뀔 줄들로 출력한다. 아무것도 쓰지 않는다. 반영할 수 없으면 코드 1. `lg answer`가 커밋 전에 판정의 효과를 보여 주고 반영할 수 없는 판정을 막는 데 쓴다.
- 반영하면 바뀐 내용, 커밋 명령, 메시지(`.lg/pending/APPLY_MSG`)와 경로 목록(`.lg/pending/APPLY_PATHS`)을 낸다. 메시지는 `log(<scope>): apply <타입> <해시>` + `Applies: <해시>`이고, `respond`면 `task(<Task>): resume after response <해시>`다.

```bash
scripts/apply-human-commits
# 반영: 70ea21b plan(M0-T0): approve initial task
#   plan/milestones/M0/tasks/M0-T0.md: status draft → approved
#   plan/milestones/M0/milestone.md: M0-T0 행 → approved
# 커밋: scripts/agent-commit -F .lg/pending/APPLY_MSG -- plan/milestones/M0/milestone.md plan/milestones/M0/tasks/M0-T0.md  (STATUS.md를 고쳤으면 함께)
```

| 종료 코드 | 의미 |
|---|---|
| 0 | 반영함, 또는 반영할 것이 없음 (`--check`는 항상 0) |
| 1 | 반영할 수 없음. 아무것도 바꾸지 않았다. 에이전트는 멈추고 사람에게 묻는다 |
| 2 | Git 저장소가 아님, 사람 커밋 대기 상태, 지난 반영이 커밋되지 않음, 반영할 파일에 커밋되지 않은 변경 |

## .lg/hooks/commit-msg

모든 커밋에서 Git이 실행한다(`lg init`이 `core.hooksPath`를 `.lg/hooks`로 설정한다). 저장소를 새로 클론했다면 이 설정을 다시 해야 한다(생성된 `README.md`의 "저장소를 새로 클론했을 때").

### 메시지 형식

```
<type>(<scope>): <요약>      ← 72자 이하

<본문 (선택)>

Actor: human | agent          ← trailer 블록 = 메시지의 마지막 한 문단
<기타 trailer>
```

trailer는 모두 마지막 한 문단에 쓴다. `Co-Authored-By` 같은 줄을 별도 문단으로 뒤에 붙이면 hook이 trailer를 찾지 못한다.

### 타입

| 분류 | 타입 | Actor |
|---|---|---|
| 사람 전용 | `gate`, `decide`, `plan`, `spec`, `respond` | `human` |
| 에이전트 전용 | `task`, `review`, `propose` | `agent` |
| 공통 | `exp`, `run`, `result`, `ref`, `log`, `init`, `chore` | 둘 다 |

### Trailer

| Key | 필수 | 값 |
|---|---|---|
| `Actor` | 항상 | `human` \| `agent`. 작성자 신원과 같아야 한다 |
| `Task` | `gate`, `respond`, `task`, `run`, `result`, `review` | `M<n>-T<n>`. 이 타입들은 scope가 Task와 같아야 한다 |
| `Verdict` | `gate` | `approve` \| `revise` \| `redirect` |
| `Source` | `gate`, `decide`, `respond` | `document` \| `conversation` |
| `Decisions` | `decide` (그 외 선택) | `D<n>.<n>` 쉼표 목록 |
| `Next` | 선택 (`gate`) | `M<n>-T<n>` 또는 `none` |
| `Milestone-Verdict` | 선택 (`gate`) | `go` \| `nogo` \| `conditional` |
| `Approve` | 선택 (`plan`) | `M<n>-T<n>` 쉼표 목록 |
| `Applies` | 선택 (반영 커밋) | 상태 필드에 반영한 사람 커밋의 해시(16진수 7–40자) 쉼표 목록 |
| `Refs`, `Review` | 선택 | 자유 형식 |

### 검사하지 않는 것

- 헤더가 `Revert `, `fixup! `, `squash! `, `amend! `로 시작하는 커밋
- 헤더가 `Merge `로 시작하는 커밋 (단, 작성자가 에이전트면 거부)

### 작성자 신원

커밋 작성자 이메일이 `.lg/identities.json`의 에이전트면 `agent`, 사람 중 하나면 `human`으로 보고 `Actor`와 비교한다. 어느 쪽도 아니면 "등록되지 않은 작성자"로 거부한다.

### 거부되면

오류를 모두 출력하고 종료 코드 1로 커밋을 막는다. 첫 줄은 `✗ 커밋 메시지가 규약(specs/git-commit.md)에 맞지 않습니다:`이다. `git commit --no-verify`로 우회할 수 있지만 사람이 긴급할 때만 쓰고, 다음 커밋 본문에 이유를 남긴다.

### lg와의 관계

`lg commit`, `lg draft`는 이 파일을 모듈로 읽어 타입·trailer 상수와 검사 함수 `check(text, check_author)`를 쓴다. 그래서 프로젝트를 만든 시점의 규약과 `lg`의 판단이 어긋나지 않는다.
