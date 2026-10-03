# `labgate` CLI 설계 문서 — v3 (`lg init`, `lg commit`, `lg draft`, 프로젝트 도구)

> 문서 버전: 3.0 · 대상: CLI 구현자(사람 또는 코딩 에이전트)
> 이 문서만으로 `lg init`, `lg commit`, `lg draft`를 구현·테스트할 수 있어야 한다. 생성될 모든 파일의 원문은 부록 A·B·C에 있다.

변경 이력은 `git log -- labgate-design.md`로 본다.

---

## 0. 읽는 법

- §1–3: 무엇을 왜 만드는가 (범위, 확정된 결정, 용어)
- §4–13: `lg init`을 어떻게 만드는가 (명령, 설정, 생성 결과, 모듈, Git, hook, 오류)
- §14–15: 무엇으로 완성을 판단하는가 (테스트, 수용 기준), 이후 확장
- §16–21: v2·v3 — 규칙의 층과 우선순위, 사람의 변경과 `session-check`, `lg commit`, `lg draft`, 한계, `apply-human-commits`
- 부록 A: 프로젝트 루트·계획·참고문헌 등 생성 문서 템플릿 원문
- 부록 B: `specs/` 문서 원문 (완성 사양 5종, stub 생성 규칙, 양식, 절차 문서 8종)
- 부록 C: commit-msg hook, agent-commit, session-check, apply-human-commits 스크립트 원문

표기: `<...>`는 값 자리, `{{ ... }}`/`{% ... %}`는 Jinja2 템플릿 문법이다.

---

## 1. 목적과 범위

### 1.1 목적

에이전트(초기에는 Claude Code)가 작업하고 사람이 task 경계마다 승인하는 연구 프로젝트의 작업 공간을 한 번의 명령으로 초기화한다. 초기화 결과에는 폴더 구조, 문서 사양, 에이전트 규칙, 커밋 규약 검사 hook, 초기 Git 커밋이 포함된다.

v2는 초기화된 프로젝트 안에서 쓰는 명령을 더한다. 사람의 변경을 사람 신원으로 확정하는 `lg commit`(사람 전용)과, 그 커밋의 초안을 준비하는 `lg draft`(에이전트도 사용)다. 함께 에이전트 규칙을 매 세션 읽는 일반 규칙(`AGENTS.md`)과 상황별로 읽는 절차 문서(`specs/procedures/`)로 나눈다.

### 1.2 범위

| 포함 | 제외 (§15 향후 확장) |
|---|---|
| `lg init` (대화형 / 설정 파일) | `lg gate`, `lg status`, `lg validate`, `lg upgrade` |
| `lg commit`, `lg draft` (§18, §19) | 세션 도중 사람 변경의 자동 감지 (§20) |
| 절차 문서 8종, `scripts/session-check` (§16, §17) | Claude Code 외 도구의 hook 연결 |
| 폴더·문서 생성, 완성 사양 5종, stub 사양 11종 | 기존 계획서 자동 가져오기 |
| `commit-msg` hook, `scripts/agent-commit` | 문서 내용 검증 도구 |
| Claude Code 연결 파일 (선택) | 다른 에이전트 도구 연결 |
| Git 저장소 초기화, 사람 신원의 `init` 커밋 | 원격 저장소 설정 |
| 문서 언어: 한국어 | 다국어 템플릿 |

---

## 2. 확정된 설계 결정

| 항목 | 결정 |
|---|---|
| 브랜치 | `main` 하나의 선형 이력. task 브랜치 없음. 게이트 지점은 tag(`gate/<Task>`, `milestone/<M>-<verdict>`)로 표시. Claude Code 워크트리(`worktree-<name>` 브랜치)는 **실험 격리용**으로만 쓰고 `main`에 병합·cherry-pick하지 않는다. 채택할 결과는 `main`에서 다시 커밋한다 |
| 승인 단위 | task = 승인 게이트 사이의 작업 단위. 게이트 1회가 "현재 task 판정 + 다음 task 승인"을 함께 처리 |
| 사람/에이전트 구분 | (1) 커밋 작성자 신원 분리, (2) 사람 전용 커밋 타입. hook으로 둘의 일치를 강제 |
| 커밋 타입 분류 | 판정·확정은 사람 전용(`gate`, `decide`, `plan`, `spec`, `respond`), 에이전트가 사람에게 요청하는 흐름은 에이전트 전용(`task`, `review`, `propose`). 작업 내용(`exp`, `run`, `result`, `ref`, `log`)은 공통이다. 사람도 코드·문서를 직접 고치므로, 누가 했는지는 타입이 아니라 작성자 신원과 `Actor`로 구분한다 |
| 사람의 미커밋 변경 | 에이전트는 자기가 바꾼 파일만 경로를 지정해 stage한다. 세션 시작 때 이미 있던 변경은 사람의 것으로 보고 stage·커밋·되돌리기를 하지 않는다. 사람이 요청하면 stage와 메시지 초안(`lg draft`)까지 준비하고, 커밋은 사람이 한다(`lg commit`) |
| 규칙 층 | 일반 규칙(`AGENTS.md`)은 언제나 지켜야 하는 불변 규칙만 담는다. 시작 조건이 있는 단계 목록은 절차 문서(`specs/procedures/`)로 두고 그때만 읽는다 (§16) |
| 예외의 표기 | 절차가 일반 규칙을 풀면 일반 규칙 쪽에 "예외: 절차 X", 절차 쪽에 "푸는 일반 규칙: N번"을 함께 적는다. 절차는 규칙을 좁게 풀 수만 있다 |
| 사람 신원의 커밋 | 사람만 만든다. 에이전트는 `git commit`, `lg commit`을 실행하지 않는다. 에이전트가 할 수 있는 최대치는 stage와 초안(`lg draft`)이다 |
| 확정의 조건 | `lg commit`은 표준 입력과 출력이 모두 터미널일 때만 커밋한다 (§18) |
| 사람 변경의 감지 | 세션 시작 시 `scripts/session-check`가 커밋되지 않은 변경을 알리고 목록을 `.lg/pending/HUMAN_FILES`에 기록한다. Claude Code는 SessionStart hook으로, 다른 도구는 `session-start` 절차의 첫 단계로 실행한다 (§17) |
| 커밋 규칙의 원본 | 프로젝트의 `.lg/hooks/commit-msg`. `lg`는 그 파일을 모듈로 읽어 상수와 검사 함수를 쓰고, 최종 검증은 커밋할 때 hook이 한다 |
| `lg`의 위치 | 생성된 프로젝트에서 `lg`는 편의 도구다. `lg` 없이 `git commit`으로 커밋해도 hook을 통과하면 유효하다 |
| `gate` 커밋 | v2에서는 `lg commit`이 받는다(tag 포함). `lg gate`가 생기면 그쪽으로 옮긴다 |
| 대화로 전달된 판정 | 에이전트는 변경을 stage하고 커밋 메시지 초안만 작성(`lg draft`). 커밋은 사람이 실행(`lg commit`) |
| 참고문헌 원본 | 전부 Git에 포함 (비공개 저장소 전제). `references/library/`에 ID 파일명으로 한 번만 저장 |
| 사양 작성 순서 | `conventions`, `workflow`, `git-commit`, `task-card`, `review` 5종과 절차 문서 8종은 완성본으로 생성. 나머지 11종은 stub으로 생성 후 M0 진행 중 보완 |
| 게이트 요청과 에스컬레이션 | 하나의 사양(`review.spec.md`)으로 통합, `kind: gate | escalation`으로 구분 |
| 기존 계획서 가져오기 | v1 제외. `M0-T0` task에서 에이전트가 이관 |
| 규칙의 원본 | 도구 중립 문서(`AGENTS.md`, `specs/`). `CLAUDE.md`, `.claude/`는 연결 계층 |
| 사실의 원본 | Git 커밋(특히 사람 커밋의 trailer). 문서의 상태 필드는 이를 반영한 것이며, 불일치 시 커밋이 우선 |

---

## 3. 용어

| 용어 | 뜻 |
|---|---|
| 마일스톤 | `M0`, `M1`, … 연구의 큰 단계 |
| Task | `M1-T2`처럼 마일스톤 안의 작업 단위. 승인 게이트 사이 구간 |
| T0 | 모든 마일스톤의 첫 task. 문헌 정리와 task 분해(착수 계획) |
| 게이트 | task 종료 시 사람이 판정하는 지점 |
| 에스컬레이션 | task 진행 중 에이전트가 사람의 판단을 요청하고 멈추는 것 |
| 사람 전용 타입 | `gate`, `decide`, `plan`, `spec`, `respond` 커밋 타입 |
| stub 사양 | 공통 구조만 있고 내용은 TODO인 사양 문서 |
| 일반 규칙 | `AGENTS.md`의 "반드시 지킬 규칙". 언제나 지킨다 |
| 절차 | `specs/procedures/<name>.md`. 시작 조건이 있을 때 읽고 따르는 단계 목록 |
| 사람의 변경 | 사람이 직접 고쳤고 아직 커밋되지 않은 변경. 세션 시작 시점에 커밋되지 않은 변경은 사람의 변경으로 본다 |
| 사람 커밋 대기 상태 | `.lg/pending/COMMIT_MSG`가 있는 상태. stage된 변경이 사람의 `lg commit`을 기다린다 |

---

## 4. 기술 스택과 실행 환경

| 항목 | 선택 |
|---|---|
| 언어 | Python 3.10–3.14 지원 (CLI, 다섯 버전 모두에서 테스트 통과가 조건). 생성되는 hook은 Python ≥ 3.9 표준 라이브러리만 사용 |
| 명령 구조 | `typer` ≥ 0.15.4. 그 아래 버전은 click 상한을 두지 않아 최신 click과 함께 설치되는데, 이 조합에서 0.12는 `--version`이 "Missing command"로, 0.13–0.15.3은 `--help`가 `make_metavar()` 오류로 실패한다 |
| 대화형 입력 | `questionary` ≥ 2.0 |
| 템플릿 | `jinja2` ≥ 3.1 |
| 설정 | `pyyaml` ≥ 6.0.2, 검증은 `pydantic` ≥ 2.8 (이보다 낮으면 Python 3.12/3.13용 wheel이 없어 설치 실패). Python 3.14에서는 `pyyaml` ≥ 6.0.3, `pydantic` ≥ 2.12 (환경 마커) |
| 테스트 | `pytest` |
| 배포 | `pipx install .` (패키지명·import 이름 `labgate`, 명령명 `lg`) |
| 외부 의존 | `git` 실행 파일 (`--no-git`이면 불필요), 생성된 프로젝트에서 `python3`, `bash`. 생성된 프로젝트에서 `lg`는 권장(필수 아님, §2) |
| 지원 OS | macOS, Linux. Windows는 Git Bash 환경에서 최선 노력(공식 지원 아님) |

이름은 labgate(연구실 lab + 승인 게이트 gate), 명령명은 그 이니셜 `lg`다. PyPI의 `rp` 패키지("Ryan's Python")가 같은 이름의 명령과 import 패키지를 설치해 충돌하므로 처음 쓰던 `rp`를 버렸다. 생성되는 프로젝트의 도구 폴더는 `.lg/`다.

---

## 5. 명령 사양: `lg init`

### 5.1 형식

```
lg init [PATH] [--config FILE] [--force] [--dry-run] [--no-git] [--yes]
lg --version
```

| 인자/옵션 | 설명 |
|---|---|
| `PATH` | 생성할 프로젝트 폴더. 생략 시 대화형으로 묻는다. `--config` 사용 시 필수 |
| `--config FILE` | 설정 파일(§6.1 형식)로 모든 입력을 받는다. 대화형 질문 없음 |
| `--force` | 비어 있지 않은 폴더에도 생성을 허용한다. **기존 파일을 덮어쓰지는 않는다** (§5.3). Git을 쓰면 원래 있던 파일도 `git add -A`로 `init` 커밋에 포함된다 |
| `--dry-run` | 생성될 파일 트리와 개수만 출력하고 아무것도 쓰지 않는다 |
| `--no-git` | Git 초기화, hook 경로 설정, 초기 커밋을 하지 않는다 |
| `--yes`, `-y` | 대화형 모드의 마지막 확인 질문을 건너뛴다 |

Typer는 명령이 하나뿐인 앱에서 하위 명령을 생략해 버리므로, `@app.callback()`으로 빈 콜백을 등록해 `lg init` 형태를 유지한다.

### 5.2 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 성공 (dry-run 포함) |
| 1 | 예기치 못한 실행 오류 |
| 2 | 사용법·설정 검증 오류 |
| 3 | 대상 폴더 충돌 (비어 있지 않음, 파일 충돌) |
| 4 | Git 관련 오류 (Git 없음, 이미 Git 저장소 내부, 커밋 실패) |
| 130 | 사용자가 중단 (Ctrl-C, 확인 거부) |

### 5.3 동작 순서

1. **경로 확정.** `PATH` 인자, 또는 대화형 첫 질문(§6.3 #1)으로 대상 경로를 정한다. `--config`인데 `PATH`가 없으면 코드 2.
2. **대상 폴더 검사.** 나머지 입력을 받기 전에 한다(대화형에서 질문에 다 답한 뒤 실패하지 않도록).
   - 존재하지 않음 → 진행. 상위 폴더가 없어도 진행한다(쓰기 단계에서 만든다, §8.3).
   - 존재하는데 폴더가 아님 → 코드 3.
   - 존재하고 비어 있음 → 진행.
   - 존재하고 비어 있지 않음 → `--force` 없으면 코드 3. (파일 단위 충돌 검사는 생성 계획이 나온 뒤 4단계에서 한다.)
3. **Git 사전 검사** (`--no-git`이 아닐 때). 이것도 나머지 입력 전에 한다.
   - `git --version` 실패 → 코드 4.
   - 대상 폴더(또는 존재하는 가장 가까운 상위 폴더)에서 `git rev-parse --is-inside-work-tree`가 `true` → 중첩 저장소를 막기 위해 코드 4. 메시지에 `--no-git` 사용 안내. (Git 저장소 밖이면 이 명령은 0이 아닌 코드로 끝나는데, 이는 "저장소 아님"으로 처리한다.)
   - **`--dry-run`이면** 위 두 경우를 오류 대신 경고로 출력하고 계속한다(아무것도 쓰지 않으므로).
4. **입력 수집과 설정 검증.** `--config`가 있으면 파일을 읽고, 없으면 §6.3의 나머지 질문을 한다. §6.2 규칙으로 검증하고, 실패 시 모든 오류를 모아 출력하고 코드 2.
5. **생성 계획 작성.** §7의 표대로 `PlannedFile(path, content, mode)` 목록을 메모리에 만든다. 이 단계에서 모든 템플릿을 렌더링한다. 렌더링 오류는 코드 1. 대상 폴더가 존재하고 `--force`이면, 생성할 경로와 같은 파일이 하나라도 있을 때 충돌 목록을 출력하고 코드 3 (dry-run이면 경고만). 디렉터리가 이미 있는 것은 충돌이 아니다.
6. **dry-run이면** 트리와 파일 수를 출력하고 코드 0.
7. **대화형 모드이고 `--yes`가 아니면** 입력 요약을 보여주고 확인을 받는다. 거부 시 코드 130.
8. **파일 쓰기.** §8.3 쓰기 규칙.
9. **Git 초기화.** §10. 실패 시 생성된 파일은 그대로 두고, 실패한 단계와 수동 복구 명령을 출력한 뒤 코드 4.
10. **다음 단계 안내 출력** (§5.4).

어느 단계에서든 Ctrl-C(`KeyboardInterrupt`, questionary가 `None`을 돌려주는 경우 포함)와 대화형 입력 중 입력 종료(EOF, Ctrl-D)는 쓰기 전이면 그대로, 쓰기 중이면 §8.3 롤백 후 코드 130으로 끝낸다. Git 초기화 중 중단이면 생성된 파일은 그대로 두고 그 사실을 알린다. Typer/click의 기본 `Abort` 처리(코드 1)에 맡기지 않는다.

대화형 모드(`--config` 없음)는 표준 입력이 터미널일 때만 진행한다. 아니면 `--config` 사용을 안내하고 코드 2.

`--dry-run`의 트리는 §7.1 모양(폴더별로 파일 먼저, 그다음 하위 폴더)으로 출력하고, 실행 파일 뒤에 `*`를 붙인다.

### 5.4 성공 시 출력 예

```
✓ 프로젝트를 만들었습니다: /home/me/research/cap-partition
  파일 78개, 초기 커밋 3f2a1c9 (init)

다음 단계:
  1. notes/ 에 기존 계획 자료를 넣으세요.
  2. STATUS.md 를 확인하고, M0-T0 을 승인하세요:
       git commit --allow-empty -m "plan(M0-T0): approve initial task" -m "Actor: human
     Approve: M0-T0"
     (M0-T0 카드의 status 를 approved 로 바꿔 함께 커밋해도 됩니다)
     또는 터미널에서 lg commit --allow-empty (타입 plan, Approve M0-T0)
  3. 에이전트 세션을 시작하세요 (Claude Code: /session-start)
```

- 2번의 `M0`는 첫 마일스톤 ID다.
- `--no-git`이면 둘째 줄은 `파일 N개 (Git 초기화 안 함: --no-git)`이고, 2번은 Git 초기화 명령(§10.1의 1–3)을 먼저 실행하라는 안내로 바뀐다.
- Claude Code를 쓰지 않으면 3번은 `AGENTS.md`의 "세션 시작 절차"를 가리킨다.

---

## 6. 설정

### 6.1 설정 파일 형식 (`--config`, 그리고 생성되는 `.lg/project.yaml`)

```yaml
schema_version: 1
project:
  name: "Capacity-Driven Adaptive State Partitioning"
  slug: cap-partition
  summary: "Log-linear attention의 Fenwick 분할을 state 포화도 기반 적응 분할로 대체하는 연구"
  research_question: "같은 state 예산에서 capacity 기반 분할이 long-context recall을 개선하는가?"
people:
  humans:
    - name: "홍길동"
      email: "gildong@example.com"
  agent:
    name: "research-agent"
    email: "agent@cap-partition.local"
agent_tools:
  claude_code: true
milestones:
  - title: "기반 구축 및 재현"
  - title: "디텍터 신호 유효성 검증"
  - title: "Split-only 적응 분할"
```

- 마일스톤 ID는 입력하지 않는다. 순서대로 `M0`, `M1`, …을 부여한다. 설정 파일에 `id`가 있으면 순서와 일치하는지 검사하고, 다르면 오류.
- `people.agent`는 생략 가능하다. 기본값: 이름 `research-agent`, 이메일 `agent@<slug>.local`.
- 생성되는 `.lg/project.yaml`에는 위 내용에 다음이 추가된다:
  ```yaml
  generated:
    labgate_version: "0.3.0"
    spec_version: 3
    created: "2026-10-01"
  ```

### 6.2 검증 규칙

| 필드 | 규칙 |
|---|---|
| `schema_version` | `1` |
| `project.name` | 1–100자, 줄바꿈 없음 |
| `project.slug` | `^[a-z0-9][a-z0-9-]{0,39}$` |
| `project.summary` | 1–200자, 줄바꿈 없음 |
| `project.research_question` | 1–500자, 줄바꿈 없음 |
| `people.humans` | 1명 이상. `name` 1–60자, `email`은 `^[^@\s]+@[^@\s]+$` |
| 이메일 전체 | 소문자로 정규화. 사람끼리 중복 불가, 에이전트 이메일은 어떤 사람과도 같으면 안 됨 |
| `people.agent.name` | 1–60자 |
| `agent_tools.claude_code` | bool, 기본 `true` |
| `milestones` | 1–20개. `title` 1–80자, 줄바꿈 없음 |

검증은 pydantic 모델로 구현하고, 오류는 필드 경로와 함께 전부 모아 한 번에 출력한다.

### 6.3 대화형 질문 순서

| # | 질문 | 기본값 / 처리 |
|---|---|---|
| 1 | 프로젝트 경로 | `PATH` 인자가 있으면 생략. 답한 직후 §5.3의 2–3단계(폴더·Git 검사)를 한다 |
| 2 | 프로젝트 이름 | 필수 |
| 3 | slug | 경로의 마지막 이름을 소문자화하고 `[a-z0-9-]` 외 문자를 `-`로 바꾼 값. 결과가 규칙에 안 맞으면 기본값 없이 재질문 |
| 4 | 한 줄 요약 | 필수 |
| 5 | 핵심 연구 질문 | 필수 |
| 6 | 사람 이름 | `git config --global user.name` (없으면 빈 값) |
| 7 | 사람 이메일 | `git config --global user.email` |
| 8 | 사람을 더 추가할까요? | 기본 No. Yes면 6–7 반복 |
| 9 | 에이전트 이름 | `research-agent` |
| 10 | 에이전트 이메일 | `agent@<slug>.local` |
| 11 | Claude Code를 사용합니까? | 기본 Yes |
| 12 | 마일스톤 제목 반복 입력 | 프롬프트 `M<n> 제목 (빈 입력이면 종료)`. 최소 1개 |
| 13 | 요약 확인 | `--yes`면 생략 |

각 질문 직후 해당 필드를 검증하고, 실패하면 이유를 보여주고 같은 질문을 다시 한다.

---

## 7. 생성 결과

### 7.1 디렉터리 트리 (마일스톤 3개, Claude Code 사용 시)

```
<project>/
├── README.md
├── FILEMAP.md
├── AGENTS.md
├── CLAUDE.md                          # claude_code=true
├── STATUS.md
├── .gitignore
├── .lg/
│   ├── project.yaml
│   ├── identities.json
│   ├── hooks/
│   │   └── commit-msg                 # 실행 권한
│   └── pending/                       # Git 제외. 생성하지 않음 (실행 중 COMMIT_MSG, HUMAN_FILES)
├── .claude/                           # claude_code=true
│   ├── settings.json
│   └── commands/
│       ├── session-start.md
│       ├── task-start.md
│       ├── task-gate.md
│       ├── escalate.md
│       ├── session-close.md
│       └── commit-prep.md
├── specs/
│   ├── README.md
│   ├── conventions.md
│   ├── workflow.md
│   ├── git-commit.md
│   ├── doc-types/
│   │   ├── task-card.spec.md          # 완성
│   │   ├── review.spec.md             # 완성
│   │   ├── roadmap.spec.md            # stub
│   │   ├── milestone.spec.md          # stub
│   │   ├── task-map.spec.md           # stub
│   │   ├── catalog.spec.md            # stub
│   │   ├── decision.spec.md           # stub
│   │   ├── experiment-readme.spec.md  # stub
│   │   ├── run-record.spec.md         # stub
│   │   ├── task-result.spec.md        # stub
│   │   ├── milestone-report.spec.md   # stub
│   │   ├── worklog.spec.md            # stub
│   │   └── status.spec.md             # stub
│   ├── templates/
│   │   ├── task-card.md
│   │   └── review.md
│   └── procedures/
│       ├── session-start.md
│       ├── session-close.md
│       ├── commit-prep.md
│       ├── task-start.md
│       ├── task-gate.md
│       ├── escalate.md
│       ├── gate-conversation.md
│       └── gate-apply.md
├── plan/
│   ├── roadmap.md
│   └── milestones/
│       ├── M0/
│       │   ├── milestone.md
│       │   └── tasks/
│       │       └── M0-T0.md
│       ├── M1/ (동일)
│       └── M2/ (동일)
├── decisions/
│   └── index.md
├── references/
│   ├── catalog.md
│   ├── library/.gitkeep
│   ├── M0/task-map.md
│   ├── M1/task-map.md
│   └── M2/task-map.md
├── experiments/
│   ├── src/.gitkeep
│   ├── tests/.gitkeep
│   ├── M0/.gitkeep
│   ├── M1/.gitkeep
│   └── M2/.gitkeep
├── runs/.gitkeep
├── results/
│   ├── M0/figures/.gitkeep
│   ├── M0/tables/.gitkeep
│   └── … (M1, M2 동일)
├── reviews/
│   ├── open/.gitkeep
│   └── closed/.gitkeep
├── logs/.gitkeep
├── data/.gitkeep
├── paper/.gitkeep
├── notes/.gitkeep
├── scripts/
│   ├── agent-commit                   # 실행 권한
│   ├── apply-human-commits            # 실행 권한
│   └── session-check                  # 실행 권한
└── env/.gitkeep
```

### 7.2 파일 생성 표

"원문"은 이 문서에서 템플릿 원문이 있는 위치다. 종류: **J** = Jinja2 렌더링, **S** = 그대로 복사, **G** = 코드가 직접 생성.

| 출력 경로 | 종류 | 원문 | 조건/반복 | 권한 |
|---|---|---|---|---|
| `README.md` | J | A.1 | | 644 |
| `FILEMAP.md` | J | A.2 | | 644 |
| `AGENTS.md` | J | A.3 | | 644 |
| `CLAUDE.md` | J | A.4 | claude_code | 644 |
| `.claude/settings.json` | S | A.5 | claude_code | 644 |
| `.claude/commands/<name>.md` | S | A.6 | claude_code, 6개 | 644 |
| `STATUS.md` | J | A.7 | | 644 |
| `.gitignore` | S | A.8 | | 644 |
| `.lg/project.yaml` | G | §6.1 | | 644 |
| `.lg/identities.json` | G | §10.3 | | 644 |
| `.lg/hooks/commit-msg` | S | C.1 | | 755 |
| `scripts/agent-commit` | S | C.2 | | 755 |
| `scripts/session-check` | S | C.3 | | 755 |
| `scripts/apply-human-commits` | S | C.4 | | 755 |
| `plan/roadmap.md` | J | A.9 | | 644 |
| `plan/milestones/<M>/milestone.md` | J | A.10 | 마일스톤마다 | 644 |
| `plan/milestones/<M>/tasks/<M>-T0.md` | J | A.11 | 마일스톤마다 | 644 |
| `decisions/index.md` | J | A.12 | | 644 |
| `references/catalog.md` | J | A.13 | | 644 |
| `references/<M>/task-map.md` | J | A.14 | 마일스톤마다 | 644 |
| `specs/README.md` | J | B.1 | | 644 |
| `specs/conventions.md` | S | B.2 | | 644 |
| `specs/workflow.md` | S | B.3 | | 644 |
| `specs/git-commit.md` | S | B.4 | | 644 |
| `specs/doc-types/task-card.spec.md` | S | B.5 | | 644 |
| `specs/doc-types/review.spec.md` | S | B.6 | | 644 |
| `specs/doc-types/<name>.spec.md` | J | B.7 | stub 11개 (B.7 표) | 644 |
| `specs/templates/task-card.md` | S | B.8 | | 644 |
| `specs/templates/review.md` | S | B.9 | | 644 |
| `specs/procedures/<name>.md` | S | B.10 | 8개 | 644 |
| `.gitkeep` 들 | G | 빈 파일 | §7.1의 빈 폴더마다 | 644 |

`.gitkeep` 목록: `references/library/`, `experiments/src/`, `experiments/tests/`, `experiments/<M>/`, `runs/`, `results/<M>/figures/`, `results/<M>/tables/`, `reviews/open/`, `reviews/closed/`, `logs/`, `data/`, `paper/`, `notes/`, `env/`.

모든 텍스트 파일은 UTF-8, LF 줄바꿈, 파일 끝 개행 1개로 쓴다.

생성 파일 수 (마일스톤 N개): `claude_code=true`이면 `60 + 6N`, `false`이면 `52 + 6N` (`CLAUDE.md`와 `.claude/` 8개 제외). 마일스톤 하나당 6개는 `milestone.md`, `<M>-T0.md`, `task-map.md`, `.gitkeep` 3개(`experiments/<M>/`, `results/<M>/figures/`, `results/<M>/tables/`)다. 예: N=3, Claude Code 사용 → 78개.

---

## 8. 패키지 구조와 모듈 책임

### 8.1 소스 트리

```
labgate/
├── pyproject.toml
├── README.md
├── src/labgate/
│   ├── __init__.py          # __version__, SPEC_VERSION = 3
│   ├── cli.py               # Typer 앱, init·commit·draft 명령, 종료 코드 처리
│   ├── project.py           # 생성된 프로젝트 찾기, spec_version·신원 확인, hook 규칙 읽기 (§18.3)
│   ├── errors.py            # 종료 코드, Fail 예외
│   ├── commit.py            # lg commit (§18)
│   ├── draft.py             # lg draft (§19)
│   ├── config.py            # pydantic 모델, YAML 로드/저장, 정규화
│   ├── prompts.py           # questionary 대화형 입력
│   ├── plan.py              # 생성 계획(PlannedFile 목록) 작성
│   ├── render.py            # Jinja2 환경, 컨텍스트, 필터
│   ├── stubs.py             # stub 사양 정의 표 (B.7)
│   ├── writer.py            # 충돌 검사, 쓰기, 롤백
│   ├── gitops.py            # Git 명령 래퍼
│   └── templates/
│       ├── jinja/           # .j2 파일 (출력 경로 구조를 그대로 따름)
│       └── static/          # 그대로 복사할 파일
└── tests/
```

`templates/` 아래 파일 이름은 출력 경로를 따른다. 예: `jinja/plan/milestones/milestone.md.j2`, `static/specs/workflow.md`. 반복 생성되는 파일은 `plan.py`가 템플릿 하나를 여러 경로로 렌더링한다. 템플릿은 `importlib.resources.files("labgate") / "templates"`로 읽는다.

예외: 출력 경로가 `.`으로 시작하는 파일·폴더는 템플릿 쪽에서 앞의 `.`을 빼고 `dot-`를 붙여 저장한다 (`static/dot-gitignore` → `.gitignore`, `static/dot-claude/settings.json` → `.claude/settings.json`, `static/dot-lg/hooks/commit-msg` → `.lg/hooks/commit-msg`). 이유: (1) `templates/static/.gitignore`를 그대로 두면 이 CLI 저장소의 Git이 그것을 실제 ignore 규칙으로 적용해 템플릿 폴더 안의 파일을 무시한다. (2) 빌드 도구가 숨김 파일·VCS 무시 파일을 패키지에서 빼는 경우가 있다. 변환은 `plan.py`의 경로 매핑 한 곳에서만 한다. 패키지 테스트에서 wheel에 모든 템플릿이 들어갔는지 확인한다.

### 8.2 `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "labgate"
version = "0.3.0"
requires-python = ">=3.10"
dependencies = [
  "typer>=0.15.4",
  "questionary>=2.0",
  "jinja2>=3.1",
  "pyyaml>=6.0.2",
  "pydantic>=2.8",
  "pyyaml>=6.0.3; python_version >= '3.14'",
  "pydantic>=2.12; python_version >= '3.14'",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
lg = "labgate.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/labgate"]
```

### 8.3 쓰기 규칙 (`writer.py`)

- **대상이 존재하지 않을 때:** 부모 폴더가 없으면 먼저 `os.makedirs`로 만들고, 이때 새로 만든 상위 폴더를 기록해 둔다. 같은 부모 폴더에 `.<name>.lg-tmp-<8자리 hex>` 임시 폴더를 만들어 모두 쓴 뒤 `os.rename`으로 대상 이름으로 바꾼다. 중간 실패 시 임시 폴더와 새로 만든 상위 폴더를 삭제한다.
- **대상이 존재할 때(비어 있거나 `--force`):** 직접 쓴다. 새로 만든 파일과 폴더를 기록해 두고, 중간 실패 시 역순으로 삭제한다. 원래 있던 파일·폴더는 건드리지 않는다.
- 실행 권한은 `PlannedFile.mode`대로 `os.chmod`로 설정한다.

### 8.4 핵심 자료형

```python
@dataclass(frozen=True)
class PlannedFile:
    path: PurePosixPath   # 프로젝트 루트 기준 상대 경로
    content: str
    mode: int = 0o644
```

`plan.build_plan(config, today) -> list[PlannedFile]`은 부작용이 없어야 한다(테스트 용이성).

---

## 9. 렌더링 규칙 (`render.py`)

- Jinja2 환경: `undefined=StrictUndefined`, `autoescape=False`, `keep_trailing_newline=True`, `trim_blocks=True`, `lstrip_blocks=True`.
- 필터 `yq`: 문자열을 YAML frontmatter에 안전하게 넣기 위해 `json.dumps(value, ensure_ascii=False)`로 변환한다 (JSON 문자열은 유효한 YAML 문자열이다). frontmatter 안의 사용자 입력 문자열에는 반드시 `| yq`를 쓴다.
- 템플릿 실수 감지: 컨텍스트의 모든 문자열을 `"x"`로 바꾼 **검사용 컨텍스트**로 한 번 더 렌더링하고, 그 결과에 `{{` 또는 `{%`가 남아 있으면 오류로 처리한다. 실제 출력에는 이 검사를 하지 않는다. 사용자 입력에는 LaTeX 수식(`x^{{2}}`)이나 BibTeX 관례(`{{Transformer}}`)처럼 `{{`가 정당하게 들어갈 수 있기 때문이다.
  - 이 방식은 템플릿의 분기·반복이 문자열 값에 의존하지 않을 때만 정확하다. 템플릿 제어문은 불 값(`claude_code`), 목록(`milestones`), `None` 검사(`prev is none`)만 쓴다. 문자열 비교로 분기하는 제어문을 추가하지 않는다.

공통 컨텍스트:

| 이름 | 내용 |
|---|---|
| `project` | `name`, `slug`, `summary`, `research_question` |
| `humans` | `[{name, email}]` |
| `agent` | `{name, email}` |
| `milestones` | `[{id: "M0", index: 0, title}]` |
| `claude_code` | bool |
| `today` | `YYYY-MM-DD` (로컬 날짜) |
| `labgate_version`, `spec_version` | 문자열, 정수 |

마일스톤별 템플릿(A.10, A.11, A.14)에는 추가로 `m`(해당 마일스톤), `prev`(직전 마일스톤 또는 `None`)를 넘긴다. stub 사양 템플릿(B.7)에는 `stub`(B.7 표의 한 행)을 넘긴다.

---

## 10. Git 연동 (`gitops.py`)

### 10.1 순서 (`--no-git`이 아닐 때)

1. `git init` 후 `git symbolic-ref HEAD refs/heads/main` (Git 버전과 무관하게 기본 브랜치를 `main`으로).
2. `git config user.name "<humans[0].name>"`, `git config user.email "<humans[0].email>"` (저장소 로컬 설정).
3. `git config core.hooksPath .lg/hooks`.
4. `git add -A`.
5. 초기 커밋: 메시지를 임시 파일에 써서 `git commit -F <tmp>`. subprocess 환경에서 `GIT_AUTHOR_*`, `GIT_COMMITTER_*` 변수를 제거하여 로컬 설정(사람 신원)이 쓰이게 한다. 이 커밋은 hook을 통과해야 한다(자체 점검).

초기 커밋 메시지:

```
init: initialize research project

<project.name>

Actor: human
```

6. 커밋 해시(짧은 형식)를 출력에 사용한다.

### 10.2 실패 처리

각 단계는 `subprocess.run(..., check=True, capture_output=True, text=True)`로 실행하고, 실패 시 단계 이름, 명령, stderr를 출력한 뒤 남은 수동 명령을 안내한다. 예: hook 검사로 초기 커밋이 실패하면 hook이나 identities 생성 버그이므로 stderr를 그대로 보여준다.

### 10.3 `.lg/identities.json`

```json
{
  "schema_version": 1,
  "humans": [
    {"name": "홍길동", "email": "gildong@example.com"}
  ],
  "agent": {"name": "research-agent", "email": "agent@cap-partition.local"}
}
```

이메일은 소문자. `json.dumps(..., ensure_ascii=False, indent=2)` + 끝 개행. hook과 agent-commit이 이 파일을 읽는다 (표준 라이브러리만으로 읽을 수 있도록 JSON).

### 10.4 클론 후 주의

`core.hooksPath`는 저장소 로컬 설정이라 클론에 따라오지 않는다. 생성되는 README(A.1)에 재설정 명령을 적어 둔다.

---

## 11. commit-msg hook 사양

원문은 부록 C.1. 아래는 동작 규칙이다(구현과 이 표가 다르면 이 표가 기준).

### 11.1 메시지 구조

```
<type>(<scope>): <요약>          ← 헤더 (필수, 72자 이하)
                                  ← 빈 줄 (본문이나 trailer가 있으면 필수)
<본문>                            ← 선택
                                  ← 빈 줄
Key: value                        ← trailer 블록 = 메시지의 마지막 문단
```

- `#`으로 시작하는 줄은 무시한다 (Git 주석). `core.commentChar`를 바꾼 환경은 지원하지 않는다.
- 가위 줄 `# ------------------------ >8 ------------------------`과 그 아래는 모두 무시한다. Git은 commit-msg hook을 메시지 정리(cleanup) **전에** 실행하므로, `git commit -v`나 `commit.verbose=true`로 편집기를 쓰면 이 줄 아래에 diff가 붙은 채로 hook에 전달된다. 이를 자르지 않으면 diff가 마지막 문단으로 잡혀 trailer를 찾지 못한다.
- 마지막 문단의 모든 줄이 `Key: value` 형식(`Key`는 대문자로 시작하는 영문·하이픈)이면 trailer 블록으로 본다.
- 헤더가 `Revert `, `fixup! `, `squash! `, `amend! `로 시작하면 검사하지 않고 통과.
- 헤더가 `Merge `로 시작하면 작성자가 에이전트일 때만 오류("에이전트는 병합 커밋을 만들 수 없습니다"), 그 밖에는 검사하지 않고 통과. `git merge`는 commit-msg hook을 실행하므로 여기서 막을 수 있다. (`git cherry-pick`은 hook을 실행하지 않으므로 규약과 `.claude/settings.json`의 deny로만 막는다.)
- 마지막 문단에 `Actor`가 없는데 그 앞 문단에 `Actor:` 줄이 있으면 "trailer가 여러 문단으로 나뉘었다"는 안내를 오류에 덧붙인다. Claude Code가 공동 작성자 줄을 별도 문단으로 붙이는 경우의 원인을 바로 알 수 있게 한다.

### 11.2 타입

| 분류 | 타입 | 허용 Actor |
|---|---|---|
| 사람 전용 | `gate`, `decide`, `plan`, `spec`, `respond` | `human` |
| 에이전트 전용 | `task`, `review`, `propose` | `agent` |
| 공통 | `exp`, `run`, `result`, `ref`, `log`, `init`, `chore` | 둘 다 |

### 11.3 Trailer

| Key | 필수 조건 | 형식 |
|---|---|---|
| `Actor` | 항상 | `human` \| `agent` |
| `Task` | `gate`, `respond`, `task`, `run`, `result`, `review` | `M<n>-T<n>` |
| `Verdict` | `gate` | `approve` \| `revise` \| `redirect` |
| `Source` | `gate`, `decide`, `respond` | `document` \| `conversation` |
| `Decisions` | `decide` (다른 타입은 선택) | `D<n>.<n>` 쉼표 목록 |
| `Next` | 선택 (`gate`) | `M<n>-T<n>` 또는 `none` |
| `Milestone-Verdict` | 선택 (`gate`) | `go` \| `nogo` \| `conditional` |
| `Approve` | 선택 (`plan`) | `M<n>-T<n>` 쉼표 목록 |
| `Applies` | 선택 (반영 커밋) | 커밋 해시(16진수 7–40자) 쉼표 목록. 이 커밋이 상태 필드에 반영한 사람 커밋 (§21) |
| `Refs`, `Review` | 선택 | 자유 형식 (검사 안 함) |

같은 Key가 두 번 나오면 오류.

### 11.4 검사 규칙

1. 헤더 형식이 `^(?P<type>[a-z]+)(?:\((?P<scope>[^()\s]+)\))?: (?P<summary>\S.*)$`와 일치.
2. 헤더 72자 이하 (Python `len` 기준).
3. 헤더 다음 줄이 있으면 빈 줄.
4. 타입이 §11.2 목록에 있음.
5. `Actor`가 타입 분류와 일치.
6. **작성자 신원 일치:** `git var GIT_AUTHOR_IDENT`의 이메일(소문자)이
   - `identities.json`의 에이전트 이메일이면 작성자 역할 = `agent`,
   - 사람 이메일 중 하나면 = `human`,
   - 둘 다 아니면 오류 ("등록되지 않은 작성자").
   작성자 역할 ≠ `Actor`이면 오류.
7. `Task` 필수 타입에서 `Task`가 없거나 형식이 틀리면 오류. 또한 scope가 `Task` 값과 같아야 한다.
8. §11.3의 형식·필수 조건.
9. 오류가 하나라도 있으면 모두 stderr에 출력하고 종료 코드 1. 첫 줄은 `✗ 커밋 메시지가 규약(specs/git-commit.md)에 맞지 않습니다:`.

### 11.5 우회

검사 본체는 `check(text, check_author=True)` 함수다. `lg commit`·`lg draft`는 이 파일을 모듈로 읽어 `check_author=False`로 사전 검사한다 (§18.3). 함수 이름과 상수 이름은 `lg`와의 계약이므로 바꾸지 않는다.

`git commit --no-verify`는 막을 수 없다. 규약상 사람만 긴급 시 사용할 수 있고(`specs/git-commit.md`), 에이전트는 사용 금지(`AGENTS.md`).

---

## 12. `scripts/agent-commit`

원문은 부록 C.2. `identities.json`의 에이전트 이름·이메일을 `GIT_AUTHOR_*`, `GIT_COMMITTER_*` 환경 변수로 설정하고 `git commit "$@"`을 실행한다. 에이전트는 `git commit` 대신 이것만 사용한다. Claude Code에서는 `.claude/settings.json`이 `git commit` 직접 실행을 막는다. `--author` 옵션은 막는다. hook은 `--author`로 지정한 작성자도 그대로 인식하므로(Git이 hook 실행 시 `GIT_AUTHOR_*`를 내보냄) 판별 자체는 문제가 없다. 막는 이유는 에이전트가 `--author`로 사람 이메일을 넣으면 사람 전용 타입 커밋을 만들 수 있기 때문이다. 이 스크립트는 작성자를 항상 에이전트로 고정한다. `-a`(`--all`)도 막는다. 추적 중인 모든 변경을 커밋하므로 사람의 미커밋 변경이 에이전트 커밋에 섞이기 때문이다. 묶인 짧은 옵션(`-am`, `-nm`)도 한 글자씩 검사하되, 값을 받는 옵션(`-m`, `-F`, `-C`, `-c`, `-t`) 뒤의 글자와 그 값은 검사하지 않는다.

---

## 13. 오류 메시지 원칙

- 무엇이 잘못되었는지, 어떤 값이었는지, 어떻게 고치는지를 한 줄씩.
- 검증 오류는 모아서 한 번에 출력.
- 예외 traceback은 `LG_DEBUG=1` 환경 변수가 있을 때만 출력.

---

## 14. 테스트 계획과 수용 기준

### 14.1 단위 테스트

| 대상 | 내용 |
|---|---|
| `config` | 정상 설정 로드, 각 검증 규칙 위반 시 해당 필드 경로가 오류에 포함, 이메일 소문자화, 마일스톤 ID 자동 부여, `id` 불일치 오류, 에이전트 기본값 |
| `render` | `yq` 필터가 따옴표·콜론·한글을 안전하게 처리, StrictUndefined로 누락 변수 감지, 템플릿에서 생긴 잔여 `{{` 감지, 사용자 입력의 `{{`·`{%`는 허용 |
| `plan` | 마일스톤 N개 → 경로 집합이 §7 표와 일치, `claude_code=false`면 `CLAUDE.md`·`.claude/` 없음, 실행 파일 mode 755, 모든 경로 상대 경로, 모든 `.md`의 frontmatter가 YAML로 파싱됨(있는 경우) |
| `writer` | 신규 폴더 원자적 생성, 비어 있지 않은 폴더 거부, `--force` 시 파일 충돌 거부, 중간 실패 롤백 |
| hook | 부록 C.1을 임시 Git 저장소에 설치하고 아래 표의 사례 검증 |

hook 테스트 사례 (사람 `h@x.com`, 에이전트 `a@x.local`):

| 작성자 | 메시지 | 기대 |
|---|---|---|
| h | `init: initialize research project` + `Actor: human` | 통과 |
| a | `task(M1-T2): start signal validation` + `Actor: agent`, `Task: M1-T2` | 통과 |
| a | `gate(M1-T2): approve` + `Actor: agent` … | 실패 (사람 전용 타입) |
| a | `task(M1-T2): x` + `Actor: human`, `Task: M1-T2` | 실패 (Actor 불일치) |
| h | `review(M1-T2): request gate` + `Actor: human`, `Task: M1-T2` | 실패 (에이전트 전용 타입) |
| h | `exp: fix data loader` + `Actor: human` | 통과 (공통 타입) |
| h | `result(M1-T2): add table` + `Actor: human`, `Task: M1-T2` | 통과 (공통 타입) |
| h | `gate(M1-T2): approve, next M1-T3` + `Actor: human`, `Task: M1-T2`, `Verdict: approve`, `Source: document`, `Next: M1-T3` | 통과 |
| h | 위에서 `Source` 누락 | 실패 |
| h | 위에서 `Verdict: ok` | 실패 |
| a | `task(M1-T3): x` + `Actor: agent`, `Task: M1-T2` | 실패 (scope 불일치) |
| a | `exp: add model` (trailer 없음) | 실패 (Actor 누락) |
| 등록 안 된 `z@y.com` | 정상 형식 | 실패 (등록되지 않은 작성자) |
| h | `decide(D1.3): confirm PR metric` + `Actor: human`, `Decisions: D1.3`, `Source: conversation` | 통과 |
| h | `plan(M0-T0): approve initial task` + `Actor: human`, `Approve: M0-T0` | 통과 |
| h, 등록 안 된 작성자 | `Merge branch 'x'` | 통과 |
| a | `Merge branch 'worktree-x'` | 실패 (에이전트 병합 금지) |
| a | `log: x` ⏎⏎ `Actor: agent` ⏎⏎ `Co-Authored-By: Claude …` (trailer가 두 문단) | 실패 (Actor 누락 + 문단 분리 안내) |
| a | `log: x` ⏎⏎ `Actor: agent` ⏎ `Co-Authored-By: Claude …` (한 문단) | 통과 |
| a | 헤더 73자 이상 | 실패 |
| h | 통과하는 `gate` 메시지 뒤에 가위 줄과 diff(`+foo: bar` 같은 줄 포함)가 붙음 | 통과 |

v2 (`tests/test_commit.py`, 사람 `h@x.com`, `lg init`으로 만든 프로젝트에서):

| 대상 | 내용 |
|---|---|
| 프로젝트 확인 | Git 저장소 밖 → 2, `.lg/project.yaml` 없음 → 2, spec_version 1 → 2, hook에 계약 이름 없음 → 2, hook의 타입 상수를 바꾸면 `lg`의 판단도 바뀜 |
| `lg draft` | 경로 지정 stage(다른 변경은 stage 안 됨), 현재 폴더 기준 경로, Task로 scope 결정, 만든 초안이 `git commit -F`로 hook 통과, 경로 생략 시 `HUMAN_FILES`의 경로만 stage(세션 도중 변경 제외), `HUMAN_FILES` 없이 경로 생략 → 2, 검사 실패(에이전트 전용 타입, `Actor` trailer, 형식, 필수 trailer, 헤더 길이) → 2이고 아무것도 바뀌지 않음, 오류를 모아 출력, 대기 상태 → 3, 대상 밖 stage → 2, stage할 것 없음 → 3 |
| hook (v3) | `Applies` 형식(16진수 7–40자) 검사 |
| `lg commit` | TTY 아님 → 2, 미등록 신원 → 2, `--pending`인데 초안 없음 → 3, `plan` 작성 시 `Approve` 선택(하나면 scope도 그 Task), `--allow-empty`로 빈 승인 커밋, 초안 모드 성공(작성자 사람, 초안 삭제, `HUMAN_FILES` 갱신), `gate` 승인 → `gate/<Task>`·`milestone/<M>-<v>` tag, `--no-tag`, 취소 → 130(초안·stage 유지), 편집 후 재검사, `core.editor` 사용, Git 거부 → 4(초안 유지), 작성 모드(파일 선택·타입·요약), 변경 없음 → 3 |
| `apply-human-commits` | `plan`+`Approve` 반영(카드, 마일스톤 표), 이미 만족한 상태는 건너뛰고 빈 반영 커밋, `gate` approve+`Next`+`Milestone-Verdict`+`Decisions`(카드·다음 카드·마일스톤 착수와 종료·결정·결정 목록·review 이동·게이트 이력), revise, respond(`task` 메시지, esc review), 반영 불가 → 1이고 아무것도 바뀌지 않음, 대기 상태·반영 대상 파일의 미커밋 변경 → 2, 오래된 것부터 하나씩, `Applies` 접두어 판별, `--check`. Python 3.9로도 실행 |
| `session-check` | 이미 커밋된 초안 정리, 반영되지 않은 사람 커밋 알림, 깨끗하면 출력 없음·`HUMAN_FILES` 삭제, 목록 출력과 기록(이름 바꾸기는 두 경로), 20개 초과 생략 표시, 대기 상태에서는 기록하지 않음, Git 저장소 밖에서 조용히 0. 매트릭스에서 Python 3.9로도 실행 |

### 14.2 통합 테스트

1. 설정 파일로 `lg init <tmp>/proj --config cfg.yaml` → 종료 코드 0, `git log`에 커밋 1개, 작성자 = 사람, `git config core.hooksPath` = `.lg/hooks`.
2. 생성된 프로젝트에서 `scripts/agent-commit --allow-empty -m "log: test" -m "Actor: agent"` → 성공, 작성자 = 에이전트.
3. 같은 곳에서 `scripts/agent-commit --allow-empty -m "gate(M0-T0): approve" -m "Actor: agent
   Task: M0-T0
   Verdict: approve
   Source: document"` → hook 실패.
4. `--dry-run` → 대상 폴더가 생성되지 않음.
5. `--no-git` → `.git` 없음, 파일은 생성.
6. 이미 Git 저장소 안의 하위 폴더를 대상으로 → 종료 코드 4.

### 14.3 수용 기준

- §14.1, §14.2 테스트 모두 통과.
- 마일스톤 1개, 20개 설정 모두에서 생성 성공.
- 생성된 모든 Markdown 문서에 렌더링되지 않은 템플릿 문법이 없음 (사용자 입력에 `{{`, `{%`가 없는 설정 기준. 있는 설정에서는 그 문자열이 출력에 그대로 들어가고 생성은 성공해야 함).
- 생성 직후 `git status`가 깨끗함.
- 사람이 §5.4의 안내대로 `M0-T0` 승인 커밋을 실행하면 hook을 통과함.

---

## 15. 향후 확장 (범위 밖, 설계 시 고려만)

| 명령 | 역할 | 미리 지킬 것 |
|---|---|---|
| `lg gate <verdict> <Task>` | review 응답 기록, 카드 상태 변경, 사람 신원 `gate` 커밋, tag 생성을 한 번에. `lg commit`(§18) 위에 만들고, 생기면 `gate` 타입은 `lg gate`로만 받는다 | 상태값·trailer를 사양대로 고정 |
| `lg status` | frontmatter와 커밋 이력으로 `STATUS.md` 재생성 | 모든 문서에 frontmatter |
| `lg validate` | 문서를 사양의 검증 규칙으로 검사 | 사양마다 §7 검증 규칙 섹션 유지 |
| `lg upgrade` | 사양 버전 갱신: 규칙·도구 파일 교체와 모든 문서의 `spec_version` 일괄 갱신(§16.4), v0.1 프로젝트의 1 → 2 포함 | `spec_version` 필드 |
| `lg doctor` | hooksPath 등 로컬 설정 점검·복구 | `.lg/` 안에 필요한 정보 보관 |
| 계획서 가져오기 | Markdown 계획서 → roadmap, milestone, decisions | — |
| 세션 도중 사람 변경 감지 | 에이전트가 편집한 파일 목록을 기록해(PostToolUse hook 등) 그 밖의 변경을 사람의 변경으로 판별 | §20 |

---

## 16. 규칙 구조: 불변 원칙, 일반 규칙, 특별 규칙, task 카드

근거가 된 작업 목록은 [docs/operations.md](docs/operations.md)에 있다.

### 16.1 층과 우선순위

규칙의 층은 두 축으로 본다. 법령에 빗대면 일반 규칙은 헌법이다. 작업 중에는 고칠 수 없고 사람만 개정한다. 그러나 **적용할 때는** 더 구체적인 규범이 먼저다: task 카드(특별법), 절차의 특별 규칙(법률), 일반 규칙(헌법) 순이다.

| 층 | 위치 | 고치는 사람 | 적용 순서 |
|---|---|---|---|
| 불변 원칙 (P1–P6) | `AGENTS.md` 1절 | 사람, `spec` 커밋 | 예외 없음. task 카드로도 풀 수 없다 |
| task 카드 "범위 › 포함" | task 카드 | 사람이 task 승인 때 확정 | 1 (그 task 수행 중) |
| 절차의 특별 규칙 | `specs/procedures/*.md`의 "특별 규칙" 절 | 사람, `spec` 커밋 | 2 (그 절차 수행 중) |
| 일반 규칙 (G1–G10) | `AGENTS.md` 2절 | 사람, `spec` 커밋 | 3 (그 밖의 모든 경우) |

불변 원칙은 어기면 기록 자체가 거짓이 되는 것(사람 신원 커밋, 이력 재작성, 사람 변경의 폐기, 지어낸 판정)이라 적용에서도 예외가 없다. 규칙끼리 충돌하거나 어느 규칙에도 없는 상황이면 불변 원칙에 맞는 쪽을 택하고, 그래도 정할 수 없으면 멈추고 묻는다. 이 선언은 `AGENTS.md` 0절에 있다(A.3).

### 16.2 코드 우선 원칙

정확하게 검증·실행할 수 있는 일은 문서 규칙이 아니라 도구(스크립트)로 만든다. 도구가 하는 일은 도구의 명세와 테스트로 정하고, 특별 규칙으로 허용하지 않는다. 특별 규칙은 도구가 할 수 없는 에이전트의 판단 작업(사람의 말을 문서로 옮기기, 변경을 보고 타입 고르기)에만 둔다.

| 일 | 맡는 것 |
|---|---|
| 사람의 변경 감지·기록, 이미 커밋된 초안 정리, 반영되지 않은 사람 커밋 감지 | `scripts/session-check` (§17.2) |
| 사람 커밋의 결과를 상태 필드에 반영 | `scripts/apply-human-commits` (§21) |
| 사람 커밋의 초안 쓰기 | `lg draft` (§19) |

### 16.3 절차 목록

| 절차 | 시작 조건 | 특별 규칙 | 쓰는 도구 | Claude Code 명령 |
|---|---|---|---|---|
| `session-start` | 세션 시작 | 없음 | `session-check` | `/session-start` |
| `session-close` | 세션 종료 | 없음 | | `/session-close` |
| `commit-prep` | 사람의 변경 감지, 사람이 자기 변경을 알리거나 커밋 준비를 요청 | G2 | `lg draft` | `/commit-prep` |
| `task-start` | 승인된 task 착수 | 없음 | | `/task-start` |
| `task-gate` | task 완료, 게이트 요청 | 없음 | | `/task-gate` |
| `escalate` | 멈춤 조건 (workflow §7.1) | 없음 | | `/escalate` |
| `gate-conversation` | 사람이 대화로 판정·결정·응답 | G5 | `lg draft` | — |
| `gate-apply` | 반영되지 않은 사람 커밋이 있음 | G4 | `apply-human-commits` | — |

원문은 부록 B.10. 형식:

```markdown
---
id: <name>
type: procedure
spec_version: 3
---
# <제목>

- 시작 조건: <언제 이 문서를 읽는가>
- 끝나는 상태: <절차가 끝났을 때의 작업 트리·문서 상태>

## 특별 규칙

<"없음. 일반 규칙을 따른다." 또는 아래 표>

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|

## 단계
## 멈추는 경우 (있을 때)
```

### 16.4 사양 버전 갱신

프로젝트의 사양 버전(spec_version)은 `lg init` 때 정해지고 자동으로 바뀌지 않는다. 문서 frontmatter의 `spec_version`은 그 문서가 따르는 사양 버전이다.

- 사양을 올릴 때(예: 2 → 3)는 사람이 규칙·도구 파일과 함께 **프로젝트의 모든 문서의 `spec_version`을 일괄로** 올리고 하나의 `spec` 커밋으로 확정한다. 연구 문서(`plan/`, `decisions/`, `references/`, `STATUS.md` 등)는 내용은 그대로 두고 이 값만 바꾼다. 절차는 [docs/guide/upgrade.md](docs/guide/upgrade.md).
- 에이전트는 문서를 쓰거나 고칠 때 `spec_version`을 바꾸지 않는다. 생성되는 `specs/conventions.md`의 frontmatter 표에 이 규칙을 둔다(B.2).
- 초기화 기록은 바꾸지 않는다: `.lg/project.yaml`의 `generated.labgate_version`, `generated.created`, 생성된 `README.md` 맨 아래 줄. `.lg/project.yaml`의 `generated.spec_version`만 올린다.
- 이 일괄 갱신은 기계적인 일이므로, `lg upgrade`(§15)가 생기면 그 도구가 한다.

---

## 17. 사람의 변경과 `scripts/session-check`

### 17.1 세 가지 시작 경로, 한 가지 결과

```
A. 사람이 먼저 정리     사람: 수정 → lg commit ───────────────────────────────┐
B. 감지 → 사람이 직접   세션 시작 → session-check 감지 → 에이전트 멈춤, 선택지   │
                        → 사람: lg commit ────────────────────────────────────┤──▶ 사람 신원 커밋
C. 감지 → 초안 → 확정   세션 시작 → session-check 감지 → 에이전트: lg draft    │    → 에이전트 작업
                        → 사람: lg commit (초안 확인 후 확정) ─────────────────┘
```

B·C에서 사람이 "버린다"를 고르면 사람이 직접 되돌린다. 에이전트는 되돌리지 않는다. 단계는 절차 `commit-prep`(B.10).

### 17.2 `scripts/session-check`

원문은 부록 C.3. Python 표준 라이브러리만 쓰고 `lg` 없이 동작한다. 저장소 루트는 스크립트 위치(`scripts/`의 부모)로 정한다.

순서대로 확인한다. 출력은 여러 항목이 함께 나올 수 있다.

1. **Git 저장소가 아니면** 아무것도 출력하지 않고 끝낸다.
2. **이미 커밋된 초안 정리.** `.lg/pending/COMMIT_MSG`가 있고, 최근 20개 커밋 중 사람이 작성한 커밋의 메시지가 초안과 같으면(양끝 공백 무시) 초안을 지우고 알린다. 사람이 `lg commit` 대신 `git commit -F`로 확정한 경우다.
3. **사람 커밋 대기 상태.** 초안이 남아 있으면 대기 상태를 알리고 4–6단계는 하지 않는다(`HUMAN_FILES`도 건드리지 않는다).
4. **지난 반영.** `scripts/apply-human-commits --tidy`로 `.lg/pending/APPLY_MSG`의 상태를 본다. 그 `Applies` 해시를 담은 커밋이 있으면 기록 파일(`APPLY_MSG`, `APPLY_PATHS`)을 지운다. 없으면 "반영했지만 커밋하지 않음"을 알리고 커밋 명령을 안내하며, 그 경로는 6단계의 사람의 변경에서 빼고, 5단계는 하지 않는다. 세션이 반영과 커밋 사이에 끝난 경우, 반영 도구가 바꾼 파일이 사람의 변경으로 잘못 분류되지 않게 하기 위해서다.
5. **반영되지 않은 사람 커밋.** `scripts/apply-human-commits --check`의 결과가 있으면 커밋 목록과 함께 절차 `gate-apply`를 안내한다. 이 스크립트가 없으면(spec_version 2 프로젝트) 건너뛴다.
6. **사람의 변경.**

| 상태 | 표준 출력 | `.lg/pending/HUMAN_FILES` |
|---|---|---|
| 커밋되지 않은 변경 있음 | 사람의 변경 안내와 파일 목록(최대 20개, 넘으면 "외 N개") | 전체 목록을 한 줄에 하나씩 기록 |
| 깨끗함 | 없음 | 있으면 지움 |

- 변경 목록은 `git status --porcelain=v1 -z --untracked-files=all`로 얻는다. 이름 바꾸기(`R`)는 새 경로와 이전 경로를 모두 기록한다(`git add -A -- <둘>`로 stage할 수 있도록).
- 종료 코드는 항상 0이다(알리기만 한다).

### 17.3 Claude Code 연결

`.claude/settings.json`(A.5)에 SessionStart hook을 둔다. matcher를 생략해 새 세션, 재개, `/clear`, compact 모두에서 실행한다. 명령은 셸 형식 `"$CLAUDE_PROJECT_DIR"/scripts/session-check`다. 표준 출력은 에이전트 맥락에 들어간다. SessionStart hook은 세션을 막을 수 없으므로(종료 코드와 무관), 멈추는 것은 `AGENTS.md` 규칙과 절차 `commit-prep`이 한다.

권한 `deny`에 `Bash(lg commit *)`를 둔다. 끝의 ` *`는 옵션 없는 `lg commit`에도 일치한다. deny는 allow로 예외를 만들 수 없으므로(deny → ask → allow 순서), 준비 명령은 `lg commit`의 옵션이 아닌 별도 명령 `lg draft`로 둔다.

---

## 18. `lg commit` (사람 전용)

### 18.1 형식

```
lg commit [--pending | --no-pending] [--no-tag] [--allow-empty]
```

| 옵션 | 설명 |
|---|---|
| (없음) | `.lg/pending/COMMIT_MSG`가 있으면 초안 모드, 없으면 작성 모드 |
| `--pending` | 초안 모드를 강제한다. 초안이 없으면 코드 3 |
| `--no-pending` | 초안이 있어도 작성 모드로 간다 (초안 파일은 그대로 둔다) |
| `--no-tag` | `gate` + `Verdict: approve`여도 tag를 만들지 않는다 |
| `--allow-empty` | 바뀐 파일 없이 커밋한다. 첫 task 승인(`plan` + `Approve`)처럼 기록만 남기는 커밋에 쓴다 |

### 18.2 동작 순서

1. **프로젝트 확인** (§18.3). 실패 시 코드 2.
2. **TTY 확인.** 표준 입력·출력이 모두 터미널이 아니면 코드 2: "lg commit은 사람이 터미널에서 직접 실행합니다. 에이전트는 lg draft로 초안만 준비합니다."
3. **신원 확인.** `git config user.email`(소문자)이 `identities.json`의 humans에 없으면 코드 2.
4. **메시지 준비.** 초안 모드(§18.5) 또는 작성 모드(§18.4).
5. **확인.** `git diff --cached --stat`과 메시지를 보여 주고 "커밋 / 편집기로 수정 / 취소" 중 고르게 한다. 편집기는 Git과 같은 규칙으로 고른다(`git var GIT_EDITOR`: `core.editor`, `GIT_EDITOR`, `VISUAL`, `EDITOR` 순)하고 Git처럼 `sh -c '<편집기> "$@"'`로 실행한다. 편집 후에는 hook의 `check(text, check_author=False)`로 다시 검사하고, 오류가 있으면 보여 준 뒤 이 단계를 반복한다. 취소는 코드 130 (stage와 초안은 그대로).
6. **커밋.** 메시지를 임시 파일에 써서 `git commit -F <파일>`. hook이 거부하면 hook 출력을 그대로 보여 주고 코드 4 (초안은 남긴다).
7. **정리.** 초안 모드면 `.lg/pending/COMMIT_MSG`를 지운다. `.lg/pending/HUMAN_FILES`가 있으면 아직 커밋되지 않은 경로만 남기고, 남는 것이 없으면 지운다.
8. **tag.** `gate` + `Verdict: approve`이고 `--no-tag`가 아니면 `gate/<Task>`. `Milestone-Verdict`가 있으면 `milestone/<M>-<verdict>`도 (`<M>`은 Task ID의 마일스톤 부분). tag 실패는 코드 4 (커밋은 남는다).
9. **출력.** "✓ 커밋했습니다: <짧은 해시> <헤더>", 만든 tag, "에이전트에게 커밋했다고 알리세요."

### 18.3 프로젝트 확인과 규칙 읽기 (`project.py`)

1. 현재 폴더에서 `git rev-parse --show-toplevel`. 실패하면 "Git 저장소가 아닙니다".
2. `<root>/.lg/project.yaml`이 없으면 "labgate 프로젝트가 아닙니다".
3. `generated.spec_version`이 지원 범위(2, 3)가 아니면 오류. spec_version 2와 3은 커밋 규약(타입·trailer)이 같으므로 둘 다 지원한다. 1이면 "labgate 0.1로 만든 프로젝트입니다(spec_version 1). git commit을 직접 쓰세요."
4. `.lg/identities.json`을 읽는다.
5. `.lg/hooks/commit-msg`를 `runpy.run_path(path, run_name="labgate_hook")`로 읽어 `HUMAN_TYPES`, `AGENT_TYPES`, `COMMON_TYPES`, `TASK_REQUIRED`, `SOURCE_REQUIRED`, `MAX_HEADER`, `HEADER_RE`, `TASK_ID_RE`, `DECISION_ID_RE`, `parse`, `check`를 가져온다. 하나라도 없으면 "hook이 spec_version 2 형식이 아닙니다".

사람이 쓸 수 있는 타입 = `HUMAN_TYPES ∪ COMMON_TYPES - {"init"}`. 규칙을 `lg` 안에 따로 두지 않으므로, 프로젝트를 만든 시점의 hook과 `lg`가 어긋나지 않는다.

### 18.4 작성 모드

1. stage된 변경이 없으면 커밋되지 않은 파일 목록을 체크박스로 보여 주고, 고른 경로를 `git add -A -- <경로>`로 stage한다. 아무것도 고르지 않으면 코드 3. 커밋되지 않은 변경도 없으면 코드 3. `--allow-empty`면 이 단계를 건너뛰고 stage된 것만(없으면 빈 커밋) 커밋한다.
2. 타입: 사람이 쓸 수 있는 타입 (사람 전용을 먼저).
3. Task: 타입이 `TASK_REQUIRED`면 `plan/milestones/*/tasks/*.md`의 파일 이름 중 Task ID 형식인 것에서 고른다(없으면 입력). scope는 Task와 같게 정한다. `plan`이면 `Approve`(승인할 task)를 같은 목록에서 여러 개 고르게 하고(고르지 않으면 생략), 하나만 골랐으면 scope도 그 Task ID로 정한다. 그 밖의 경우 scope를 선택 입력으로 묻는다.
4. 타입별 trailer: `SOURCE_REQUIRED`면 `Source`, `gate`면 `Verdict`, 선택 `Next`(Task ID 또는 `none`)와 `Milestone-Verdict`, `decide`면 `Decisions`.
5. 요약 한 줄. 헤더가 `MAX_HEADER`를 넘으면 다시 묻는다.
6. `Actor: human`을 넣어 메시지를 만든다. 본문은 5단계(확인)의 편집기에서 쓴다.

### 18.5 초안 모드

1. 초안을 읽는다. stage된 변경이 없으면 코드 3: "초안은 있는데 stage된 변경이 없습니다".
2. hook의 `parse`로 trailer를 읽어 `Actor: human`이 아니면 코드 2: "초안이 사람 커밋용이 아닙니다".
3. §18.2의 5단계로 간다.

### 18.6 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 커밋 성공 |
| 1 | 예기치 못한 실행 오류 |
| 2 | 사용법·환경 오류 (TTY 아님, 신원 미등록, labgate 프로젝트 아님, spec_version 불일치, 초안이 사람 커밋용 아님, 메시지 검사 실패) |
| 3 | 커밋할 것 없음 (stage·변경 없음, 초안 없음) |
| 4 | Git 오류 (hook 거부, tag 실패) |
| 130 | 사용자가 취소 |

---

## 19. `lg draft` (초안 준비)

사람 커밋의 초안을 준비한다. 커밋하지 않는다. 에이전트와 사람 모두 쓸 수 있다.

### 19.1 형식

```
lg draft --type T --summary TEXT [--scope S] [--body TEXT] [--trailer KEY=VALUE ...] [PATH ...]
```

- `PATH`를 주면 그 경로만 stage한다 (세션 도중 사람이 알려 준 변경, 대화 경로의 판정처럼 감지 목록에 없는 경우).
- 생략하면 `.lg/pending/HUMAN_FILES`의 경로만 stage한다. 이 파일이 없으면 코드 2: "경로를 지정하세요". 커밋되지 않은 모든 변경을 stage하는 형태는 두지 않는다. 세션 도중에 쓰면 에이전트의 변경까지 사람 커밋에 섞이기 때문이다.
- `Actor: human`은 자동으로 넣는다. `--trailer Actor=...`는 코드 2.
- `--scope`가 없고 `--trailer Task=...`가 있으면 scope는 Task로 정한다.

### 19.2 동작 순서

1. 프로젝트 확인 (§18.3). TTY와 신원은 확인하지 않는다.
2. 초안 파일이 이미 있으면 코드 3: "사람 커밋 대기 상태입니다".
3. 메시지를 만들고 검사한다: 타입이 사람이 쓸 수 있는 타입인지, 그리고 hook의 `check(text, check_author=False)`. 오류를 모두 모아 코드 2. 이 단계까지는 아무것도 바꾸지 않는다.
4. 대상 경로 밖에 이미 stage된 변경이 있으면 코드 2: "stage된 다른 변경이 있습니다: <경로>. 먼저 커밋하거나 unstage하세요." (에이전트의 변경이 사람 커밋에 섞이는 것을 막는다.)
5. `git add -A -- <경로>`. 그 뒤 stage된 변경이 없으면 코드 3.
6. `.lg/pending/COMMIT_MSG`에 메시지를 쓴다.
7. 출력: "초안을 준비했습니다 (stage된 파일 N개). 터미널에서 lg commit 을 실행하세요."

### 19.3 종료 코드

0 성공, 1 예기치 못한 오류, 2 사용법·검사 오류, 3 대기 상태 또는 stage할 것 없음, 4 Git 오류, 130 중단(Ctrl-C).

---

## 20. 한계

1. **세션 도중의 사람 수정은 감지하지 못한다.** 감지는 세션 시작 시점 기준이다. 사용 규칙: 세션 도중에는 직접 수정하지 않는다. 했다면 에이전트에게 알리고, 에이전트는 `commit-prep`으로 간다(경로 지정 `lg draft`).
2. **TTY 확인은 보안 경계가 아니다.** 의사 터미널을 만드는 도구로 우회할 수 있다. 의도하지 않은 실수를 막는 장치이며, `.claude/settings.json` deny와 같은 수준이다.
3. **Claude Code 프롬프트의 `!` 실행.** `! lg commit`이 터미널로 인식되지 않으면 사람은 별도 터미널에서 실행한다.
4. **다른 에이전트 도구에는 자동 실행이 없다.** `session-start` 절차의 첫 단계에서 에이전트가 `scripts/session-check`를 직접 실행한다.
5. **세션 시작 때 남은 에이전트의 변경.** 이전 세션이 비정상 종료해 에이전트의 변경이 남았다면 사람의 변경으로 분류된다. 보수적인 쪽(에이전트가 건드리지 않음)으로 틀리므로 허용하고, 사람이 `commit-prep`의 선택지에서 정리한다.


## 21. `scripts/apply-human-commits` (사람 커밋의 반영)

사람 커밋의 trailer가 정한 상태 전이를 문서의 상태 필드에 반영한다. 불변 원칙 P1("사실의 원본은 커밋, 반영은 에이전트의 책임")을 코드로 수행한다. 원문은 부록 C.4.

### 21.1 형식

```
scripts/apply-human-commits            # 가장 오래된 반영되지 않은 사람 커밋 하나를 반영
scripts/apply-human-commits --check    # 바꾸지 않고 반영되지 않은 사람 커밋을 나열
```

Python 표준 라이브러리만 쓰고 `lg` 없이 동작한다. 저장소 루트는 스크립트 위치로 정한다. **커밋하지 않는다.** 커밋은 에이전트가 `scripts/agent-commit`으로 한다(작성자는 항상 에이전트).

### 21.2 반영 대상

- **사람 커밋:** 작성자 이메일이 `.lg/identities.json`의 사람 중 하나.
- **반영 대상 커밋:** 헤더 타입이 `gate`, `respond`, `decide`이거나, `plan`이면서 `Approve` trailer가 있는 사람 커밋. `gate`·`decide`의 `Decisions` trailer도 반영한다.
- **반영됨:** 그 뒤의 어떤 커밋의 `Applies` trailer에 그 커밋 해시(앞 7자 이상)가 있으면 반영된 것이다.
- 반영되지 않은 커밋이 여럿이면 **오래된 것부터 하나씩** 반영한다. 반영 커밋 하나가 사람 커밋 하나에 대응한다.

### 21.3 전이

| 사람 커밋 | 대상 | 출발 상태 | 목표 상태 | 이미 만족 (건너뜀) |
|---|---|---|---|---|
| `plan` + `Approve: T` | 카드 T | `draft` | `approved` | `draft`가 아닌 모든 상태 |
| `gate` + `Verdict: approve` | 카드 Task | `in-review` | `closed` | `closed` |
| `gate` + `Verdict: revise` | 카드 Task | `in-review` | `revise` | `revise`, `in-progress`, `blocked` |
| `gate` + `Verdict: redirect` | 카드 Task | `in-review` | `redirected` | `redirected` |
| `gate` + `Next: T` | 카드 T | `draft` | `approved` | `draft`가 아닌 모든 상태 |
| `gate` + `Verdict: approve`, Task가 `<M>-T0` | 마일스톤 M | `planned` | `active` | `active`, `closed` |
| `gate` + `Milestone-Verdict` | 마일스톤 M | `active` | `closed` | `closed` |
| `respond` | 카드 Task | `blocked` | `in-progress` | `blocked`가 아닌 모든 상태 |
| `decide` 또는 `gate` + `Decisions: D…` | 결정 D | `proposed`, `discussing` | `confirmed` | `confirmed` |

- 상태가 출발 상태도 아니고 이미 만족도 아니면 **반영할 수 없다.** 이때 아무것도 바꾸지 않고 이유를 출력한 뒤 코드 1로 끝낸다. 에이전트는 멈추고 사람에게 묻는다.
- "이미 만족"은 `Applies`가 없던 v0.2 프로젝트에서 에이전트가 판단으로 반영해 둔 경우를 받아들이기 위한 것이다. 이때도 반영 커밋은 만들어 `Applies`로 기록을 남긴다. 바꿀 파일이 하나도 없으면 출력에 이 이유(상태는 이미 반영됨, `Applies` 기록이 없어 빈 반영 커밋만 남김)를 적는다. `Refs` 등 다른 trailer는 반영 기록으로 보지 않는다.
- 한 사람 커밋의 전이는 모두 반영하거나 하나도 반영하지 않는다. 바꾸기 전에 전부 계산한다.

### 21.4 함께 바꾸는 것

| 파일 | 바꾸는 것 |
|---|---|
| 카드 `plan/milestones/<M>/tasks/<T>.md` | frontmatter `status`, `updated`(오늘). `gate`·`respond`면 "## 게이트 이력"에 `- <날짜> <타입> <Verdict> \`<짧은 해시>\`` 한 줄 |
| `plan/milestones/<M>/milestone.md` | 마일스톤이면 frontmatter `status`. 카드 상태가 바뀌면 "Task 목록" 표에서 그 task 행의 상태 칸 |
| `decisions/<D>_*.md` | frontmatter `status`, `updated` |
| `decisions/index.md` | 그 결정 행의 상태 칸과 "확정 커밋" 칸 |
| review 문서 (`gate`·`respond`) | `Review` trailer의 문서, 없으면 `reviews/open/<Task>_gate-NN.md`(respond면 `esc`) 중 번호가 가장 큰 것을 `reviews/closed/`로 옮기고(`git mv`) frontmatter `status: closed`. 이미 `closed/`에 있으면 건너뛴다 |

`STATUS.md`는 바꾸지 않는다. 다음 할 일을 쓰는 것은 에이전트의 판단이다(절차 `gate-apply`).

### 21.5 출력

반영했으면 바뀐 내용, 커밋할 경로, 커밋 메시지를 출력하고 메시지를 `.lg/pending/APPLY_MSG`에, 커밋할 경로를 `.lg/pending/APPLY_PATHS`에 쓴다. 지난 반영이 아직 커밋되지 않았으면(`APPLY_MSG`의 `Applies` 해시를 담은 커밋이 없음) 새로 반영하지 않고 코드 2로 끝나며 커밋 명령을 안내한다. `--tidy`는 지난 반영을 확인해, 커밋됐으면 기록 파일을 지우고 결과를 JSON 한 줄(`state`: `cleaned` | `pending`, `applies`, `paths`)로 출력한다(`session-check`가 쓴다).

```
반영: 70ea21b plan(M0-T0): approve initial task
  plan/milestones/M0/tasks/M0-T0.md: status draft → approved
  plan/milestones/M0/milestone.md: M0-T0 draft → approved
커밋: scripts/agent-commit -F .lg/pending/APPLY_MSG -- <경로…> (STATUS.md를 고쳤으면 함께)
```

| 사람 커밋 | 반영 커밋 메시지 |
|---|---|
| `respond` | `task(<Task>): resume after response <짧은 해시>` + `Actor: agent`, `Task: <Task>`, `Applies: <해시>` |
| 그 밖 | `log(<scope>): apply <타입> <짧은 해시>` + `Actor: agent`, `Applies: <해시>`. scope는 Task, Approve의 첫 task, 또는 결정 ID |

`--check`는 반영되지 않은 커밋을 한 줄에 하나씩 `<짧은 해시> <헤더>`로 출력한다.

### 21.6 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 반영함, 또는 반영할 것이 없음 (`--check`는 항상 0) |
| 1 | 반영할 수 없음 (카드·결정 문서 없음, 출발 상태가 아님). 아무것도 바꾸지 않았다 |
| 2 | Git 저장소가 아님, 사람 커밋 대기 상태(G3), 지난 반영이 커밋되지 않음, 커밋되지 않은 변경이 반영 대상 파일에 있음 |

---

# 부록 A. 생성 문서 템플릿

> 바깥 `~~~~` 울타리는 이 설계 문서의 표기일 뿐 파일 내용이 아니다. 울타리 안이 파일 원문이다.

## A.1 `README.md` (J)

~~~~markdown
# {{ project.name }}

{{ project.summary }}

## 연구 질문

{{ project.research_question }}

## 처음 볼 문서

1. [STATUS.md](STATUS.md): 현재 상태와 사람의 판단이 필요한 항목
2. [plan/roadmap.md](plan/roadmap.md): 전체 계획
3. [FILEMAP.md](FILEMAP.md): 폴더 구조
4. [specs/README.md](specs/README.md): 문서 작성 규칙
5. [specs/workflow.md](specs/workflow.md): 작업 절차와 승인 게이트

## 사람이 하는 일

- `STATUS.md`의 "사람 판단 대기"를 확인하고 `reviews/open/`의 요청에 응답한다.
- 판정과 확정은 사람 신원의 커밋으로 남긴다. 사람 전용 커밋 타입: `gate`, `decide`, `plan`, `spec`, `respond` ([specs/git-commit.md](specs/git-commit.md)).
- 커밋은 터미널에서 `lg commit`으로 한다. 타입과 필수 trailer를 물어 메시지를 만들고, 게이트 승인이면 tag `gate/<Task>`도 남긴다. `git commit`을 직접 써도 되며, 그때 tag는 `git tag gate/<Task>`로 남긴다.
- 코드·문서를 직접 고쳤다면 에이전트가 작업하기 전에 커밋한다(`exp`, `result` 등 공통 타입 사용 가능). 에이전트에게 초안을 부탁하면 에이전트가 `lg draft`로 준비하고, `lg commit`으로 확인해 확정한다 ([specs/workflow.md](specs/workflow.md) §4).

## 저장소를 새로 클론했을 때

```bash
git config core.hooksPath .lg/hooks
git config user.name "<이름>"
git config user.email "<.lg/identities.json에 등록된 이메일>"
```

`lg commit`을 쓰려면 labgate(spec_version {{ spec_version }} 지원 버전)를 설치한다. 없어도 `git commit`으로 커밋할 수 있다.

<sub>labgate {{ labgate_version }}로 {{ today }}에 초기화됨 · spec_version {{ spec_version }}</sub>
~~~~

## A.2 `FILEMAP.md` (J)

~~~~markdown
---
id: FILEMAP
type: filemap
spec_version: {{ spec_version }}
updated: {{ today }}
---
# 폴더 지도

이 문서는 "무엇이 어디에 있는가"를 설명한다. "어떻게 써야 하는가"는 [specs/](specs/README.md)에 있다.

## 루트 문서

| 파일 | 역할 | 주로 쓰는 쪽 |
|---|---|---|
| `README.md` | 사람용 입구 | 사람 |
| `FILEMAP.md` | 이 문서 | 공통 |
| `AGENTS.md` | 에이전트 행동 규칙의 원본 | 사람 (에이전트는 읽기만) |
{% if claude_code %}
| `CLAUDE.md` | Claude Code 연결: `AGENTS.md` 참조 | 사람 |
{% endif %}
| `STATUS.md` | 현재 상태판, 사람 판단 대기 목록 | 에이전트 |

## 폴더

| 폴더 | 내용 | 명명 규칙 |
|---|---|---|
| `.lg/` | 프로젝트 설정, 신원, Git hook | 수정하지 않음 (`.lg/pending/`만 예외: 사람 커밋 초안 `COMMIT_MSG`, 사람의 변경 목록 `HUMAN_FILES`, Git 제외) |
{% if claude_code %}
| `.claude/` | Claude Code 설정과 슬래시 커맨드 | |
{% endif %}
| `specs/` | 문서 사양, 워크플로우, 커밋 규약, 양식, 에이전트 절차 | `doc-types/<유형>.spec.md`, `procedures/<절차>.md` |
| `plan/` | 로드맵과 마일스톤·task 계획 | `milestones/<M>/tasks/<Task>.md` |
| `decisions/` | 결정 문서와 목록 | `<D-ID>_<slug>.md` |
| `references/` | 참고문헌 목록, 원본, 마일스톤별 task-문헌 매핑 | `library/<Ref-ID>.<ext>` |
| `experiments/` | 공용 코드(`src/`, `tests/`)와 task별 실험 | `<M>/<Task>_<slug>/` |
| `runs/` | 실행 산출물 원본 (Git 제외) | `<Run-ID>/` |
| `results/` | task 결과, 마일스톤 보고, 그림, 표 | `<M>/<Task>_result.md`, `<M>/report.md` |
| `reviews/` | 게이트 요청과 에스컬레이션 (`open/` → `closed/`) | `<Task>_gate-NN.md`, `<Task>_esc-NN.md` |
| `logs/` | 에이전트 세션 작업 일지 | `YYYY-MM-DD_sNN.md` |
| `data/` | 데이터 생성 설정, 데이터 설명서 | |
| `paper/` | 원고, 그림, 참고문헌 bib | |
| `notes/` | 아이디어 원문, 회의 메모, 기존 자료 | 자유 |
| `scripts/` | 프로젝트 도구 (`agent-commit`, `session-check`) | |
| `env/` | 환경 설정 | |

## 마일스톤

| ID | 제목 | 계획 | 문헌 매핑 | 결과 |
|---|---|---|---|---|
{% for m in milestones %}
| `{{ m.id }}` | {{ m.title }} | [milestone.md](plan/milestones/{{ m.id }}/milestone.md) | [task-map.md](references/{{ m.id }}/task-map.md) | `results/{{ m.id }}/` |
{% endfor %}

## ID가 문서를 잇는 방식

모든 문서는 ID로 서로를 가리킨다. 규칙은 [specs/conventions.md](specs/conventions.md) §1.
예: `results/M1/M1-T2_result.md`의 근거가 `M1-T2_run-003`이고, 이 실행은 결정 `D1.1`과 참고문헌 `guo2025-loglinear`를 따른다.
~~~~

## A.3 `AGENTS.md` (J)

~~~~markdown
# 에이전트 작업 규칙

이 문서는 이 저장소에서 작업하는 모든 에이전트가 따르는 규칙의 원본이다. 도구별 설정 파일은 이 문서를 참조할 뿐 규칙을 바꾸지 않는다. 이 문서는 사람만 수정한다.

## 프로젝트

- 이름: {{ project.name }}
- 연구 질문: {{ project.research_question }}
- 에이전트 신원: {{ agent.name }} <{{ agent.email }}>

## 역할

에이전트는 **승인된 task의 범위 안에서** 자율적으로 일한다. 판정·확정·계획 변경은 사람의 몫이다. 상태 기계는 [specs/workflow.md](specs/workflow.md)에, 상황별 단계는 아래 3절의 절차 문서에 있다.

## 0. 규칙의 우선순위

규칙은 사람만 고친다(`spec` 커밋). 작업 중에는 고치지 않는다. 적용할 때는 더 구체적인 규범이 먼저다.

1. 불변 원칙(1절)은 무엇으로도 바뀌지 않는다. task 카드에 적혀 있어도 마찬가지다.
2. 현재 task 카드의 "범위 › 포함"에 명시된 것은 그 task를 수행하는 동안 특별 규칙과 일반 규칙보다 우선한다.
3. 절차를 수행하는 동안에는 그 절차 문서의 "특별 규칙"이 일반 규칙보다 우선한다. 특별 규칙은 그 절차 안에서만 유효하다.
4. 그 밖에는 일반 규칙(2절)을 따른다.
5. 규칙끼리 충돌하거나 어느 규칙에도 없는 상황이면 불변 원칙에 맞는 쪽을 택한다. 그래도 정할 수 없으면 멈추고 사람에게 묻는다.

도구(`scripts/session-check`, `scripts/apply-human-commits`, `lg draft`)가 하는 일은 그 도구가 정한다. 도구가 하는 일을 손으로 하지 않는다.

## 1. 불변 원칙

- **P1.** 사실의 원본은 Git 커밋이다. 문서의 상태 필드는 커밋을 반영한 것이며, 둘이 다르면 커밋이 우선한다. 사람 커밋의 결과를 상태 필드에 반영하는 것은 에이전트의 책임이며, `scripts/apply-human-commits`로 한다(절차 `gate-apply`).
- **P2.** 사람 신원으로 커밋하지 않는다. `git commit`, `lg commit`을 실행하지 않는다. 커밋은 `scripts/agent-commit`으로만 하고 `--no-verify`, `--author`, `-a`를 쓰지 않는다. trailer(`Actor` 등)는 메시지의 마지막 한 문단에 모두 쓰고, 그 뒤에 다른 문단(서명, `Co-Authored-By` 등)을 붙이지 않는다([specs/git-commit.md](specs/git-commit.md) §2).
- **P3.** 사람 전용 커밋 타입(`gate`, `decide`, `plan`, `spec`, `respond`)을 쓰지 않는다.
- **P4.** 이력을 다시 쓰지 않는다(rebase, 사람 커밋 amend, force push). 브랜치를 병합하거나 cherry-pick하지 않는다. tag를 만들지 않는다.
- **P5.** 사람의 변경을 되돌리거나 치우지 않는다(`git restore`, `git checkout --`, `git stash`). 사람의 변경을 에이전트 커밋에 넣지 않는다.
- **P6.** 사람이 말하지 않은 판정·결정을 만들어 내지 않는다. 확인하지 않은 서지 정보나 수치를 지어내지 않는다. 사실과 추측을 구분해 쓴다.

## 2. 일반 규칙

- **G1.** 문서는 `specs/`의 사양을 따른다. 사양이 `stub`이면 `specs/conventions.md`의 공통 규칙을 지키고, 사용한 구조를 작업 일지에 남긴다.
- **G2.** 자기가 바꾼 파일만 경로를 지정해 stage한다(`git add -A`, `git add .`, `git add -u` 금지). 사람의 변경은 stage하지 않고, 사람의 변경이 있는 파일은 고치지 않는다. 그런 파일을 고쳐야 하면 먼저 사람에게 커밋을 요청한다.
- **G3.** 사람 커밋 대기 상태(`.lg/pending/COMMIT_MSG` 있음)에서는 커밋하지 않는다.
- **G4.** 사람 몫의 상태 전이를 하지 않는다: task `draft → approved`, `in-review → closed | revise | redirected`, 결정 `→ confirmed`, 마일스톤 `planned → active → closed`.
- **G5.** review 문서의 `## 응답` 섹션을 쓰지 않는다.
- **G6.** `plan/roadmap.md`와 `active` 이상인 마일스톤의 목표·기준을 바꾸지 않는다. 변경은 `notes/`에 제안하고 `propose` 커밋을 남긴다.
- **G7.** `specs/`, `AGENTS.md`{% if claude_code %}, `CLAUDE.md`, `.claude/`{% endif %}, `.lg/`를 고치지 않는다. 변경은 `notes/`에 제안하고 `propose` 커밋을 남긴다.
- **G8.** 워크트리(Claude Code `--worktree`, 서브에이전트 `isolation: worktree`)는 실험 격리용으로만 쓴다. 워크트리 안에서도 커밋 규약은 같다. 워크트리 브랜치는 병합하거나 cherry-pick하지 않는다. 채택할 결과는 파일을 `main` 작업 트리로 옮겨 `scripts/agent-commit`으로 새로 커밋하고, 쓰지 않을 워크트리는 정리한다.
- **G9.** 승인된 task의 범위와 자원 예산 안에서만 일한다. [specs/workflow.md](specs/workflow.md) §7.1의 경우에는 멈추고 에스컬레이션한다(절차 `escalate`).
- **G10.** 본문은 한국어로 쓴다. 식별자, frontmatter 키, 상태값, 커밋 타입은 영어로 쓴다.

## 3. 절차

아래 상황이 되면 해당 문서를 읽고 그 단계를 따른다. 특별 규칙은 각 문서의 "특별 규칙" 절에 있다.

| 상황 | 절차 | 특별 규칙 |
|---|---|---|
| 세션 시작 | [session-start](specs/procedures/session-start.md) | 없음 |
| 세션 종료 | [session-close](specs/procedures/session-close.md) | 없음 |
| 커밋되지 않은 사람의 변경이 있음, 사람이 자기 변경을 알리거나 커밋 준비를 요청 | [commit-prep](specs/procedures/commit-prep.md) | G2 |
| 승인된 task 착수 | [task-start](specs/procedures/task-start.md) | 없음 |
| task 완료, 게이트 요청 | [task-gate](specs/procedures/task-gate.md) | 없음 |
| G9의 멈춤 조건 | [escalate](specs/procedures/escalate.md) | 없음 |
| 사람이 대화로 판정·결정·응답 | [gate-conversation](specs/procedures/gate-conversation.md) | G5 |
| 반영되지 않은 사람 커밋이 있음 | [gate-apply](specs/procedures/gate-apply.md) | G4 |

## 참고

- 상태 기계와 게이트: [specs/workflow.md](specs/workflow.md)
- 커밋 규약: [specs/git-commit.md](specs/git-commit.md)
- 공통 규칙: [specs/conventions.md](specs/conventions.md)
~~~~

## A.4 `CLAUDE.md` (J, claude_code)

~~~~markdown
# Claude Code 지침

이 저장소의 규칙 원본은 `AGENTS.md`다. 아래 import로 읽어 들인다.

@AGENTS.md

## Claude Code 고유 사항

- 커밋은 `scripts/agent-commit`으로만 한다. `git commit`, `lg commit` 직접 실행은 `.claude/settings.json`에서 차단되어 있다.
- 세션이 시작될 때(재개, `/clear`, compact 포함) hook이 `scripts/session-check`를 실행한다. 출력이 있으면 그 내용이 절차 `session-start`의 1단계 결과다.
- 절차는 슬래시 커맨드로 시작할 수 있다:
  - `/session-start`: 세션 시작
  - `/task-start <Task>`: 승인된 task 착수
  - `/task-gate <Task>`: task 완료와 게이트 요청 제출
  - `/escalate <Task>`: 에스컬레이션 제출
  - `/commit-prep [경로…]`: 사람의 변경 커밋 준비
  - `/session-close`: 세션 종료
~~~~

## A.5 `.claude/settings.json` (S, claude_code)

규칙 문법은 Claude Code 문서(code.claude.com/docs/en/permissions)의 `Bash(<prefix> *)` 형식이다 (2026-10 확인. `:*` 형식도 같은 뜻이지만 공백 형식이 표준). 복합 명령(`cd x && git commit …`)은 하위 명령마다 검사되므로 막힌다. 그러나 `git -C . commit`처럼 프로그램과 하위 명령 사이에 옵션을 넣으면 일치하지 않는다. 즉 이 파일은 실수 방지 장치이고 보안 경계가 아니다. 실제 강제는 commit-msg hook(신원·타입 검사)이 한다. 끝의 ` *`는 옵션 없는 명령에도 일치한다(`Bash(git add -A *)`는 `git add -A`도 막는다). `git add` 일괄 stage와 `git stash`를 막는 것은 사람의 미커밋 변경이 에이전트 커밋에 섞이거나 치워지는 것을 막기 위해서다 (workflow.md §4.1). `Bash(git add . *)`는 `git add .`을 막고 `git add ./path`는 막지 않는다. `Bash(lg commit *)`는 에이전트가 사람 신원으로 커밋하는 것을 막는다. 준비 명령 `lg draft`는 이 규칙에 일치하지 않는다 (§17.3).

`hooks.SessionStart`는 세션 시작·재개·`/clear`·compact 때 `scripts/session-check`를 실행해 그 출력을 에이전트 맥락에 넣는다 (§17.3). `args`가 없으므로 셸 형식으로 실행되어 `"$CLAUDE_PROJECT_DIR"`가 확장된다.

`attribution`은 Claude Code가 커밋 메시지 끝에 붙이는 공동 작성자 줄(기본 `Co-Authored-By: <모델> <noreply@anthropic.com>`)과 PR 문구를 끈다. 이 줄이 별도 문단으로 붙으면 hook이 마지막 문단에서 `Actor`를 찾지 못해 커밋이 거부된다. 빈 문자열이 문서상 끄는 방법이다. `"attribution": false`는 v2.1.281 미만에서 설정 파일 전체를 건너뛰게 해 deny 규칙까지 사라지므로 쓰지 않는다. 사용 중단된 `includeCoAuthoredBy`도 쓰지 않는다.

~~~~json
{
  "permissions": {
    "deny": [
      "Bash(git commit *)",
      "Bash(git tag *)",
      "Bash(git rebase *)",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(git reset --hard *)",
      "Bash(git merge *)",
      "Bash(git cherry-pick *)",
      "Bash(git add -A *)",
      "Bash(git add --all *)",
      "Bash(git add -u *)",
      "Bash(git add --update *)",
      "Bash(git add . *)",
      "Bash(git stash *)",
      "Bash(lg commit *)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/session-check" }
        ]
      }
    ]
  },
  "attribution": {
    "commit": "",
    "pr": "",
    "sessionUrl": false
  }
}
~~~~

## A.6 `.claude/commands/*.md` (S, claude_code)

절차의 원본은 `specs/procedures/`(B.10)다. 명령 파일은 절차 문서를 가리키기만 한다.

`session-start.md`

~~~~markdown
specs/procedures/session-start.md 를 따르라.
~~~~

`task-start.md`

~~~~markdown
task $ARGUMENTS 를 착수한다. specs/procedures/task-start.md 를 따르라 (<Task> = $ARGUMENTS).
~~~~

`task-gate.md`

~~~~markdown
task $ARGUMENTS 의 게이트 요청을 제출한다. specs/procedures/task-gate.md 를 따르라 (<Task> = $ARGUMENTS).
~~~~

`escalate.md`

~~~~markdown
task $ARGUMENTS 에서 에스컬레이션을 제출한다. specs/procedures/escalate.md 를 따르라 (<Task> = $ARGUMENTS).
~~~~

`session-close.md`

~~~~markdown
specs/procedures/session-close.md 를 따르라.
~~~~

`commit-prep.md`

~~~~markdown
사람의 변경을 커밋할 수 있게 준비한다. specs/procedures/commit-prep.md 를 따르라. 경로가 주어지면($ARGUMENTS) 사람이 알려 준 변경으로 본다.
~~~~

## A.7 `STATUS.md` (J)

~~~~markdown
---
id: STATUS
type: status
spec_version: {{ spec_version }}
updated: {{ today }}
---
# 상태판

## 현재 위치

- 마일스톤: `{{ milestones[0].id }}` ({{ milestones[0].title }})
- Task: `{{ milestones[0].id }}-T0` (draft: 사람 승인 대기)

## 사람 판단 대기

| 항목 | 종류 | 요청일 | 문서 |
|---|---|---|---|
| `{{ milestones[0].id }}-T0` 승인 | task 승인 | {{ today }} | [{{ milestones[0].id }}-T0](plan/milestones/{{ milestones[0].id }}/tasks/{{ milestones[0].id }}-T0.md) |

## 진행 중

(없음)

## 막힘

(없음)

## 최근 게이트

(없음)

## 다음 예정

- `{{ milestones[0].id }}-T0` 승인 후: 착수 계획 수립 (문헌 정리, task 분해, 기존 계획 이관)
~~~~

## A.8 `.gitignore` (S)

~~~~gitignore
# 실행 산출물 원본
runs/*
!runs/.gitkeep

# 대화 경로 게이트용 임시 커밋 메시지
.lg/pending/

# Claude Code 워크트리 (실험 격리용, main에 병합하지 않음)
.claude/worktrees/

# Python
__pycache__/
*.py[cod]
.venv/
venv/
.ipynb_checkpoints/
.pytest_cache/

# 실험 도구
wandb/
mlruns/

# OS / 편집기
.DS_Store
Thumbs.db
.idea/
.vscode/

# 대용량 원본 데이터는 필요 시 아래 주석을 해제
# data/raw/
~~~~

## A.9 `plan/roadmap.md` (J)

~~~~markdown
---
id: roadmap
type: roadmap
spec_version: {{ spec_version }}
status: draft
created: {{ today }}
updated: {{ today }}
---
# 로드맵: {{ project.name }}

## 연구 질문

{{ project.research_question }}

## 가설

> TODO: {{ milestones[0].id }}-T0에서 작성

## 마일스톤

| ID | 제목 | 상태 | 계획 |
|---|---|---|---|
{% for m in milestones %}
| `{{ m.id }}` | {{ m.title }} | planned | [milestone.md](milestones/{{ m.id }}/milestone.md) |
{% endfor %}

## 공통 실험 원칙

> TODO: {{ milestones[0].id }}-T0에서 작성

## 범위 밖

> TODO

## 변경 이력

| 날짜 | 변경 | 커밋 |
|---|---|---|
| {{ today }} | 초기화 | `init` |
~~~~

## A.10 `plan/milestones/<M>/milestone.md` (J, 마일스톤마다)

~~~~markdown
---
id: {{ m.id }}
type: milestone
spec_version: {{ spec_version }}
title: {{ m.title | yq }}
status: planned
go_nogo: null
created: {{ today }}
updated: {{ today }}
---
# {{ m.id }}. {{ m.title }}

## 목표

> TODO: {{ m.id }}-T0에서 작성

## Task 목록

| ID | 제목 | 상태 | 카드 |
|---|---|---|---|
| `{{ m.id }}-T0` | 착수 계획 | draft | [{{ m.id }}-T0](tasks/{{ m.id }}-T0.md) |

## Go / No-go 기준

> TODO: {{ m.id }}-T0에서 작성

## 관련 결정

(없음)

## 결과

- 마일스톤 보고: `results/{{ m.id }}/report.md` (마일스톤 종료 시 작성)
~~~~

## A.11 `plan/milestones/<M>/tasks/<M>-T0.md` (J, 마일스톤마다)

~~~~markdown
---
id: {{ m.id }}-T0
type: task-card
spec_version: {{ spec_version }}
title: "착수 계획"
milestone: {{ m.id }}
status: draft
depends_on: []
decisions: []
references: []
budget:
  gpu_hours: 0
  wall_days: null
created: {{ today }}
updated: {{ today }}
---
# {{ m.id }}-T0. 착수 계획

## 목표

{{ m.id }} ({{ m.title }})의 실행 계획을 세운다. 필요한 문헌을 정리하고, 마일스톤을 task로 분해하고, task와 문헌을 연결한다.

## 범위

### 포함

- 문헌 조사, 원본을 `references/library/`에 저장, `references/catalog.md`에 등록
- task 분해: `{{ m.id }}-T1` 이후 task 카드를 `draft`로 작성
- `references/{{ m.id }}/task-map.md` 작성
- `plan/milestones/{{ m.id }}/milestone.md`의 목표, task 목록, Go/No-go 기준 초안 작성 (마일스톤이 `planned`인 동안 허용)
{% if prev is none %}
- `notes/`의 기존 계획 자료를 `plan/roadmap.md`, 각 `milestone.md`, `decisions/`로 이관 (기존 결정은 `proposed` 상태로)
- 이번 마일스톤에 필요한 stub 사양의 초안을 `notes/spec-drafts/`에 작성 (확정은 사람의 `spec` 커밋)
{% endif %}

### 제외

- 실험 코드 작성과 실행
- 결정 확정

## 입력

- `plan/roadmap.md`
- `plan/milestones/{{ m.id }}/milestone.md`
{% if prev is none %}
- `notes/`의 기존 계획 자료 (사람이 넣어 둠)
{% else %}
- 이전 마일스톤 보고: `results/{{ prev.id }}/report.md`
{% endif %}

## 산출물

- `{{ m.id }}-T1` 이후 task 카드 (`draft`)
- `references/{{ m.id }}/task-map.md`
- 갱신된 `references/catalog.md`, `references/library/`
- `milestone.md` 초안
{% if prev is none %}
- 이관된 `plan/roadmap.md`, 각 `milestone.md`, `decisions/` 문서
{% endif %}
- 게이트 요청서 `reviews/open/{{ m.id }}-T0_gate-01.md`

## 완료 기준

- [ ] 모든 새 task 카드가 `specs/doc-types/task-card.spec.md`를 만족한다
- [ ] 모든 task가 검증 가능한 완료 기준을 하나 이상 갖는다
- [ ] `task-map.md`에 각 task의 참고문헌, 또는 참고문헌이 없는 이유가 있다
- [ ] 등록한 모든 문헌의 원본이 `references/library/`에 있고 `catalog.md`에 기재되어 있다
- [ ] `milestone.md`에 Go/No-go 기준 초안이 있다
{% if prev is none %}
- [ ] 기존 계획의 결정 항목이 모두 `decisions/`에 `proposed`로 옮겨졌다
{% endif %}
- [ ] 게이트 요청서를 제출했다

## 자원 예산

- GPU: 0시간 (실행 없음)

## 위험과 가정

> 착수 시 에이전트가 작성

## 진행 메모

> 에이전트가 세션마다 갱신

## 게이트 이력

(없음)
~~~~

## A.12 `decisions/index.md` (J)

~~~~markdown
---
id: decisions-index
type: decision-index
spec_version: {{ spec_version }}
updated: {{ today }}
---
# 결정 목록

상태: `proposed` → `discussing` → `confirmed` (사람의 `decide` 커밋) / `superseded`

| ID | 제목 | 상태 | 마일스톤 | 확정 커밋 | 문서 |
|---|---|---|---|---|---|
~~~~

## A.13 `references/catalog.md` (J)

~~~~markdown
---
id: catalog
type: catalog
spec_version: {{ spec_version }}
updated: {{ today }}
---
# 참고문헌 목록

ID 규칙: [specs/conventions.md](../specs/conventions.md) §1. 원본은 `library/<ID>.<ext>`.

| ID | 제목 | 저자 | 연도 | 원본 | 관련 마일스톤 | 한 줄 요약 |
|---|---|---|---|---|---|---|
~~~~

## A.14 `references/<M>/task-map.md` (J, 마일스톤마다)

~~~~markdown
---
id: {{ m.id }}-task-map
type: task-map
spec_version: {{ spec_version }}
milestone: {{ m.id }}
updated: {{ today }}
---
# {{ m.id }} task ↔ 참고문헌

| Task | 참고문헌 ID | 볼 부분 | 이유 |
|---|---|---|---|
| `{{ m.id }}-T0` | (T0에서 작성) | | |
~~~~

---

# 부록 B. `specs/` 문서

모든 사양(`*.spec.md`)은 같은 7개 섹션을 가진다: 1 목적, 2 위치와 파일명, 3 frontmatter, 4 본문 구조, 5 작성·수정 권한, 6 생성·갱신 시점, 7 검증 규칙.

## B.1 `specs/README.md` (J)

~~~~markdown
---
id: specs-index
type: spec-index
spec_version: {{ spec_version }}
updated: {{ today }}
---
# 문서 사양

이 폴더는 "문서를 어떻게 써야 하는가"를 정한다. 모든 문서는 여기의 사양을 따른다. 사양 변경은 사람의 `spec` 커밋으로만 확정한다.

## 공통 규칙

| 문서 | 내용 | 상태 |
|---|---|---|
| [conventions.md](conventions.md) | ID, 파일명, 날짜, frontmatter 공통 필드, 상태 어휘, 언어 | complete |
| [workflow.md](workflow.md) | 원칙, 역할, task 상태 기계, 사람의 커밋, 게이트·에스컬레이션·마일스톤 원칙 | complete |
| [git-commit.md](git-commit.md) | 커밋 메시지 규약, 신원, tag | complete |

## 문서 유형

| 유형 | 사양 | 양식 | 위치 | 상태 |
|---|---|---|---|---|
| task-card | [task-card.spec.md](doc-types/task-card.spec.md) | [task-card.md](templates/task-card.md) | `plan/milestones/<M>/tasks/<Task>.md` | complete |
| review | [review.spec.md](doc-types/review.spec.md) | [review.md](templates/review.md) | `reviews/{open,closed}/<Task>_{gate,esc}-NN.md` | complete |
| roadmap | [roadmap.spec.md](doc-types/roadmap.spec.md) | — | `plan/roadmap.md` | stub |
| milestone | [milestone.spec.md](doc-types/milestone.spec.md) | — | `plan/milestones/<M>/milestone.md` | stub |
| task-map | [task-map.spec.md](doc-types/task-map.spec.md) | — | `references/<M>/task-map.md` | stub |
| catalog | [catalog.spec.md](doc-types/catalog.spec.md) | — | `references/catalog.md` | stub |
| decision | [decision.spec.md](doc-types/decision.spec.md) | — | `decisions/<D-ID>_<slug>.md` | stub |
| experiment-readme | [experiment-readme.spec.md](doc-types/experiment-readme.spec.md) | — | `experiments/<M>/<Task>_<slug>/README.md` | stub |
| run-record | [run-record.spec.md](doc-types/run-record.spec.md) | — | `experiments/<M>/<Task>_<slug>/runs/<Run-ID>.yaml` | stub |
| task-result | [task-result.spec.md](doc-types/task-result.spec.md) | — | `results/<M>/<Task>_result.md` | stub |
| milestone-report | [milestone-report.spec.md](doc-types/milestone-report.spec.md) | — | `results/<M>/report.md` | stub |
| worklog | [worklog.spec.md](doc-types/worklog.spec.md) | — | `logs/YYYY-MM-DD_sNN.md` | stub |
| status | [status.spec.md](doc-types/status.spec.md) | — | `STATUS.md` | stub |

`stub` 사양은 공통 구조만 있다. 해당 유형의 문서를 쓸 때는 `conventions.md`를 지키고, 초기화 때 생성된 같은 유형의 문서(있다면)의 구조를 따른다. 사양 보완은 M0 진행 중에 한다.

## 절차

에이전트가 상황별로 읽고 따르는 단계 목록이다. 언제 어느 절차를 읽는지는 [AGENTS.md](../AGENTS.md)의 "절차" 표에 있다.

| 절차 | 시작 조건 |
|---|---|
| [session-start](procedures/session-start.md) | 세션 시작 |
| [session-close](procedures/session-close.md) | 세션 종료 |
| [commit-prep](procedures/commit-prep.md) | 커밋되지 않은 사람의 변경, 사람의 커밋 준비 요청 |
| [task-start](procedures/task-start.md) | 승인된 task 착수 |
| [task-gate](procedures/task-gate.md) | task 완료, 게이트 요청 |
| [escalate](procedures/escalate.md) | 멈춤 조건 |
| [gate-conversation](procedures/gate-conversation.md) | 사람이 대화로 판정·결정·응답 |
| [gate-apply](procedures/gate-apply.md) | 반영되지 않은 사람의 `gate`·`respond` 커밋 |

## 모든 사양의 구조

1. 목적 · 2. 위치와 파일명 · 3. frontmatter · 4. 본문 구조 · 5. 작성·수정 권한 · 6. 생성·갱신 시점 · 7. 검증 규칙
~~~~

## B.2 `specs/conventions.md` (S)

~~~~markdown
---
id: conventions
type: spec
spec_version: 3
status: complete
---
# 공통 규칙

## 1. ID 체계

| 대상 | 형식 | 예 | 비고 |
|---|---|---|---|
| 마일스톤 | `M<n>` | `M1` | 0부터 |
| Task | `M<n>-T<n>` | `M1-T2` | 마일스톤마다 T0부터 |
| 결정 | `D<n>.<n>` | `D1.3` | 앞 숫자 = 마일스톤 번호, 뒤 숫자 = 그 마일스톤 안의 순번(1부터) |
| 참고문헌 | `<1저자 성><연도>-<키워드>` | `guo2025-loglinear` | 소문자 ASCII, 키워드는 하이픈 연결 영문 1–3단어. 충돌 시 연도 뒤에 `b`, `c` (`guo2025b-…`) |
| 실행 | `<Task>_run-<NNN>` | `M1-T2_run-003` | task 안에서 001부터 |
| Review | `<Task>_gate-<NN>`, `<Task>_esc-<NN>` | `M1-T2_gate-01` | task 안에서 종류별 01부터 |
| 작업 일지 | `YYYY-MM-DD_s<NN>` | `2026-10-03_s02` | 그날 세션 순번 |

ID는 한 번 부여하면 바꾸지 않는다. 폐기된 대상의 ID는 재사용하지 않는다.

## 2. 파일과 폴더 이름

- 위 ID를 파일명에 그대로 쓴다. 추가 설명이 필요하면 `<ID>_<slug>` 형식으로 붙인다.
- `slug`는 소문자 ASCII와 하이픈만 쓴다 (`^[a-z0-9]+(-[a-z0-9]+)*$`).
- 위치는 [FILEMAP.md](../FILEMAP.md)와 각 사양 §2를 따른다.

## 3. 날짜와 시간

- 날짜: `YYYY-MM-DD` (로컬 날짜).
- 시각이 필요하면 ISO 8601 (`2026-10-03T14:05:00+09:00`).

## 4. Frontmatter

Markdown 문서는 YAML frontmatter로 시작한다. 다음은 예외다(frontmatter 없음):

- 루트 `README.md`: 사람용 입구
- `AGENTS.md`, 그리고 있다면 `CLAUDE.md`와 `.claude/` 아래 파일: 에이전트 도구가 그대로 읽는 지침
- `notes/`, `paper/` 아래 파일: 형식 자유

`specs/templates/`의 양식은 frontmatter를 갖지만 값이 `<...>` 자리 표시이므로 검증 대상이 아니다.

공통 필드:

| 필드 | 필수 | 설명 |
|---|---|---|
| `id` | ✓ | 문서 ID |
| `type` | ✓ | 문서 유형. 아래 표 참고 |
| `spec_version` | ✓ | 따르는 사양 버전 (현재 3). 사양을 갱신할 때 사람이 모든 문서를 일괄로 올린다(`spec` 커밋). 문서를 쓰거나 고칠 때는 바꾸지 않는다 |
| `status` | 유형별 | §5의 상태값 |
| `created` | 유형별 | 생성일 |
| `updated` | ✓ (사양 문서 제외) | 마지막 수정일. 사양 문서(`type: spec`)의 변경 시점은 `spec` 커밋 이력으로 본다 |

`type` 값:

| 구분 | `type` |
|---|---|
| 사양이 있는 문서 | `specs/doc-types/`의 사양 이름과 같다: `task-card`, `review`, `roadmap`, `milestone`, `task-map`, `catalog`, `decision`, `experiment-readme`, `run-record`, `task-result`, `milestone-report`, `worklog`, `status` |
| 사양 문서 자신 | `spec` |
| 절차 문서 (`specs/procedures/`) | `procedure` |
| 목록·안내 문서 (사양 없음) | `filemap` (`FILEMAP.md`), `spec-index` (`specs/README.md`), `decision-index` (`decisions/index.md`) |

- 값이 없으면 `null`. 목록이 비면 `[]`.
- 사람이 입력한 문자열은 큰따옴표로 감싼다.
- 다른 문서를 가리키는 필드에는 경로가 아니라 ID를 쓴다.

## 5. 상태값

| 유형 | 상태값 |
|---|---|
| task-card | `draft`, `approved`, `in-progress`, `blocked`, `in-review`, `revise`, `closed`, `redirected` |
| milestone | `planned`, `active`, `closed` |
| decision | `proposed`, `discussing`, `confirmed`, `superseded` |
| review | `open`, `answered`, `closed` |
| roadmap | `draft`, `active` |
| spec | `stub`, `complete` |

전이 규칙은 [workflow.md](workflow.md) §3.

## 6. 링크와 참조

- 문서 본문에서 다른 문서를 언급할 때는 ID를 백틱으로 쓴다: `M1-T2`, `D1.3`, `guo2025-loglinear`.
- 처음 언급하거나 바로 열어 봐야 하는 경우에는 상대 경로 Markdown 링크를 함께 쓴다.
- 커밋을 가리킬 때는 짧은 해시 7자리.

## 7. 언어와 문체

- 본문: 한국어. 식별자, frontmatter 키, 상태값, 커밋 타입, 코드: 영어.
- 사실과 추측을 구분한다. 추측에는 "추정", "가설", "미확인"을 붙인다.
- 수치에는 출처(실행 ID, 참고문헌 ID)를 붙인다.

## 8. Stub 사양의 문서를 쓸 때

해당 사양이 `stub`이면 이 문서의 규칙을 지키고, 초기화 때 생성된 같은 유형의 문서가 있으면 그 구조를 따른다. 새로 구조를 정했다면 작업 일지에 적어 둔다(사양 보완 근거가 된다).
~~~~

## B.3 `specs/workflow.md` (S)

~~~~markdown
---
id: workflow
type: spec
spec_version: 3
status: complete
---
# 워크플로우

## 1. 원칙

1. **Task는 승인 게이트 사이의 작업 단위다.** 에이전트는 승인된 task 범위 안에서 자율적으로 일하고, 경계에서 사람이 판정한다.
2. **사실의 원본은 Git 커밋이다.** 사람의 판정·확정은 사람 신원의 커밋(trailer 포함)이 원본이고, 문서의 상태 필드는 그것을 반영한다([AGENTS.md](../AGENTS.md) P1).
3. **이력은 `main` 하나로 선형이다.** 게이트 지점은 tag로 표시한다. 워크트리 브랜치는 실험 격리용 임시 브랜치이며 `main`에 병합·cherry-pick하지 않는다 ([AGENTS.md](../AGENTS.md)).
4. **규칙의 층과 우선순위는 [AGENTS.md](../AGENTS.md) 0절에 있다.** 불변 원칙은 예외가 없고, 적용할 때는 task 카드, 절차의 특별 규칙([procedures/](procedures/)), 일반 규칙 순으로 구체적인 것이 먼저다. 이 문서는 상태 기계와 게이트를 정한다.

## 2. 역할

| 주체 | 하는 일 |
|---|---|
| 사람 | task 승인, 게이트 판정, 에스컬레이션 응답, 결정 확정, 계획·사양 변경, tag 생성. 필요하면 코드·문서를 직접 고치고 사람 신원으로 커밋 (§4) |
| 에이전트 | 승인된 task 수행, 문서·코드·실행 기록 작성, 결정·계획·사양 변경 제안, 게이트 요청, 에스컬레이션, 사람 커밋의 초안 준비, 사람 커밋의 결과를 문서에 반영 |

## 3. Task 상태 기계

```
draft ──▶ approved ──▶ in-progress ──▶ in-review ──┬──▶ closed
                          │   ▲                    ├──▶ revise ──▶ in-progress
                          ▼   │                    └──▶ redirected
                         blocked
```

| 전이 | 주체 | 기록하는 커밋 |
|---|---|---|
| `draft → approved` | 사람 | 이전 task의 `gate` 커밋 `Next:`, 또는 `plan` 커밋 `Approve:` (반영: `gate-apply`) |
| `approved → in-progress` | 에이전트 | `task` |
| `in-progress → blocked` | 에이전트 | `review` (에스컬레이션 제출) |
| `blocked → in-progress` | 에이전트 | `task` (사람의 `respond` 커밋 이후에만) |
| `in-progress → in-review` | 에이전트 | `review` (게이트 요청 제출) |
| `in-review → closed / revise / redirected` | 사람 | `gate` (`Verdict:`) |
| `revise → in-progress` | 에이전트 | `task` |

- `redirected`는 끝 상태다. 대체 계획은 사람의 `plan` 커밋으로 반영한다.
- 사람이 기록하는 전이는 사람이 해당 커밋에서 직접 바꾸거나, 에이전트가 `scripts/apply-human-commits`로 반영한다(절차 [gate-apply](procedures/gate-apply.md)). 반영 커밋은 `Applies:` trailer로 사람 커밋을 가리킨다.

마일스톤 상태: `planned → active`는 그 마일스톤 T0의 게이트 승인 시(T0 동안에는 `planned`이므로 에이전트가 목표·기준 초안을 쓸 수 있다), `active → closed`는 마지막 task의 `gate` 커밋에 `Milestone-Verdict:`가 있을 때.

## 4. 사람의 커밋

### 4.1 사람의 변경

사람도 코드·문서를 직접 고칠 수 있다. 사람의 변경은 사람 신원으로 커밋하며, 공통 타입(`exp`, `run`, `result`, `ref`, `log`, `chore`)을 쓸 수 있다 ([git-commit.md](git-commit.md) §3). 커밋은 터미널에서 `lg commit`으로 하거나 `git commit`으로 한다.

사람의 변경은 에이전트 작업보다 먼저 커밋한다. 세션 시작 때 커밋되지 않은 변경은 사람의 변경으로 본다(`scripts/session-check`가 알리고 `.lg/pending/HUMAN_FILES`에 기록한다). 에이전트는 그것을 건드리지 않고 사람에게 정리를 요청한다 (절차 [commit-prep](procedures/commit-prep.md)). 세션 도중에는 직접 수정하지 않는다. 했다면 에이전트에게 알린다.

### 4.2 사람 커밋 대기 상태

에이전트가 사람 커밋을 준비하면(`lg draft`) stage된 변경과 `.lg/pending/COMMIT_MSG`가 남는다. 사람이 `lg commit`으로 확인·확정할 때까지 에이전트는 어떤 커밋도 하지 않는다.

### 4.3 깨끗한 작업 트리

모든 세션은 깨끗한 작업 트리로 끝난다. 예외는 사람 커밋 대기 상태의 stage된 변경과 커밋되지 않은 사람의 변경뿐이다.

## 5. Task 진행

- 착수와 게이트 요청: 절차 [task-start](procedures/task-start.md), [task-gate](procedures/task-gate.md).
- 작업 단위마다 알맞은 타입으로 커밋한다 (`exp`, `run`, `result`, `ref`, `task` …).
- 새로운 결정이 필요하면 `decisions/`에 `proposed`로 쓰고 `propose` 커밋한다. 확정은 하지 않는다.
- 실행은 카드의 자원 예산 안에서만 한다. 실행마다 run-record를 남긴다.

## 6. 게이트

### 6.1 문서 경로 (사람이 직접 작성)

1. 사람이 review 문서의 `## 응답`을 작성하고 frontmatter `verdict`, `source: document`, `status: answered`, `answered`를 채운다.
2. 필요하면 같은 커밋에서 카드 `status`, 결정 `status`, 다음 task 카드 `status: approved`를 바꾼다.
3. `lg commit`으로 `gate(<Task>): <verdict>…` 커밋을 만든다 ([git-commit.md](git-commit.md) §4). 승인이면 `lg commit`이 tag `gate/<Task>`도 만든다. `git commit`으로 했다면 `git tag gate/<Task>`.

### 6.2 대화 경로 (사람이 대화로 판정)

절차 [gate-conversation](procedures/gate-conversation.md). 에이전트가 사람의 발언을 review의 `## 응답`에 옮기고 초안을 준비하면(`lg draft`), 사람이 `lg commit`으로 확인·확정한다. 상태 전이는 이 단계에서 하지 않고, 사람이 커밋한 뒤 §6.3으로 반영한다. 같은 방식이 `decide`, `respond`에도 적용된다.

### 6.3 판정 후 정리

절차 [gate-apply](procedures/gate-apply.md). 사람의 커밋 이후 `scripts/apply-human-commits`가 review 문서를 닫고 상태 필드를 커밋 trailer에 맞추며, 에이전트가 그 결과를 커밋한다. 문서 경로와 대화 경로가 같은 반영 경로를 쓴다.

### 6.4 판정별 다음 단계

| Verdict | 카드 | 다음 |
|---|---|---|
| `approve` | `closed` | `Next:`의 task가 `approved`. 없으면(`none`) 사람의 다음 지시 대기 |
| `revise` | `revise` | 같은 task 재개. 다음 게이트 요청은 `gate-NN`의 번호를 올린다 |
| `redirect` | `redirected` | 사람의 `plan` 커밋을 기다린다 |

## 7. 에스컬레이션

### 7.1 해야 하는 경우

- 승인된 범위 밖의 작업이 필요할 때
- 결과가 확정되지 않은 결정에 크게 좌우될 때
- 자원 예산을 넘어야 할 때
- 완료 기준 자체가 잘못되었거나 달성 불가능하다고 판단될 때
- 사양·규칙끼리 충돌할 때

### 7.2 진행

에이전트는 절차 [escalate](procedures/escalate.md)로 제출하고 멈춘다. 사람은 `respond(<Task>): …` 커밋으로 응답한다(§6.1 또는 §6.2와 같은 방식, `Verdict` 없음). 에이전트는 절차 [gate-apply](procedures/gate-apply.md)로 반영하고 작업으로 돌아간다.

## 8. 마일스톤 착수와 종료

- **착수:** 모든 마일스톤은 T0(착수 계획)으로 시작한다. T0의 게이트에서 사람이 task 분해를 승인하면 `Next: <M>-T1`, 마일스톤은 `active`.
- **종료:** 마지막 task의 게이트 요청에 마일스톤 보고(`results/<M>/report.md`)와 Go/No-go 근거를 포함한다. 사람의 `gate` 커밋에 `Milestone-Verdict:`를 넣고 tag `milestone/<M>-<go|nogo|conditional>`을 만든다(`lg commit`은 자동). 다음 마일스톤 T0의 승인도 같은 커밋 `Next:`로 한다.
- 마일스톤 종료 게이트에서는 해당 결과를 `paper/` 초안에 반영하는 것을 마일스톤 보고의 일부로 한다.

## 9. 계획·사양 변경

- 에이전트는 변경안을 `notes/` 또는 해당 문서의 제안 섹션에 쓰고 `propose` 커밋한다.
- 사람이 `plan`(로드맵·마일스톤) 또는 `spec`(사양·AGENTS 등) 커밋으로 확정한다.

## 10. 규칙 위반과 실수

- 잘못된 커밋은 사람이 `git revert`로 되돌린다. 이력은 재작성하지 않는다.
- `--no-verify`는 사람만, 긴급할 때만 쓰고 이유를 다음 커밋 본문에 남긴다.
~~~~

## B.4 `specs/git-commit.md` (S)

~~~~markdown
---
id: git-commit
type: spec
spec_version: 3
status: complete
---
# 커밋 규약

이 규약은 `.lg/hooks/commit-msg`가 검사한다.

## 1. 신원

| 주체 | 커밋 방법 | 작성자 |
|---|---|---|
| 사람 | 터미널에서 `lg commit`, 또는 `git commit` (저장소 로컬 설정) | `.lg/identities.json`의 `humans` 중 하나 |
| 에이전트 | `scripts/agent-commit` | `.lg/identities.json`의 `agent` |

작성자 이메일이 둘 중 어디에도 없으면 커밋이 거부된다.

에이전트가 사람 커밋을 준비할 때는 `lg draft`로 stage와 초안(`.lg/pending/COMMIT_MSG`)까지만 하고, 확정은 사람이 `lg commit`으로 한다 ([procedures/commit-prep.md](procedures/commit-prep.md)).

## 2. 메시지 형식

```
<type>(<scope>): <요약>

<본문 (선택)>

Actor: human | agent
<기타 trailer>
```

- 헤더는 72자 이하. 요약은 무엇을 했는지 한 문장.
- 본문은 왜 했는지, 무엇이 달라졌는지.
- 마지막 문단은 trailer 블록(`Key: value` 줄만). **trailer는 이 한 문단에 모두 쓴다.** `Co-Authored-By` 같은 다른 trailer를 넣으려면 같은 문단에 넣는다. trailer 뒤에 빈 줄을 두고 다른 문단을 붙이면 hook이 trailer를 찾지 못한다.
- scope: task 관련 타입은 Task ID와 같아야 한다. 그 밖에는 선택(결정 ID, 마일스톤 ID 등).

## 3. 타입

| 분류 | 타입 | 용도 |
|---|---|---|
| 사람 전용 | `gate` | task 게이트 판정 |
| | `decide` | 결정 확정 |
| | `plan` | 로드맵·마일스톤 변경, 첫 task 승인 |
| | `spec` | 사양·규칙 문서 변경 확정 |
| | `respond` | 에스컬레이션 응답 |
| 에이전트 전용 | `task` | task 상태 전이, 카드 갱신 |
| | `propose` | 결정·계획·사양 변경 제안 |
| | `review` | 게이트 요청, 에스컬레이션 제출 |
| 공통 | `exp` | 실험 코드 |
| | `run` | 실행 기록 |
| | `result` | 결과 문서, 그림, 표 |
| | `ref` | 참고문헌 추가, 매핑 문서 |
| | `log` | 작업 일지, STATUS, 사람 커밋 반영 |
| | `init` | 초기화 |
| | `chore` | 위에 속하지 않는 잡무 |

사람 전용 타입은 판정·확정을, 에이전트 전용 타입은 에이전트가 사람에게 요청하는 흐름을 나타낸다. 공통 타입은 작업 내용을 나타내며, 누가 했는지는 작성자 신원과 `Actor`로 구분한다.

## 4. Trailer

| Key | 필수 | 값 |
|---|---|---|
| `Actor` | 항상 | `human` \| `agent` (타입 분류·작성자와 일치) |
| `Task` | `gate`, `respond`, `task`, `run`, `result`, `review` | `M<n>-T<n>` |
| `Verdict` | `gate` | `approve` \| `revise` \| `redirect` |
| `Source` | `gate`, `decide`, `respond` | `document` \| `conversation` |
| `Decisions` | `decide` (그 외 선택) | `D<n>.<n>` 쉼표 목록 |
| `Next` | 선택 (`gate`) | `M<n>-T<n>` 또는 `none` |
| `Milestone-Verdict` | 선택 (`gate`) | `go` \| `nogo` \| `conditional` |
| `Approve` | 선택 (`plan`) | `M<n>-T<n>` 쉼표 목록 |
| `Applies` | 선택 (반영 커밋) | 이 커밋이 상태 필드에 반영한 사람 커밋의 해시(7–40자) 쉼표 목록. `scripts/apply-human-commits`가 쓴다 |
| `Refs` | 선택 | 관련 ID 목록 |
| `Review` | 선택 | review 문서 ID |

## 5. 예시

에이전트 착수:

```
task(M1-T2): start signal validation

Actor: agent
Task: M1-T2
```

에이전트 게이트 요청:

```
review(M1-T2): request gate

완료 기준 5개 중 5개 충족. D1.3 확정 필요.

Actor: agent
Task: M1-T2
Review: M1-T2_gate-01
Decisions: D1.3
```

사람 게이트 판정:

```
gate(M1-T2): approve, next M1-T3

신호 검증 결과 수용. PR 기준 채택.

Actor: human
Task: M1-T2
Verdict: approve
Source: conversation
Next: M1-T3
Decisions: D1.3
```

사람 결정 확정:

```
decide(D1.3): confirm participation ratio as primary signal

Actor: human
Decisions: D1.3
Source: document
```

사람이 직접 고친 실험 코드:

```
exp(M1-T2): fix off-by-one in window mask

Actor: human
Task: M1-T2
```

사람 커밋의 반영 (에이전트):

```
log(M0-T0): apply plan 70ea21b

Actor: agent
Applies: 70ea21b
```

첫 task 승인:

```
plan(M0-T0): approve initial task

Actor: human
Approve: M0-T0
```

## 6. Tag

| 시점 | tag | 만드는 사람 |
|---|---|---|
| task 게이트 `approve` | `gate/<Task>` | 사람 (`lg commit`이 자동) |
| 마일스톤 판정 | `milestone/<M>-<go\|nogo\|conditional>` | 사람 (`lg commit`이 자동) |

tag는 해당 `gate` 커밋에 붙인다.

## 7. 금지

- 에이전트: `git commit`·`lg commit` 실행, `--no-verify`, `--author`, `-a`, 사람 전용 타입, tag, 이력 재작성, 브랜치 병합과 cherry-pick (워크트리는 실험 격리용, AGENTS.md). 일괄 stage(`git add -A`, `git add .`, `git add -u`)와 사람의 미커밋 변경을 커밋에 넣는 것 ([workflow.md](workflow.md) §4.1).
- 사람: 이력 재작성 (실수는 `git revert`).
- `--no-verify`는 사람이 긴급할 때만 쓰고, 다음 커밋 본문에 이유를 남긴다.
~~~~

## B.5 `specs/doc-types/task-card.spec.md` (S)

~~~~markdown
---
id: task-card
type: spec
spec_version: 3
status: complete
---
# Task 카드 사양

## 1. 목적

하나의 task(승인 게이트 사이의 작업 단위)의 범위, 입력, 산출물, 완료 기준, 상태를 한 곳에 정의한다. 사람은 이 카드를 보고 착수를 승인하고, 게이트에서 완료 기준 충족 여부를 판정한다.

## 2. 위치와 파일명

`plan/milestones/<M>/tasks/<Task>.md` (예: `plan/milestones/M1/tasks/M1-T2.md`)

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | Task ID |
| `type` | ✓ | `task-card` |
| `spec_version` | ✓ | `3` |
| `title` | ✓ | 큰따옴표 문자열, 40자 이내 |
| `milestone` | ✓ | 마일스톤 ID |
| `status` | ✓ | conventions §5의 task 상태값 |
| `depends_on` | ✓ | 선행 Task ID 목록 (`[]` 가능) |
| `decisions` | ✓ | 관련 결정 ID 목록 |
| `references` | ✓ | 관련 참고문헌 ID 목록 |
| `budget.gpu_hours` | ✓ | 숫자 (0 가능) |
| `budget.wall_days` | ✓ | 숫자 또는 `null` |
| `created`, `updated` | ✓ | 날짜 |

## 4. 본문 구조

순서대로, 제목은 그대로 쓴다.

| 섹션 | 내용 |
|---|---|
| `# <Task>. <title>` | |
| `## 목표` | 이 task가 끝나면 무엇을 알게 되거나 갖게 되는가. 1–3문장 |
| `## 범위` | `### 포함`, `### 제외` 하위 섹션. 경계를 명확히 |
| `## 입력` | 시작에 필요한 문서·코드·데이터·결정 |
| `## 산출물` | 만들 파일 목록 (경로 포함) |
| `## 완료 기준` | `- [ ]` 체크리스트. 각 항목은 제3자가 참/거짓을 판단할 수 있어야 한다 |
| `## 자원 예산` | GPU 시간, 기간, 기타 제약 |
| `## 위험과 가정` | 실패 가능성과 그때의 대응 |
| `## 진행 메모` | 에이전트가 세션마다 추가 (날짜, 요약, 일지 ID) |
| `## 게이트 이력` | 판정마다 한 줄: 날짜, review ID, verdict, 커밋 해시 |

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| `draft` 상태의 카드 전체 | 작성·수정 | 수정 |
| `approved` 이후의 목표·범위·산출물·완료 기준·예산 | 수정 금지 (변경은 에스컬레이션) | 수정 (`plan` 커밋) |
| `status` | workflow §3의 에이전트 전이, 사람 커밋 반영 | 모든 전이 |
| 진행 메모, 게이트 이력, `updated` | 작성 | 작성 |

## 6. 생성·갱신 시점

- 생성: 마일스톤 T0에서 에이전트가 `draft`로 (T0 카드 자체는 초기화 시 생성).
- 갱신: 상태 전이마다, 세션 종료마다(진행 메모), 게이트 판정 반영 시(게이트 이력).

## 7. 검증 규칙

- frontmatter 필수 필드가 모두 있고 값이 허용 범위 안이다.
- `id`가 파일명과 같고, `milestone`이 폴더의 마일스톤과 같다.
- 본문 섹션이 §4의 순서대로 모두 있다.
- `## 완료 기준`에 체크리스트 항목이 1개 이상 있다.
- `depends_on`, `decisions`, `references`의 ID가 실제로 존재한다.
- `status`가 `closed`이면 게이트 이력에 `approve` 줄이 있다.
~~~~

## B.6 `specs/doc-types/review.spec.md` (S)

~~~~markdown
---
id: review
type: spec
spec_version: 3
status: complete
---
# Review 문서 사양 (게이트 요청 · 에스컬레이션)

## 1. 목적

에이전트가 사람의 판단을 요청하고, 사람이 응답을 남기는 비동기 창구다. `kind`로 두 종류를 구분한다.

- `gate`: task 완료 후 판정 요청
- `escalation`: task 진행 중 막혔을 때 판단 요청

## 2. 위치와 파일명

- 대기 중: `reviews/open/<Task>_gate-<NN>.md`, `reviews/open/<Task>_esc-<NN>.md`
- 처리 후: `reviews/closed/` 로 이동 (파일명 유지)

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | 파일명에서 `.md`를 뺀 것 |
| `type` | ✓ | `review` |
| `spec_version` | ✓ | `3` |
| `kind` | ✓ | `gate` \| `escalation` |
| `task` | ✓ | Task ID |
| `status` | ✓ | `open` \| `answered` \| `closed` |
| `requested` | ✓ | 요청일 |
| `answered` | ✓ | 응답일 또는 `null` |
| `verdict` | ✓ | `gate`: `approve` \| `revise` \| `redirect` \| `null`. `escalation`: 항상 `null` |
| `source` | ✓ | `document` \| `conversation` \| `null` |
| `decisions` | ✓ | 이 요청에서 확정이 필요한 결정 ID 목록 |
| `proposed_next` | gate만 | 제안하는 다음 Task ID 또는 `null` |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

### 4.1 `kind: gate`

| 섹션 | 작성자 | 내용 |
|---|---|---|
| `# <id>` | 에이전트 | |
| `## 요약` | 에이전트 | 무엇을 했고 무엇을 알게 되었는지 3–5문장 |
| `## 완료 기준 점검` | 에이전트 | 표: 기준 / 충족 여부(✓, ✗, 부분) / 근거(경로·실행 ID) |
| `## 예상과 달랐던 점` | 에이전트 | 없으면 "없음" |
| `## 확정이 필요한 결정` | 에이전트 | 결정 ID별 추천안과 근거 |
| `## 다음 task 제안` | 에이전트 | 계획대로인지, 수정안이 있는지, 다음 task의 자원 요청 |
| `## 응답` | 사람 | 아래 하위 섹션 |

### 4.2 `kind: escalation`

| 섹션 | 작성자 | 내용 |
|---|---|---|
| `# <id>` | 에이전트 | |
| `## 상황` | 에이전트 | 무엇이 막혔는지, 어떤 규칙(workflow §7.1)에 해당하는지 |
| `## 선택지` | 에이전트 | 선택지별 내용과 영향(시간, 자원, 결과 해석) |
| `## 추천` | 에이전트 | 추천안과 이유 |
| `## 응답` | 사람 | 아래 하위 섹션 |

### 4.3 `## 응답` (공통)

```
## 응답

### 판정
<gate: approve | revise | redirect. escalation: 선택한 선택지>

### 코멘트
<자유>

### 확정 결정
<결정 ID와 확정 내용, 없으면 "없음">

### 다음 task 승인
<gate만: 승인하는 Task ID 또는 "없음">
```

응답 섹션은 요청 시 하위 제목만 두고 비워 둔다.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| `## 응답` 위의 모든 섹션 | 작성 (제출 후 수정 금지) | 읽기 |
| `## 응답` | 대화 경로에서 사람 발언 그대로 기록만 (procedures/gate-conversation.md) | 작성 |
| `verdict`, `source`, `answered`, `status: answered` | 대화 경로에서만 기록 | 작성 |
| `status: closed`, 폴더 이동 | 사람 커밋 이후 수행 | 가능 |

## 6. 생성·갱신 시점

- 생성: 게이트 요청(procedures/task-gate.md), 에스컬레이션(procedures/escalate.md).
- 응답: 사람의 `gate` / `respond` 커밋과 같은 커밋.
- 종료: 다음 세션에서 에이전트가 `closed/`로 이동(procedures/gate-apply.md).

## 7. 검증 규칙

- `id`가 파일명과 같고, 파일명의 Task·종류가 `task`, `kind`와 일치한다.
- `open/`에 있으면 `status`가 `open` 또는 `answered`, `closed/`에 있으면 `closed`.
- `status`가 `answered` 이상이면 `answered`, `source`가 채워져 있고, `gate`는 `verdict`도 채워져 있다.
- `closed`인 gate review에 대응하는 사람의 `gate` 커밋이 존재한다 (`Review:` trailer 또는 `Task:`와 날짜로 대응).
- `## 완료 기준 점검` 표의 항목 수가 task 카드의 완료 기준 수와 같다.
~~~~

## B.7 Stub 사양 (J, 11개)

템플릿 하나(`specs/doc-types/_stub.spec.md.j2`)를 아래 표의 행마다 렌더링해 `specs/doc-types/<name>.spec.md`로 쓴다. 표는 `stubs.py`에 상수로 둔다.

| name | title | purpose | location |
|---|---|---|---|
| `roadmap` | 로드맵 | 연구 질문, 가설, 마일스톤 목록, 공통 실험 원칙을 정의한다 | `plan/roadmap.md` |
| `milestone` | 마일스톤 | 마일스톤의 목표, task 목록, Go/No-go 기준을 정의한다 | `plan/milestones/<M>/milestone.md` |
| `task-map` | Task–문헌 매핑 | 마일스톤의 각 task에 필요한 참고문헌과 읽을 부분을 연결한다 | `references/<M>/task-map.md` |
| `catalog` | 참고문헌 목록 | 참고문헌마다 ID, 서지 정보, 원본 파일, 요약을 한 행으로 기록한다 | `references/catalog.md` |
| `decision` | 결정 | 하나의 설계·실험 결정의 선택지, 근거, 상태를 기록한다 | `decisions/<D-ID>_<slug>.md` |
| `experiment-readme` | 실험 설명 | task별 실험 폴더의 목적, 실행 방법, 연결된 task·결정을 설명한다 | `experiments/<M>/<Task>_<slug>/README.md` |
| `run-record` | 실행 기록 | 실행 한 번의 설정, 시드, 커밋, 환경, 지표 요약을 기록한다 | `experiments/<M>/<Task>_<slug>/runs/<Run-ID>.yaml` |
| `task-result` | Task 결과 | task의 결과와 해석을 정리해 게이트 판정의 근거로 삼는다 | `results/<M>/<Task>_result.md` |
| `milestone-report` | 마일스톤 보고 | 마일스톤 전체 결과를 종합하고 Go/No-go 판단 근거를 제시한다 | `results/<M>/report.md` |
| `worklog` | 작업 일지 | 에이전트 세션마다 한 일과 판단 이유를 기록한다 | `logs/YYYY-MM-DD_sNN.md` |
| `status` | 상태판 | 현재 위치, 사람 판단 대기, 진행·막힘·최근 게이트를 보여준다 | `STATUS.md` |

템플릿 원문:

~~~~markdown
---
id: {{ stub.name }}
type: spec
spec_version: {{ spec_version }}
status: stub
---
# {{ stub.title }} 사양 (stub)

> 이 사양은 아직 공통 구조만 있다. 이 유형의 문서를 쓸 때는 [conventions.md](../conventions.md)를 지키고, 초기화 때 생성된 같은 유형의 문서가 있으면 그 구조를 따른다. 보완은 M0 진행 중에 하고, 확정은 사람의 `spec` 커밋으로 한다.

## 1. 목적

{{ stub.purpose }}

## 2. 위치와 파일명

`{{ stub.location }}`

## 3. Frontmatter

> TODO

## 4. 본문 구조

> TODO

## 5. 작성·수정 권한

> TODO

## 6. 생성·갱신 시점

> TODO

## 7. 검증 규칙

> TODO
~~~~

## B.8 `specs/templates/task-card.md` (S)

~~~~markdown
---
id: <M>-T<n>
type: task-card
spec_version: 3
title: "<40자 이내 제목>"
milestone: <M>
status: draft
depends_on: []
decisions: []
references: []
budget:
  gpu_hours: 0
  wall_days: null
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
# <M>-T<n>. <제목>

## 목표

<이 task가 끝나면 무엇을 알게 되거나 갖게 되는가>

## 범위

### 포함

- <…>

### 제외

- <…>

## 입력

- <…>

## 산출물

- <경로>

## 완료 기준

- [ ] <제3자가 참/거짓을 판단할 수 있는 기준>

## 자원 예산

- GPU: <n>시간
- 기간: <n>일

## 위험과 가정

- <…>

## 진행 메모

## 게이트 이력
~~~~

## B.9 `specs/templates/review.md` (S)

~~~~markdown
---
id: <Task>_<gate|esc>-<NN>
type: review
spec_version: 3
kind: <gate|escalation>
task: <Task>
status: open
requested: <YYYY-MM-DD>
answered: null
verdict: null
source: null
decisions: []
proposed_next: null
updated: <YYYY-MM-DD>
---
# <Task>_<gate|esc>-<NN>

<!-- kind: gate 인 경우 아래 다섯 섹션 -->

## 요약

## 완료 기준 점검

| 기준 | 충족 | 근거 |
|---|---|---|

## 예상과 달랐던 점

## 확정이 필요한 결정

## 다음 task 제안

<!-- kind: escalation 인 경우 위 다섯 섹션 대신 아래 세 섹션 -->

## 상황

## 선택지

## 추천

<!-- 공통: 사람이 작성 -->

## 응답

### 판정

### 코멘트

### 확정 결정

### 다음 task 승인
~~~~

## B.10 `specs/procedures/*.md` (S)

절차 문서 8종. 형식과 목록은 §16.3. 일반 규칙(G1–G10)과 불변 원칙(P1–P6)의 번호는 A.3 `AGENTS.md`의 것이다.

`session-start.md`

~~~~markdown
---
id: session-start
type: procedure
spec_version: 3
---
# 세션 시작

- 시작 조건: 세션을 시작할 때 (Claude Code: `/session-start`).
- 끝나는 상태: 이번 세션에 할 일이 정해지고 사람에게 보고되었다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. `scripts/session-check`의 출력을 확인한다. Claude Code에서는 세션 시작 hook이 이미 실행해 출력이 맥락에 있다. 다른 도구에서는 직접 실행한다.
2. "사람 커밋 대기 상태"가 있으면: 사람에게 터미널에서 `lg commit` 실행을 요청하고, 아래 읽기 단계(5, 6, 8–10)만 한 뒤 보고하고 멈춘다.
3. "커밋되지 않은 사람의 변경"이 있으면: 절차 [commit-prep](commit-prep.md)의 1단계(선택지 제시)를 한다. 사람이 답할 때까지는 아래 읽기 단계(5, 6, 8–10)만 한다.
4. "반영되지 않은 사람 커밋"이 있으면: 절차 [gate-apply](gate-apply.md)를 먼저 한다. 카드 상태는 반영한 뒤에 판단한다.
5. `STATUS.md`를 읽는다.
6. 현재 task 카드(`plan/milestones/<M>/tasks/<Task>.md`)를 읽는다.
7. 카드 상태가 `approved`, `in-progress`, `revise` 중 하나가 아니면 작업하지 않고 STATUS에 이유를 적은 뒤 절차 [session-close](session-close.md)로 간다.
8. 카드에 연결된 결정(`decisions/`)과 `references/<M>/task-map.md`를 읽는다.
9. `logs/`의 최근 일지 1–2개를 읽는다.
10. 이번 세션에 쓸 문서 유형의 사양(`specs/doc-types/`)을 읽는다.
11. 3–5줄로 보고한다: 사람 커밋 대기 상태나 사람의 변경(있으면 먼저), 반영한 사람 커밋, 현재 task와 상태, 이번 세션에 할 일.
~~~~

`session-close.md`

~~~~markdown
---
id: session-close
type: procedure
spec_version: 3
---
# 세션 종료

- 시작 조건: 세션을 마칠 때 (Claude Code: `/session-close`).
- 끝나는 상태: 작업 트리에 남은 것은 사람의 변경과 사람 커밋 대기 상태의 stage된 변경뿐이다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. 사람 커밋 대기 상태(`.lg/pending/COMMIT_MSG` 있음)이면 2–5단계를 하지 않는다. 파일을 바꾸면 커밋할 수 없어 다음 세션에 사람의 변경으로 보이기 때문이다. 사람에게 터미널에서 `lg commit` 실행을 다시 요청하고, 일지에 쓸 내용은 보고로 대신한 뒤 7단계로 간다.
2. 작업 일지 `logs/YYYY-MM-DD_sNN.md`를 쓴다.
3. task 카드의 "진행 메모"와 `updated`를 갱신한다.
4. `STATUS.md`를 갱신한다.
5. 이번 세션에서 바꾼 파일만 경로를 지정해 stage하고 `log` 타입으로 커밋한다.
6. 사람의 변경이 남아 있으면 그대로 두고, 남은 파일 목록을 보고에 넣는다.
7. `git status`로 끝나는 상태를 확인한다.
8. 이번 세션 요약을 3줄로 보고한다.
~~~~

`commit-prep.md`

~~~~markdown
---
id: commit-prep
type: procedure
spec_version: 3
---
# 사람 커밋 준비

- 시작 조건: `scripts/session-check`가 커밋되지 않은 사람의 변경을 알렸을 때, 사람이 세션 도중 직접 고친 파일을 알렸을 때, 사람이 자기 변경의 커밋 준비를 요청했을 때 (Claude Code: `/commit-prep`).
- 끝나는 상태: 사람의 변경이 사람 신원으로 커밋되었거나, 사람 커밋 대기 상태이거나, 사람이 직접 정리하기로 했다.

## 특별 규칙

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|
| G2 (사람의 변경을 stage하지 않는다) | 사람의 변경을 stage할 수 있다. 단, `lg draft`를 통해서만 하고 3단계에서만 한다 |

## 단계

1. 사람의 변경 목록(`.lg/pending/HUMAN_FILES`, 또는 사람이 알려 준 경로)을 보여 주고 고르게 한다. 사람이 답할 때까지 파일을 바꾸지 않는다.
   1. 직접 커밋: 사람이 터미널에서 `lg commit`을 실행한다.
   2. 초안 준비: 에이전트가 초안을 만들고(3단계), 사람이 `lg commit`으로 확인·확정한다.
   3. 직접 정리: 사람이 이어서 고치거나 버린 뒤 알려 준다.
2. 1이나 3을 고르면, 사람이 끝났다고 알려 줄 때 `scripts/session-check`를 다시 실행한다. 변경이 남아 있으면 1단계로 돌아간다.
3. 2를 고르면:
   1. 이번 세션에 자기가 바꾼 파일이 있으면 먼저 `scripts/agent-commit`으로 커밋한다(경로 지정).
   2. 사람의 변경을 `git diff`로 읽고 타입과 요약을 정한다. 타입은 사람이 쓸 수 있는 것 중 내용에 맞는 것이다: 사양·규칙 문서는 `spec`, 로드맵·마일스톤은 `plan`, 실험 코드는 `exp`, 결과 문서는 `result`, 참고문헌은 `ref`, 그 밖은 `chore`.
   3. 초안을 만든다: `lg draft --type <타입> --summary "<요약>" [--body "<무엇을 왜>"] [--trailer Task=<Task>]`. 감지된 변경이면 경로를 생략한다(`HUMAN_FILES`의 경로만 stage된다). 사람이 알려 준 변경이면 그 경로를 붙인다.
   4. 사람에게 `git diff --cached` 확인과 터미널에서 `lg commit` 실행을 요청하고 멈춘다. 이제 사람 커밋 대기 상태다.
4. 사람이 커밋했다고 알리면 `git log -1 --format='%an <%ae>%n%s'`로 사람 신원의 커밋인지 확인하고 원래 작업으로 돌아간다.

## 멈추는 경우

- 한 파일에 사람의 변경과 자기 변경이 섞였을 때: 그 파일을 어느 쪽으로도 커밋하지 않고 사람에게 알린 뒤 지시를 기다린다.
- `lg`가 설치되어 있지 않을 때: 1단계에서 1(사람이 `git commit`으로 직접 커밋) 또는 3만 제시한다.
~~~~

`task-start.md`

~~~~markdown
---
id: task-start
type: procedure
spec_version: 3
---
# Task 착수

- 시작 조건: 승인된 task를 착수할 때 (Claude Code: `/task-start <Task>`).
- 끝나는 상태: 카드가 `in-progress`이고 `task(<Task>): start` 커밋이 있다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. 카드 상태가 `approved` 또는 `revise`인지 확인한다. `draft`이고 `scripts/apply-human-commits --check`에 이 task의 승인이 있으면 절차 [gate-apply](gate-apply.md)를 먼저 한다. 그 밖에는 중단하고 이유를 보고한다.
2. `revise`에서 시작하면 해당 gate review의 `## 응답`을 먼저 읽고 반영 계획을 세운다.
3. 카드 `status`를 `in-progress`로 바꾸고 `updated`를 갱신한다.
4. `STATUS.md`를 갱신한다.
5. `scripts/agent-commit`으로 `task(<Task>): start` 커밋을 만든다 (`Actor: agent`, `Task: <Task>`).
6. 카드의 완료 기준을 기준으로 이번 세션 작업 계획을 보고한다.
~~~~

`task-gate.md`

~~~~markdown
---
id: task-gate
type: procedure
spec_version: 3
---
# 게이트 요청

- 시작 조건: task의 완료 기준을 모두 충족했다고 판단할 때 (Claude Code: `/task-gate <Task>`).
- 끝나는 상태: 카드가 `in-review`이고 게이트 요청 문서와 `review` 커밋이 있다. 이 task에서는 더 작업하지 않는다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. 완료 기준을 하나씩 점검한다. 충족하지 못한 기준이 있으면 게이트 대신 계속 작업할지 사람에게 묻는다.
2. task 결과 문서 `results/<M>/<Task>_result.md`를 쓴다. 마일스톤의 마지막 task면 마일스톤 보고 `results/<M>/report.md`와 Go/No-go 근거도 쓴다 ([workflow.md](../workflow.md) §8).
3. `specs/templates/review.md`로 `reviews/open/<Task>_gate-NN.md`를 쓴다 (`kind: gate`, [review.spec.md](../doc-types/review.spec.md)).
4. 카드를 `in-review`로 바꾸고, `STATUS.md`의 "사람 판단 대기"에 항목을 추가한다.
5. `review(<Task>): request gate` 커밋 (`Actor: agent`, `Task: <Task>`, `Review: <review id>`).
6. 사람에게 무엇을 판정해야 하는지 요약해 보고하고 멈춘다.
~~~~

`escalate.md`

~~~~markdown
---
id: escalate
type: procedure
spec_version: 3
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
~~~~

`gate-conversation.md`

~~~~markdown
---
id: gate-conversation
type: procedure
spec_version: 3
---
# 대화 경로 판정

- 시작 조건: 사람이 게이트 판정, 결정 확정, 에스컬레이션 응답을 대화로 전했을 때.
- 끝나는 상태: 사람 커밋 대기 상태 (review 문서가 stage되고 초안이 있다).

## 특별 규칙

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|
| G5 (review의 `## 응답`을 쓰지 않는다) | 사람의 발언을 그대로 `## 응답`에 옮기고 frontmatter `verdict`, `source: conversation`, `status: answered`, `answered`를 채운다. 사람이 말하지 않은 내용을 더하지 않는다 |

## 단계

1. 이번 세션에 자기가 바꾼 파일이 있으면 먼저 `scripts/agent-commit`으로 커밋한다(경로 지정).
2. review 문서의 `## 응답`을 쓴다(특별 규칙). 카드·결정·마일스톤의 상태는 바꾸지 않는다. 사람이 커밋한 뒤 절차 [gate-apply](gate-apply.md)가 반영한다.
3. review 문서 경로를 붙여 초안을 만든다. 사람이 말한 판정을 trailer로 옮긴다.
   - 게이트: `lg draft --type gate --summary "<verdict>, next <Next>" --trailer Task=<Task> --trailer Verdict=<verdict> --trailer Source=conversation [--trailer Next=<Task|none>] [--trailer Milestone-Verdict=<go|nogo|conditional>] [--trailer Decisions=<D-ID,…>] <review 경로>`
   - 결정 확정: `lg draft --type decide --summary "<요약>" --trailer Decisions=<D-ID,…> --trailer Source=conversation <review 경로 또는 결정 문서 경로>`
   - 에스컬레이션 응답: `lg draft --type respond --summary "<요약>" --trailer Task=<Task> --trailer Source=conversation <review 경로>`
4. 사람에게 `git diff --cached` 확인과 터미널에서 `lg commit` 실행을 요청하고 멈춘다. 내용이 다르면 사람이 `lg commit`의 편집 단계에서 고친다. 게이트 승인이면 `lg commit`이 tag를 만든다.
5. 사람이 커밋했다고 알리면 절차 [gate-apply](gate-apply.md).

## 멈추는 경우

- 판정이 모호하면(verdict, 다음 task, 확정할 결정이 분명하지 않으면) 초안을 만들기 전에 묻는다.
- `lg`가 설치되어 있지 않으면 3단계 대신 review 문서를 경로로 stage하고, 같은 내용의 메시지를 `.lg/pending/COMMIT_MSG`에 직접 쓴다(`Actor: human` 포함). 사람에게 `git commit -F .lg/pending/COMMIT_MSG && rm .lg/pending/COMMIT_MSG` 실행과, 승인이면 `git tag gate/<Task>`를 요청한다.
~~~~

`gate-apply.md`

~~~~markdown
---
id: gate-apply
type: procedure
spec_version: 3
---
# 사람 커밋의 반영

- 시작 조건: `scripts/session-check`가 반영되지 않은 사람 커밋을 알렸을 때, 사람이 판정·결정·응답·승인을 커밋했다고 알렸을 때.
- 끝나는 상태: 반영되지 않은 사람 커밋이 없고(`scripts/apply-human-commits --check`가 빈 결과), 반영 커밋들이 있다.

## 특별 규칙

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|
| G4 (사람 몫의 상태 전이를 하지 않는다) | 사람 커밋이 정한 상태 전이를 커밋한다. 전이는 `scripts/apply-human-commits`가 만든 것만 쓰고, 상태 필드를 직접 편집하지 않는다 |

## 단계

1. 사람 커밋 대기 상태가 아닌지 확인한다(대기 상태면 커밋할 수 없다, G3). 이번 세션에 자기가 바꾼 파일이 있으면 먼저 커밋한다.
2. `scripts/apply-human-commits`를 실행한다. 가장 오래된 반영되지 않은 사람 커밋 하나를 반영하고, 바뀐 파일과 커밋 명령을 출력한다.
3. "반영할 수 없음"(종료 코드 1)이면 아무것도 바뀌지 않았다. 출력된 이유를 사람에게 보고하고 멈춘다.
4. 바뀐 내용을 `git diff`로 확인하고, `STATUS.md`에 다음 할 일을 반영한다(아래 표).
5. 출력된 명령대로 커밋한다: `scripts/agent-commit -F .lg/pending/APPLY_MSG -- <출력된 경로…> STATUS.md`
6. `scripts/apply-human-commits --check`가 빈 결과를 낼 때까지 2–5를 반복한다.
7. 반영한 결과와 다음 할 일을 보고한다.

| 반영한 것 | 다음 할 일 |
|---|---|
| 승인 (`Approve`, `Next`) | 승인된 task 착수 (절차 [task-start](task-start.md)) |
| `approve` (`Next: none`) | 사람의 다음 지시를 기다린다 |
| `revise` | 같은 task 재개. review의 `## 응답`을 읽고 반영 계획을 세운다 |
| `redirect` | 사람의 `plan` 커밋을 기다린다 |
| `respond` | 막혔던 task로 돌아간다 |
| 결정 확정 | 그 결정에 의존하던 작업을 이어 간다 |
~~~~

---

# 부록 C. 실행 파일 원문

## C.1 `.lg/hooks/commit-msg` (S, 755)

~~~~python
#!/usr/bin/env python3
"""labgate commit-msg hook (spec_version 3).

specs/git-commit.md 규약을 검사한다. 표준 라이브러리만 사용한다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HUMAN_TYPES = {"gate", "decide", "plan", "spec", "respond"}
AGENT_TYPES = {"task", "propose", "review"}
COMMON_TYPES = {"exp", "run", "result", "ref", "log", "init", "chore"}
ALL_TYPES = HUMAN_TYPES | AGENT_TYPES | COMMON_TYPES

TASK_REQUIRED = {"gate", "respond", "task", "run", "result", "review"}
SOURCE_REQUIRED = {"gate", "decide", "respond"}
PASSTHROUGH_PREFIXES = ("Revert ", "fixup! ", "squash! ", "amend! ")
MERGE_PREFIX = "Merge "

HEADER_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^()\s]+)\))?: (?P<summary>\S.*)$")
TRAILER_RE = re.compile(r"^(?P<key>[A-Z][A-Za-z-]*): (?P<value>\S.*)$")
TASK_ID_RE = re.compile(r"^M\d+-T\d+$")
DECISION_ID_RE = re.compile(r"^D\d+\.\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")
MAX_HEADER = 72
SCISSORS = "# ------------------------ >8 ------------------------"


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def split_list(value):
    return [v.strip() for v in value.split(",") if v.strip()]


def load_identities():
    root = Path(git("rev-parse", "--show-toplevel"))
    path = root / ".lg" / "identities.json"
    return json.loads(path.read_text(encoding="utf-8"))


def author_email():
    match = re.search(r"<([^>]*)>", git("var", "GIT_AUTHOR_IDENT"))
    return match.group(1).strip().lower() if match else ""


def parse(text):
    """(header, trailers, errors)를 돌려준다. 메시지가 비면 header는 None."""
    raw = text.splitlines()
    if SCISSORS in raw:  # commit -v: 가위 줄 아래(diff)는 메시지가 아니다
        raw = raw[: raw.index(SCISSORS)]
    lines = [l.rstrip() for l in raw if not l.startswith("#")]
    while lines and not lines[-1]:
        lines.pop()
    if not lines:
        return None, {}, ["커밋 메시지가 비어 있습니다."]

    header, body = lines[0], lines[1:]
    errors = []
    if body and body[0]:
        errors.append("헤더 다음 줄은 비어 있어야 합니다.")

    block = []
    for line in reversed(body):
        if not line:
            break
        block.append(line)
    block.reverse()

    trailers = {}
    if block and all(TRAILER_RE.match(l) for l in block):
        for line in block:
            m = TRAILER_RE.match(line)
            key = m.group("key")
            if key in trailers:
                errors.append(f"trailer '{key}'가 중복되었습니다.")
            trailers[key] = m.group("value").strip()
    earlier = body[: len(body) - len(block)]
    if "Actor" not in trailers and any(l.startswith("Actor:") for l in earlier):
        errors.append(
            "trailer가 여러 문단으로 나뉘었습니다. Actor 등 trailer와 Co-Authored-By 같은 "
            "줄을 마지막 한 문단에 모아 쓰세요 (Claude Code는 .claude/settings.json의 attribution)."
        )
    return header, trailers, errors


def author_role():
    """작성자 역할: ("human" | "agent", None) 또는 (None, 오류 문구)."""
    try:
        ids = load_identities()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        return None, f".lg/identities.json을 읽지 못했습니다: {e}"
    email = author_email()
    humans = {h["email"].lower() for h in ids.get("humans", [])}
    agent = ids.get("agent", {}).get("email", "").lower()
    if email and email == agent:
        return "agent", None
    if email in humans:
        return "human", None
    return None, f"등록되지 않은 작성자입니다: <{email}> (.lg/identities.json 확인)"


def check_identity(actor, errors):
    role, error = author_role()
    if error:
        errors.append(error)
    elif role != actor:
        errors.append(f"작성자 신원({role})과 Actor({actor})가 다릅니다.")


def check_list(trailers, key, pattern, errors):
    if key not in trailers:
        return
    items = split_list(trailers[key])
    bad = [v for v in items if not pattern.match(v)]
    if not items or bad:
        errors.append(f"{key} 형식이 잘못되었습니다: {trailers[key]}")


def report(errors):
    if not errors:
        return 0
    print("✗ 커밋 메시지가 규약(specs/git-commit.md)에 맞지 않습니다:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    return 1


def check(text, check_author=True):
    """규약 위반 목록을 돌려준다 (없으면 빈 목록).

    check_author=False면 작성자 신원 검사를 건너뛴다. lg commit·lg draft가 커밋 전 사전 검사에 쓴다.
    """
    header, trailers, errors = parse(text)
    if header is None:
        return errors
    if header.startswith(MERGE_PREFIX):
        if check_author and author_role()[0] == "agent":
            return [
                "에이전트는 병합 커밋을 만들 수 없습니다. 워크트리는 실험 격리용이며 main에 병합하지 "
                "않습니다. 채택할 결과는 main에서 scripts/agent-commit 으로 다시 커밋하세요 (AGENTS.md)."
            ]
        return []
    if header.startswith(PASSTHROUGH_PREFIXES):
        return []

    m = HEADER_RE.match(header)
    if not m:
        errors.append("헤더 형식은 '<type>(<scope>): <요약>' 입니다.")
        return errors
    ctype, scope = m.group("type"), m.group("scope")

    if len(header) > MAX_HEADER:
        errors.append(f"헤더가 {MAX_HEADER}자를 넘습니다 ({len(header)}자).")
    if ctype not in ALL_TYPES:
        errors.append(f"알 수 없는 타입입니다: {ctype}")
        return errors

    actor = trailers.get("Actor")
    if actor not in ("human", "agent"):
        errors.append("Actor trailer가 필요합니다 (human | agent).")
    else:
        if ctype in HUMAN_TYPES and actor != "human":
            errors.append(f"'{ctype}'는 사람 전용 타입입니다.")
        if ctype in AGENT_TYPES and actor != "agent":
            errors.append(f"'{ctype}'는 에이전트 전용 타입입니다.")
        if check_author:
            check_identity(actor, errors)

    task = trailers.get("Task")
    if ctype in TASK_REQUIRED and not task:
        errors.append(f"'{ctype}' 커밋에는 Task trailer가 필요합니다.")
    if task:
        if not TASK_ID_RE.match(task):
            errors.append(f"Task 형식이 잘못되었습니다: {task}")
        elif ctype in TASK_REQUIRED and scope != task:
            errors.append(f"scope({scope})가 Task({task})와 같아야 합니다.")

    if ctype in SOURCE_REQUIRED and trailers.get("Source") not in ("document", "conversation"):
        errors.append(f"'{ctype}' 커밋에는 Source trailer가 필요합니다 (document | conversation).")

    if ctype == "gate":
        if trailers.get("Verdict") not in ("approve", "revise", "redirect"):
            errors.append("gate 커밋에는 Verdict trailer가 필요합니다 (approve | revise | redirect).")
        nxt = trailers.get("Next")
        if nxt and nxt != "none" and not TASK_ID_RE.match(nxt):
            errors.append(f"Next 형식이 잘못되었습니다: {nxt}")
        mv = trailers.get("Milestone-Verdict")
        if mv and mv not in ("go", "nogo", "conditional"):
            errors.append(f"Milestone-Verdict 값이 잘못되었습니다: {mv}")

    if ctype == "decide" and "Decisions" not in trailers:
        errors.append("decide 커밋에는 Decisions trailer가 필요합니다.")
    check_list(trailers, "Decisions", DECISION_ID_RE, errors)
    check_list(trailers, "Approve", TASK_ID_RE, errors)
    check_list(trailers, "Applies", HASH_RE, errors)
    return errors


def main():
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    return report(check(text))


if __name__ == "__main__":
    sys.exit(main())
~~~~

## C.2 `scripts/agent-commit` (S, 755)

~~~~bash
#!/usr/bin/env bash
# 에이전트 신원으로 커밋한다.
# 사용법: scripts/agent-commit -m "<헤더>" -m "<trailer 블록>"
#         scripts/agent-commit -F <메시지 파일>
# 나머지 인자는 git commit에 그대로 전달된다. --author, --no-verify, -a는 쓰지 않는다.
set -euo pipefail

reject() {
  echo "agent-commit: '$1' 옵션은 사용할 수 없습니다." >&2
  exit 2
}

value_next=0
for arg in "$@"; do
  if [ "$value_next" = 1 ]; then
    value_next=0
    continue
  fi
  case "$arg" in
    --) break ;;
    --no-verify|--author|--author=*|--all) reject "$arg" ;;
    --message|--file|--reuse-message|--reedit-message|--template|--fixup|--squash|--cleanup|--trailer|--date)
      value_next=1 ;;
    --*) ;;
    -?*)
      rest="${arg#-}"
      while [ -n "$rest" ]; do
        c="${rest:0:1}"
        rest="${rest:1}"
        case "$c" in
          a|n) reject "-$c" ;;
          m|F|C|c|t)
            [ -z "$rest" ] && value_next=1
            break ;;
        esac
      done
      ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
CFG="$ROOT/.lg/identities.json"

field() {
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["agent"][sys.argv[2]])' "$CFG" "$1"
}

NAME="$(field name)"
EMAIL="$(field email)"

export GIT_AUTHOR_NAME="$NAME" GIT_AUTHOR_EMAIL="$EMAIL"
export GIT_COMMITTER_NAME="$NAME" GIT_COMMITTER_EMAIL="$EMAIL"
exec git commit "$@"
~~~~

> 참고: `-n`은 `git commit`에서 `--no-verify`의 짧은 형식이라 함께 막는다. `-a`는 사람의 미커밋 변경까지 커밋하므로 막는다. 묶인 짧은 옵션(`-am "..."`)도 검사하며, 값을 받는 옵션(`-m`, `-F`, `-C`, `-c`, `-t`)의 값은 검사하지 않는다(메시지가 `-a`로 시작해도 통과). 메시지를 여러 `-m`으로 줄 때 마지막 `-m`이 trailer 블록이 되도록 한다(각 `-m`은 빈 줄로 구분된 문단이 된다).

## C.3 `scripts/session-check` (S, 755)

~~~~python
#!/usr/bin/env python3
"""labgate 세션 시작 점검 (spec_version 3).

1. 사람이 이미 커밋한 초안(.lg/pending/COMMIT_MSG)을 정리한다.
2. 사람 커밋 대기 상태를 알린다.
3. 커밋된 반영 기록(.lg/pending/APPLY_MSG)을 정리하고, 반영했지만 커밋하지 않은 것을 알린다.
4. 상태 필드에 반영되지 않은 사람 커밋을 알린다 (scripts/apply-human-commits --check).
5. 커밋되지 않은 변경을 사람의 변경으로 알리고 .lg/pending/HUMAN_FILES에 기록한다.
   반영 도구가 바꾼 경로(커밋 대기 중)는 사람의 변경에서 뺀다.
표준 라이브러리만 사용한다. 출력은 에이전트의 맥락에 들어간다. 종료 코드는 항상 0이다.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT / ".lg" / "pending"
APPLY = ROOT / "scripts" / "apply-human-commits"
MAX_LIST = 20
RECENT = 20


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def changed_paths():
    """커밋되지 않은 변경의 경로 (새 파일 포함, 이름 바꾸기는 이전 경로도)."""
    entries = git("status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
    paths = set()
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if not entry:
            continue
        status, path = entry[:2], entry[3:]
        paths.add(path)
        if "R" in status or "C" in status:  # 다음 항목이 원래 경로
            if "R" in status:
                paths.add(entries[i])
            i += 1
    return sorted(paths)


def normalize(message):
    return "\n".join(line.rstrip() for line in message.strip().splitlines())


def committed_draft():
    """초안과 같은 메시지의 최근 사람 커밋 해시 (없으면 None)."""
    try:
        ids = json.loads((ROOT / ".lg" / "identities.json").read_text(encoding="utf-8"))
        humans = {h["email"].lower() for h in ids.get("humans", [])}
        draft = normalize((PENDING / "COMMIT_MSG").read_text(encoding="utf-8"))
        out = git("log", f"-{RECENT}", "--format=%H%x00%ae%x00%B%x1e")
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
        return None
    for record in out.split("\x1e"):
        record = record.lstrip("\n")
        if not record:
            continue
        sha, email, body = record.split("\x00", 2)
        if email.strip().lower() in humans and normalize(body) == draft:
            return sha
    return None


def run_apply(flag):
    if not APPLY.is_file():
        return ""
    result = subprocess.run([sys.executable, str(APPLY), flag], cwd=ROOT, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else ""


def unreflected():
    return [line for line in run_apply("--check").splitlines() if line.strip()]


def last_apply():
    """apply-human-commits --tidy 결과: None 또는 {"state", "applies", "paths"}."""
    out = run_apply("--tidy").strip()
    try:
        return json.loads(out) if out else None
    except ValueError:
        return None


def main():
    try:
        paths = changed_paths()
    except (OSError, subprocess.CalledProcessError):
        return 0  # Git 저장소가 아니거나 git이 없다
    lines = []

    draft = PENDING / "COMMIT_MSG"
    if draft.exists():
        sha = committed_draft()
        if sha:
            draft.unlink()
            lines.append(f"[labgate] 사람이 이미 커밋한 초안을 정리했습니다 ({sha[:7]}).")
    if draft.exists():
        lines.append(
            "[labgate] 사람 커밋 대기 상태입니다 (.lg/pending/COMMIT_MSG). 커밋하지 말고 사람에게 "
            "터미널에서 lg commit 실행을 요청하세요 (specs/procedures/session-start.md 2단계)."
        )
        print("\n".join(lines))
        return 0

    apply = last_apply()
    applying = set()
    if apply and apply["state"] == "cleaned":
        lines.append(f"[labgate] 커밋된 반영 기록을 정리했습니다 ({apply['applies']}).")
    elif apply and apply["state"] == "pending":
        applying = set(apply["paths"])
        command = ("scripts/agent-commit -F .lg/pending/APPLY_MSG -- " + " ".join(apply["paths"])
                   if apply["paths"] else "scripts/agent-commit --allow-empty -F .lg/pending/APPLY_MSG")
        lines.append(
            f"[labgate] 사람 커밋({apply['applies']})을 반영했지만 아직 커밋하지 않았습니다. "
            "이 변경은 에이전트의 것이며, specs/procedures/gate-apply.md 5단계로 먼저 커밋하세요:"
        )
        lines.append(f"  {command}")

    pending = [] if apply and apply["state"] == "pending" else unreflected()
    if pending:
        lines.append(
            "[labgate] 상태 필드에 반영되지 않은 사람 커밋이 있습니다. 작업 전에 "
            "specs/procedures/gate-apply.md 를 따르세요."
        )
        lines += [f"  - {p}" for p in pending]

    paths = [p for p in paths if p not in applying]
    record = PENDING / "HUMAN_FILES"
    if paths:
        PENDING.mkdir(parents=True, exist_ok=True)
        record.write_text("".join(p + "\n" for p in paths), encoding="utf-8")
        lines.append(
            "[labgate] 커밋되지 않은 사람의 변경이 있습니다. 작업 전에 "
            "specs/procedures/commit-prep.md 를 따르세요."
        )
        lines += [f"  - {p}" for p in paths[:MAX_LIST]]
        if len(paths) > MAX_LIST:
            lines.append(f"  … 외 {len(paths) - MAX_LIST}개 (전체 목록: .lg/pending/HUMAN_FILES)")
    elif record.exists():
        record.unlink()

    if lines:
        print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
~~~~

## C.4 `scripts/apply-human-commits` (S, 755)

사양은 §21.

~~~~python
#!/usr/bin/env python3
"""labgate 사람 커밋 반영 도구 (spec_version 3).

사람 커밋의 trailer가 정한 상태 전이를 문서의 상태 필드에 반영한다. 커밋하지 않는다.
표준 라이브러리만 사용한다. 사양: labgate 설계 문서 §21.

사용법:
  scripts/apply-human-commits            가장 오래된 반영되지 않은 사람 커밋 하나를 반영
  scripts/apply-human-commits --check    바꾸지 않고 반영되지 않은 사람 커밋을 나열
  scripts/apply-human-commits --tidy     지난 반영의 커밋 여부를 JSON 한 줄로 알린다 (session-check가 쓴다)
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PENDING = ROOT / ".lg" / "pending"
APPLY_MSG = PENDING / "APPLY_MSG"
APPLY_PATHS = PENDING / "APPLY_PATHS"

HEADER_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^()\s]+)\))?: (?P<summary>\S.*)$")
TRAILER_RE = re.compile(r"^(?P<key>[A-Z][A-Za-z-]*): (?P<value>\S.*)$")
TASK_ID_RE = re.compile(r"^M(\d+)-T\d+$")
HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")

TASK_STATES = {"draft", "approved", "in-progress", "blocked", "in-review", "closed", "revise", "redirected"}
NOT_DRAFT = TASK_STATES - {"draft"}
NOT_BLOCKED = TASK_STATES - {"blocked"}
VERDICT = {  # Verdict → (목표 상태, 이미 만족)
    "approve": ("closed", {"closed"}),
    "revise": ("revise", {"revise", "in-progress", "blocked"}),
    "redirect": ("redirected", {"redirected"}),
}


class CannotApply(Exception):
    """반영할 수 없음 (종료 코드 1). 아무것도 바꾸지 않는다."""


class UsageError(Exception):
    """환경 오류 (종료 코드 2)."""


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        raise UsageError(f"git {' '.join(args)} 실패: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def parse(message):
    """(타입, scope, 헤더, trailer dict)."""
    lines = [l.rstrip() for l in message.strip().splitlines()]
    header = lines[0] if lines else ""
    block = []
    for line in reversed(lines[1:]):
        if not line:
            break
        block.append(line)
    trailers = {}
    if block and all(TRAILER_RE.match(l) for l in block):
        for line in block:
            m = TRAILER_RE.match(line)
            trailers[m.group("key")] = m.group("value").strip()
    m = HEADER_RE.match(header)
    return (m.group("type") if m else None), (m.group("scope") if m else None), header, trailers


def split_list(value):
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def human_emails():
    try:
        data = json.loads((ROOT / ".lg" / "identities.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise UsageError(f".lg/identities.json을 읽지 못했습니다: {e}")
    return {h["email"].lower() for h in data.get("humans", [])}


def commits():
    """오래된 순서의 (해시, 작성자 이메일, 메시지)."""
    out = git("log", "--reverse", "--format=%H%x00%ae%x00%B%x1e")
    result = []
    for record in out.split("\x1e"):
        record = record.lstrip("\n")
        if record:
            sha, email, body = record.split("\x00", 2)
            result.append((sha, email.strip().lower(), body))
    return result


def is_target(ctype, trailers):
    return ctype in ("gate", "respond", "decide") or (ctype == "plan" and "Approve" in trailers)


def applied_hashes(history):
    """모든 커밋의 Applies trailer에 적힌 해시."""
    applied = set()
    for _, _, body in history:
        applied.update(h.lower() for h in split_list(parse(body)[3].get("Applies")) if HASH_RE.match(h.lower()))
    return applied


def unreflected():
    """반영되지 않은 사람 커밋: [(해시, 타입, scope, 헤더, trailer)] (오래된 순)."""
    humans = human_emails()
    history = commits()
    applied = applied_hashes(history)
    pending = []
    for sha, email, body in history:
        ctype, scope, header, trailers = parse(body)
        if email in humans and is_target(ctype, trailers) and not any(sha.startswith(p) for p in applied):
            pending.append((sha, ctype, scope, header, trailers))
    return pending


# ---------------------------------------------------------------- 문서 편집 계획


class Plan:
    """바꾸기 전에 모든 변경을 계산한다. 하나라도 반영할 수 없으면 아무것도 쓰지 않는다."""

    def __init__(self, today):
        self.today = today
        self.texts = {}   # 최종 경로 → 새 내용
        self.moves = []   # (원래 경로, 새 경로)
        self.log = []

    def read(self, rel):
        if rel in self.texts:
            return self.texts[rel]
        path = ROOT / rel
        if not path.is_file():
            raise CannotApply(f"파일이 없습니다: {rel}")
        return path.read_text(encoding="utf-8")

    def status(self, rel):
        return frontmatter_value(self.read(rel), "status", rel)

    def transition(self, rel, label, sources, target, satisfied):
        current = self.status(rel)
        if current == target or current in satisfied:
            self.log.append(f"  {rel}: status {current} (이미 반영됨)")
            return False
        if current not in sources:
            raise CannotApply(
                f"{rel}: status가 {current}라서 {label}을(를) {target}(으)로 반영할 수 없습니다 "
                f"(출발 상태: {', '.join(sorted(sources))})"
            )
        text = set_frontmatter(self.read(rel), "status", target, rel)
        if frontmatter_value(text, "updated", rel, required=False) is not None:
            text = set_frontmatter(text, "updated", self.today, rel)
        self.texts[rel] = text
        self.log.append(f"  {rel}: status {current} → {target}")
        return True

    def task(self, task_id, label, sources, target, satisfied):
        m = TASK_ID_RE.match(task_id or "")
        if not m:
            raise CannotApply(f"Task ID 형식이 아닙니다: {task_id}")
        milestone = f"M{m.group(1)}"
        card = f"plan/milestones/{milestone}/tasks/{task_id}.md"
        if self.transition(card, label, sources, target, satisfied):
            self.table_row(f"plan/milestones/{milestone}/milestone.md", task_id, 2, target)
        return card

    def table_row(self, rel, row_id, column, value, column2=None, value2=None):
        """표에서 첫 칸이 row_id인 행의 칸을 바꾼다. 행이 없으면 그대로 둔다."""
        if not (ROOT / rel).is_file() and rel not in self.texts:
            return
        lines = self.read(rel).split("\n")
        for i, line in enumerate(lines):
            cells = line.split("|")
            if len(cells) > column + 1 and cells[1].strip().strip("`") == row_id:
                cells[column + 1] = f" {value} "
                if column2 is not None and len(cells) > column2 + 1:
                    cells[column2 + 1] = f" {value2} "
                lines[i] = "|".join(cells)
                self.texts[rel] = "\n".join(lines)
                self.log.append(f"  {rel}: {row_id} 행 → {value}")
                return

    def history(self, card, line, short):
        text = self.read(card)
        if short in text:
            return
        heading = "\n## 게이트 이력\n"
        if heading not in text:
            text = text.rstrip("\n") + "\n" + heading + "\n"
        start = text.index(heading) + len(heading)
        end = text.find("\n## ", start)
        end = len(text) if end == -1 else end
        body = text[start:end].rstrip("\n")
        text = text[:start] + (body + "\n" if body.strip() else "\n") + line + "\n" + text[end:]
        self.texts[card] = text
        self.log.append(f"  {card}: 게이트 이력에 추가")

    def close_review(self, task_id, kind, review_id):
        if review_id:
            name = f"{review_id}.md"
        else:
            found = sorted((ROOT / "reviews" / "open").glob(f"{task_id}_{kind}-*.md"))
            if not found:
                return
            name = found[-1].name
        src, dst = f"reviews/open/{name}", f"reviews/closed/{name}"
        if (ROOT / dst).exists() or not (ROOT / src).exists():
            return
        self.texts[dst] = set_frontmatter(self.read(src), "status", "closed", src)
        self.moves.append((src, dst))
        self.log.append(f"  {src} → {dst} (status closed)")

    def decision(self, decision_id, short):
        found = sorted((ROOT / "decisions").glob(f"{decision_id}_*.md"))
        if len(found) != 1:
            raise CannotApply(f"결정 문서를 하나로 찾지 못했습니다: decisions/{decision_id}_*.md ({len(found)}개)")
        rel = found[0].relative_to(ROOT).as_posix()
        if self.transition(rel, f"결정 {decision_id}", {"proposed", "discussing"}, "confirmed", set()):
            self.table_row("decisions/index.md", decision_id, 2, "confirmed", 4, f"`{short}`")

    def paths(self):
        return sorted({p for move in self.moves for p in move} | set(self.texts))

    def write(self):
        for src, dst in self.moves:
            (ROOT / dst).parent.mkdir(parents=True, exist_ok=True)
            git("mv", src, dst)
        for rel, text in self.texts.items():
            write_lf(ROOT / rel, text)


def write_lf(path, text):
    """LF 줄바꿈으로 쓴다. Path.write_text의 newline 인자는 Python 3.10부터라 open을 쓴다."""
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def frontmatter_bounds(text, rel):
    if not text.startswith("---\n") or "\n---\n" not in text[3:]:
        raise CannotApply(f"frontmatter가 없습니다: {rel}")
    return 4, text.index("\n---\n", 3) + 1


def frontmatter_value(text, key, rel, required=True):
    start, end = frontmatter_bounds(text, rel)
    m = re.search(rf"^{key}:[ \t]*(.*)$", text[start:end], re.M)
    if not m:
        if required:
            raise CannotApply(f"frontmatter에 {key}가 없습니다: {rel}")
        return None
    return m.group(1).strip().strip('"')


def set_frontmatter(text, key, value, rel):
    start, end = frontmatter_bounds(text, rel)
    head, n = re.subn(rf"^{key}:.*$", f"{key}: {value}", text[start:end], count=1, flags=re.M)
    if not n:
        raise CannotApply(f"frontmatter에 {key}가 없습니다: {rel}")
    return text[:start] + head + text[end:]


def plan_for(sha, ctype, scope, trailers, today):
    """한 사람 커밋의 반영 계획과 커밋 메시지."""
    plan = Plan(today)
    short = sha[:7]
    task = trailers.get("Task")
    if ctype == "plan":
        approve = split_list(trailers.get("Approve"))
        for t in approve:
            plan.task(t, f"승인 {t}", {"draft"}, "approved", NOT_DRAFT)
        msg_scope = approve[0] if approve else scope
    elif ctype == "gate":
        verdict = trailers.get("Verdict")
        if verdict not in VERDICT:
            raise CannotApply(f"Verdict가 없거나 알 수 없습니다: {verdict}")
        target, satisfied = VERDICT[verdict]
        card = plan.task(task, f"판정 {verdict}", {"in-review"}, target, satisfied)
        nxt = trailers.get("Next")
        if nxt and nxt != "none":
            plan.task(nxt, f"다음 task {nxt}", {"draft"}, "approved", NOT_DRAFT)
        milestone = f"M{TASK_ID_RE.match(task).group(1)}"
        mfile = f"plan/milestones/{milestone}/milestone.md"
        if verdict == "approve" and task.endswith("-T0"):
            plan.transition(mfile, f"마일스톤 {milestone} 착수", {"planned"}, "active", {"active", "closed"})
        if trailers.get("Milestone-Verdict"):
            plan.transition(mfile, f"마일스톤 {milestone} 판정", {"active"}, "closed", {"closed"})
        for d in split_list(trailers.get("Decisions")):
            plan.decision(d, short)
        plan.history(card, f"- {today} gate {verdict} `{short}`", short)
        plan.close_review(task, "gate", trailers.get("Review"))
        msg_scope = task
    elif ctype == "respond":
        card = plan.task(task, "에스컬레이션 응답", {"blocked"}, "in-progress", NOT_BLOCKED)
        plan.history(card, f"- {today} respond `{short}`", short)
        plan.close_review(task, "esc", trailers.get("Review"))
        msg_scope = task
    else:  # decide
        decisions = split_list(trailers.get("Decisions"))
        for d in decisions:
            plan.decision(d, short)
        msg_scope = decisions[0] if decisions else scope

    if ctype == "respond":
        message = f"task({task}): resume after response {short}\n\nActor: agent\nTask: {task}\nApplies: {short}\n"
    else:
        head = f"log({msg_scope}): apply {ctype} {short}" if msg_scope else f"log: apply {ctype} {short}"
        message = f"{head}\n\nActor: agent\nApplies: {short}\n"
    return plan, message


def last_apply():
    """지난 반영(.lg/pending/APPLY_MSG)의 상태: None, ("cleaned", 해시, []), ("pending", 해시, 경로들).

    그 Applies 해시를 담은 커밋이 있으면 반영 커밋이 끝난 것이므로 기록 파일을 지운다.
    없으면 반영은 했지만 커밋하지 않은 것이다(세션이 중간에 끝난 경우 등).
    """
    if not APPLY_MSG.exists():
        return None
    short = (parse(APPLY_MSG.read_text(encoding="utf-8"))[3].get("Applies") or "").lower()
    paths = APPLY_PATHS.read_text(encoding="utf-8").splitlines() if APPLY_PATHS.exists() else []
    if short and short in applied_hashes(commits()):
        for f in (APPLY_MSG, APPLY_PATHS):
            if f.exists():
                f.unlink()
        return ("cleaned", short, [])
    return ("pending", short, [p for p in paths if p])


def commit_command(paths):
    if paths:
        return "scripts/agent-commit -F .lg/pending/APPLY_MSG -- " + " ".join(paths)
    return "scripts/agent-commit --allow-empty -F .lg/pending/APPLY_MSG"


def main(argv):
    try:
        if "--tidy" in argv:
            state = last_apply()
            if state:
                print(json.dumps({"state": state[0], "applies": state[1], "paths": state[2]}, ensure_ascii=False))
            return 0
        pending = unreflected()
        if "--check" in argv:
            for sha, _, _, header, _ in pending:
                print(f"{sha[:7]} {header}")
            return 0
        if not pending:
            print("반영할 사람 커밋이 없습니다.")
            return 0
        if (PENDING / "COMMIT_MSG").exists():
            raise UsageError("사람 커밋 대기 상태입니다(.lg/pending/COMMIT_MSG). 사람이 lg commit 으로 확정한 뒤 실행하세요.")
        state = last_apply()
        if state and state[0] == "pending":
            raise UsageError(
                f"지난 반영({state[1]})이 아직 커밋되지 않았습니다. 먼저 커밋하세요:\n  {commit_command(state[2])}"
            )
        sha, ctype, scope, header, trailers = pending[0]
        plan, message = plan_for(sha, ctype, scope, trailers, datetime.date.today().isoformat())
        paths = plan.paths()
        dirty = git("status", "--porcelain", "--", *paths).strip() if paths else ""
        if dirty:
            raise UsageError("반영할 파일에 커밋되지 않은 변경이 있습니다. 먼저 커밋하세요:\n" + dirty)
        plan.write()
        PENDING.mkdir(parents=True, exist_ok=True)
        write_lf(APPLY_MSG, message)
        write_lf(APPLY_PATHS, "".join(p + "\n" for p in paths))
    except CannotApply as e:
        print(f"✗ 반영할 수 없습니다: {e}\n  아무것도 바꾸지 않았습니다. 사람에게 보고하세요.", file=sys.stderr)
        return 1
    except UsageError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 2

    print(f"반영: {sha[:7]} {header}")
    print("\n".join(plan.log) if plan.log else "  (바뀐 파일 없음)")
    if not paths:
        print("  상태는 이미 반영되어 있습니다. 이 커밋을 가리키는 Applies 기록이 없어(Refs 등 다른 trailer는\n"
              "  반영 기록으로 보지 않는다) 기록만 남기는 빈 반영 커밋을 만듭니다.")
    if paths:
        print("커밋: " + commit_command(paths) + "  (STATUS.md를 고쳤으면 함께)")
    else:
        print("커밋: " + commit_command(paths) + "  (STATUS.md를 고쳤으면 -- STATUS.md)")
    if len(pending) > 1:
        print(f"남은 사람 커밋 {len(pending) - 1}개: 커밋한 뒤 다시 실행하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
~~~~
