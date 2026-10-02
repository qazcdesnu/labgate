# 프로젝트 스크립트

`lg init`이 생성된 프로젝트 안에 만드는 실행 파일 세 개. 모두 Python 표준 라이브러리(Python 3.9 이상)와 `bash`만 쓰므로 `lg`가 설치되어 있지 않아도 동작한다.

| 파일 | 누가 실행 | 하는 일 |
|---|---|---|
| `scripts/agent-commit` | 에이전트 | 에이전트 신원으로 커밋 |
| `scripts/session-check` | 에이전트 (Claude Code는 hook이 자동) | 커밋되지 않은 사람의 변경을 알리고 기록 |
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

| 상태 | 출력 | `.lg/pending/HUMAN_FILES` |
|---|---|---|
| Git 저장소가 아님 | 없음 | 건드리지 않음 |
| 사람 커밋 대기 상태 (`.lg/pending/COMMIT_MSG` 있음) | 대기 상태 안내 | 건드리지 않음 |
| 커밋되지 않은 변경 있음 | 사람의 변경 안내와 파일 목록(20개까지, 넘으면 "외 N개") | 전체 목록을 한 줄에 하나씩 기록 |
| 깨끗함 | 없음 | 있으면 지움 |

- 세션 시작 시점의 커밋되지 않은 변경은 사람의 변경으로 본다. 이전 세션은 깨끗한 작업 트리로 끝나기 때문이다.
- 새 파일도 포함하고, 이름 바꾸기는 새 경로와 이전 경로를 모두 기록한다.
- 종료 코드는 항상 0이다(알리기만 한다).
- `lg draft`를 경로 없이 실행하면 이 목록의 경로만 stage한다.

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
