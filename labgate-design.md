# `labgate` CLI 설계 문서 — v8 (`lg init`, `lg commit`, `lg draft`, `lg upgrade`, `lg verify`, `lg status`, `lg answer`, `lg spec`, `lg ideas`, 프로젝트 도구)

> 문서 버전: 8.0 · 대상: CLI 구현자(사람 또는 코딩 에이전트)
> 이 문서만으로 `lg init`, `lg commit`, `lg draft`를 구현·테스트할 수 있어야 한다. 생성될 모든 파일의 원문은 부록 A·B·C에 있다.

변경 이력은 `git log -- labgate-design.md`로 본다.

---

## 0. 읽는 법

- §1–3: 무엇을 왜 만드는가 (범위, 확정된 결정, 용어)
- §4–13: `lg init`을 어떻게 만드는가 (명령, 설정, 생성 결과, 모듈, Git, hook, 오류)
- §14–15: 무엇으로 완성을 판단하는가 (테스트, 수용 기준), 이후 확장
- §16–27: v2–v8 — 규칙의 층과 우선순위, 사람의 변경과 `session-check`, `lg commit`, `lg draft`, 한계, `apply-human-commits`, `lg upgrade`, `lg verify`, `lg status`·`lg answer`·`lg spec adopt`, 프로젝트 종류(`--kind`)와 자료 가져오기, 아이디어 탐색(`--kind ideation`, `--from`, `lg ideas`), 앵커 연구
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
| `lg upgrade` (§22) | spec_version 1 프로젝트의 갱신 |
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
    labgate_version: "0.7.0"
    spec_version: 4
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
│   ├── __init__.py          # __version__, SPEC_VERSION = 4
│   ├── cli.py               # Typer 앱, init·commit·draft 명령, 종료 코드 처리
│   ├── project.py           # 생성된 프로젝트 찾기, spec_version·신원 확인, hook 규칙 읽기 (§18.3)
│   ├── errors.py            # 종료 코드, Fail 예외
│   ├── commit.py            # lg commit (§18)
│   ├── draft.py             # lg draft (§19)
│   ├── kinds.py             # 생성 파일 분류, 정규화·해시 (§22.3, §22.4)
│   ├── upgrade.py           # lg upgrade (§22)
│   ├── verify.py            # lg verify, lg commit의 gate 검사 (§23)
│   ├── hashes/<n>.json      # 릴리즈된 spec_version의 관리 문서 해시표 (§22.4)
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
version = "0.7.0"
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

v2 (`tests/commands/`, `tests/tools/`, 사람 `h@x.com`, `lg init`으로 만든 프로젝트에서. 테스트 계층은 `tests/README.md`):

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

`lg gate`(응답 기록과 `gate` 커밋을 한 번에)와 `lg status`는 v0.5.0의 `lg answer`, `lg status`로 만들었다(§24). 상태 반영은 사람 커밋 뒤 에이전트가 `apply-human-commits`로 하고, `STATUS.md`는 에이전트의 서술로 남긴다.

| 명령 | 역할 | 미리 지킬 것 |
|---|---|---|
| `lg validate` | 문서를 사양의 검증 규칙으로 검사 | 사양마다 §7 검증 규칙 섹션 유지 |
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
| `gate-apply` | 반영되지 않은 사람 커밋이 있음 | G4, G6 (로드맵의 마일스톤 상태 칸, v0.5.0) | `apply-human-commits` | — |

원문은 부록 B.10. 형식:

```markdown
---
id: <name>
type: procedure
spec_version: 4
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
- 이 일괄 갱신은 `lg upgrade`(§22)가 한다. `lg`가 없을 때의 수동 절차는 [docs/guide/upgrade.md](docs/guide/upgrade.md)에 있다.

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
5. **확인.** 사람이 `git diff --cached`를 따로 치지 않아도 되게 다음을 모두 보여 준다: `git diff --cached --stat`, stage된 review 문서의 `## 응답` 원문(대화 경로에서 에이전트가 옮겨 적은 것), `gate`면 `lg verify` 요약(§23.6), 반영되는 커밋(`gate`, `respond`, `decide`, `plan`+`Approve`)이면 반영 미리보기(§24.5.4, spec_version 5 이상), 메시지. 반영할 수 없는 커밋이면 이유를 보여 주고 선택지를 `커밋 (반영할 수 없음)`으로 표시한다(막지는 않는다). "커밋 / 편집기로 수정 / 변경 내용 자세히 보기 (diff) / 취소" 중 고르게 한다. 자세히 보기는 `git diff --cached` 전체를 pager로 보여 주고 이 단계로 돌아온다. 편집기는 Git과 같은 규칙으로 고른다(`git var GIT_EDITOR`: `core.editor`, `GIT_EDITOR`, `VISUAL`, `EDITOR` 순)하고 Git처럼 `sh -c '<편집기> "$@"'`로 실행한다. 편집 후에는 hook의 `check(text, check_author=False)`로 다시 검사하고, 오류가 있으면 보여 준 뒤 이 단계를 반복한다. 취소는 코드 130 (stage와 초안은 그대로).
6. **커밋.** 메시지를 임시 파일에 써서 `git commit -F <파일>`. hook이 거부하면 hook 출력을 그대로 보여 주고 코드 4 (초안은 남긴다).
7. **정리.** 초안 모드면 `.lg/pending/COMMIT_MSG`를 지운다. `.lg/pending/HUMAN_FILES`가 있으면 아직 커밋되지 않은 경로만 남기고, 남는 것이 없으면 지운다.
8. **tag.** `gate` + `Verdict: approve`이고 `--no-tag`가 아니면 `gate/<Task>`. `Milestone-Verdict`가 있으면 `milestone/<M>-<verdict>`도 (`<M>`은 Task ID의 마일스톤 부분). tag 실패는 코드 4 (커밋은 남는다).
9. **출력.** "✓ 커밋했습니다: <짧은 해시> <헤더>", 만든 tag, 그리고 커밋 종류에 따른 다음 할 일. 에이전트는 세션을 시작할 때 사람 커밋을 자동으로 확인하므로(`session-check`), 알려야 하는 것은 열린 세션이 기다리고 있을 때뿐이다.

   | 커밋 | 안내 |
   |---|---|
   | 초안 모드 (에이전트가 준비하고 기다림) | 에이전트가 기다리고 있으면 '커밋했어'라고 알리라. 새 세션에서는 자동으로 확인한다 |
   | `gate`, `respond`, `decide`, `plan`+`Approve` | 다음 세션 시작 때 자동으로 반영된다. 열린 세션에서 바로 이어 가려면 알리라 |
   | `spec` | 규칙 문서가 바뀌었다. 열린 에이전트 세션이 있으면 새로 시작하라 |
   | 그 밖 | 없음 |

### 18.3 프로젝트 확인과 규칙 읽기 (`project.py`)

1. 현재 폴더에서 `git rev-parse --show-toplevel`. 실패하면 "Git 저장소가 아닙니다".
2. `<root>/.lg/project.yaml`이 없으면 "labgate 프로젝트가 아닙니다".
3. `generated.spec_version`이 지원 범위(2–4)가 아니면 오류. spec_version 2–4는 커밋 규약(타입·trailer)이 같으므로 모두 지원한다. 1이면 "labgate 0.1로 만든 프로젝트입니다(spec_version 1). git commit을 직접 쓰세요."
4. `.lg/identities.json`을 읽는다.
5. `.lg/hooks/commit-msg`를 `runpy.run_path(path, run_name="labgate_hook")`로 읽어 `HUMAN_TYPES`, `AGENT_TYPES`, `COMMON_TYPES`, `TASK_REQUIRED`, `SOURCE_REQUIRED`, `MAX_HEADER`, `HEADER_RE`, `TASK_ID_RE`, `DECISION_ID_RE`, `parse`, `check`를 가져온다. 하나라도 없으면 "hook이 spec_version 2 형식이 아닙니다".

사람이 쓸 수 있는 타입 = `HUMAN_TYPES ∪ COMMON_TYPES - {"init"}`. 규칙을 `lg` 안에 따로 두지 않으므로, 프로젝트를 만든 시점의 hook과 `lg`가 어긋나지 않는다.

### 18.4 작성 모드

1. stage된 변경이 없으면 커밋되지 않은 파일 목록을 체크박스로 보여 주고, 고른 경로를 `git add -A -- <경로>`로 stage한다. 아무것도 고르지 않으면 코드 3. 커밋되지 않은 변경도 없으면 코드 3. `--allow-empty`면 이 단계를 건너뛰고 stage된 것만(없으면 빈 커밋) 커밋한다.
2. 타입: 사람이 쓸 수 있는 타입 (사람 전용을 먼저).
3. Task: 타입이 `TASK_REQUIRED`면 `plan/milestones/*/tasks/*.md`의 파일 이름 중 Task ID 형식인 것에서 고른다(없으면 입력). scope는 Task와 같게 정한다. `plan`이면 `Approve`(승인할 task)를 같은 목록에서 여러 개 고르게 하고(고르지 않으면 생략), 하나만 골랐으면 scope도 그 Task ID로 정한다. 그 밖의 경우 scope를 선택 입력으로 묻는다.
4. 타입별 trailer: `SOURCE_REQUIRED`면 `Source`, `gate`면 `Verdict`, 선택 `Next`(Task ID 또는 `none`), `decide`면 `Decisions`. `Milestone-Verdict`는 그 task가 마일스톤의 마지막일 때만 묻는다: `Next`가 같은 마일스톤이거나 닫히지(`closed`·`redirected`) 않은 다른 카드가 있으면 묻지 않는다(v0.5.0. 실사용에서 M0-T0 판정 중 `go`를 고를 뻔했다. 카드를 읽지 못하면 묻는다).
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

## 22. `lg upgrade` (사양 버전 갱신)

### 22.1 목적

이전 spec_version으로 만든 프로젝트를 현재 labgate의 spec_version으로 올린다. 지금은 사람이 손으로 한다(`docs/guide/upgrade.md`의 수동 절차): 새 버전의 임시 프로젝트를 만들어 규칙·도구 파일을 복사하고, 모든 문서의 `spec_version`을 올리고, `spec` 커밋을 한다. 이 일은 규칙이 정해진 기계적인 일이므로 코드로 만든다([코드 우선 원칙](labgate-design.md) §22.16.2).

손으로 할 때 실제로 생긴 문제가 이 설계의 요구사항이다.

| 실사용에서 생긴 일 | 요구사항 |
|---|---|
| 연구 문서의 frontmatter `spec_version`을 갱신 절차가 다루지 않았다 | 모든 문서의 버전 표기를 규칙대로 처리한다 |
| 템플릿을 직접 복사해 실행 권한이 빠졌다 | 생성 계획(`plan.py`)의 권한을 그대로 쓴다 |
| 사람이 고쳤을 수 있는 파일을 덮어쓸 위험 | 사람이 고친 관리 문서는 덮어쓰지 않는다 |
| `dev` 중간 상태를 복사해 같은 spec_version 안에서도 파일이 달랐다 | 같은 spec_version의 생성 파일은 하나로 고정한다 |

### 22.2 버전 형식

#### 22.2.1 정의

| 항목 | 형식 | 의미 | 위치 |
|---|---|---|---|
| labgate 버전 | `MAJOR.MINOR.PATCH` (semver) | 도구의 버전 | `lg --version`, `.lg/project.yaml`의 `generated.labgate_version` |
| spec_version | 양의 정수 | 생성되는 문서 형식과 규칙의 계약 | `.lg/project.yaml`의 `generated.spec_version`, 문서 frontmatter |
| 문서 frontmatter | 정확히 한 줄 `spec_version: <정수>` (`^spec_version: (\d+)$`) | 그 문서가 따르는 사양 버전 | frontmatter가 있는 모든 `.md` |
| 갱신 이력 | 목록 | 언제 무엇으로 올렸는지 | `.lg/project.yaml`의 `upgrades` (새 키) |

```yaml
generated:
  labgate_version: "0.2.0"      # 만든 버전 (바뀌지 않는다)
  spec_version: 4               # 현재 사양 버전 (upgrade가 바꾼다)
  created: "2026-10-02"         # 만든 날 (바뀌지 않는다)
upgrades:                       # upgrade가 추가한다. 오래된 순
  - from: 3
    to: 4
    labgate_version: "0.4.0"
    date: "2026-10-04"
    forced: []                  # --force로 덮어쓴 관리 문서
```

#### 22.2.2 버전 규칙

1. **spec_version은 마이너 버전에서만 바뀐다.** 패치 버전은 생성되는 파일을 바꾸지 않는다.
2. **같은 spec_version의 생성 파일은 하나다.** 릴리즈된 spec_version의 템플릿은 다시 바꾸지 않는다. 바꿔야 하면 spec_version을 올린다. 버전별 해시표(§22.4)와 테스트로 강제한다.
3. **labgate 버전마다 하나의 spec_version을 만든다**(`SPEC_VERSION`). `lg commit`·`lg draft`가 지원하는 범위는 따로 둔다(`SUPPORTED_SPEC_VERSIONS`).
4. `lg upgrade`는 프로젝트를 `SPEC_VERSION`으로 올린다. 이동 규칙은 한 단계씩 이어 간다(2→3→4).

| labgate | 만드는 spec_version | `lg upgrade`로 올릴 수 있는 출발 버전 |
|---|---|---|
| 0.2.x | 2 | — |
| 0.3.x | 3 | — |
| 0.4.x | 4 (`lg upgrade` deny, `.gitignore` 관리 구역) | 2, 3 |

### 22.3 파일 분류

생성 계획의 모든 파일에 분류를 붙인다(`PlannedFile.kind`, `plan.py` 한 곳). `lg upgrade`는 분류마다 정해진 일만 한다. 테스트가 모든 생성 파일에 분류가 있는지 확인한다.

| 분류 | 파일 | 해시가 그 버전과 같음 | 다름 | `--force` |
|---|---|---|---|---|
| **관리 문서** | `AGENTS.md`, `CLAUDE.md`, `.claude/settings.json`, `.claude/commands/*`, `specs/conventions.md`, `specs/workflow.md`, `specs/git-commit.md`, 완성 사양(`task-card`, `review`, ideation의 `idea`·`criteria`·`brief`·`anchor`), `specs/templates/*`, `specs/procedures/*`, `scripts/*`, `.lg/hooks/commit-msg` | 새 버전으로 교체 | **갱신 실패** | 새 버전으로 덮어씀 |
| **사람이 채우는 관리 문서** | stub 사양 11종, `specs/README.md` | 새 버전으로 교체 | 사람이 채운 것으로 보고 내용 유지, `spec_version`만 갱신 | 덮어쓰지 않음 |
| **관리 구역** | `.gitignore` | `# labgate:begin` ~ `# labgate:end` 구역만 새 버전으로 바꾸고, 구역 밖의 줄은 그대로 (§22.5.2) | | |
| **연구 문서** | 위에 없는, Git이 추적하는 모든 `.md` (`plan/`, `decisions/`, `references/`, `reviews/`, `results/`, `logs/`, `STATUS.md`, `FILEMAP.md`, `README.md`, …) | frontmatter `spec_version`만 갱신. 내용은 그대로 | | |
| **초기화 기록** | `.lg/identities.json`, `.lg/project.yaml`의 `generated.labgate_version`·`created`, `README.md` 맨 아래 줄 | 그대로 | | |
| **갱신 기록** | `.lg/project.yaml`의 `generated.spec_version`, `upgrades` | 갱신 | | |
| **기타** | `.gitkeep`, Git이 추적하지 않는 파일 | 무시 | | |

- 새 버전에 새로 생긴 관리 문서는 추가한다. 없어진 관리 문서는 해시가 같으면 지우고, 다르면 갱신 실패로 본다.
- `FILEMAP.md`는 연구 문서지만, labgate가 만드는 부분(루트 문서 표, 폴더 표)이 두 버전 사이에 바뀌었으면 갱신 출력에 "FILEMAP.md에 반영할 변경"을 안내한다. 반영 여부는 사람이나 에이전트가 정한다.

### 22.4 버전별 해시표

#### 22.4.1 무엇을 두나

릴리즈된 spec_version마다 관리 문서의 해시를 패키지에 둔다: `src/labgate/hashes/<spec_version>.json`. 프로젝트 안에는 아무것도 기록하지 않는다(manifest 없음). 어느 프로젝트든 자기 spec_version의 해시표와 비교해 판별한다. 그래서 manifest가 없던 v0.2·v0.3 프로젝트도 같은 방식으로 판별된다.

```json
{
  "spec_version": 3,
  "labgate_version": "0.3.0",
  "files": {
    "specs/procedures/gate-apply.md": {"claude_code": "sha256:…", "no_claude_code": "sha256:…"},
    "AGENTS.md": {"claude_code": "sha256:…", "no_claude_code": "sha256:…"},
    "CLAUDE.md": {"claude_code": "sha256:…"}
  },
  "gitignore": ["# 실행 산출물 원본", "runs/*", "…"],
  "filemap": ["…"]
}
```

#### 22.4.2 정규화

프로젝트마다 내용이 달라지는 관리 문서는 정해진 규칙으로 정규화한 뒤 해시한다. 비교할 때도 같은 규칙을 쓴다.

| 문서 | 프로젝트마다 다른 부분 | 정규화 |
|---|---|---|
| `AGENTS.md` | "## 프로젝트"의 이름·연구 질문·에이전트 신원 세 줄, Claude Code 사용 여부(G7의 파일 목록) | 세 줄의 값을 자리표시(`<name>`, `<research_question>`, `<agent>`)로 바꾼다. Claude Code 사용·미사용 두 변형의 해시를 둔다 |
| `specs/README.md` | frontmatter `updated:` | 그 줄을 뺀다 |
| 그 밖의 관리 문서 | 없음 | 그대로 |

- 파일 끝 개행, 줄바꿈(LF)은 생성 규칙대로라 정규화하지 않는다. 사람이 줄바꿈만 바꿔도 "다름"이다.
- 정규화 규칙은 `lg`의 코드 한 곳에 두고, 해시표를 만드는 스크립트와 `lg upgrade`가 같이 쓴다.

#### 22.4.3 해시표를 만드는 방법

- `scripts/hash-templates.py <tag> <spec_version>`: 그 tag의 템플릿으로 시험용 설정을 렌더링하고, 정규화해 해시표를 만든다. 2는 `v0.2.1`, 3은 `v0.3.0`에서 만든다.
- 릴리즈할 때 새 spec_version의 해시표를 만들어 넣는다.
- 테스트: 현재 `SPEC_VERSION`의 해시표가 있으면(릴리즈된 뒤) 현재 템플릿의 해시가 그와 같아야 한다(§22.2.2 규칙 2). 해시표가 없으면 아직 릴리즈 전인 dev 버전이다.
- 해시표가 없는 spec_version은 릴리즈되지 않은 dev 버전으로 만든 프로젝트다. dev 버전은 개발자만 쓰고 실사용에 쓰지 않는 것이 원칙이므로, 이런 프로젝트의 갱신은 지원하지 않는다(코드 2, `--force`로도 하지 않는다).

### 22.5 사람의 수정, 갱신 실패, `--force`

**사람이 항상 우선이다.** `lg`가 사람의 수정을 발견하면 그 수정을 지우거나 되돌리지 않고, 터미널에 무엇을 발견했고 어떻게 했는지 알린다. 분류별로는 이렇다.

| 발견한 사람의 수정 | 동작 | 터미널 안내 |
|---|---|---|
| 관리 문서를 고침 | 갱신을 멈춘다 (§22.5.1). `--force`일 때만 덮어쓴다 | 고친 문서 목록, 해결 방법 |
| stub 사양·`specs/README.md`를 채움 | 내용 유지, `spec_version`만 갱신 | 유지한 문서 목록 |
| `.gitignore` 관리 구역에서 줄을 지우거나 더함 | 사람의 선택을 따른다 (§22.5.2) | 지운 줄은 다시 넣지 않았다, 더한 줄은 구역 밖으로 옮겼다 |
| `FILEMAP.md` 등 연구 문서 | 내용 유지 | labgate 구조가 바뀌었으면 반영할 내용 |


#### 22.5.1 관리 문서가 다를 때

- 관리 문서 중 하나라도 해시가 그 버전과 다르면 **아무것도 바꾸지 않는다.** 다른 문서 목록(지금 → 새 버전의 줄 수 포함)과 해결 방법을 출력하고 코드 3으로 끝낸다. 도구는 릴리즈된 파일과 다르다는 것만 알 수 있으므로 출력은 "사람이 고쳤다"고 단정하지 않고 "릴리즈된 spec_version N과 다르다"고 쓴다(v0.4.0에서 릴리즈 전 `dev` 중간 상태를 복사한 파일이 "사람이 고친 문서"로 표시되어 오해를 낳았다). 일부만 갱신하면 규칙 문서끼리 버전이 섞이므로(`AGENTS.md`는 v3, 절차는 v4) 전체를 멈춘다.
- 해결:
  - 사람이 의도해서 고친 것이 아니면(예: 중간 버전 복사) `lg upgrade --force`.
  - 의도해서 고친 것이면 `--force`로 갱신한 뒤, 남겨 둔 원래 내용(아래)을 보고 다시 합친다.
- `--force`는 다른 관리 문서를 모두 새 버전으로 덮어쓴다. 덮어쓰기 전 내용은 `.lg/pending/upgrade/<경로>`에 남기고(Git 제외), 덮어쓴 목록을 `upgrades[].forced`에 기록한다. 사람이 채우는 관리 문서(stub 사양, `specs/README.md`)는 `--force`로도 덮어쓰지 않는다.
- `lg upgrade`는 커밋하지 않으므로, 결과가 마음에 들지 않으면 `git restore`로 되돌릴 수 있다.

#### 22.5.2 `.gitignore` 관리 구역

```
# labgate:begin  (labgate가 관리한다. 이 구역 밖에 자유롭게 추가한다)
.lg/pending/
runs/
…
# labgate:end

# 사람이 추가한 줄
checkpoints/
```

줄 단위로 비교한다(빈 줄과 주석 제외). 기준은 출발 버전이 만든 줄(해시표에 줄 목록도 둔다)이다.

| 경우 | 동작 | 안내 |
|---|---|---|
| 출발 버전의 줄이 있음 | 새 버전의 줄로 바꾼다 | — |
| 출발 버전의 줄을 사람이 지움 | **다시 넣지 않는다.** 새 버전에서도 그 줄은 빼고 구역을 만든다 | "사람이 지운 labgate 줄: … (그대로 둡니다)" |
| 새 버전에 새로 생긴 줄 | 넣는다 | — |
| 구역 안에 사람이 더한 줄 | 구역 밖(바로 아래)으로 옮겨 보존한다 | "구역 안에 추가된 줄을 구역 밖으로 옮겼습니다: …" |
| 구역 밖의 줄 | 그대로 | — |

- 구역 표시가 없는 기존 프로젝트(spec_version 2·3)는 파일 전체를 "구역"으로 보고 같은 규칙을 적용한 뒤, 새 구역을 맨 앞에 넣고 사람이 더한 줄을 그 뒤에 원래 순서대로 둔다.
- `.gitignore` 때문에 갱신이 실패하는 일은 없다.

### 22.6 버전별 이동 규칙

기본 갱신(관리 문서 교체, 문서의 `spec_version` 갱신)으로 충분하지 않은 변화는 단계마다 규칙으로 등록한다(`MIGRATIONS[n]`: n → n+1).

| 단계 | 추가 규칙 |
|---|---|
| 2 → 3 | 없음 (기본 갱신) |
| 3 → 4 | `.gitignore`에 관리 구역 도입 (§22.5.2) |

2→4는 2→3, 3→4를 차례로 적용한 결과를 한 번에 쓴다. 판별은 출발 버전의 해시표로 한다.

문서 frontmatter의 `spec_version`:
- 목표보다 작으면 목표로 올린다. 출발 값별 개수를 보고한다(예: 연구 프로젝트는 `generated`가 3인데 문서는 2).
- 목표보다 크면 오류(코드 2).
- `spec_version` 줄이 정확한 형식이 아니면(따옴표, 공백) 바꾸지 않고 보고한다.

### 22.7 명령

```
lg upgrade [--dry-run] [--diff] [--force]
```

1. 프로젝트 확인: Git 저장소, `.lg/project.yaml`, spec_version이 출발 가능 범위인지, 그 버전의 해시표가 있는지. 이미 최신이면 "이미 spec_version N입니다"로 끝낸다.
2. 전제: 작업 트리가 깨끗하고, `.lg/pending/COMMIT_MSG`·`APPLY_MSG`가 없다(코드 2).
3. 계획: §22.3–§22.6에 따라 모든 변경을 메모리에서 계산한다.
4. `--dry-run`이면 표만 출력하고 끝낸다(코드 0, 갱신 실패 대상이 있어도 표에 보인다). `--diff`면 그 버전과 다른 문서(관리 문서, 사람이 채우는 관리 문서)마다 지금 파일 → 새 버전의 unified diff를 출력하고 끝낸다(코드 0). 해시표에는 옛 파일이 없으므로 비교 대상은 `--force`가 쓸 새 버전이다. 버전 갱신으로 바뀌는 줄과 그 프로젝트에서 바뀐 줄이 함께 보인다.
5. 관리 문서가 다르고 `--force`가 아니면 §22.5.1 (코드 3).
6. 쓴다: 교체·추가·삭제, 문서 버전 갱신, `.gitignore` 구역, `.lg/project.yaml`. 실행 권한은 생성 계획대로.
7. 출력: 바뀐 것 요약, `FILEMAP.md` 안내(있으면), 다음 단계("`git diff`로 확인하고 터미널에서 `lg commit` — 타입 `spec`").

**커밋하지 않는다.** 규칙을 바꾸는 일이므로 사람이 확인하고 `spec` 커밋으로 확정한다.

| 종료 코드 | 의미 |
|---|---|
| 0 | 갱신함, 이미 최신, `--dry-run` |
| 1 | 예기치 못한 오류 |
| 2 | labgate 프로젝트가 아님, 출발할 수 없는 spec_version, 해시표 없음(dev 버전으로 만든 프로젝트), 작업 트리가 깨끗하지 않음, 대기 상태, 형식 오류 |
| 3 | 관리 문서가 그 버전과 다름 (아무것도 바꾸지 않음, `--diff`로 보고 `--force`로 해결) |
| 4 | Git 오류 |
| 130 | 중단 |

**누가:** 사람. 에이전트는 실행하지 않는다(G7: 규칙 파일 수정 금지). 생성되는 `.claude/settings.json`에 `Bash(lg upgrade *)` deny를 넣는다. 터미널 확인(TTY)은 하지 않는다. 커밋하지 않으므로 사람이 `git diff`로 확인할 기회가 있다.

### 22.8 연구 프로젝트에서 예상되는 결과

`ssm-latent-reasoning` (generated 3, 문서 대부분 2). v0.3.0 템플릿과 직접 비교한 결과를 바탕으로 했다.

| 파일 | 예상 |
|---|---|
| `specs/conventions.md` | 3-4 때 `dev` 중간 상태를 복사해 v3 해시와 다름 → **갱신 실패** (코드 3). 사람이 고친 것이 아니므로 `--force` |
| 그 밖의 관리 문서 | v3 해시와 같음 → v4로 교체 |
| stub 사양 | M0에서 채웠으면 내용 유지·버전만 갱신, 아니면 교체 |
| `.gitignore` | 관리 구역 도입 |
| 연구 문서 20개 이상 | `spec_version` 2 → 4 (그사이 에이전트가 만든 문서 포함) |
| `.lg/project.yaml` | `spec_version: 4`, `upgrades`에 3 → 4 (`forced: [specs/conventions.md]`) |

### 22.9 문서와 테스트

- 명령 설명서 `docs/cli/lg-upgrade.md`, 작업 설명서 `docs/guide/upgrade.md` 개정(수동 절차는 `lg` 없이 할 때의 대안으로만 남김).
- 테스트:
  - 해시표: 정규화 규칙, 현재 템플릿이 현재 spec_version 해시표와 같음(릴리즈 뒤), 2·3 해시표가 그 tag의 템플릿과 같음.
  - 갱신: spec_version 2·3 프로젝트를 올리기, 같은 관리 문서 교체, 다른 관리 문서가 있으면 아무것도 바뀌지 않고 코드 3, `--force`(덮어씀, 원래 내용 보관, `forced` 기록), stub 사양을 채운 경우 내용 유지.
  - `.gitignore`: 구역 도입, 사람이 추가한 줄 보존, 사람이 지운 labgate 줄은 다시 넣지 않고 안내, 구역 안에 더한 줄은 밖으로 옮기고 안내.
  - 문서 버전 갱신과 형식 오류 보고, 새 파일 추가와 없어진 파일 삭제, 실행 권한, `upgrades` 기록, `--dry-run`, 작업 트리가 깨끗하지 않을 때·대기 상태 거부, 모든 생성 파일의 분류.

### 22.10 결정된 사항

1. **버전별 해시표를 패키지에 둔다.** 관리 문서가 그 버전의 해시와 다르면 사람이 고친 것으로 보고 갱신을 실패한다. `lg upgrade --force`는 다른 관리 문서를 새 버전으로 덮어쓴다.
2. **`.gitignore`는 관리 구역의 줄만 합친다.**
3. **`README.md`, `FILEMAP.md`는 연구 문서다.** `FILEMAP.md`는 labgate가 만드는 부분이 바뀐 버전이면 갱신 출력에서 안내한다.
4. **프로젝트 안에 manifest를 두지 않는다.** 버전별 해시표로 어느 프로젝트든 판별되므로 `--adopt` 같은 모드도 필요 없다.
5. **stub 사양과 `specs/README.md`는 "다르면 실패"에서 뺀다.** M0에서 사람이 채우라고 만든 문서이므로, 다르면 내용을 유지하고 `spec_version`만 갱신한다. `--force`로도 덮어쓰지 않는다.
6. **dev 버전은 실사용에 쓰지 않는다.** dev는 개발자만 쓴다. 해시표가 없는 spec_version(dev로 만든 프로젝트)의 갱신은 지원하지 않는다(코드 2, `--force`로도 하지 않는다).
7. **사람이 항상 우선이다.** `lg`가 사람의 수정을 발견하면 지우거나 되돌리지 않고 터미널에 알린다(§22.5). `.gitignore`에서 사람이 지운 labgate 줄은 다시 넣지 않고 안내한다.

## 23. `lg verify` (규칙 준수의 사후 확인)

### 23.1 목적

에이전트가 일한 결과가 규칙을 지켰는지 **커밋 이력과 문서로 사후에 확인한다.** 지금 강제되는 것은 커밋하는 순간의 메시지와 작성자 신원(commit-msg hook)뿐이다. 파일 내용에 대한 규칙(G4 상태 전이, G5 응답, G7 규칙 파일)은 에이전트가 규칙 문서를 따르는 데 기대고 있고, hook을 우회했거나 hook이 없던 환경의 커밋은 아무도 다시 확인하지 않는다.

| 규칙 | 지금 | v0.4.1 `lg verify` |
|---|---|---|
| P2·P3 신원, 사람 전용 타입 | 커밋 순간 hook | + 사후 확인 (우회·hook 없던 커밋) |
| P4 병합 | 커밋 순간 hook | + 사후 확인 |
| G4 사람 몫의 상태 전이 | 없음 | 사후 확인 |
| G5 review `## 응답` | 없음 | 사후 확인 |
| G7 규칙 파일 | 없음 | 사후 확인 |
| P1 반영 누락 | 세션 시작 알림 | (검사하지 않음: `session-check`와 중복) |
| 문서 형식 | 없음 | 사후 확인 |
| 요청한 일을 했는가 | 사람의 게이트 판정 | 판정하지 않고 점검표만 |

### 23.2 패치의 조건

버전 규칙(§22.2.2)상 패치는 생성되는 파일을 바꾸지 않는다. 그래서:

- `lg verify`는 `lg` 패키지에 명령만 더하고, `lg commit`(역시 `lg` 패키지)의 게이트 확인 단계에 연결한다(§23.5). 생성되는 프로젝트(템플릿, hook, 절차)는 그대로다. spec_version 2–4 프로젝트에 모두 쓸 수 있다.
- **읽기만 한다.** 파일도 커밋도 바꾸지 않는다. 그래서 사람과 에이전트 모두 실행할 수 있다(Claude Code deny 없음).
- 다음 마이너 버전(spec_version 5)으로 미루는 것: hook에서 커밋 순간 막기(G3 대기 상태, G7 보호 경로), 절차에 "게이트 요청 전 `lg verify`" 넣기.

### 23.3 규칙의 원본은 프로젝트의 문서다

검사 기준을 `lg` 안에 따로 두지 않는다. 프로젝트를 만든 버전의 규칙으로 검사해야 하므로, 그 프로젝트의 파일에서 읽는다.

| 기준 | 읽는 곳 |
|---|---|
| 커밋 타입 분류, trailer 형식, 메시지 검사 | `.lg/hooks/commit-msg` (`lg commit`과 같은 방식, `check(text, check_author=False)`와 상수) |
| 사람·에이전트 신원 | `.lg/identities.json` |
| 상태값 어휘 | `specs/conventions.md`의 "상태값" 표 |
| 문서 유형별 필수 frontmatter 필드 | `specs/doc-types/<유형>.spec.md`의 frontmatter 표 (완성 사양만: `task-card`, `review`) |
| 사람 몫의 상태 전이 (G4) | 아래 §23.4.3 표. `AGENTS.md` G4와 같은 내용이며, 테스트가 현재 spec_version의 `AGENTS.md`와 맞는지 확인한다 |
| 보호 경로 (G7) | `specs/`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.lg/`. 테스트가 현재 spec_version의 `AGENTS.md` G7과 맞는지 확인한다 |

Markdown 표를 읽는 규칙은 정해져 있다(첫 열 값으로 행을 찾고, 백틱 안의 값을 쓴다). 테스트가 spec_version 2·3·4의 템플릿에서 같은 결과를 얻는지 확인한다.

### 23.4 검사

#### 23.4.1 범위

| 옵션 | 검사할 커밋 |
|---|---|
| (없음) | 마지막 `gate/*` tag 이후. tag가 없으면 처음부터 |
| `--since <커밋>` | 그 커밋 이후 |
| `--task <Task>` | 그 task에 관련된 커밋: `Task` trailer나 scope가 그 Task인 커밋, `Approve`·`Next`에 그 Task가 있는 커밋, 그 task 카드 파일을 바꾼 커밋, 그 커밋들을 `Applies`로 가리키는 반영 커밋. V5(지금 상태)는 이 커밋들이 바꾼 문서의 위반만 세고, 나머지는 건수만 알린다 (v0.8.0, 실사용: 다른 task 몫의 기존 위반이 연습용 ideation M1-T4의 완료 기준 "lg verify 위반 없음"을 막았다) |
| `--all` | 처음부터 |

문서 형식(§23.4.6)은 범위와 상관없이 지금 상태를 본다. 반영 누락(P1)은 검사하지 않는다(`session-check`가 세션마다 알린다).

#### 23.4.2 V1 — 신원과 타입 (P2, P3, P4)

범위의 모든 커밋에 대해:

- 작성자 이메일로 역할을 정한다(사람, 에이전트, 등록 안 됨). 등록 안 된 작성자는 위반이다.
- 메시지를 hook의 `check(text, check_author=False)`로 검사한다(형식, 타입, trailer).
- `Actor`가 작성자 역할과 같아야 한다. 사람 전용 타입은 사람, 에이전트 전용 타입은 에이전트.
- 부모가 둘 이상인 커밋(병합)의 작성자가 에이전트면 위반이다.
- hook이 검사하지 않는 커밋(`Revert`, `fixup!` 등)은 hook과 같이 건너뛴다.

#### 23.4.3 V2 — 사람 몫의 상태 전이 (G4)

에이전트 커밋마다, 바뀐 `.md` 파일의 frontmatter `status`를 커밋 전후로 비교한다.

| 문서 유형 | 사람 몫의 전이 |
|---|---|
| task-card | `draft →` 무엇이든, `in-review → closed / revise / redirected` |
| decision | `→ confirmed` |
| milestone | `planned → active`, `active → closed` |

- 이런 전이가 있으면 그 커밋에 **근거**가 있어야 한다: `Applies`(또는 v0.2 방식의 `Refs`)가 가리키는 사람 커밋이 그 전이를 정한다(`plan`의 `Approve`, `gate`의 `Verdict`·`Next`·`Milestone-Verdict`, `decide`·`gate`의 `Decisions`, `respond`). 근거가 없거나 근거가 그 전이를 정하지 않으면 위반이다.
- `draft →` 무엇이든인 이유: v0.2에서 에이전트가 승인을 반영하며 `draft → in-progress`로 한 번에 바꾼 예가 있다(근거 `Refs`가 있으면 위반이 아니다).
- 새로 만든 문서(전 상태 없음)는 보지 않는다.

#### 23.4.4 V3 — review `## 응답` (G5)

에이전트 커밋이 `reviews/` 문서의 `## 응답` 섹션 내용을 바꾸면 위반이다. 대화 경로(`gate-conversation`)에서도 응답이 담긴 커밋은 사람의 커밋이므로 예외가 없다. 반영 도구가 review를 `reviews/closed/`로 옮기는 것(내용 그대로)은 해당하지 않는다(이름 바꾸기를 따라가서 비교한다).

#### 23.4.5 V4 — 규칙 파일 (G7)

에이전트 커밋이 보호 경로(`specs/`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.lg/`)의 파일을 추가·수정·삭제하면 위반이다. task 카드의 "범위 › 포함"이 이를 허용했을 수도 있지만(우선순위 2), 그 문장은 자연어라 코드로 판정하지 않는다. 그래서 위반으로 보고하되, 그 커밋의 Task와 카드의 "범위 › 포함" 원문을 함께 보여 준다. 사람이 보고 허용된 것이면 넘어간다.

#### 23.4.6 V5 — 문서 형식

Git이 추적하는 frontmatter가 있는 모든 `.md`에 대해 지금 상태를 본다.

- frontmatter가 YAML로 읽힌다.
- `spec_version`이 정확한 형식이고 프로젝트의 spec_version 이하다. 프로젝트보다 낮은 문서는 위반이 아니라 알림이다(갱신 전 문서).
- `type`이 conventions의 `type` 표에 있다.
- `status`가 있으면 그 유형의 상태값 어휘 안에 있다.
- 완성 사양이 있는 유형(`task-card`, `review`)은 사양의 필수 필드가 모두 있고, `id`가 파일 이름과 같다.

#### 23.4.7 점검표 (판정하지 않음)

`--task <Task>`일 때 덧붙인다.

- 카드의 `## 완료 기준` 항목들(체크 여부 포함).
- 그 task의 가장 최근 게이트 요청서(`reviews/*/<Task>_gate-NN.md`)의 "완료 기준 점검" 표에서, "근거" 칸에 적힌 경로가 저장소에 실제로 있는지. 경로로 보는 것은 `/`가 있거나 확장자로 끝나는 토큰이고, 섹션 인용(`## …`), 공백이 든 문구, URL, ID(`D1.1`)는 뺀다. `#앵커`와 `:줄 번호`는 떼고, 파일 이름만 쓴 것(`M0-T5.md`)은 저장소 어디에든 있으면 있다.
- 범위의 커밋이 바꾼 파일 목록(카드의 "범위"와 나란히 보도록).

충족 여부는 사람이 게이트에서 판정한다.

### 23.5 명령

```
lg verify [--task TASK | --since REV | --all]
```

출력 예:

```
lg verify: 마지막 게이트 이후 커밋 12개 (abc1234..HEAD)

✗ V2 사람 몫의 상태 전이 (G4)  1건
    3f2a1c9 task(M1-T2): start
      plan/milestones/M1/tasks/M1-T2.md: status draft → in-progress, 근거 없음
✓ V1 신원과 타입
✓ V3 review 응답
✓ V4 규칙 파일
✓ V5 문서 형식 (알림 2: 갱신 전 문서 spec_version 3)

위반 1건.
```

| 종료 코드 | 의미 |
|---|---|
| 0 | 위반 없음 (알림은 있을 수 있음) |
| 1 | 예기치 못한 오류 |
| 2 | labgate 프로젝트가 아님, 지원하지 않는 spec_version, 범위 옵션 오류 |
| 3 | 위반 있음 |
| 4 | Git 오류 |

### 23.6 `lg commit` 연결

검사 로직은 모듈 하나(`verify.py`)에 두고, `lg verify` 명령과 `lg commit`이 같이 쓴다. 사람은 게이트를 판정할 때 반드시 `lg commit`을 지나므로, 따로 기억하지 않아도 승인 직전에 한 번 보게 된다. 에이전트는 `lg commit`을 쓸 수 없지만 `lg verify`는 읽기 전용이라 직접 실행해 게이트 요청 전에 스스로 점검할 수 있다.

- **언제:** `lg commit`의 확인 단계(커밋 / 편집기로 수정 / 취소를 묻기 전). 메시지의 타입이 `gate`일 때만, 그 `Task` trailer로 `--task` 범위를 검사한다. 초안 모드와 작성 모드 모두.
- **보여 주는 것:**
  - 위반이 없으면 한 줄: `✓ lg verify --task M1-T2: 위반 없음`.
  - 위반이 있으면 규칙별 건수와 커밋(최대 5줄)을 메시지 위에 보여 주고 `자세히: lg verify --task M1-T2`를 안내한다.
  - 점검표 요약: 완료 기준 체크 수(`4/5`), 게이트 요청서의 근거 경로 중 없는 것.
- **막지 않는다(사람 우선).** 위반이 있어도 사람이 커밋 / 편집 / 취소 중에서 고른다. 선택지 문구에 위반이 있음을 함께 적는다(예: `커밋 (위반 1건 있음)`).
- 검사가 실패하면(예: 문서를 읽지 못함) 그 사실만 한 줄로 알리고 커밋 흐름은 계속한다. 검사는 판정을 돕는 정보일 뿐 커밋의 조건이 아니다.
- `--no-verify` 같은 끄는 옵션은 두지 않는다. 막지 않으므로 끌 이유가 없다.

### 23.7 문서와 테스트

- 명령 설명서 `docs/cli/lg-verify.md`, `docs/cli/lg-commit.md`(게이트 확인 단계). 작업 설명서: `judge-gate.md`(`lg commit`이 보여 주는 검사 결과를 읽는 법, 자세히 보려면 `lg verify --task`), `daily-loop.md`(에이전트에게 게이트 요청 전 `lg verify`를 시킬 수 있음), `mistakes.md`(위반을 찾았을 때).
- 테스트: 각 위반을 일부러 만든 프로젝트(hook을 `--no-verify`로 우회해 사람 전용 타입을 에이전트로, 근거 없는 상태 전이, 응답 수정, 규칙 파일 수정, 문서 형식 오류)에서 검출, 정상 흐름(승인 → 반영 → 착수 → 게이트 요청 → 판정 → 반영)은 위반 0, `Refs` 근거(v0.2 방식) 인정, 이름 바꾸기를 따라간 V3, 범위 옵션, spec_version 2·3·4 프로젝트(tag로 생성)의 규칙 읽기, `lg commit`의 `gate` 확인 단계에 결과 표시(위반 없음 한 줄, 위반 요약, 막지 않음, 검사 실패 시 흐름 계속), `gate`가 아닌 커밋에서는 검사하지 않음.
- 실사용: 연구 프로젝트의 지금 이력에 돌려, 위반이 있으면 실제 위반인지 오탐인지 확인한다.

### 23.8 알려진 한계

- **G2·P5 (사람의 변경을 에이전트 커밋에 넣음):** 커밋된 뒤에는 그 변경이 원래 누구 것이었는지 알 수 없다. 사후 검사하지 않는다.
- **G3 (대기 상태에서 커밋):** 대기 상태 파일(`.lg/pending/`)은 Git에 없으므로 과거 시점을 재구성할 수 없다. 다음 마이너에서 hook으로 막는다.
- **이력 재작성(P4):** 저장소 안의 이력만으로는 재작성 여부를 알 수 없다(원격과 비교해야 한다).
- **범위·예산(G9):** 판단이 필요하다. 점검표로만 보인다.

### 23.9 결정된 사항

1. **별도 명령 `lg verify`와 `lg commit` 연결을 모두 둔다.** 검사 로직은 하나(`verify.py`)다. `lg commit`은 `gate` 확인 단계에서 요약을 보여 주고 막지 않는다.
2. **기본 범위는 마지막 `gate/*` tag 이후**다. tag가 없으면 처음부터 본다.
3. **V4(규칙 파일)는 카드 범위의 허용 여부를 판정하지 않는다.** 위반으로 보고하되 카드의 "범위 › 포함" 원문을 함께 보여 준다.
4. **갱신 전 문서(문서 spec_version < 프로젝트)는 알림**이다.
5. **반영 누락(P1)은 검사하지 않는다.** `session-check`가 세션마다 알린다.
6. 다음 마이너 버전(spec_version 5)에서 할 일: hook에서 커밋 순간 막기(G3, G7, 가능하면 G4·G5), `task-gate` 절차에 "`lg verify --task` 통과" 넣기. 검사 로직은 그때 hook에서도 쓸 수 있게 짠다(표준 라이브러리만 쓰는 부분을 분리).

## 24. `lg status`, `lg answer` (터미널에서 판단하기)

v0.5.0, spec_version 5.

### 24.1 목적

`lg init` 이후에도 사람이 **터미널 두 개(`lg`와 에이전트)만으로** 연구를 진행할 수 있게 한다. 이를 위해 사람이 판단해야 할 일을 찾고, 읽고, 답하는 과정을 명령으로 만든다.

v0.4.1까지 실사용(ssm-latent-reasoning M0-T0 게이트)에서 겪은 불편:

| 불편 | 원인 |
|---|---|
| 무엇을 판단해야 하는지 알려면 `reviews/open/`, `STATUS.md`, 카드를 직접 열어야 한다 | 판단 대기 목록을 사실에서 모아 주는 도구가 없다. `STATUS.md`는 에이전트가 쓰는 문서다 |
| 같은 판정을 두 번 쓴다: 요청서 `## 응답`에 글로, `lg commit`에서 trailer로 | 응답 문서와 커밋 trailer를 따로 만든다. 둘이 어긋나도 아무도 모른다 |
| 다음 task 넷을 함께 승인하려면 따로 `plan`+`Approve` 커밋이 필요하다는 것을 사람이 알아야 한다 | `Next`에는 Task 하나만 쓴다 |
| "M0 active 전환에 `plan` 커밋이 필요하다"는 에이전트의 틀린 안내를 걸러 낼 수 없었다 | 판정이 만들 상태 변화를 판정 전에 보여 주는 곳이 없다 |
| 카드의 완료 기준이 0/7 체크인데 요청서 표에는 모두 ✓다 | 절차 task-gate에 카드 체크 단계가 없다 |

| 명령 | 누가 | 하는 일 |
|---|---|---|
| `lg spec adopt` | 사람 (터미널에서만) | 에이전트가 쓴 사양 초안을 stub 사양에 합쳐 `spec` 커밋으로 확정한다 (§24.8) |
| `lg status` | 사람, 에이전트 (읽기만) | 사람이 할 일, 에이전트 몫, 진행을 파일과 이력에서 모아 보여 준다 |
| `lg answer [ID]` | 사람 (터미널에서만) | 열린 review를 보여 주고 판정을 한 번 묻는다(결정 ID면 그 결정을 확정한다, §24.4.5). 그 답으로 `## 응답`, frontmatter, 사람 커밋을 **한 번에** 만든다. 판정이 만들 상태 변화를 먼저 보여 준다 |

요청서에 직접 쓰는 길(문서 경로)과 대화로 판정하는 길(절차 gate-conversation)은 그대로 둔다. `lg answer`는 세 번째 길이고, 안내는 이것을 기본으로 한다.

### 24.2 원칙

- **사실에서 모은다.** `lg status`는 `STATUS.md`를 읽지 않는다. frontmatter, `.lg/pending/`, 커밋 이력에서 계산한다.
- **규칙의 원본은 프로젝트다 (§23.3).**
  - 판정이 만들 상태 변화는 프로젝트의 `scripts/apply-human-commits --preview`가 계산한다(§24.5.4). 그래서 `lg`와 반영 규칙이 어긋나지 않는다.
  - 커밋 규약은 프로젝트의 hook을 따른다.
- **`## 응답`은 사람만 쓴다 (G5).** `lg answer`는 `lg commit`처럼 표준 입력·출력이 모두 터미널일 때만 쓴다. 그래서 에이전트는 실행할 수 없다(Claude Code deny도 있다). 응답은 사람이 썼다는 것을 도구가 보장한다.
- **사람이 우선이다.** 사람이 이미 손댄 응답이나 stage는 덮어쓰지 않는다. 멈추고 알린다.
- **확인 전에는 쓰지 않는다.** 취소하거나 반영할 수 없는 판정이면 아무것도 바뀌지 않는다.

### 24.3 `lg status`

```
lg status [--json]
```

읽기만 한다. 사람과 에이전트 모두 실행할 수 있다. 종료 코드는 0이고, 프로젝트가 아니면 2.

| 묶음 | 항목 | 출처 | 안내 |
|---|---|---|---|
| 사람이 할 일 | 열린 gate·escalation review (`status: open`) | `reviews/open/*.md` frontmatter | `lg answer <ID>` |
| | 요청서에 응답을 쓰는 중 (커밋되지 않은 변경) | `git status` | `lg commit` |
| | 닫힌 review의 사본 (`reviews/closed/`에 같은 ID가 있음) | 파일 이름 | 내용을 확인하고 지우기 (`rm`) |
| | 사람 커밋 대기 (초안) | `.lg/pending/COMMIT_MSG` | `lg commit` |
| | task 승인 대기: 현재 마일스톤에 진행 중인 task가 없고 draft 카드만 있음 (첫 task, 게이트에서 다음 task를 고르지 않았을 때). 사람의 다른 할 일이나 에이전트 몫이 있으면 보이지 않는다 | 카드 frontmatter | `lg commit --allow-empty` (타입 `plan`, Approve) |
| | 커밋되지 않은 내 변경 | `.lg/pending/HUMAN_FILES` | `lg commit` |
| 에이전트 몫 | 반영되지 않은 사람 커밋 | 프로젝트의 `scripts/apply-human-commits --check` | 다음 세션에서 자동 |
| | 반영했지만 커밋 전 | `scripts/apply-human-commits --tidy` | 다음 세션에서 자동 |
| 진행 | 현재 마일스톤(active인 첫 것, 없으면 planned인 첫 것), 그 task의 상태별 목록, proposed·discussing 결정 | frontmatter | — |

- `HUMAN_FILES`가 없으면 커밋되지 않은 변경의 수만 "진행"에 적는다(요청서는 빼고). 누구의 것인지는 `session-check`가 기록한다.
- 사람이 할 일이 없고 에이전트 몫만 있으면 "에이전트 세션을 시작하면 이어서 진행합니다"로 끝난다.
- spec_version 2 프로젝트에는 반영 도구가 없으므로 에이전트 몫은 알 수 없다고 적는다.
- 한글이 섞인 열은 터미널 칸 수(한글 두 칸)로 맞춘다.
- `lg status`를 `session-check`에 연결하지 않는다. `session-check`는 `lg` 없이(표준 라이브러리, Python 3.9) 도는 것이 원칙이고, 겹치는 정보는 이미 있다.

### 24.4 `lg answer`

```
lg answer [REVIEW_ID] [--no-tag]
```

#### 24.4.1 전제

`REVIEW_ID`를 생략하면 다음과 같이 고른다.

- 열린(`open`) review가 하나면 그것을 쓴다.
- 여럿이면 목록에서 고른다.
- 없으면 코드 3으로 끝난다.

터미널과 사람 신원 검사는 `lg commit`과 같다(§18.2 2–3, `commit.require_human_terminal`). 추가로 다음을 확인한다.

| 확인 | 실패 시 |
|---|---|
| `reviews/closed/`에 같은 ID가 없다 | 코드 3. 남은 사본이다(반영 도구가 옮긴 뒤 편집기가 다시 저장한 경우 등). 지우라고 안내. 고를 목록에서도 뺀다 |
| 사람 커밋 대기 상태가 아니다 | 코드 3. 대화로 판정해 초안이 있으면 `lg commit`으로 확정하라고 안내 |
| review가 `open`이다 | 코드 3. `answered`면 `lg commit` 안내 |
| 그 review에 커밋되지 않은 변경이 없다 | 코드 3. 사람이 응답을 쓰는 중이다. 덮어쓰지 않고 `lg commit`을 안내 |
| review 외의 stage된 변경이 없다 | 코드 2 (응답 커밋에 다른 변경이 섞이지 않게) |
| `kind`가 gate·escalation이고 `task`가 Task ID 형식이다 | 코드 2 |

#### 24.4.2 흐름

1. **보여 주기.** review에서 `## 응답` 위의 에이전트 섹션을 rich Markdown(typer와 함께 설치됨)으로 렌더링한다.
   - gate면 `lg verify --task <Task>`의 요약(§23.6의 `summary_for_commit`: 위반 수, 완료 기준 체크 수, 근거 경로)을 붙인다.
   - 터미널보다 길면 pager(`pydoc.pager`: `MANPAGER`, `PAGER`, 없으면 `less`)로 연다. 색 코드는 pager가 해석할 때만 보낸다: `less`면 `LESS`에 `-R`을 더하고, 다른 pager면 색 없는 글을 보낸다. 링크는 터미널 하이퍼링크 코드 대신 글로 보인다(실사용: 옵션 없는 `less`에서 `ESC[1m`, `ESC]8;…`이 그대로 보였다, v0.7.0).
2. **묻기** (§24.4.3, §24.4.4).
3. **메시지 만들기와 검사.** 만든 커밋 메시지를 프로젝트 hook으로 검사한다. 어긋나면 labgate 버그로 보고 코드 2.
4. **미리보기** (§24.5.4). 메시지마다 `scripts/apply-human-commits --preview`를 돌려 반영될 변화를 보여 준다.
   - 반영할 수 없는 판정이면 코드 3으로 멈춘다(아무것도 쓰지 않음).
   - spec_version 4 이하이거나 스크립트가 없으면 미리보기 대신 커밋할 trailer를 보여 주고 `lg upgrade`를 권한다.
   - gate 승인이면 만들 tag도 보여 준다.
5. **확인.** 응답 원문과 커밋 메시지를 보여 주고 고른다: 커밋 / 편집기로 응답 수정 / 취소.
   - 편집기는 `lg commit`과 같다(`git var GIT_EDITOR`).
   - 고친 응답을 다시 검사한다: 첫 줄이 `## 응답`, 하위 섹션 넷이 모두 있음, 판정이 비어 있지 않음, gate 판정이 고른 것과 같음(판정을 바꾸려면 취소하고 다시 한다. trailer와 어긋나지 않게).
6. **쓰기와 커밋.**
   - review의 `## 응답` 절을 바꾼다.
   - frontmatter에 사람 몫 필드를 채운다(review.spec §5): `status: answered`, `answered`, `verdict`(gate만), `source: document`, `updated`. 키가 없으면 더한다.
   - review 하나만 stage하고 첫 커밋을 만든다.
   - tag를 만든다(`--no-tag`면 생략). `lg commit`의 `_tag`를 쓴다.
   - 이어지는 커밋(`plan`, `decide`)은 빈 커밋이다. 실패하면 첫 커밋은 그대로 두고 코드 4로 끝내며, 남은 메시지를 보여 준다.
7. **안내.** `lg commit`의 커밋 뒤 안내(§18.2 9)와 같다.

#### 24.4.3 gate 질문과 커밋

| # | 질문 | 선택지·기본값 | 응답 | trailer |
|---|---|---|---|---|
| 1 | 판정 | approve / revise / redirect | `### 판정` | `Verdict` |
| 2 | 다음 task (approve일 때) | 같은 마일스톤의 `draft` 카드 여러 개. 요청서의 `proposed_next`를 미리 골라 둔다 | `### 다음 task 승인` (없으면 "없음") | 첫째(`proposed_next`를 골랐으면 그것)는 `Next`, 없으면 `Next: none`. 나머지는 이어지는 `plan` 커밋의 `Approve` |
| 3 | 마일스톤 판정 (approve이고, 다음 task를 고르지 않았고, 그 마일스톤에 닫히지(`closed`·`redirected`) 않은 다른 task가 없을 때만) | 하지 않음 / go / nogo / conditional | `### 판정`에 `마일스톤 <M>: <판정>` 한 줄 | `Milestone-Verdict` |
| 4 | 확정할 결정 | **요청서 `decisions`에 있고 proposed·discussing인 결정만**, `ID 제목 (상태)`로 보여 주고 미리 골라 둔다. 요청이 없으면 묻지 않는다(실사용: 요청하지 않은 제안 결정 7개가 ID만으로 나와 무엇을 묻는지 알 수 없었다). 그 밖의 결정은 `lg answer <D-ID>`(§24.4.5). 고른 결정마다 확정 내용 한 줄 | `### 확정 결정` (`- D0.1: 내용`) | `Decisions` |
| 5 | 코멘트 | 한 줄. revise·redirect면 필수 | `### 코멘트` (없으면 "없음") | — |

- 헤더: `gate(<Task>): <verdict>` + (`, next <Next>`, 72자를 넘으면 뺀다).
- trailer 순서: `Actor`, `Task`, `Verdict`, `Source: document`, `Next`, `Milestone-Verdict`, `Decisions`, `Review: <ID>`. `Review`는 hook이 허용하고, `apply-human-commits`가 이것으로 닫을 review를 찾는다.
- 다음 task가 둘 이상이면 `plan: approve <나머지>` + `Approve`. 72자를 넘으면 `plan: approve <n> tasks after <Task> gate`.
- 다음 task를 여럿 승인하려고 `Next`에 목록을 허용하지 않는다. 커밋 규약을 그대로 두고, 두 커밋은 도구가 만든다.

#### 24.4.4 escalation 질문과 커밋

| # | 질문 | 선택지 | 응답 |
|---|---|---|---|
| 1 | 선택 | 요청서 `## 선택지`의 항목 + "직접 입력". 항목은 `### 제목`들, 없으면 맨 바깥 목록 항목(`-`, `*`, `1.`)의 첫 줄(굵게 표시는 뗀다). 항목이 없으면 직접 입력만 | `### 판정` |
| 2 | 확정할 결정 | gate의 4와 같음 | `### 확정 결정` |
| 3 | 코멘트 | 한 줄 | `### 코멘트` |
| 4 | 커밋 요약 | 기본값은 고른 선택지의 앞부분 (헤더 72자 안) | — |

- 커밋: `respond(<Task>): <요약>` + `Task`, `Source: document`, `Review: <ID>`. `### 다음 task 승인`은 "없음", frontmatter `verdict`는 `null` 그대로.
- 결정을 골랐으면 이어서 빈 `decide` 커밋을 만든다. 결정이 하나면 `decide(<D>): confirm`, 여럿이면 `decide: confirm <D, …>`. 본문은 `<review ID> 응답에서 확정.`, trailer는 `Decisions`, `Source: document`. `respond` 커밋에 `Decisions`를 허용하지 않는 지금 규약을 그대로 쓴다.

#### 24.4.5 결정 확정 (`lg answer <D-ID>`)

게이트와 별개로 결정 하나를 확정한다(결정 ID가 hook의 `DECISION_ID_RE`에 맞으면 이 모드).

- 전제:
  - 결정 문서가 `decisions/<ID>_*.md` 하나다.
  - `status`가 `proposed`나 `discussing`이다.
  - 사람 커밋 대기 상태가 아니다.
  - 결정 문서에 커밋되지 않은 변경이 없다.
  - stage된 변경이 없다.
  - 어긋나면 코드 3(stage는 2).
- 흐름: 결정 문서를 보여 준다 → 묻는다(확정 내용 한 줄(필수), 근거·코멘트(선택), 커밋 요약(기본값 `confirm <확정 내용>`)) → 미리보기 → 커밋 / 취소.
- 커밋: 빈 커밋 `decide(<ID>): <요약>`. 본문은 `확정: <내용>`(+ 빈 줄과 코멘트), trailer는 `Decisions: <ID>`, `Source: document`.
- 결정 문서는 고치지 않는다. 결정 문서의 양식은 프로젝트가 채우는 stub 사양(`decision`)이라 labgate가 구조를 모른다. 확정 내용은 커밋 본문에 남고, 상태(`confirmed`)와 결정 목록은 다음 세션에 반영 도구가 바꾼다. 절차 gate-apply의 "다음 할 일" 표가 확정 내용의 위치를 알려 준다.

### 24.5 생성되는 프로젝트의 변경 (spec_version 5)

`lg status`와 `lg answer`는 지금의 review 양식과 trailer만으로 동작한다(spec_version 2–4에서도 쓸 수 있다). 다만 아래는 생성되는 파일을 바꿔야 해결되므로 spec_version을 5로 올린다. 4 → 5는 기본 갱신만으로 된다(`MIGRATIONS[4] = ()`, §22.6).

#### 24.5.1 절차 task-gate (부록 B)

- 1단계: 충족한 완료 기준은 카드에서 `- [x]`로 바꾼다.
- 3단계(새로): `lg`가 있으면 작업을 커밋한 뒤 `lg verify --task <Task>`를 실행한다. 고칠 수 있는 위반은 고치고, 이미 커밋되어 고칠 수 없는 것은 요청서 "예상과 달랐던 점"에 적는다.
- 마지막 단계(보고): 판정하는 방법으로 `lg answer <review id>`를 쓴다(요청서에 직접 쓰거나 대화로 판정해도 된다).

#### 24.5.2 절차 escalate (부록 B)

- 보고 단계: 응답하는 방법으로 `lg answer <review id>`를 쓴다.

#### 24.5.3 `.claude/settings.json`, `CLAUDE.md` (부록 A.4, A.5)

- deny에 `Bash(lg answer *)`를 더한다. 터미널 검사로 이미 막히지만 `lg commit`과 같게 둔다.
- `CLAUDE.md`의 차단 목록에 `lg answer`를 더한다.

#### 24.5.4 `scripts/apply-human-commits --preview` (부록 C)

- 표준 입력으로 아직 커밋하지 않은 사람 커밋 메시지 하나를 받는다. 반영 대상이면 `미리보기: <헤더>`와 반영 계획(`Plan.log`의 줄들)을 출력하고, 아무것도 쓰지 않는다. 반영 대상이 아니면 `반영할 것이 없습니다: <헤더>`.
- 계획은 반영과 같은 `plan_for`로 만든다. 해시 자리에는 `(새 커밋)`을 쓴다.
- 반영할 수 없으면 코드 1과 `✗ 이 커밋은 반영할 수 없습니다: <이유>`. 예: 카드가 `in-review`가 아님, 다음 카드가 `draft`가 아님.

#### 24.5.5 로드맵 표의 마일스톤 상태 (부록 C, 절차 gate-apply)

- 실사용: M0-T0 승인 뒤 마일스톤 문서는 `active`가 됐지만 `plan/roadmap.md`의 "마일스톤" 표는 `planned`로 남았다.
- `apply-human-commits`가 마일스톤을 바꿀 때(`planned → active`, `active → closed`) 로드맵 표에서 그 행의 상태 칸도 바꾼다(`Plan.milestone`).
- G6은 에이전트가 로드맵을 바꾸지 못하게 하므로, 절차 gate-apply의 특별 규칙에 G6을 더한다: 도구가 바꾼 상태 칸만 커밋하고 로드맵의 다른 내용은 바꾸지 않는다. `AGENTS.md`의 절차 표도 `G4, G6`.

#### 24.5.6 사양 초안 (부록 B.2 conventions §8, stub 템플릿, A.4, A.5)

- conventions §8: 사양 보완은 `notes/`에 사양 하나당 파일 하나로, 그 사양의 번호 붙은 절만 쓴다. 사람이 `lg spec adopt`로 확정한다(§24.8).
- stub 안내 문단: "확정은 사람이 한다(`lg spec adopt`, `spec` 커밋)".
- deny에 `Bash(lg spec *)`, `CLAUDE.md`의 차단 목록에 `lg spec`.

#### 24.5.7 README 템플릿 (부록 A.1)

- "사람이 하는 일"에 `lg status`, `lg answer`를 쓴다.
- README는 연구 문서로 분류되므로(§22.3) 기존 프로젝트에서는 `lg upgrade`가 바꾸지 않는다. 새 프로젝트에만 들어간다.

### 24.6 문서와 테스트

- 명령 설명서: `docs/cli/lg-status.md`, `docs/cli/lg-answer.md`, `README.md` 표, `project-scripts.md`의 `--preview`. 명령 설명서의 종료 코드 표는 그 명령이 쓰는 코드만 적는다(0, 1, 130은 모두에 있다).
- 작업 설명서:
  - `judge-gate.md`, `respond-escalation.md`: `lg answer`가 방법 1이다. 요청서에 직접 쓰는 방법과 대화는 방법 2·3이다.
  - `daily-loop.md`: `lg status`
  - `approve-task.md`: 다음 task 여럿
  - `upgrade.md`: spec_version 5
- 루트 `README.md` "사용": 터미널 A의 명령, 한 task의 흐름, 사람이 쓰는 명령 표.
- 테스트 (`tests/README.md`의 계층):

| 계층 | 파일 | 내용 |
|---|---|---|
| unit | `test_answer_parts.py` | 응답 만들기(하위 섹션 순서, "없음"), 고친 응답 검사, 선택지 읽기, 커밋 메시지(헤더 줄이기, plan·decide 커밋) |
| tools | `test_apply.py` | `--preview`: 변화 출력, 아무것도 쓰지 않음, 반영 불가 → 1, 반영 대상 아님 (Python 3.9 포함) |
| commands | `test_status.py` | 새 프로젝트, 열린 gate, 응답 작성 중(두 번 세지 않음), 초안·내 변경, 반영 대기와 반영 후 커밋 전, 결정과 `--json`, spec_version 2 |
| commands | `test_answer.py` | approve(다음 task 여럿 → plan 커밋, tag, 응답·frontmatter), 미리보기 = 실제 반영 결과, revise 코멘트 필수, 마지막 task의 마일스톤 판정, 결정 확정, 고친 응답 재검사, 취소, 반영할 수 없는 판정, escalation(respond, decide), 전제 실패, spec_version 4 프로젝트(v0.4.0 tag로 만듦, 미리보기 없음) |
| unit | `test_spec_merge.py` | 사양 초안 합치기: 초안의 절만 바뀜, 초안 frontmatter 무시, 거부(TODO가 남음, 번호 없는 절, 없는 절, 절 없음) |
| commands | `test_spec.py` | `lg spec adopt`: 합치기·색인·커밋, 여러 초안과 frontmatter의 이름, 거부, 취소, 덮어쓰지 않음, 터미널 |
| commands | `test_answer.py` (결정) | `lg answer D0.1`: 확정 커밋과 본문, 미리보기, 반영 뒤 confirmed, 거부 |
| contract | `test_templates.py` | 절차의 `- [x]`·`lg verify`·`lg answer` 안내, conventions §8의 `lg spec adopt`, deny |
| contract | `test_releases.py` | spec_version 4 해시표 유지, 5는 릴리즈 뒤 동결 |

### 24.7 결정된 사항

| 질문 | 결정 | 이유 |
|---|---|---|
| 명령 이름 | `lg answer` | `review`는 에이전트 전용 커밋 타입 `review(...)`(게이트 요청)와 이름이 같다. `judge`는 에스컬레이션 응답에 맞지 않는다. `answer`는 문서의 `## 응답`과 같은 말이다 |
| spec_version 5 범위 | §24.5 전부 | 미리보기가 실사용의 혼란을 직접 막고, 카드 체크는 실제로 겪은 문제다. 열린 세션 자동 감지 hook(UserPromptSubmit)과 커밋 순간 G3·G7 차단은 에이전트 쪽 강제라 성격이 다르고 근거가 적어 다음 마이너로 미룬다 |
| 다음 task 여럿 | gate + `plan` 두 커밋 | 커밋 규약을 바꾸지 않는다 |
| escalation에서 결정 확정 | 이어지는 `decide` 커밋 | `respond`에 `Decisions`를 허용하지 않는 지금 규약 그대로 |
| `lg status`와 `session-check` | 연결하지 않음 | `session-check`는 `lg` 없이 돈다 |
| 결정 따로 확정 | `lg answer <D-ID>`. 결정 문서는 고치지 않고 확정 내용은 커밋 본문에 | 결정 문서의 양식은 프로젝트가 채우는 stub 사양이다 |
| 사양 초안 확정 | v0.5.0에 `lg spec adopt` (§24.8) | 연구 프로젝트에 확정을 기다리는 초안 9종이 있다. 미루지 않기로 했다 |

### 24.8 `lg spec adopt` (사양 초안 확정)

```
lg spec adopt DRAFT... [--name NAME]
```

실사용: M0-T0에서 에이전트가 stub 사양 9종의 초안(§3–§7)을 `notes/spec-drafts/`에 썼다. 확정하려면 사람이 초안을 `specs/doc-types/`로 옮기며 stub의 frontmatter·§1–§2와 합치고, `status`를 바꾸고, `specs/README.md` 표를 고쳐야 했다.

- **사람만, 터미널에서만.** 규칙 문서는 사람만 고친다(G7). `lg commit`과 같은 검사를 하고, Claude Code deny도 있다.
- **이름:**
  - 초안 frontmatter의 `id`, 없으면 파일 이름(`catalog.md`, `catalog.spec.md`), 또는 `--name`(초안 하나일 때).
  - stub 사양 11종(`labgate.stubs.STUBS`) 중 하나여야 한다.
  - 한 번에 같은 사양에 초안 둘을 줄 수 없다.
- **합치기 (`spec.merge`):**
  - 초안의 frontmatter와 첫 `## N.` 앞부분(초안 제목)은 버린다.
  - 대상의 절 가운데 초안에 있는 번호의 절만 내용을 바꾼다. 절 제목은 대상의 것을 쓴다.
  - 초안에 번호 없는 `## ` 절이 있거나, 대상에 없는 번호의 절이 있으면 오류다(내용을 소리 없이 버리지 않는다).
  - 합친 뒤 비어 있는(`> TODO`) 절이 남으면 오류다. `complete`라고 표시된 불완전한 사양이 생기지 않게 하기 위해서다.
  - 머리 부분: `status: stub` → `complete`, 제목의 ` (stub)`과 stub 안내 문단(`> 이 사양은 아직 공통 구조만 있다.`로 시작)을 지운다. `spec_version`은 그대로 둔다.
  - 이미 `complete`인 사양에도 쓸 수 있다(개정).
- **색인:** `specs/README.md`의 사양 표에서 그 행의 마지막 칸 `stub` → `complete`.
- **전제:**
  - 사람 커밋 대기 상태가 아니다(코드 3).
  - 대상 사양·색인에 커밋되지 않은 변경이 없다(코드 3, 덮어쓰지 않음).
  - stage된 변경이 없다(코드 2).
- **확인과 커밋:**
  - 파일마다 unified diff(지금 → 확정)와 메시지를 보여 주고 고른다: 커밋 / 취소. 확인 전에는 쓰지 않는다.
  - 커밋: 대상들과 색인만 stage한 `spec: adopt <이름…> spec(s)`. 72자를 넘으면 `spec: adopt <n> doc-type specs`. 본문은 `초안: <경로…>`.
  - 초안 파일은 지우지 않는다.
  - 커밋 뒤 안내는 `spec` 커밋의 것(§18.2 9): 열린 에이전트 세션이 있으면 새로 시작한다.
- **`lg upgrade`와의 관계:** 채운 stub은 "사람이 채운 것"으로 보고 내용을 유지한다(§22.5). 그래서 확정한 사양은 갱신 때 덮어써지지 않는다.

## 25. 프로젝트 종류 (`--kind`)와 자료 가져오기

v0.6.0, spec_version 6.

### 25.1 목적

labgate의 구조(사람이 게이트에서 판정하고 에이전트가 그 사이를 수행한다, 결정·참고자료·사람 커밋)는 연구가 아닌 일에도 맞는다. 첫 대상은 **사업 제안서**다. 예: 제조기업의 AI 에이전트 구축 제안. 연구용 템플릿에 설정만 바꿔 쓰면 다음 두 가지가 어색하다.

- 용어가 맞지 않는다: 연구 질문, 가설, 실험, 문헌, 논문.
- 원고 폴더가 `paper/`다.

### 25.2 종류

| | `research` (기본) | `proposal` |
|---|---|---|
| 핵심 질문 | 연구 질문 | 제안 핵심 질문 (설정 필드는 같은 `research_question`) |
| 로드맵 절 | 가설, 공통 실험 원칙 | 제안 전략과 가정, 공통 작업 원칙 |
| 마일스톤 판정 | Go / No-go | 같은 값(`go`·`nogo`·`conditional`)에 뜻을 적는다: go = 다음 단계로 진행(마지막 마일스톤이면 제출), conditional = 보완 조건부 진행, nogo = 중단 |
| T0 카드 | 문헌 조사, 실험 코드 제외 | 자료 조사(고객 자료, 공개 자료, 사례), 제안서 본문·PoC 코드 제외 |
| 원고 폴더 | `paper/` | `deliverables/` (제안서 원고, 그림, 제출본) |
| `experiments/` | task별 실험 | task별 PoC·검증 |

- **같은 것:** 규칙(`AGENTS.md`의 원칙과 일반 규칙), 절차, 사양, 커밋 규약, hook, 생성 스크립트, 모든 `lg` 명령. 그래서 종류마다 다른 것은 Jinja 템플릿 일곱 개의 문구와 `.gitkeep` 하나뿐이다.
  - 문구가 바뀌는 템플릿: README, AGENTS의 프로젝트 줄, STATUS, FILEMAP, roadmap, milestone, T0 카드
  - 정적 문서(conventions §4, workflow §8)는 두 원고 폴더를 함께 적는다.
- **템플릿 분기:** 문자열이 아니라 불리언 `proposal`로 한다(§9의 잔여 문법 검사 규칙).
- **기록:** 종류는 `.lg/project.yaml`의 `project.kind`에 남는다. 생략하면 `research`다(spec_version 5 이하 프로젝트).
- **설정 필드 이름:** `research_question`을 그대로 쓴다. 바꾸면 설정 형식(`schema_version`)이 바뀌어야 하기 때문이다.

### 25.3 입력

- 설정 파일: `project.kind: research | proposal`.
- 명령: `lg init --kind proposal`.
  - 설정 파일에 `kind`가 없으면 명령의 값을 쓴다.
  - 설정 파일이 `research`가 아닌 다른 값을 정했는데 명령이 다른 값이면 오류(코드 2)다.
- 대화형: `--kind`가 없으면 처음에 묻는다("프로젝트 종류": 연구 / 제안서). 그다음 질문 문구가 종류를 따른다("핵심 연구 질문" / "제안 핵심 질문").
- 초기 커밋 헤더: `init: initialize <kind> project`.

### 25.4 원래 있던 파일은 init 커밋에 넣지 않는다

실사용: 자료가 이미 있는 폴더에 `--force`로 만들면 자료가 루트에 남았고, `git add -A`라서 init 커밋에 함께 들어갔다. 큰 파일이나 기밀 자료가 의도치 않게 이력에 남는다.

- init 커밋은 **생성한 파일만** stage한다(`git add -- <생성 경로…>`).
- 원래 있던 파일·폴더는 커밋하지 않은 채 남기고, 안내에 목록(앞의 5개)을 보여 준다: 정한 자리로 옮겨 커밋하거나 `.gitignore`에 넣는다.

### 25.5 `--import DIR`

- **검사:** 자료 폴더는 있어야 하고, 비어 있지 않아야 하며, 프로젝트 폴더 밖이어야 한다. 쓰기 전에 검사한다(코드 2).
- **복사:** init 커밋 뒤에 폴더 내용을 `notes/` 아래로 같은 구조로 복사한다. 같은 이름이 이미 있으면 건너뛰고 알린다. `.git`으로 시작하는 경로는 뺀다.
- **stage:** Git을 쓰면 복사한 파일을 stage만 한다. 첫 task 승인 커밋(`plan`+`Approve`)에 함께 들어가고, 이는 §5.4의 안내와 같은 흐름이다. init 커밋은 생성 파일만으로 남는다.
- **기밀:** 고객 자료처럼 다루는 정책이 있는 자료는 가져오기 전에 확인한다. 도구는 판단하지 않는다.

### 25.6 `lg upgrade`와 해시표

- 해시표의 변형 이름은 `kinds.variant(claude_code, kind)`다.
  - 연구는 spec_version 2부터 쓰던 이름(`claude_code`, `no_claude_code`) 그대로다. 그래서 옛 해시표와 맞는다.
  - 다른 종류는 앞에 종류를 붙인다(`proposal_claude_code`).
- `scripts/hash-templates.py`는 그 버전의 labgate가 `kind`를 알면 종류마다 변형을 만든다. spec_version 6부터 해당한다.
- `AGENTS.md` 정규화에 `- 제안 핵심 질문:` 줄을 더한다. 연구의 정규화는 바꾸지 않는다.
- `MIGRATIONS[5] = ()`: 5 → 6은 기본 갱신이다. spec_version 5 이하 프로젝트는 모두 연구다.

### 25.7 결정된 사항

| 질문 | 결정 | 이유 |
|---|---|---|
| 옵션 이름 | `--kind` | 종류가 늘어도 같은 옵션. 설정 필드 `project.kind`와 같은 이름 |
| 시기 | v0.6.0. ideation은 v0.7.0으로 | 사용자가 제안서 프로젝트를 바로 시작한다(2026-10-04) |
| 정적 사양·절차 | 종류마다 나누지 않음 | 규칙은 같다. 연구 용어가 남는 곳(workflow의 실험 원칙 등)은 실제로 써 보고 v0.6.x에서 고친다 |
| `Milestone-Verdict` 값 | 그대로 (`go`·`nogo`·`conditional`) | hook·반영 도구·tag를 바꾸지 않는다. 뜻만 마일스톤 문서에 적는다 |

## 26. 아이디어 탐색 (`--kind ideation`, `lg init --from`, `lg ideas`)

v0.7.0, spec_version 7.

### 26.1 목적

**무엇을 연구(또는 제안)할지 정하는 단계**를 labgate 안으로 들인다. 그리고 그 결과를 실행 프로젝트로 넘기는 일을 명령으로 만든다.

지금 labgate는 방향이 정해진 뒤에 시작한다. `lg init`이 연구 질문과 마일스톤을 받고, M0이 그 방향을 검증·확정한다. 방향을 고르는 일(후보를 만들고 비교해 하나를 고르는 것)은 labgate 밖에서 일어나고, 그 판단은 기록되지 않는다.

### 26.2 근거: 지금까지 실제로 일어난 일

| # | 단계 | 일어난 일 | 기록 |
|---|---|---|---|
| 1 | init 전 발산 (labgate 밖, 2026-10-02) | 주제 전환("mamba 계열 × latent reasoning으로 다시 ideation"). 두 계보 정리, 결합 구조 A–D, 아이디어 후보 5개와 가설·최소 실험, "1→2→5" 뼈대 추천, 새로움 위험, 문헌 검색 | 대화에만 남았다. `notes/literature-review.md` 한 파일로 요약되어 `lg init` 설정을 손으로 만들었다. 후보 비교와 선택 이유는 커밋·결정으로 남지 않았다 |
| 2 | 원래 프로젝트 M0-T0 | 에이전트가 메모를 로드맵·결정(proposed)·문헌으로 옮겼다 | 커밋과 결정 문서 |
| 3 | 연습용 프로젝트 M0 (2026-10-04) | T1에서 가까운 선행 연구(Penelope 등)가 빈틈을 좁혔다. 사람이 대화로 "선택지 C(표현력)"를 지시했고, M0-T4에서 질문을 바꿔 D0.1을 확정했다. 새 질문의 핵심은 처음 메모의 **하위 가설 3(표현력)**이었다 | 결정 D0.1의 선택지 A/B/C와 이력. 그런데 처음 후보 목록과 연결되지 않아, "처음 후보 중 무엇이 살아남았나"는 사람이 기억해야 한다 |
| 4 | 새 프로젝트 `-v2` (2026-10-04) | 확정한 질문으로 처음부터 다시 시작했다. 설정 파일은 연습용 프로젝트의 `project.yaml`에서 손으로 옮겼고(연구 질문만), 마일스톤 제목은 예전 질문 기준이라 어긋났다 | `-v2`의 init 커밋. **두 프로젝트를 잇는 기록이 없다** |

빈틈:
- **발산 단계가 기록되지 않는다(1).** 첫 판단, 곧 "왜 이 방향인가"가 추적되지 않는다.
- **후보를 비교한 기준이 없었다(1).** "1→2→5 뼈대" 추천은 에이전트가 미리 정한 기준 없이 낸 판단이었다. 무엇을 근거로 어느 후보가 나은지 다시 따져 볼 수 없다.
- **후보가 ID를 갖지 않는다(1, 3).** 나중에 방향을 틀어도 "후보 3으로 돌아간다"고 말할 수 없다.
- **넘기는 일이 손으로 이루어지고 일부를 잃는다(4).**
  - 질문은 넘어갔지만 가설과 마일스톤은 따로 맞춰야 했다.
  - 근거 문헌 60편은 다시 등록해야 한다.
  - 출발점이 어디인지가 기록에 없다.

### 26.3 전체 그림

```
lg init my-idea --kind ideation          ← 탐색 주제만으로 시작 (연구 질문 없음)
  M0-T0 착수 계획 : 평가 기준(plan/criteria.md)을 사람이 확정하고 잠근다 ← 후보를 보기 전에
  M0 지형과 후보   : 문헌·사례 지형 → 후보(idea 문서 I1, I2 …) 생성 → 게이트
  M1 검증과 선택   : 잠근 기준으로 모든 후보를 근거와 함께 평가 → lg ideas 비교표
                     → 방향 결정(사람) → brief 작성 → 게이트(Milestone-Verdict go)
        │ brief.md (확정: 질문, 가설, 마일스톤, 근거 문헌, 버린 후보와 이유)
        ▼
lg init my-study --from ../my-idea [--kind research|proposal]
  설정(질문·가설·마일스톤) + references/ + notes/ideation-brief.md + 출발점 기록
```

- ideation도 다른 종류처럼 게이트, 결정, `lg answer`, `lg status`를 그대로 쓴다. 새 명령은 `--from` 하나다.
- 실행 프로젝트의 M0은 brief를 출발점으로 "검증·확정"을 한다. 처음부터 다시 조사하지 않는다.

### 26.4 `--kind ideation`

#### 26.4.1 입력

| 설정 | ideation에서 |
|---|---|
| `project.research_question` | **탐색 주제**. 질문이 아니어도 된다(예: "Mamba 계열 SSM의 메모리를 latent reasoning에 결합"). 설정 형식은 그대로라 같은 필드를 쓴다 |
| `milestones` | 생략하면 기본 두 개: M0 "지형 파악과 후보 생성", M1 "후보 검증과 방향 선택". 적으면 그대로 쓴다 |
| 그 밖 | 같다 |

대화형이면 "프로젝트 종류"에 "아이디어 탐색 (ideation)"이 더해지고, 질문 문구가 "탐색 주제"가 된다. 마일스톤 질문은 기본값을 보여 준다.

#### 26.4.2 생성 결과에서 다른 것

| | research | ideation |
|---|---|---|
| 핵심 칸 | 연구 질문 | 탐색 주제 |
| 로드맵 절 | 가설, 공통 실험 원칙 | 후보 목록(`ideas/` 색인), 선택 기준 |
| 후보 문서 | 없음 | `ideas/`: 후보마다 `ideas/I<n>_<slug>.md` + 색인 `ideas/index.md` (§26.5) |
| 평가 기준 | 없음 | **`plan/criteria.md`** (§26.6): 기본 기준, 사람이 고치고 잠근다 |
| 결과 문서 | task 결과, 마일스톤 보고 | 같음 + **`brief.md`** (§26.7, 루트) |
| 원고 폴더 | `paper/` | 없음 |
| T0 카드 | 문헌 조사, task 분해 | 지형 파악(문헌·사례), 후보 생성 계획, task 분해 |
| 마일스톤 판정 | Go / No-go | M1 판정 go = 방향 확정(brief 확정), nogo = 탐색 중단, conditional = 다시 탐색 |

같은 것: 규칙, 절차, 커밋 규약, hook, 결정(`decisions/`), 참고문헌(`references/`), `lg` 명령.

#### 26.4.3 에이전트가 하는 일 (절차)

새 절차를 만들지 않고, ideation의 task 카드와 사양으로 정한다(규칙을 늘리지 않는다).

- **기준 먼저:** ideation M0-T0의 범위에 "평가 기준 확정 제안"이 들어간다. 에이전트는 기본 기준을 프로젝트에 맞게 고칠 점을 제안하고, 사람이 게이트에서 확정한다. 확정하면 잠긴다(§26.6.2). 잠기기 전에는 후보를 평가하지 않는다.
- **평가:** M1에서 잠근 기준으로 모든 후보를 기준별로 매긴다(§26.6.3). 비교표와 순위는 `lg ideas`가 낸다(§26.6.4).
- **후보 만들기:** 후보마다 idea 문서를 쓴다. 사람이 대화로 낸 아이디어도 idea 문서로 옮긴다(`propose` 커밋). 버리는 후보는 지우지 않고 `status: dropped`와 이유를 남긴다.
- **방향 결정:** 고른 후보는 결정 문서(`D0.1 방향`)의 선택지로 올리고, 확정은 사람이 한다(`lg answer`).
- **brief:** M1 마지막 task에서 에이전트가 초안을 쓰고, 사람이 M1 게이트(Milestone-Verdict go)로 확정한다.

### 26.5 idea 문서 (새 문서 유형, 완성 사양)

```
---
id: I3
type: idea
spec_version: 7
title: "SSM 상태 갱신의 표현력과 상태 추적 latent 추론"
status: candidate          # candidate | exploring | selected | dropped | merged
origin: conversation       # conversation | literature | agent
merged_into: null          # merged일 때 다른 I-ID
decision: null             # 고르거나 버린 결정 ID
updated: 2026-10-02
---
# I3. …

## 한 줄 주장
## 가설
## 최소 실험          (무엇을 돌리면 맞고 틀림이 드러나나, 자원 추정)
## 가장 가까운 선행 연구와 차이   (참고문헌 ID)
## 새로움 위험
## 평가                (잠근 기준으로, 기준별 점수·근거·확신. §26.6.3)
## 판단 기록          (상태가 바뀐 날짜, 근거, 커밋)
```

- ID는 `I<n>`이다(프로젝트 안에서 한 번 쓰면 다시 쓰지 않는다). 커밋 scope와 결정의 선택지에서 이 ID로 가리킨다. hook이 scope 형식으로 `I<n>`을 받게 한다.
- **상태 전이 중 사람 몫(G4에 추가):** `→ selected`, `→ dropped`. 사람의 `decide` 커밋(`Decisions`)이나 게이트 판정으로 정하고, 반영 도구가 반영한다.
  - 에이전트는 `candidate → exploring`만 한다. 이것은 검토 중이라는 표시라 판단이 아니다.

### 26.6 평가 기준 (미리 정하고 잠근다)

에이전트가 후보를 평가할 때 임의적이거나 자의적이면 안 된다. 이를 위해 세 가지를 지킨다.

1. **기준은 후보를 보기 전에 사람이 확정한다.**
2. **에이전트는 그 기준과 척도대로만, 근거를 달아 매긴다.**
3. **합계와 순위는 도구가 계산한다.**

방향은 여전히 사람이 정한다. 점수는 판단의 입력이지 결정이 아니다.

#### 26.6.1 기준 문서 `plan/criteria.md`

ideation 프로젝트에 생성된다. 기본 기준은 **CS(특히 ML) 박사과정의 논문 아이디어 평가**에 맞춘다. 구성은 두 가지를 겹쳐 놓은 것이다.

- **학회 리뷰 기준:** NeurIPS·ICML·ICLR 리뷰 양식의 독창성(originality), 중요도(significance), 타당성(soundness)
- **박사과정의 사정:** 선점 위험, 학위 기간 안의 실행 가능성, 결과가 부정적이어도 논문이 되는가

사람은 프로젝트에 맞게 고친 뒤 잠근다.

```
---
id: criteria
type: criteria
spec_version: 7
status: draft              # draft | locked
locked_commit: null        # 잠근 사람 커밋 (반영 도구가 채움)
updated: …
---
# 평가 기준
```

**기본 기준표** (가중치는 기본값. 사람이 바꾼다)

| ID | 기준 | 묻는 것 | 누가 | 가중치 | 결격 (점수와 상관없이 탈락) |
|---|---|---|---|---|---|
| C1 | 독창성 | 가장 가까운 선행 연구가 이미 한 것과 무엇이 다른가 | 에이전트 | 3 | 핵심 주장을 이미 한 논문(arXiv 포함)이 있다 |
| C2 | 중요도 | 답이 나오면 그 분야에서 무엇이 바뀌나, 누가 인용하나 | 에이전트 | 3 | — |
| C3 | 검증 가능성 | 가설과 반증 조건, 지표, 비교 대상이 분명한가 | 에이전트 | 2 | 어떤 결과가 나와도 가설이 틀렸다고 말할 수 없다 |
| C4 | 전제의 근거 | 아이디어가 기대는 전제(이론, 선행 결과, 예비 관찰)가 얼마나 단단한가 | 에이전트 | 2 | — |
| C5 | 실행 가능성 | 연산 자원·데이터·공개 코드·기간이 가진 자원 안에 드는가. 첫 결과까지 걸리는 시간 | 에이전트 | 2 | 필요한 자원이 가진 자원의 몇 배를 넘는다 (배수는 사람이 정한다) |
| C6 | 선점 위험 | 최근 6–12개월 같은 방향 논문의 속도, 큰 연구실이 먼저 낼 가능성 | 에이전트 | 2 | — |
| C7 | 결과의 견고성 | 가설이 틀려도(음성 결과) 논문·학위 논문의 한 장이 되는가 | 에이전트 | 1 | — |
| C8 | 연구자 적합성 | 관심, 가진 역량과 배울 것, 연구실·지도교수 방향, 학위 일정 | **사람** | 2 | — |

**수준별 근거 조건** (예: C1, C5, C6. 기준마다 1–5 모두 적는다)

| 점수 | C1 독창성 | C5 실행 가능성 | C6 선점 위험 (낮을수록 높은 점수) |
|---|---|---|---|
| 1 | 핵심 주장을 이미 한 논문이 있다(ID, 표·절) | 필요 자원 > 가진 자원의 결격 배수 | 같은 주장을 하는 동시 연구가 이미 나왔다 |
| 2 | 같은 문제·같은 방법. 차이는 설정(데이터, 규모)뿐 | 자원은 들지만 첫 결과까지 T(가진 기간)를 넘는다 | 최근 3개월 안에 아주 가까운 논문이 2편 넘게 나왔다 |
| 3 | 방법 또는 문제 중 하나가 새롭다. 가까운 연구 2편 이상과의 차이 표가 있다 | 공개 코드·데이터가 있고 첫 결과(최소 실험)까지 T/2–T | 가까운 논문이 있지만 축이 다르다 |
| 4 | 둘 다 새롭다. 검색 기록(검색어, 날짜, 결과 수)으로 빈틈을 보일 수 있다 | 첫 결과까지 T/4–T/2, 자원 추정의 근거가 있다(비슷한 실험의 GPU 시간) | 최근 12개월 같은 방향 논문이 드물다 |
| 5 | 4에 더해, 이론 예측이나 반증 조건이 있어 결과가 어느 쪽이든 새 지식이다 | 첫 결과까지 T/4 안, 실패해도 빨리 알 수 있다 | 같은 방향이 없고, 진입 장벽(데이터, 이론)이 있다 |

필요한 근거:
- C1: 참고문헌 ID와 위치, 검색 기록(`notes/search-*.md`)
- C2: 이 문제를 열린 문제로 꼽은 논문(ID와 위치), 인용·후속 연구 흐름
- C3: 가설 문장, 반증 조건, 지표와 기준선(공개된 수치의 ID와 표)
- C4: 정리 번호, 선행 결과의 표, 예비 실험
- C5: 비슷한 실험의 자원 보고(ID와 위치), 공개 코드·데이터 주소, 가진 자원(사람이 기준 문서에 적는다: GPU 종류와 시간, 기간)
- C6: 최근 논문 목록(날짜 포함)
- C7: 음성 결과일 때의 논문 형태(분석, 반례, 벤치마크)

**사람이 기준 문서에 함께 적는 것:**
- 가진 자원: GPU 종류·수·월 사용 가능 시간, 데이터 접근
- 기간: 이 아이디어에 쓸 수 있는 개월 수, 목표 학회와 마감
- C5의 결격 배수

에이전트는 이 값을 고치지 않는다.

**예시:** 이 기준은 실제로 겪은 일과 맞물린다. 처음 ideation의 후보 5개를 C1·C6로 매겼다면 "GRU·고정 상태를 붙여 Coconut·CODI와 비교" 방향(비용 중심)은 C1 2–3점, C6 1–2점이었을 것이다(Penelope 등 2026-07~09 동시 연구). 표현력 방향은 C1 4–5점(정리 기반 반증 조건), C7도 높았을 것이다. 연습용 프로젝트 M0에서 늦게 도달한 방향 전환이 ideation 단계에서 근거와 함께 드러났을 것이다.

**제안서(`--kind proposal`)를 ideation으로 시작할 때:** 기본 기준은 위 연구 기준이다. 제안서용 기준이 필요하면 사람이 기준 문서를 고친다(부가 기능, 기본값은 따로 두지 않는다).

#### 26.6.2 잠그기

- **잠그는 시점:** ideation M0-T0(지형 파악과 후보 생성 계획)의 게이트에서 사람이 기준을 확정한다. 이 판정 커밋이 `plan/criteria.md`를 `locked`로 만든다(반영 도구, `locked_commit`).
- **사람 몫(G4에 추가):** 기준의 `draft → locked`와 잠근 뒤의 모든 변경. 에이전트는 기준 문서를 고치지 않는다. 고치고 싶으면 `notes/`에 제안한다.
- **잠근 뒤에 바꾸면:** 사람의 `plan` 커밋으로만 바꾼다. 바꾸면 이미 매긴 모든 후보의 평가가 "기준 변경 전"으로 표시되고, 에이전트가 **모든 후보를 다시** 매긴다. 일부 후보만 새 기준으로 매기는 일을 막는다.
- **잠기기 전에는 평가하지 않는다.** 에이전트는 `locked` 전에 점수를 쓰지 않는다. `lg verify`가 확인한다(§26.6.4).

#### 26.6.3 평가 (idea 문서의 `## 평가`)

```
## 평가 (기준 locked_commit 3f2a1c9)

| 기준 | 점수 | 근거 | 확신 |
|---|---|---|---|
| C1 | 4 | `chen2026-penelope` Table 1과 차이 표(results/M1/M1-T1_result.md §26.2), 검색 기록 notes/search-2026-10-05.md | 중 |
| C2 | 3 | … | 상 |
| C8 | (사람) | | |
```

- **근거 없는 점수는 무효다.** 근거 칸에는 참고문헌 ID와 위치, 결과 문서 경로, 검색 기록 같은 확인할 수 있는 것을 적는다.
- **확신**(상·중·하): 근거가 약하면 "하"로 두고, 그 기준의 근거를 보강할 task를 제안한다.
- **매기는 순서:** 모든 후보를 같은 task 안에서 기준별로 매긴다(후보별이 아니라 기준별로 한 줄씩). 먼저 매긴 후보가 기준점이 되어 뒤 후보가 흔들리는 것을 줄이기 위해서다. 다시 매기면 이전 점수와 이유를 `## 판단 기록`에 남긴다.
- **출처를 가리지 않는다.** 사람이 낸 후보(`origin: conversation`)와 에이전트가 낸 후보를 같은 기준과 같은 task에서 매긴다. 에이전트가 자기 후보를 높게 매기는 편향은 근거 요건과 사람의 판정으로 견제한다.

#### 26.6.4 도구: 비교표와 검사

- **`lg ideas` (새 명령, 읽기만, 사람·에이전트):**
  - 기준 문서와 idea 문서들을 읽어 비교표를 낸다: 후보 × 기준 점수, 가중 평균, 순위, 결격.
  - 함께 알리는 것: 근거 없는 점수, 확신 "하"인 칸, 사람이 매길 칸, 잠그기 전 점수, 기준 변경 뒤 다시 매기지 않은 후보.
  - 합계와 순위는 도구가 계산한다. 에이전트가 손으로 더하거나 순위를 매기지 않는다.
- **`lg verify` (V5 확장):**
  - 평가표의 기준이 기준 문서와 같다.
  - 점수가 척도 안에 있다.
  - 근거 칸이 비어 있지 않다.
  - 평가가 기준을 잠근 커밋 뒤에 쓰였다.
  - 위반이면 게이트 판정 때 `lg commit`·`lg answer`의 요약에 나온다.
- **방향 결정(D0.1)과 `lg answer`:**
  - 결정 문서의 선택지에 `lg ideas` 비교표를 붙인다.
  - 사람은 판정할 때 그 표를 본다. 순위와 다른 후보를 고르면 이유를 코멘트에 남긴다. 막지는 않는다.

### 26.7 brief.md (방향 확정 문서, 완성 사양)

실행 프로젝트가 읽는 넘김 문서다. 사람이 읽기 좋은 Markdown이면서, `lg init --from`이 읽는 값은 frontmatter에 둔다.

```
---
id: brief
type: brief
spec_version: 7
status: draft              # draft | confirmed (M1 게이트 go 반영 때 confirmed)
kind: research             # 넘길 실행 프로젝트의 종류 (research | proposal)
question: "…"              # 확정 질문 → research_question
summary: "…"               # → project.summary
selected: [I3]
dropped: [I1, I2, I4, I5]
milestones:                # → milestones (제목만)
  - "기준선 재현과 합성 과제 구축"
  - "표현력 변형 사다리와 H1 검증"
references: [hao2024-coconut, grazzi2024-negative-eigenvalues, …]   # 넘길 참고문헌 ID
criteria_commit: 3f2a1c9   # 평가에 쓴 기준을 잠근 커밋
decision: D0.1
updated: …
---
# 방향 확정: …

## 질문과 가설
## 왜 이 방향인가 (고른 후보와 근거, `lg ideas` 비교표. 순위와 다르게 골랐으면 그 이유)
## 버린 후보와 이유
## 첫 마일스톤에서 할 일 (실행 프로젝트의 M0-T0 입력)
## 남은 위험과 열린 질문
```

### 26.8 `lg init --from IDEATION`

```
lg init PATH --from IDEATION_PATH [--kind research|proposal] [--config FILE] [--import DIR] …
```

- **읽는 곳:** IDEATION 프로젝트의 `brief.md`. 그 프로젝트가 spec_version 7 이상의 ideation이어야 한다.
- **전제:**
  - `brief.md`의 `status: confirmed`. 아니면 오류(코드 2)이고 "M1 게이트를 먼저 판정하세요"라고 안내한다.
  - ideation 프로젝트의 작업 트리가 깨끗해야 한다. 넘기는 내용이 커밋된 것과 같도록 하기 위해서다.
- **설정 만들기:**
  - brief에서 가져오는 값: `question` → `research_question`, `summary`, `milestones`, `kind`(`--kind`가 우선). 사람 신원도 ideation 프로젝트에서 가져온다.
  - 새로 정하는 값: 이름과 slug. 대화형이면 묻는다(기본값은 brief 제목).
  - `--config`를 같이 주면 설정 파일 값이 우선한다.
- **옮기는 것:**

| 무엇 | 어디로 | 어떻게 |
|---|---|---|
| `brief.md` | `notes/ideation-brief.md` | 그대로. 실행 프로젝트 M0-T0의 입력이 된다(T0 카드의 `--from` 분기) |
| brief의 `references` | `references/library/` 원본 + `references/catalog.md` 행 | ID 그대로. 첫 승인 커밋 전에 stage |
| 고른 idea 문서 | `notes/ideation/` | 근거로 |
| 출발점 | `.lg/project.yaml`의 `origin: {path, commit, brief}`, README의 한 줄 | init 커밋에 포함(생성 파일) |

- **커밋:** 옮긴 자료는 `--import`와 같이 stage만 하고, 첫 승인 커밋에 함께 들어간다. init 커밋은 생성 파일만이다(v0.6.0 규칙). 출발점 기록은 생성 파일이라 init 커밋에 들어간다.
- **ideation 쪽:** 실행 프로젝트가 생겼다는 기록은 ideation 프로젝트에 자동으로 쓰지 않는다(다른 저장소를 바꾸지 않는다). 필요하면 사람이 남긴다. 안내에 명령 예를 보여 준다.

### 26.9 함께 넣을 것 (실사용에서 나온 빈틈)

| 항목 | 내용 | 이유 |
|---|---|---|
| 결정의 확정 내용 | 반영 도구가 결정을 `confirmed`로 바꿀 때, `확정:` 줄(커밋 본문)이나 review `## 응답`의 확정 내용을 결정 문서의 "확정 내용" 절에 옮겨 적는다(사람이 쓴 그대로). 결정 사양에 그 절이 없으면 건너뛴다 | 연습용 프로젝트: D0.1이 `confirmed`인데 본문은 "(미확정)"으로 남았다 |
| 마일스톤 `go_nogo` | `Milestone-Verdict`를 반영할 때 마일스톤 frontmatter `go_nogo`를 채운다 | 연습용 프로젝트: M0이 `closed`인데 `go_nogo: null` |
| ideation용 사람 몫 전이 | §26.5의 idea `→ selected`, `→ dropped`를 `lg verify` V2와 반영 도구에 | ideation의 기본 |

### 26.10 미루는 것

| 항목 | 이유 |
|---|---|
| 열린 세션의 사람 커밋 자동 감지 (UserPromptSubmit hook) | ideation과 무관하다. 지금은 "커밋했어"라고 알리면 되고, `lg commit`이 그렇게 안내한다 |
| 커밋 순간 G3·G7 차단 | 에이전트 쪽 강제라 성격이 다르다. `lg verify`가 사후에 찾는다 |
| 제안서 종류의 사양·절차 용어 | KZ 실사용에서 걸리는 곳이 나오면 함께 고친다 |
| 연구 프로젝트에서 바로 `--from` (M0에서 방향이 크게 바뀐 경우) | 연구 프로젝트에는 brief가 없다. 우선 ideation만 지원하고, 필요하면 연구 프로젝트에도 brief를 쓰게 하는 쪽으로 넓힌다 |

### 26.11 문서와 테스트

- 명령 설명서: `lg-init.md`(`--kind ideation`, `--from`), 작업 설명서 새 페이지 `ideation.md`(탐색부터 넘기기까지), `setup.md`.
- 설계 문서 §26으로 병합. 부록에 idea·brief 사양과 양식, ideation 템플릿 분기.
- 테스트:
  - unit: brief frontmatter 읽기, 설정 만들기(우선순위)
  - contract: ideation 템플릿(용어, `ideas/`, `brief.md`, 원고 폴더 없음), 사양, 해시표 변형
  - tools: 반영 도구의 idea 전이, 확정 내용 옮기기, `go_nogo`
  - unit: 비교표 계산(가중 평균, 결격, 순위, 동점), 평가표 검사
  - commands: `lg ideas`(근거 없는 점수, 잠그기 전 점수, 기준 변경 뒤 다시 매기지 않은 후보 표시), `lg verify` V5(평가표), 기준 잠그기·바꾸기 흐름
  - commands: `lg init --kind ideation`, `--from`(전제 실패, 설정 우선순위, 옮긴 것, 출발점 기록, 첫 승인 커밋에 함께), `lg verify` V2(idea)
  - e2e: ideation 만들기 → brief 확정 → `--from`으로 연구 프로젝트

### 26.12 결정된 사항

모두 초안의 추천대로 정했다(2026-10-04).

| 질문 | 결정 |
|---|---|
| 후보 표현 | 새 문서 유형 `idea` (`ideas/I<n>_<slug>.md`, 완성 사양) |
| 넘김 문서 | `brief.md` (Markdown + frontmatter, 완성 사양) |
| `--from`이 옮기는 것 | 질문·요약·마일스톤·사람 신원(설정), brief, 고른 후보, 넘길 참고문헌(원본과 목록 행) |
| ideation 마일스톤 | 기본 두 개(지형 파악과 후보 생성 / 후보 검증과 방향 선택), 바꿀 수 있음 |
| 함께 넣을 것 (§26.9) | 넣음 |
| `--from`의 brief 상태 | `confirmed`만 |
| 평가 기준을 정하는 시점 | ideation M0-T0 게이트에서 잠금 (후보 생성 전) |
| 척도 | 1–5, 수준마다 근거 조건. 결격은 결격이 있는 기준의 1점 |
| 합계와 순위 | `lg ideas`가 계산(가중 평균), 사람이 최종 결정 |
| 기준을 잠근 뒤 바꾸기 | 사람의 `plan` 커밋으로만, 바꾸면 모든 후보 다시 평가 |
| 기본 기준 | C1–C8 (학회 리뷰 기준 + 박사과정 사정) |

#### 26.12.1 구현하며 정한 세부

- **고르기·버리기:** `gate`·`decide` 커밋의 `Select: I3`, `Drop: I1, I2` trailer로 한다. hook은 형식(`I<n>`)과 쓸 수 있는 타입을 검사한다. `lg answer`는 요청서 frontmatter `ideas:`에 있는 후보만 묻는다(결정과 같은 규칙). 버릴 때는 이유 한 줄이 필수다.
- **기준 잠금의 반영:** `M0-T0` 게이트 승인을 반영할 때 `plan/criteria.md`가 `draft`면 `locked`로 바꾸고 `locked_commit`을 채운다. 에이전트가 이를 커밋하므로 절차 gate-apply의 특별 규칙에 G7(기준 문서의 `status`·`locked_commit`만)을 더했다. `lg verify` V4는 `Applies`가 있는 커밋이 이 세 줄(`status`, `locked_commit`, `updated`)만 바꾸면 위반으로 보지 않는다.
- **방향 확정의 반영:** **마지막 마일스톤**의 `Milestone-Verdict: go`만 `brief.md`를 `confirmed`로 바꾼다(M0을 go로 닫아도 확정되지 않는다).
- **기준 변경의 판단:** 기준 버전은 기준 **내용**을 마지막으로 바꾼 커밋이다. `status`·`locked_commit`·`updated`만 바꾼 커밋(잠금 반영)은 건너뛴다. 처음 구현은 "기준 문서를 마지막으로 바꾼 커밋"이라 잠금 반영 커밋이 버전이 되어, 사양대로 쓴 평가가 모두 "기준 변경 전"이 되었다(연습용 ideation 프로젝트에서 평가 전에 발견). 평가 표 머리의 커밋이 기준 버전과 다르면 "기준 변경 전" 평가다. 순위에서 빠지고 `lg verify` V5 위반이다. `lg ideas`가 기준 버전과 평가 표 머리에 쓸 줄을 보여 준다.
- **평균:** 합계 대신 가중 평균(1–5)을 쓴다. 사람 기준이 비어 있어도 같은 척도로 비교할 수 있게 하기 위해서다.
- **문서 유형:** conventions에 `idea`, `criteria`, `brief`, `idea-index`와 그 상태값을 더했다. `lg verify` V5는 세 사양의 필수 필드를 읽고, 후보 문서의 `id`가 파일 이름의 `I<n>_` 앞부분과 같으면 맞다고 본다.
- **`--from` 프로젝트의 M0-T0:** 카드가 `notes/ideation-brief.md`를 출발점으로 삼는다(템플릿의 `origin` 분기).
- **기본 기준의 보완 (연습용 ideation 프로젝트, 2026-10-05):** 에이전트의 기준 조정 제안 중 프로젝트와 상관없는 세 가지를 기본 기준에 넣었다.
  - C5 구간을 가진 기간 T에 대한 비율로 바꿨다(T/4, T/2, T). 기간이 1개월이면 개월 단위 구간의 2–4점이 쓰이지 않았다.
  - C6의 "아주 가까운 논문"을 정의했다: 같은 문제와 같은 방법 축이 둘 다 겹침.
  - 다른 후보의 산출물을 전제로 하는 후보는 전제 비용을 포함해 C5를 매긴다.

### 26.13 기존 프로젝트에 미치는 것

- 이미 진행 중인 프로젝트(`ssm-latent-reasoning`, `-v2`, KZ)는 바뀌지 않는다. `lg upgrade`로 7로 올려도 §26.9의 반영 도구 개선만 달라진다.
- 다음 논문 아이디어를 찾을 때 `--kind ideation`으로 시작하고, 방향이 정해지면 `--from`으로 연구 프로젝트를 만든다. 방향이 이미 정해진 일(KZ 제안서 등)은 지금처럼 바로 만든다.

## 27. ideation 앵커 연구 (`plan/anchor.md`)

v0.8.0, spec_version 8.

### 27.1 목적

ideation의 모든 후보를 **앵커 연구 하나**와 비교하게 한다. 후보는 "앵커 + 무엇을 바꾸면, 같은 과제·지표·설정에서 무엇이 얼마나 좋아지나"로 쓴다.

실사용(연습용 ideation 프로젝트, 2026-10-05): v0.7.0으로 후보 8개를 평가하니 후보마다 기준선·과제·backbone이 달랐다.

| 후보 | 기준선 | 과제 | backbone |
|---|---|---|---|
| I1, I7 | Coconut·CODI | GSM8K | GPT-2 |
| I6 | CoT·CODI·LOTUS | GSM8K | Llama-3.2-3B |
| I8 | RecurTrace | MathQA | Qwen3 |

후보들이 같은 질문에 대한 다른 답이 아니라 서로 다른 논문 계획이 되어 "중구난방"으로 보였다. 가까운 선행 연구와의 차이(새로움)는 정리되었지만, 성능 비교의 기준점이 없었다.

**역할.** 앵커는 두 가지의 기준점이다.

| 역할 | 앵커 문서가 정하는 것 | 후보가 쓰는 것 (`## 앵커 대비`) |
|---|---|---|
| 성능 기준점 | 과제·벤치마크, 지표와 보고 수치, 설정 | 같은 과제·지표·설정에서 "앵커 + X"가 무엇을 얼마나 바꾸나, 반증 조건 |
| 기여 기준점 | 도달점(앵커와 그 계열 연구가 이미 보인 것), 한계(아직 못 한 것과 근거, `L1`, `L2`, …) | 어느 한계를 푸나. 도달점을 다시 보이는 것은 기여가 아니다 |

논문의 기여는 "기존 연구가 어디까지 왔고 어디서 막혔나"에 대한 것이다. 성능 수치만 정하면 후보가 같은 표에 놓이지만, 무엇에 대한 기여인지는 여전히 후보마다 다를 수 있다. 그래서 앵커 문서가 도달점과 한계를 함께 정하고, 후보는 그 한계 중 무엇을 푸는지 적는다.

**선정 기준.** 후보 앵커 2–4개를 다음 기준마다 비교하고 하나를 고른다.

1. 같은 문제: 연구 질문과 같은 문제를 같은 과제·지표로 푼다.
2. 강한 대표: 그 문제의 최신 대표 방법이다(최근 12개월, 또는 최근 목표 학회 논문들의 주 비교 대상). 약한 앵커를 이기는 것은 기여가 아니다.
3. 재현 가능성: 공개 코드·체크포인트, 표준 벤치마크의 보고 수치, 가진 자원으로 재현.
4. 근거 있는 한계: 연구 질문과 관련된 한계가 근거(저자 서술, 후속 연구의 지적, 예비 실험)와 함께 있다.
5. 하나만.

### 27.2 앵커 문서

`plan/anchor.md`(ideation에 생성, 사양 `anchor.spec.md`, 부록 A.18, B.15).

- **frontmatter:** `status`(`draft` | `locked`), `locked_commit`, `lock_task`(앵커 선정 task ID 또는 `null`), `reference`(참고문헌 ID), `task`, `metric`, `reported`.
- **본문:**
  - 선정한 앵커: 논문, 과제, 지표와 수치, 설정, 공개 코드, 재현 비용
  - 도달점: 앵커와 그 계열 연구가 이미 보인 것
  - 한계: 표 `| ID | 한계 | 근거 | 연구 질문과의 관계 |`, ID는 `L<n>`
  - 선정 기준: 위의 다섯 기준
  - 후보 앵커 비교 표 (열이 선정 기준)
  - 선정 이유

### 27.3 정하고 잠그기

- **작성:** 앵커 선정 task(새 프로젝트는 첫 마일스톤의 지형 파악. M0-T0 카드가 이 task를 넣고 그 ID를 `lock_task`에 적게 한다)에서 에이전트가 후보 앵커 2–4개를 비교하고, 도달점·한계·추천을 채운다. 잠기기 전에는 에이전트가 고칠 수 있다.
- **잠금:** 사람은 추천을 보고 다르면 고쳐 커밋하고, `lock_task` 게이트를 `Verdict: approve`로 판정한다. 반영 도구가 `draft → locked`와 `locked_commit`을 채운다(`lock_anchor()`). `lock_task`가 `null`이면 첫 마일스톤의 마지막 게이트(`Milestone-Verdict: go`)에서 잠근다(`first_milestone()`).
  - 실사용(연습용 ideation, 2026-10-06): spec_version 7로 시작해 M0이 끝난 뒤 8로 올린 프로젝트는 첫 마일스톤의 go가 이미 지나 앵커를 잠글 길이 없었다. 앵커 선정 task를 M1에 더하고(M1-T4) 그 approve로 잠그게 했다. 첫 마일스톤의 go보다 앵커를 검토하는 그 게이트가 판단 시점으로도 맞다.
- **잠글 수 있는 조건:** `reference`·`task`·`metric`·`reported`가 있고, `reference`가 `references/catalog.md`에 있고, `## 한계`에 `L<n>`이 하나 이상 있다. 아니면 반영 도구가 아무것도 바꾸지 않고 멈춘다. `lg answer`·`lg commit`의 반영 미리보기가 같은 계산을 하므로 판정 커밋 전에 알린다. 사람이 `plan` 커밋으로 직접 잠근 경우는 `lg verify` V5가 잡는다(`ideas.lock_issues`).
- **시점:** 평가 기준(첫 T0 게이트)보다 늦은 이유는 최신 앵커를 고르려면 지형 조사가 필요해서다. 후보 평가보다는 앞이다.
- **잠근 뒤:** 사람의 `plan` 커밋으로만 바꾼다. G4에 앵커 `draft → locked`, G7에 "잠긴 `plan/anchor.md`"를 더했다.
  - `lg verify` V4: 잠기기 전의 에이전트 수정은 허용하고, 잠긴 뒤의 수정은 위반이다(잠금 반영의 `status`·`locked_commit`·`updated`는 예외).
  - V2: 잠금 전이의 근거는 `lock_task`(전이 전 문서의 값) 게이트의 approve, `lock_task`가 없으면 첫 마일스톤의 go다.

### 27.4 후보와 평가

- **앵커 대비:** idea 사양에 `## 앵커 대비` 절을 더했다(한 줄 "앵커 + X", 푸는 한계 `L<n>`, 같은 설정인가, 예상 효과와 반증, 추가 비용). 앵커 대비로 쓸 수 없거나 앵커의 어느 한계도 풀지 않는 후보는 이 방향의 범위 밖이다.
- **평가 표 머리:** `## 평가 (기준 <기준 버전>, 앵커 <앵커 버전>)`. 앵커 버전도 내용을 마지막으로 바꾼 커밋이다(잠금만 바꾼 커밋은 세지 않음, `criteria_version(project, path)`).
- **`lg ideas`:** 앵커(참고문헌, 과제, 지표와 수치, 상태, 버전)과 평가 표 머리에 쓸 줄을 보여 준다. 순위에서 빼는 것:
  - 앵커 대비 절이 없는 후보
  - 앵커 대비에 앵커 `## 한계`의 `L<n>`이 하나도 없는 후보 (`L1을`처럼 조사가 붙어도 읽는다)
  - 앵커가 잠기기 전의 평가
  - 평가 표 머리에 앵커 버전이 없거나 다른 평가
- **`lg verify` V5:** 같은 검사를 한다(`ideas.anchor_issues`).
- **spec_version 7 ideation:** 앵커 문서가 없으면 이 검사를 하지 않는다.

### 27.5 넘기기와 갱신

- **넘기기:** `brief.md`에 `anchor`(참고문헌 ID)을 더했다. `lg init --from`은 다음을 한다.
  - 앵커 문서를 `notes/ideation-anchor.md`로 옮긴다.
  - 앵커 논문을 넘길 참고문헌에 더한다.
  - 새 프로젝트의 M0-T0 카드가 "앵커 재현을 첫 task로, 모든 실험은 같은 과제·지표·설정에서 비교"를 담는다.
- **`lg upgrade` 7 → 8:** 연구 문서는 원래 새로 만들지 않는다. 다만 이 버전에서 생긴 연구 문서(`NEW_RESEARCH_DOCS[8] = ("plan/anchor.md",)`)는 그 종류(ideation)의 프로젝트에 없으면 새로 만든다.

### 27.6 결정된 사항

| 질문 | 결정 | 이유 |
|---|---|---|
| 용어 | 앵커 연구(anchor). 기준선(baseline)은 실행 프로젝트의 실험별 비교 대상에만 쓴다 | 처음엔 "기준선"이라 불렀으나, 실행 프로젝트로 넘어간 뒤 실험이 그 하나로만 비교될 위험이 있었다(사용자 지적, 2026-10-06). "모든 실험은 같은 설정에서"라는 규칙은 규모 같은 한계(`L<n>`)를 푸는 실험과도 어긋난다. 이름을 나눠 앵커는 후보 비교와 첫 재현, 기준선은 실험마다 정하는 것으로 분리했다 |
| 앵커 개수 | 정확히 하나 | 비교 상대가 여럿이면 다시 흩어진다. 보조 비교는 후보 안에서 |
| 앵커의 역할 | 성능 기준점과 기여 기준점(도달점, 한계 `L<n>`) | 수치만으로는 무엇에 대한 기여인지가 후보마다 달라진다 |
| 잠그는 시점 | 앵커 선정 task(`lock_task`)의 approve. 없으면 첫 마일스톤의 마지막 게이트(go) | 지형 조사 뒤, 후보 평가 전. 앵커를 검토하는 게이트에서 정한다. M0이 끝난 프로젝트도 잠글 수 있다 |
| 덜 채운 앵커 | 잠그지 않고 반영을 멈춘다 | 잠근 뒤 고치면 모든 후보를 다시 써야 한다. 판정 전에 미리보기가 알린다 |
| 앵커 대비가 없는 후보 | 평가하지 않고 표시 | 결격 점수보다 "범위 밖"을 드러내는 편이 정확하다 |
| 버전 | v0.8.0 (spec_version 8) | 생성 파일이 바뀌므로 패치가 될 수 없다(§22.2.2). 사용자가 v0.7.1을 원했으나 규칙대로 마이너로 정했다. 규칙(패치 = `lg upgrade` 불필요)은 1.0 이후에 다시 본다 |

---

# 부록 A. 생성 문서 템플릿

> 바깥 `~~~~` 울타리는 이 설계 문서의 표기일 뿐 파일 내용이 아니다. 울타리 안이 파일 원문이다.

## A.1 `README.md` (J)

~~~~markdown
# {{ project.name }}

{{ project.summary }}

## {% if ideation %}탐색 주제{% elif proposal %}제안 핵심 질문{% else %}연구 질문{% endif +%}

{{ project.research_question }}

{% if origin %}
출발: ideation 프로젝트 `{{ origin.path }}`(커밋 `{{ origin.commit }}`)의 방향 확정 문서. 사본은 [notes/ideation-brief.md](notes/ideation-brief.md).

{% endif %}
## 처음 볼 문서

1. [STATUS.md](STATUS.md): 현재 상태와 사람의 판단이 필요한 항목
2. [plan/roadmap.md](plan/roadmap.md): 전체 계획
3. [FILEMAP.md](FILEMAP.md): 폴더 구조
4. [specs/README.md](specs/README.md): 문서 작성 규칙
5. [specs/workflow.md](specs/workflow.md): 작업 절차와 승인 게이트
{% if ideation %}
6. [plan/criteria.md](plan/criteria.md): 후보 평가 기준 (첫 게이트에서 사람이 확정하고 잠근다)
7. [plan/anchor.md](plan/anchor.md): 모든 후보가 비교할 앵커 연구 하나 (앵커 선정 task의 게이트에서 잠근다)
8. [ideas/index.md](ideas/index.md): 아이디어 후보 목록
9. [brief.md](brief.md): 방향 확정 문서 (마지막 게이트에서 확정)
{% endif %}

## 사람이 하는 일

- 터미널에서 `lg status`로 내가 할 일(열린 요청, 커밋 대기)을 보고, 요청에는 `lg answer <ID>`로 응답한다. 요청서를 터미널에 보여 주고, 판정을 물어 `## 응답`과 사람 커밋을 함께 만든다. 요청서(`reviews/open/`)에 직접 써도 된다.
- 판정과 확정은 사람 신원의 커밋으로 남긴다. 사람 전용 커밋 타입: `gate`, `decide`, `plan`, `spec`, `respond` ([specs/git-commit.md](specs/git-commit.md)).
- 커밋은 터미널에서 `lg commit`으로 한다. 타입과 필수 trailer를 물어 메시지를 만들고, 게이트 승인이면 tag `gate/<Task>`도 남긴다. `git commit`을 직접 써도 되며, 그때 tag는 `git tag gate/<Task>`로 남긴다.
- 코드·문서를 직접 고쳤다면 에이전트가 작업하기 전에 커밋한다(`exp`, `result` 등 공통 타입 사용 가능). 에이전트에게 초안을 부탁하면 에이전트가 `lg draft`로 준비하고, `lg commit`으로 확인해 확정한다 ([specs/workflow.md](specs/workflow.md) §4).

## 저장소를 새로 클론했을 때

```bash
git config core.hooksPath .lg/hooks
git config user.name "<이름>"
git config user.email "<.lg/identities.json에 등록된 이메일>"
```

`lg`(`lg status`, `lg answer`, `lg commit`)를 쓰려면 labgate(spec_version {{ spec_version }} 지원 버전)를 설치한다. 없어도 `git commit`으로 커밋할 수 있다.

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
{% if ideation %}
| `brief.md` | 방향 확정 문서: 확정 질문, 가설, 마일스톤, 근거 문헌, 버린 후보 (`lg init --from`이 읽는다) | 에이전트 (확정은 사람) |
{% endif %}

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
{% if ideation %}
| `ideas/` | 아이디어 후보와 목록 (평가 기준은 `plan/criteria.md`) | `I<n>_<slug>.md` |
{% endif %}
| `references/` | 참고문헌 목록, 원본, 마일스톤별 task-문헌 매핑 | `library/<Ref-ID>.<ext>` |
| `experiments/` | 공용 코드(`src/`, `tests/`)와 task별 {% if proposal %}PoC·검증{% else %}실험{% endif %} | `<M>/<Task>_<slug>/` |
| `runs/` | 실행 산출물 원본 (Git 제외) | `<Run-ID>/` |
| `results/` | task 결과, 마일스톤 보고, 그림, 표 | `<M>/<Task>_result.md`, `<M>/report.md` |
| `reviews/` | 게이트 요청과 에스컬레이션 (`open/` → `closed/`) | `<Task>_gate-NN.md`, `<Task>_esc-NN.md` |
| `logs/` | 에이전트 세션 작업 일지 | `YYYY-MM-DD_sNN.md` |
| `data/` | 데이터 생성 설정, 데이터 설명서 | |
{% if proposal %}
| `deliverables/` | 제안서 원고, 그림, 제출본 | |
{% elif not ideation %}
| `paper/` | 원고, 그림, 참고문헌 bib | |
{% endif %}
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
- {% if ideation %}탐색 주제{% elif proposal %}제안 핵심 질문{% else %}연구 질문{% endif %}: {{ project.research_question }}
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
- **G4.** 사람 몫의 상태 전이를 하지 않는다: task `draft → approved`, `in-review → closed | revise | redirected`, 결정 `→ confirmed`, 마일스톤 `planned → active → closed`{% if ideation %}, 후보 `→ selected | dropped`, 평가 기준·앵커 `draft → locked`, 방향 확정 문서 `→ confirmed`{% endif %}.
- **G5.** review 문서의 `## 응답` 섹션을 쓰지 않는다.
- **G6.** `plan/roadmap.md`와 `active` 이상인 마일스톤의 목표·기준을 바꾸지 않는다. 변경은 `notes/`에 제안하고 `propose` 커밋을 남긴다.
- **G7.** `specs/`, `AGENTS.md`{% if claude_code %}, `CLAUDE.md`, `.claude/`{% endif %}, `.lg/`{% if ideation %}, `plan/criteria.md`, 잠긴 `plan/anchor.md`{% endif %}를 고치지 않는다. 변경은 `notes/`에 제안하고 `propose` 커밋을 남긴다.
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
| 반영되지 않은 사람 커밋이 있음 | [gate-apply](specs/procedures/gate-apply.md) | G4, G6, G7 |

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

- 커밋은 `scripts/agent-commit`으로만 한다. `git commit`, `lg commit`, `lg answer`, `lg spec` 직접 실행은 `.claude/settings.json`에서 차단되어 있다.
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

규칙 문법은 Claude Code 문서(code.claude.com/docs/en/permissions)의 `Bash(<prefix> *)` 형식이다 (2026-10 확인. `:*` 형식도 같은 뜻이지만 공백 형식이 표준). 복합 명령(`cd x && git commit …`)은 하위 명령마다 검사되므로 막힌다. 그러나 `git -C . commit`처럼 프로그램과 하위 명령 사이에 옵션을 넣으면 일치하지 않는다. 즉 이 파일은 실수 방지 장치이고 보안 경계가 아니다. 실제 강제는 commit-msg hook(신원·타입 검사)이 한다. 끝의 ` *`는 옵션 없는 명령에도 일치한다(`Bash(git add -A *)`는 `git add -A`도 막는다). `git add` 일괄 stage와 `git stash`를 막는 것은 사람의 미커밋 변경이 에이전트 커밋에 섞이거나 치워지는 것을 막기 위해서다 (workflow.md §4.1). `Bash(git add . *)`는 `git add .`을 막고 `git add ./path`는 막지 않는다. `Bash(lg commit *)`, `Bash(lg answer *)`, `Bash(lg spec *)`는 에이전트가 사람 신원으로 커밋하는 것을 막고(`lg answer`는 사람의 응답을, `lg spec adopt`는 규칙 문서를 쓴다, §24), `Bash(lg upgrade *)`는 에이전트가 규칙 파일을 갱신하는 것을 막는다(G7). 준비 명령 `lg draft`는 이 규칙에 일치하지 않는다 (§17.3).

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
      "Bash(lg commit *)",
      "Bash(lg answer *)",
      "Bash(lg spec *)",
      "Bash(lg upgrade *)"
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

- `{{ milestones[0].id }}-T0` 승인 후: 착수 계획 수립 ({% if ideation %}지형 파악, 평가 기준 제안, 아이디어 메모를 후보로{% elif proposal %}자료 정리{% else %}문헌 정리{% endif %}, task 분해{% if not ideation %}, 기존 계획 이관{% endif %})
~~~~

## A.8 `.gitignore` (S)

~~~~gitignore
# labgate:begin  (labgate가 관리한다. lg upgrade가 이 구역을 갱신하므로, 직접 추가할 규칙은 구역 밖에 쓴다)

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

# labgate:end
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

## {% if ideation %}탐색 주제{% elif proposal %}제안 핵심 질문{% else %}연구 질문{% endif +%}

{{ project.research_question }}

{% if ideation %}
## 후보와 평가 기준

후보 목록은 [ideas/index.md](../ideas/index.md), 평가 기준은 [criteria.md](criteria.md), 앵커 연구는 [anchor.md](anchor.md)에 있다. 기준은 {{ milestones[0].id }}-T0 게이트에서, 앵커는 앵커 선정 task(`plan/anchor.md`의 `lock_task`)의 게이트(approve)에서 사람이 확정하고 잠근다. 모든 후보는 앵커 하나와 비교한다("앵커 + X", 앵커의 어느 한계를 푸나). 잠근 뒤에 바꾸면 모든 후보를 다시 평가한다.
{% else %}
## {% if proposal %}제안 전략과 가정{% else %}가설{% endif +%}

> TODO: {{ milestones[0].id }}-T0에서 작성
{% endif %}

## 마일스톤

| ID | 제목 | 상태 | 계획 |
|---|---|---|---|
{% for m in milestones %}
| `{{ m.id }}` | {{ m.title }} | planned | [milestone.md](milestones/{{ m.id }}/milestone.md) |
{% endfor %}

{% if ideation %}
## 방향 확정

마지막 마일스톤의 게이트(Milestone-Verdict `go`)에서 [brief.md](../brief.md)를 확정한다. 확정한 방향으로 `lg init <새 폴더> --from <이 프로젝트>`를 써서 연구 프로젝트를 만든다.
{% else %}
## {% if proposal %}공통 작업 원칙{% else %}공통 실험 원칙{% endif +%}

> TODO: {{ milestones[0].id }}-T0에서 작성
{% endif %}

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

{% if ideation %}
> 마일스톤 판정: go = 다음 단계로(첫 마일스톤이면, `lock_task`로 아직 잠기지 않은 앵커 `plan/anchor.md` 잠금, 마지막 마일스톤이면 방향 확정: `brief.md` 확정), conditional = 다시 탐색, nogo = 탐색 중단.

{% elif proposal %}
> 마일스톤 판정: go = 다음 단계로 진행(마지막 마일스톤이면 제출), conditional = 보완 조건부 진행, nogo = 중단.

{% endif %}
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

{% if ideation and prev is none %}
탐색 주제의 지형(가까운 문헌, 열린 문제, 최근 동향)을 파악할 계획을 세우고, 후보를 만드는 task로 나눈다. 평가 기준(`plan/criteria.md`)에 고칠 점을 제안해, 사람이 이 게이트에서 기준을 확정하고 잠글 수 있게 한다. 후보는 기준을 잠근 뒤에 평가한다.
{% elif ideation %}
{{ m.id }} ({{ m.title }})의 실행 계획을 세운다. 후보마다 잠근 앵커 대비(`## 앵커 대비`)를 쓰고, 잠근 기준으로 모든 후보를 평가하고, 방향을 고르고, 방향 확정 문서(`brief.md`)를 쓰는 task로 나눈다.
{% elif proposal %}
{{ m.id }} ({{ m.title }})의 실행 계획을 세운다. 필요한 자료(고객 자료, 공개 자료, 사례)를 정리하고, 마일스톤을 task로 분해하고, task와 자료를 연결한다.
{% else %}
{{ m.id }} ({{ m.title }})의 실행 계획을 세운다. 필요한 문헌을 정리하고, 마일스톤을 task로 분해하고, task와 문헌을 연결한다.
{% endif %}

## 범위

### 포함

- {% if ideation %}문헌·동향 조사{% elif proposal %}자료 조사{% else %}문헌 조사{% endif %}, 원본을 `references/library/`에 저장, `references/catalog.md`에 등록
- task 분해: `{{ m.id }}-T1` 이후 task 카드를 `draft`로 작성
- `references/{{ m.id }}/task-map.md` 작성
- `plan/milestones/{{ m.id }}/milestone.md`의 목표, task 목록, Go/No-go 기준 초안 작성 (마일스톤이 `planned`인 동안 허용)
{% if ideation and prev is none %}
- 평가 기준 조정 제안을 `notes/criteria-proposal.md`에 작성 (기준 문서 `plan/criteria.md`는 사람이 고치고 이 게이트에서 잠근다. 고칠 점이 없으면 그렇게 적는다)
- `notes/`의 아이디어 메모를 후보로 옮긴다: `ideas/I<n>_<slug>.md` (`status: candidate`, [idea 사양](../../../../specs/doc-types/idea.spec.md)), `ideas/index.md`
- 이 마일스톤 task에 "앵커 선정"(후보 앵커 비교, 도달점과 한계, 추천: `plan/anchor.md`, [사양](../../../../specs/doc-types/anchor.spec.md))을 넣고, 그 task ID를 `plan/anchor.md`의 `lock_task`에 적는다. 선정과 잠금은 사람이 그 task의 게이트(approve)에서 한다
{% endif %}
{% if origin and prev is none %}
- `notes/ideation-brief.md`(ideation에서 확정한 방향)를 출발점으로 삼는다. 거기 적힌 질문·가설·근거를 검증하고 다듬는 task로 나누며, 처음부터 다시 조사하지 않는다
- 앵커 연구(`notes/ideation-anchor.md`, ideation에서 후보를 비교한 기준점)의 재현을 첫 task로 둔다. 실험마다 비교할 기준선(baseline)은 그 실험의 task 카드에서 따로 정한다
{% endif %}
{% if prev is none and not ideation %}
- `notes/`의 기존 계획 자료를 `plan/roadmap.md`, 각 `milestone.md`, `decisions/`로 이관 (기존 결정은 `proposed` 상태로)
- 이번 마일스톤에 필요한 stub 사양의 초안을 `notes/spec-drafts/`에 작성 (확정은 사람의 `spec` 커밋)
{% endif %}

### 제외

{% if ideation %}
- 후보 평가 (기준을 잠그기 전에는 점수를 쓰지 않는다), 실험 코드 작성과 실행
{% elif proposal %}
- 제안서 본문 작성, PoC 코드 작성과 실행
{% else %}
- 실험 코드 작성과 실행
{% endif %}
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
- [ ] 등록한 모든 {% if proposal %}자료{% else %}문헌{% endif %}의 원본이 `references/library/`에 있고 `catalog.md`에 기재되어 있다
- [ ] `milestone.md`에 Go/No-go 기준 초안이 있다
{% if prev is none and ideation %}
- [ ] 평가 기준 조정 제안(또는 "고칠 점 없음")이 `notes/criteria-proposal.md`에 있다
- [ ] `notes/`의 아이디어 메모가 모두 후보(`ideas/`)로 옮겨졌다
- [ ] 앵커 선정 task가 이 마일스톤에 있고, `plan/anchor.md`의 `lock_task`가 그 ID다
{% elif prev is none %}
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

## A.15 `plan/criteria.md` (J, ideation)

~~~~markdown
---
id: criteria
type: criteria
spec_version: {{ spec_version }}
status: draft
locked_commit: null
updated: {{ today }}
---
# 평가 기준

아이디어 후보를 평가하는 기준이다. **{{ milestones[0].id }}-T0 게이트에서 사람이 확정하면 잠긴다**(`status: locked`). 잠기기 전에는 후보를 평가하지 않는다. 잠근 뒤에 바꾸면(사람의 `plan` 커밋) 모든 후보를 다시 평가한다. 에이전트는 이 문서를 고치지 않고, 고칠 점은 `notes/criteria-proposal.md`에 제안한다. 사양: [criteria.spec.md](../specs/doc-types/criteria.spec.md).

기본 기준은 CS 분야 논문 아이디어 평가다(학회 리뷰의 독창성·중요도·타당성 + 박사과정의 선점 위험·실행 가능성·결과의 견고성·연구자 적합성). 프로젝트에 맞게 고친다.

## 가진 자원 (사람이 적는다)

| 항목 | 값 |
|---|---|
| GPU | (예: A100 80GB 4장, 월 300 GPU 시간) |
| 기간 | (이 아이디어에 쓸 수 있는 개월 수) |
| 목표 학회와 마감 | (예: NeurIPS 2027, 2027-05) |
| C5 결격 배수 | 3 (필요 자원이 가진 자원의 3배를 넘으면 탈락) |

## 기준

| ID | 기준 | 묻는 것 | 누가 | 가중치 | 결격 |
|---|---|---|---|---|---|
| C1 | 독창성 | 가장 가까운 선행 연구가 이미 한 것과 무엇이 다른가 | 에이전트 | 3 | 핵심 주장을 이미 한 논문(arXiv 포함)이 있다 |
| C2 | 중요도 | 답이 나오면 그 분야에서 무엇이 바뀌나, 누가 인용하나 | 에이전트 | 3 | — |
| C3 | 검증 가능성 | 가설과 반증 조건, 지표, 비교 대상이 분명한가 | 에이전트 | 2 | 어떤 결과가 나와도 가설이 틀렸다고 말할 수 없다 |
| C4 | 전제의 근거 | 아이디어가 기대는 이론·선행 결과·예비 관찰이 얼마나 단단한가 | 에이전트 | 2 | — |
| C5 | 실행 가능성 | 연산 자원·데이터·공개 코드·기간이 가진 자원 안에 드는가 | 에이전트 | 2 | 필요 자원이 가진 자원의 결격 배수를 넘는다 |
| C6 | 선점 위험 | 최근 6–12개월 같은 방향 논문의 속도, 큰 연구실이 먼저 낼 가능성 | 에이전트 | 2 | — |
| C7 | 결과의 견고성 | 가설이 틀려도(음성 결과) 논문·학위 논문의 한 장이 되는가 | 에이전트 | 1 | — |
| C8 | 연구자 적합성 | 관심, 역량과 배울 것, 연구실·지도교수 방향, 학위 일정 | 사람 | 2 | — |

결격이 있는 기준에서 1점이면 그 후보는 결격이다(1점의 근거 조건이 결격 조건과 같다).

다른 후보의 산출물을 전제로 하는 후보(예: 앞 후보의 학습된 모듈을 쓰는 후보)는 전제 후보의 비용을 포함해 C5를 매기고, 근거 칸에 전제 후보 ID를 적는다. 합치는 편이 낫다면 평가 전에 사람이 `merged`로 정한다.

## 수준별 근거 조건

점수마다 "이 근거가 있으면 이 점수"다. 근거 없는 점수는 무효다.

### C1. 독창성

| 점수 | 근거 조건 |
|---|---|
| 1 | 핵심 주장을 이미 한 논문이 있다 (참고문헌 ID, 표·절) |
| 2 | 같은 문제·같은 방법이다. 차이는 설정(데이터, 규모)뿐이다 |
| 3 | 방법 또는 문제 중 하나가 새롭다. 가까운 연구 2편 이상과의 차이 표가 있다 |
| 4 | 둘 다 새롭다. 검색 기록(검색어, 날짜, 결과 수)으로 빈틈을 보일 수 있다 |
| 5 | 4에 더해, 이론 예측이나 반증 조건이 있어 결과가 어느 쪽이든 새 지식이다 |

근거: 참고문헌 ID와 위치, 검색 기록 `notes/search-*.md`

### C2. 중요도

| 점수 | 근거 조건 |
|---|---|
| 1 | 이 질문을 열린 문제로 꼽은 문헌이 없고, 답이 나와도 바뀌는 것을 말할 수 없다 |
| 2 | 좁은 하위 문제다. 관련 후속 연구가 거의 없다 |
| 3 | 이 질문을 열린 문제나 한계로 꼽은 논문이 있다 (ID와 위치) |
| 4 | 여러 논문(3편 이상)이 이 문제를 한계로 꼽았고, 답이 나오면 쓰일 곳(방법, 벤치마크)을 말할 수 있다 |
| 5 | 4에 더해, 분야의 주요 흐름(최근 1–2년 주요 학회의 다수 논문)이 이 답에 기대고 있다 |

근거: 열린 문제·한계를 적은 문헌의 ID와 위치, 최근 논문 목록

### C3. 검증 가능성

| 점수 | 근거 조건 |
|---|---|
| 1 | 어떤 결과로도 가설이 틀렸다고 말할 수 없다 |
| 2 | 가설은 있지만 지표나 비교 대상이 정해지지 않았다 |
| 3 | 가설, 지표, 비교 대상이 있다. 반증 조건은 정성적이다 |
| 4 | 반증 조건이 수치로 있다(예: 차이 ≥ 5%p, 시드 3개) 그리고 공개된 기준선 수치가 있다(ID와 표) |
| 5 | 4에 더해, 가설이 여러 개면 서로 다른 결과를 예측해 구분할 수 있다 |

근거: 가설 문장, 반증 조건, 지표, 기준선 수치의 출처

### C4. 전제의 근거

| 점수 | 근거 조건 |
|---|---|
| 1 | 전제를 반박하는 결과가 있다 (ID와 위치) |
| 2 | 전제가 직관뿐이다 |
| 3 | 전제를 지지하는 선행 결과가 하나 있다 (ID와 위치) |
| 4 | 이론(정리 번호)이나 여러 선행 결과가 지지한다 |
| 5 | 4에 더해, 이 프로젝트의 예비 실험이 지지한다 (결과 문서 경로) |

근거: 정리 번호, 선행 결과의 표, 예비 실험 결과

### C5. 실행 가능성

T = 위 "가진 자원"의 기간. 기간에 대한 비율이라 기간이 짧아도 모든 점수가 쓰인다.

| 점수 | 근거 조건 |
|---|---|
| 1 | 필요 자원이 가진 자원의 결격 배수를 넘는다 |
| 2 | 자원은 들지만 첫 결과(최소 실험)까지 T를 넘는다 |
| 3 | 공개 코드·데이터가 있고 첫 결과까지 T/2–T |
| 4 | 첫 결과까지 T/4–T/2. 비슷한 실험의 자원 보고(GPU 시간)로 추정했다 |
| 5 | 첫 결과까지 T/4 안. 실패해도 빨리 알 수 있다 |

근거: 비슷한 실험의 자원 보고(ID와 위치), 공개 코드·데이터 주소, 위 "가진 자원"

### C6. 선점 위험 (낮을수록 높은 점수)

| 점수 | 근거 조건 |
|---|---|
| 1 | 같은 주장을 하는 동시 연구가 이미 나왔다 |
| 2 | 최근 3개월 안에 아주 가까운 논문이 2편 넘게 나왔다 |
| 3 | 가까운 논문이 있지만 축이 다르다 |
| 4 | 최근 12개월 같은 방향 논문이 드물다 |
| 5 | 같은 방향이 없고, 진입 장벽(데이터, 이론, 장비)이 있다 |

"아주 가까운 논문" = 같은 문제(과제·벤치마크)와 같은 방법 축(이 프로젝트에서 비교하는 핵심 축, 예: 모듈 종류)이 **둘 다** 겹친다. 하나만 겹치면 "가깝지만 축이 다르다"(3점).

근거: 최근 논문 목록(날짜 포함), 검색 기록

### C7. 결과의 견고성

| 점수 | 근거 조건 |
|---|---|
| 1 | 가설이 틀리면 남는 기여가 없다 |
| 2 | 음성 결과는 짧은 워크숍 논문 정도다 |
| 3 | 음성 결과도 분석 논문(왜 안 되는가)이 된다 |
| 4 | 어느 결과든 쓸 수 있는 산출물(벤치마크, 도구, 반례)이 남는다 |
| 5 | 결과 양쪽 모두 주장할 거리가 있도록 설계되어 있다 (예: 두 가설이 다른 결과를 예측) |

근거: 음성 결과일 때의 논문 형태와 산출물

### C8. 연구자 적합성 (사람이 매김)

| 점수 | 기준 |
|---|---|
| 1–5 | 관심, 역량과 배울 것, 연구실·지도교수 방향, 학위 일정을 보고 사람이 매긴다 |
~~~~

## A.16 `ideas/index.md` (J, ideation)

~~~~markdown
---
id: ideas-index
type: idea-index
spec_version: {{ spec_version }}
updated: {{ today }}
---
# 아이디어 후보

상태: `candidate` → `exploring` → `selected` | `dropped` (사람) / `merged`. 사양: [idea.spec.md](../specs/doc-types/idea.spec.md). 평가 기준: [criteria.md](../plan/criteria.md). 비교표는 터미널에서 `lg ideas`.

| ID | 제목 | 상태 | 출처 | 문서 |
|---|---|---|---|---|
~~~~

## A.17 `brief.md` (J, ideation)

~~~~markdown
---
id: brief
type: brief
spec_version: {{ spec_version }}
status: draft
kind: research
question: null
summary: null
selected: []
dropped: []
milestones: []
references: []
decision: null
criteria_commit: null
anchor: null
updated: {{ today }}
---
# 방향 확정

마지막 마일스톤에서 에이전트가 쓰고, 그 게이트(Milestone-Verdict `go`)에서 사람이 확정한다. 확정되면 `lg init <새 폴더> --from <이 프로젝트>`가 frontmatter를 읽어 연구 프로젝트를 만든다. 사양: [brief.spec.md](specs/doc-types/brief.spec.md).

## 질문과 가설

> TODO

## 왜 이 방향인가

> TODO: 고른 후보, `lg ideas` 비교표, 순위와 다르게 골랐으면 그 이유

## 버린 후보와 이유

> TODO

## 첫 마일스톤에서 할 일

> TODO: 연구 프로젝트 M0-T0의 입력

## 남은 위험과 열린 질문

> TODO
~~~~

## A.18 `plan/anchor.md` (J, ideation)

~~~~markdown
---
id: anchor
type: anchor
spec_version: {{ spec_version }}
status: draft
locked_commit: null
lock_task: null
reference: null
task: null
metric: null
reported: null
updated: {{ today }}
---
# 앵커 연구

모든 후보는 **이 앵커 하나**와 비교한다. 앵커는 ideation에서 후보끼리 비교하기 위한 기준점이며, 실행 프로젝트의 실험별 기준선(baseline)과는 다르다. 앵커는 두 가지의 기준점이다.

- **성능 기준점:** "앵커 + X"가 같은 과제·지표·설정에서 무엇을 얼마나 바꾸나.
- **기여 기준점:** 앵커가 이미 보인 것(`## 도달점`)을 다시 보이는 것은 기여가 아니다. 아직 못 한 것(`## 한계`의 `L<n>`)을 푸는 것이 기여다. 후보는 어느 한계를 푸는지 적는다.

앵커는 앵커 선정 task(frontmatter `lock_task`)의 게이트를 사람이 approve하면 잠긴다(`status: locked`). `lock_task`가 비어 있으면 {{ milestones[0].id }}의 마지막 게이트(Milestone-Verdict `go`)에서 잠긴다. 잠기기 전에는 후보를 평가하지 않는다. 에이전트는 이 문서에 후보 앵커 비교와 추천을 쓰고, 선정은 사람이 한다(잠근 뒤에는 고치지 않는다). 사양: [anchor.spec.md](../specs/doc-types/anchor.spec.md).

## 선정한 앵커

frontmatter의 `reference`(참고문헌 ID), `task`(과제·벤치마크), `metric`(지표), `reported`(보고 수치와 표 번호)에도 같은 값을 적는다.

| 항목 | 값 |
|---|---|
| 논문 | (참고문헌 ID와 제목) |
| 과제·벤치마크 | |
| 지표와 보고 수치 | (예: GSM8K 정확도 43.7, Table 2) |
| 설정 | (backbone, 학습 데이터, 학습량) |
| 공개 코드·체크포인트 | |
| 재현 비용 | (가진 자원 대비, `plan/criteria.md`의 가진 자원) |

## 도달점

> TODO: 이 앵커와 그 계열 연구가 이미 보인 것. 무엇을, 어떤 방법으로, 어떤 수치까지 (참고문헌 ID와 위치)

## 한계

후보는 `## 앵커 대비`에 여기 있는 `L<n>` 중 무엇을 푸는지 적는다.

| ID | 한계 | 근거 | 연구 질문과의 관계 |
|---|---|---|---|

## 선정 기준

1. **같은 문제:** 연구 질문과 같은 문제를 같은 과제·지표로 푼다. 이 앵커 위의 결과로 연구 질문에 답할 수 있다.
2. **강한 대표:** 그 문제의 최신 대표 방법이다. 최근 12개월 안에 나왔거나, 최근 목표 학회 논문들이 주 비교 대상으로 쓴다. 약한 앵커를 이기는 것은 기여가 아니다.
3. **재현 가능성:** 공개 코드(가능하면 체크포인트)와 표준 벤치마크의 보고 수치가 있고, 가진 자원으로 재현할 수 있다.
4. **근거 있는 한계:** 연구 질문과 관련된 한계가 근거(저자의 서술, 후속 연구의 지적, 예비 실험)와 함께 드러나 있다.
5. **하나만:** 판단은 이 앵커 하나로 한다. 다른 비교 대상은 후보 안에서 보조로 적는다.

## 후보 앵커 비교

| 후보 (참고문헌 ID) | 같은 문제 | 강한 대표 | 재현 가능성 | 근거 있는 한계 | 비고 |
|---|---|---|---|---|---|

## 선정 이유

> TODO: 에이전트 추천과 근거. 사람이 다르게 고르면 그 이유
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
spec_version: 8
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
- `notes/`, `paper/`(제안서 프로젝트는 `deliverables/`) 아래 파일: 형식 자유

`specs/templates/`의 양식은 frontmatter를 갖지만 값이 `<...>` 자리 표시이므로 검증 대상이 아니다.

공통 필드:

| 필드 | 필수 | 설명 |
|---|---|---|
| `id` | ✓ | 문서 ID |
| `type` | ✓ | 문서 유형. 아래 표 참고 |
| `spec_version` | ✓ | 따르는 사양 버전 (현재 8). 사양을 갱신할 때 사람이 모든 문서를 일괄로 올린다(`spec` 커밋). 문서를 쓰거나 고칠 때는 바꾸지 않는다 |
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
| ideation 프로젝트에만 | `idea` (`ideas/I<n>_<slug>.md`), `criteria` (`plan/criteria.md`), `anchor` (`plan/anchor.md`), `brief` (`brief.md`), `idea-index` (`ideas/index.md`) |

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
| idea | `candidate`, `exploring`, `selected`, `dropped`, `merged` |
| criteria | `draft`, `locked` |
| anchor | `draft`, `locked` |
| brief | `draft`, `confirmed` |

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

사양 보완을 제안할 때는 `notes/`에 사양 하나당 파일 하나로 초안을 쓴다(예: `notes/spec-drafts/catalog.md`). 초안에는 그 사양의 번호 붙은 절(`## 3. Frontmatter` …)만 쓰고, 번호 없는 절은 쓰지 않는다. 사람이 `lg spec adopt <초안>`으로 stub에 합쳐 확정한다. 초안에 있는 절만 바뀌고, 비어 있는(TODO) 절이 남으면 확정할 수 없다.
~~~~

## B.3 `specs/workflow.md` (S)

~~~~markdown
---
id: workflow
type: spec
spec_version: 8
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
- 마일스톤 종료 게이트에서는 해당 결과를 `paper/`(제안서 프로젝트는 `deliverables/`) 초안에 반영하는 것을 마일스톤 보고의 일부로 한다.

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
spec_version: 8
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
spec_version: 8
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
| `spec_version` | ✓ | `8` |
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
spec_version: 8
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
| `spec_version` | ✓ | `8` |
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

> 이 사양은 아직 공통 구조만 있다. 이 유형의 문서를 쓸 때는 [conventions.md](../conventions.md)를 지키고, 초기화 때 생성된 같은 유형의 문서가 있으면 그 구조를 따른다. 보완은 M0 진행 중에 하고, 확정은 사람이 한다(`lg spec adopt`, `spec` 커밋).

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
spec_version: 8
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
spec_version: 8
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
spec_version: 8
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
spec_version: 8
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
spec_version: 8
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
   4. 사람에게 터미널에서 `lg commit` 실행을 요청하고 멈춘다(확인 화면이 stage된 변경과 메시지를 보여 준다). 이제 사람 커밋 대기 상태다.
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
spec_version: 8
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
spec_version: 8
---
# 게이트 요청

- 시작 조건: task의 완료 기준을 모두 충족했다고 판단할 때 (Claude Code: `/task-gate <Task>`).
- 끝나는 상태: 카드가 `in-review`이고 게이트 요청 문서와 `review` 커밋이 있다. 이 task에서는 더 작업하지 않는다.

## 특별 규칙

없음. 일반 규칙을 따른다.

## 단계

1. 완료 기준을 하나씩 점검한다. 충족한 기준은 카드의 `## 완료 기준`에서 `- [x]`로 바꾼다. 충족하지 못한 기준이 있으면 게이트 대신 계속 작업할지 사람에게 묻는다.
2. task 결과 문서 `results/<M>/<Task>_result.md`를 쓴다. 마일스톤의 마지막 task면 마일스톤 보고 `results/<M>/report.md`와 Go/No-go 근거도 쓴다 ([workflow.md](../workflow.md) §8).
3. `lg`가 설치되어 있으면 지금까지의 작업을 커밋한 뒤 `lg verify --task <Task>`를 실행한다(읽기만 한다). 위반이 있으면 고칠 수 있는 것은 고치고, 이미 커밋되어 고칠 수 없는 것은 요청서의 "예상과 달랐던 점"에 적는다.
4. `specs/templates/review.md`로 `reviews/open/<Task>_gate-NN.md`를 쓴다 (`kind: gate`, [review.spec.md](../doc-types/review.spec.md)).
5. 카드를 `in-review`로 바꾸고, `STATUS.md`의 "사람 판단 대기"에 항목을 추가한다.
6. `review(<Task>): request gate` 커밋 (`Actor: agent`, `Task: <Task>`, `Review: <review id>`).
7. 사람에게 무엇을 판정해야 하는지 요약해 보고하고 멈춘다. 판정하는 방법을 끝에 쓴다: 터미널에서 `lg answer <review id>` (요청서에 직접 쓰거나 대화로 판정해도 된다).
~~~~

`escalate.md`

~~~~markdown
---
id: escalate
type: procedure
spec_version: 8
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
4. 사람에게 질문을 요약해 보고하고 멈춘다. 응답하는 방법을 끝에 쓴다: 터미널에서 `lg answer <review id>` (요청서에 직접 쓰거나 대화로 답해도 된다).
5. 사람의 응답은 `respond` 커밋으로 온다. 대화로 답하면 절차 [gate-conversation](gate-conversation.md), 커밋 이후에는 절차 [gate-apply](gate-apply.md).
~~~~

`gate-conversation.md`

~~~~markdown
---
id: gate-conversation
type: procedure
spec_version: 8
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
4. 사람에게 터미널에서 `lg commit` 실행을 요청하고 멈춘다. 확인 화면이 옮겨 적은 응답, 반영 미리보기, 메시지를 보여 준다. 내용이 다르면 사람이 `lg commit`의 편집 단계에서 고친다. 게이트 승인이면 `lg commit`이 tag를 만든다.
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
spec_version: 8
---
# 사람 커밋의 반영

- 시작 조건: `scripts/session-check`가 반영되지 않은 사람 커밋을 알렸을 때, 사람이 판정·결정·응답·승인을 커밋했다고 알렸을 때.
- 끝나는 상태: 반영되지 않은 사람 커밋이 없고(`scripts/apply-human-commits --check`가 빈 결과), 반영 커밋들이 있다.

## 특별 규칙

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|
| G4 (사람 몫의 상태 전이를 하지 않는다) | 사람 커밋이 정한 상태 전이를 커밋한다. 전이는 `scripts/apply-human-commits`가 만든 것만 쓰고, 상태 필드를 직접 편집하지 않는다 |
| G6 (`plan/roadmap.md`를 바꾸지 않는다) | 로드맵 "마일스톤" 표의 상태 칸은 `scripts/apply-human-commits`가 바꾼 것을 커밋한다. 로드맵의 다른 내용은 바꾸지 않는다 |
| G7 (`plan/criteria.md`, 잠긴 `plan/anchor.md`를 고치지 않는다, ideation) | 평가 기준·앵커 문서의 `status`·`locked_commit`은 `scripts/apply-human-commits`가 바꾼 것을 커밋한다. 내용은 바꾸지 않는다 |

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
| 결정 확정 | 그 결정에 의존하던 작업을 이어 간다. 확정 내용은 `decide` 커밋 본문(`확정:` 줄)이나 review의 `## 응답`에 있다 |
~~~~

## B.11 `specs/doc-types/idea.spec.md` (S, ideation)

~~~~markdown
---
id: idea
type: spec
spec_version: 8
status: complete
---
# 아이디어 후보 사양

## 1. 목적

연구 방향 후보 하나를 주장, 가설, 최소 실험, 가까운 선행 연구, 평가와 함께 기록한다. 후보마다 ID가 있어 방향을 틀 때 되돌아갈 수 있고, 버린 후보와 이유도 남는다.

## 2. 위치와 파일명

`ideas/I<n>_<slug>.md`. `I<n>`은 프로젝트 안에서 한 번 쓰면 다시 쓰지 않는다. 목록은 `ideas/index.md`.

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | `I<n>` |
| `type` | ✓ | `idea` |
| `spec_version` | ✓ | `8` |
| `title` | ✓ | 한 줄 |
| `status` | ✓ | `candidate` \| `exploring` \| `selected` \| `dropped` \| `merged` |
| `origin` | ✓ | `conversation` (사람이 낸 것) \| `literature` \| `agent` |
| `merged_into` | ✓ | `merged`일 때 다른 `I<n>`, 아니면 `null` |
| `decision` | ✓ | 고르거나 버린 사람 커밋의 결정 ID 또는 `null` |
| `created` | ✓ | 날짜 |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

| 섹션 | 내용 |
|---|---|
| `# <id>. <title>` | |
| `## 한 줄 주장` | 이 방향이 보이려는 것 |
| `## 가설` | 반증할 수 있는 문장 |
| `## 최소 실험` | 무엇을 돌리면 맞고 틀림이 드러나나, 자원 추정 |
| `## 가장 가까운 선행 연구와 차이` | 참고문헌 ID와 차이 |
| `## 새로움 위험` | 선점 가능성, 이미 있을 수 있는 연구 |
| `## 앵커 대비` | 잠근 앵커(`plan/anchor.md`) 하나와의 비교: 한 줄 "앵커 + X", 푸는 한계(앵커 `## 한계`의 `L<n>`), 같은 과제·지표·설정인가, 예상 효과와 반증 조건, 앵커 재현 외에 더 드는 비용. 앵커 대비로 쓸 수 없는 후보는 이 방향의 범위 밖이다(평가하지 않는다) |
| `## 평가 (기준 <기준 버전>, 앵커 <앵커 버전>)` | 아래 표. 두 버전은 `lg ideas`가 보여 주는 커밋(내용을 마지막으로 바꾼 커밋)이다. 기준과 앵커가 모두 잠기기 전에는 쓰지 않는다 |
| `## 판단 기록` | 상태가 바뀐 날짜, 근거, 커밋. 다시 매기면 이전 점수와 이유 |

평가 표:

```
| 기준 | 점수 | 근거 | 확신 |
|---|---|---|---|
| C1 | 4 | `<참고문헌 ID>` Table 2, 검색 기록 notes/search-2026-10-05.md | 중 |
| C8 | (사람) | | |
```

- 기준은 `plan/criteria.md`의 기준 전부, 같은 ID로.
- 점수는 1–5(수준별 근거 조건을 따른다). "누가"가 사람인 기준은 `(사람)`.
- 근거 없는 점수는 무효다. 확신은 상·중·하.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| 새 후보, 주장~새로움 위험 | 작성 (사람이 대화로 낸 아이디어도 옮겨 적는다, `origin: conversation`) | 작성 |
| `status: exploring`, `merged` | 가능 | 가능 |
| `status: selected`, `dropped` | 하지 않는다. 사람 커밋의 `Select`·`Drop` trailer를 반영 도구가 반영한다 | 결정 |
| `## 평가` | 기준이 잠긴 뒤에, 모든 후보를 같은 task에서 기준별로 | 사람 기준(`(사람)`)을 채운다 |

## 6. 생성·갱신 시점

- 생성: 후보를 만드는 task, 사람이 대화로 아이디어를 냈을 때.
- 평가: 기준을 잠근 뒤 평가 task. 기준이 바뀌면 모든 후보를 다시 평가한다.
- 고르기·버리기: 사람의 `gate`·`decide` 커밋(`Select: I3`, `Drop: I1, I2`).

## 7. 검증 규칙

- `id`가 파일 이름의 `I<n>`과 같다.
- `## 평가`가 있으면 `## 앵커 대비`가 비어 있지 않고 앵커 `## 한계`의 `L<n>`을 하나 이상 적는다. 앵커(`plan/anchor.md`)가 잠겨 있고 평가 표 머리의 앵커 버전이 지금 버전과 같다.
- `## 평가`가 있으면: 기준이 `plan/criteria.md`와 같고, 점수가 1–5 또는 `(사람)`이며, 에이전트 기준의 근거가 비어 있지 않고, 기준이 잠긴 상태다(`lg verify` V5).
- 버린 후보도 지우지 않는다.
~~~~

## B.12 `specs/doc-types/criteria.spec.md` (S, ideation)

~~~~markdown
---
id: criteria
type: spec
spec_version: 8
status: complete
---
# 평가 기준 사양

## 1. 목적

아이디어 후보를 평가하는 기준을 **후보를 보기 전에** 정하고 잠근다. 에이전트의 평가가 임의적이지 않도록, 기준마다 1–5 점수의 근거 조건을 미리 적는다.

## 2. 위치와 파일명

`plan/criteria.md` (ideation 프로젝트에 하나).

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | `criteria` |
| `type` | ✓ | `criteria` |
| `spec_version` | ✓ | `8` |
| `status` | ✓ | `draft` \| `locked` |
| `locked_commit` | ✓ | 잠근 사람 커밋의 해시 또는 `null` |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

| 섹션 | 내용 |
|---|---|
| `## 가진 자원` | GPU, 기간, 목표 학회와 마감, 결격 배수 (사람이 적는다) |
| `## 기준` | 표: `ID \| 기준 \| 묻는 것 \| 누가 \| 가중치 \| 결격`. ID는 `C<n>`, 누가는 `에이전트` 또는 `사람`, 가중치는 0 이상의 정수 |
| `## 수준별 근거 조건` | 기준마다 `### C<n>. <이름>`과 1–5 점수의 근거 조건 표, 필요한 근거 |

결격이 있는 기준에서 1점이면 그 후보는 결격이다.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| 전체 | 고치지 않는다. 고칠 점은 `notes/criteria-proposal.md`에 제안 | 작성 |
| `status: draft → locked`, `locked_commit` | 하지 않는다. 첫 마일스톤 T0의 게이트 승인을 반영 도구가 반영한다 | 결정 |

## 6. 생성·갱신 시점

- 생성: `lg init --kind ideation` (기본 기준).
- 잠금: 첫 마일스톤 T0 게이트 승인.
- 잠근 뒤 변경: 사람의 `plan` 커밋. 바꾸면 기준 버전(기준 내용을 마지막으로 바꾼 커밋, 잠금 반영처럼 `status`·`locked_commit`·`updated`만 바꾼 커밋은 세지 않음)이 바뀌어, 이미 매긴 평가는 "기준 변경 전"이 되고(`lg ideas`가 표시) 에이전트가 모든 후보를 다시 평가한다.

## 7. 검증 규칙

- 기준 표의 ID가 겹치지 않고, 수준별 근거 조건 절이 기준마다 있다.
- 평가는 `status: locked`일 때만 있다.
~~~~

## B.13 `specs/doc-types/brief.spec.md` (S, ideation)

~~~~markdown
---
id: brief
type: spec
spec_version: 8
status: complete
---
# 방향 확정 문서 사양

## 1. 목적

ideation에서 고른 방향을 실행 프로젝트로 넘긴다. 사람이 읽고 판정하는 문서이면서, `lg init --from`이 frontmatter를 읽는다.

## 2. 위치와 파일명

`brief.md` (ideation 프로젝트 루트에 하나).

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | `brief` |
| `type` | ✓ | `brief` |
| `spec_version` | ✓ | `8` |
| `status` | ✓ | `draft` \| `confirmed` |
| `kind` | ✓ | 넘길 실행 프로젝트의 종류: `research` \| `proposal` |
| `question` | ✓ | 확정 질문 (실행 프로젝트의 `research_question`) |
| `summary` | ✓ | 한 줄 요약 |
| `selected` | ✓ | 고른 후보 ID 목록 |
| `dropped` | ✓ | 버린 후보 ID 목록 |
| `milestones` | ✓ | 실행 프로젝트의 마일스톤 제목 목록 (1개 이상) |
| `references` | ✓ | 넘길 참고문헌 ID 목록 |
| `decision` | ✓ | 방향을 정한 결정 ID |
| `criteria_commit` | ✓ | 평가에 쓴 기준을 잠근 커밋 |
| `anchor` | ✓ | 앵커 논문의 참고문헌 ID (`plan/anchor.md`의 `reference`). 실행 프로젝트로 넘어가 첫 task가 그 재현이 된다. 실행 프로젝트의 실험별 기준선(baseline)과는 다르다 |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

`## 질문과 가설`, `## 왜 이 방향인가`(고른 후보와 `lg ideas` 비교표, 순위와 다르게 골랐으면 그 이유), `## 버린 후보와 이유`, `## 첫 마일스톤에서 할 일`, `## 남은 위험과 열린 질문`.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| 내용 | 작성 (마지막 마일스톤의 task) | 수정 |
| `status: draft → confirmed` | 하지 않는다. 마지막 마일스톤 게이트의 `Milestone-Verdict: go`를 반영 도구가 반영한다 | 결정 |

## 6. 생성·갱신 시점

생성: `lg init --kind ideation`(빈 양식). 작성: 마지막 마일스톤. 확정: 그 게이트.

## 7. 검증 규칙

- `confirmed`이면 `question`, `summary`, `milestones`가 비어 있지 않다.
- `selected`, `dropped`의 ID가 `ideas/`에 있다. `references`의 ID가 `references/catalog.md`에 있다.
~~~~

## B.14 `specs/templates/idea.md` (S, ideation)

~~~~markdown
---
id: I<n>
type: idea
spec_version: 8
title: ""
status: candidate
origin: agent
merged_into: null
decision: null
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
---
# I<n>. <title>

## 한 줄 주장

## 가설

## 최소 실험

## 가장 가까운 선행 연구와 차이

## 새로움 위험

## 앵커 대비

## 판단 기록
~~~~

## B.15 `specs/doc-types/anchor.spec.md` (S, ideation)

~~~~markdown
---
id: anchor
type: spec
spec_version: 8
status: complete
---
# 앵커 연구 사양

## 1. 목적과 역할

후보를 평가하기 전에 **앵커 연구 하나**를 정하고 잠근다. 앵커는 두 가지의 기준점이다.

| 역할 | 앵커 문서가 정하는 것 | 후보가 쓰는 것 (`## 앵커 대비`) |
|---|---|---|
| 성능 기준점 | 과제·벤치마크, 지표와 보고 수치, 설정(backbone, 데이터, 학습량) | 같은 과제·지표·설정에서 "앵커 + X"가 무엇을 얼마나 바꾸나, 반증 조건 |
| 기여 기준점 | 도달점(이 앵커와 그 계열 연구가 이미 보인 것), 한계(아직 못 한 것과 그 근거, `L<n>`) | 어느 한계(`L<n>`)를 푸나. 도달점을 다시 보이는 것은 기여가 아니다 |

앵커가 없으면 후보마다 비교 대상·과제·설정이 달라 후보끼리 비교할 수 없고, 무엇에 대한 기여인지도 후보마다 달라진다.

**앵커는 기준선(baseline)이 아니다.** 앵커는 ideation에서 후보를 서로 비교하기 위한 기준점 하나이고, 실행 프로젝트에서는 첫 재현 대상이 된다. 실행 프로젝트의 실험마다 비교하는 대상은 기준선(baseline)이라 부르고, 실험마다 따로 정한다(여럿일 수 있다).

## 2. 위치와 파일명

`plan/anchor.md` (ideation 프로젝트에 하나).

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | `anchor` |
| `type` | ✓ | `anchor` |
| `spec_version` | ✓ | `8` |
| `status` | ✓ | `draft` \| `locked` |
| `locked_commit` | ✓ | 잠근 사람 커밋의 해시 또는 `null` |
| `lock_task` | ✓ | 앵커 선정 task ID(그 게이트의 `Verdict: approve`에서 잠긴다) 또는 `null`(첫 마일스톤의 마지막 게이트 go에서 잠긴다) |
| `reference` | ✓ | 앵커 논문의 참고문헌 ID |
| `task` | ✓ | 과제·벤치마크 |
| `metric` | ✓ | 지표 |
| `reported` | ✓ | 보고 수치와 표 번호 |
| `updated` | ✓ | 날짜 |

## 4. 선정 기준

후보 앵커 2–4개를 아래 기준마다 비교하고(`## 후보 앵커 비교`의 열) 하나를 고른다.

1. **같은 문제:** 연구 질문과 같은 문제를 같은 과제·지표로 푼다. 이 앵커 위의 결과로 연구 질문에 답할 수 있다.
2. **강한 대표:** 그 문제의 최신 대표 방법이다. 최근 12개월 안에 나왔거나, 최근 목표 학회 논문들이 주 비교 대상으로 쓴다. 약한 앵커를 이기는 것은 기여가 아니다.
3. **재현 가능성:** 공개 코드(가능하면 체크포인트)와 표준 벤치마크의 보고 수치가 있고, 가진 자원(`plan/criteria.md`)으로 재현할 수 있다.
4. **근거 있는 한계:** 연구 질문과 관련된 한계가 근거(저자의 서술, 후속 연구의 지적, 예비 실험)와 함께 드러나 있다. 한계가 없으면 그 위에서 기여를 말할 수 없다.
5. **하나만:** 판단은 이 앵커 하나로 한다. 다른 비교 대상은 후보 안에서 보조로 적는다.

## 5. 본문 구조

| 절 | 내용 |
|---|---|
| `## 선정한 앵커` | 논문, 과제·벤치마크, 지표와 보고 수치(표 번호), 설정, 공개 코드·체크포인트, 재현 비용 |
| `## 도달점` | 이 앵커와 그 계열 연구가 이미 보인 것: 무엇을, 어떤 방법으로, 어떤 수치까지. 참고문헌 ID와 위치 |
| `## 한계` | 표 `\| ID \| 한계 \| 근거 \| 연구 질문과의 관계 \|`. ID는 `L1`, `L2`, …. 근거는 참고문헌 ID와 위치(저자 서술, 후속 연구), 또는 예비 실험 결과의 경로 |
| `## 선정 기준` | §4의 다섯 기준 (프로젝트에 맞게 고칠 수 있다) |
| `## 후보 앵커 비교` | 후보 2–4개를 §4의 기준마다 비교한 표 |
| `## 선정 이유` | 에이전트 추천과 근거. 사람이 다르게 고르면 그 이유 |

## 6. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| 비교, 도달점, 한계, 추천, 선정 이유 | 작성 (잠기기 전) | 수정 |
| 선정(frontmatter `reference` 등), `lock_task` | 추천과 앵커 선정 task ID를 채운다 (잠기기 전) | 결정 |
| `status: draft → locked`, `locked_commit` | 하지 않는다. 반영 도구가 `lock_task` 게이트의 approve(`lock_task`가 `null`이면 첫 마일스톤의 go)를 반영한다 | 결정 |
| 잠근 뒤 | 고치지 않는다 (G7). 새로 찾은 한계는 `notes/anchor-proposal.md`에 제안한다 | `plan` 커밋으로만. 바꾸면 모든 후보를 다시 쓰고 평가한다 |

## 7. 생성·갱신 시점

생성: `lg init --kind ideation`. 작성: 앵커 선정 task(보통 첫 마일스톤의 지형 조사). 잠금: `lock_task` 게이트의 approve, `lock_task`가 `null`이면 첫 마일스톤의 마지막 게이트(go).

## 8. 검증 규칙

- 잠그는 반영은 다음이 모두 맞을 때만 한다(아니면 반영 도구가 멈추고, `lg answer`·`lg commit`은 판정 커밋 전에 알린다): `reference`, `task`, `metric`, `reported`가 비어 있지 않고, `reference`가 `references/catalog.md`에 있고, `## 한계`에 `L<n>`이 하나 이상 있다.
- 후보의 평가는 앵커가 잠긴 뒤에만 있고, 평가 표 머리의 앵커 버전이 지금 버전과 같다.
- 평가가 있는 후보의 `## 앵커 대비`는 앵커 `## 한계`에 있는 `L<n>`을 하나 이상 적는다.
~~~~

---

# 부록 C. 실행 파일 원문

## C.1 `.lg/hooks/commit-msg` (S, 755)

~~~~python
#!/usr/bin/env python3
"""labgate commit-msg hook (spec_version 8).

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
IDEA_ID_RE = re.compile(r"^I\d+$")
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
    for key in ("Select", "Drop"):  # ideation 후보 고르기·버리기 (§26)
        if key in trailers and ctype not in ("gate", "decide"):
            errors.append(f"{key} trailer는 gate·decide 커밋에만 쓸 수 있습니다.")
        check_list(trailers, key, IDEA_ID_RE, errors)
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
"""labgate 세션 시작 점검 (spec_version 8).

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
"""labgate 사람 커밋 반영 도구 (spec_version 8).

사람 커밋의 trailer가 정한 상태 전이를 문서의 상태 필드에 반영한다. 커밋하지 않는다.
표준 라이브러리만 사용한다. 사양: labgate 설계 문서 §21.

사용법:
  scripts/apply-human-commits            가장 오래된 반영되지 않은 사람 커밋 하나를 반영
  scripts/apply-human-commits --check    바꾸지 않고 반영되지 않은 사람 커밋을 나열
  scripts/apply-human-commits --tidy     지난 반영의 커밋 여부를 JSON 한 줄로 알린다 (session-check가 쓴다)
  scripts/apply-human-commits --preview  표준 입력의 커밋 메시지가 반영되면 생길 변화를 출력한다. 쓰지 않는다 (lg answer가 쓴다)
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
    """반영되지 않은 사람 커밋: [(해시, 타입, scope, 헤더, trailer, 메시지)] (오래된 순)."""
    humans = human_emails()
    history = commits()
    applied = applied_hashes(history)
    pending = []
    for sha, email, body in history:
        ctype, scope, header, trailers = parse(body)
        if email in humans and is_target(ctype, trailers) and not any(sha.startswith(p) for p in applied):
            pending.append((sha, ctype, scope, header, trailers, body))
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

    def milestone(self, milestone, label, sources, target, satisfied):
        """마일스톤 문서의 상태와, 로드맵 "마일스톤" 표의 그 행을 함께 바꾼다."""
        mfile = f"plan/milestones/{milestone}/milestone.md"
        if self.transition(mfile, f"마일스톤 {milestone} {label}", sources, target, satisfied):
            self.table_row("plan/roadmap.md", milestone, 2, target)

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

    def review_text(self, task_id, kind, review_id):
        """반영할 review 문서의 내용 (없으면 None)."""
        if review_id:
            path = ROOT / "reviews" / "open" / f"{review_id}.md"
        else:
            found = sorted((ROOT / "reviews" / "open").glob(f"{task_id}_{kind}-*.md"))
            path = found[-1] if found else None
        return path.read_text(encoding="utf-8") if path and path.is_file() else None

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

    def decision(self, decision_id, short, content=None):
        found = sorted((ROOT / "decisions").glob(f"{decision_id}_*.md"))
        if len(found) != 1:
            raise CannotApply(f"결정 문서를 하나로 찾지 못했습니다: decisions/{decision_id}_*.md ({len(found)}개)")
        rel = found[0].relative_to(ROOT).as_posix()
        if self.transition(rel, f"결정 {decision_id}", {"proposed", "discussing"}, "confirmed", set()):
            self.table_row("decisions/index.md", decision_id, 2, "confirmed", 4, f"`{short}`")
            if content:  # 사람이 쓴 확정 내용을 그대로 "확정 내용" 절에 (절이 없으면 건너뛴다)
                self.set_section(rel, "확정 내용", f"{content}\n\n(사람 커밋 `{short}`)")

    def idea(self, idea_id, target, short):
        """ideation 후보를 고르거나 버린다 (Select·Drop, §26)."""
        found = sorted((ROOT / "ideas").glob(f"{idea_id}_*.md"))
        if len(found) != 1:
            raise CannotApply(f"후보 문서를 하나로 찾지 못했습니다: ideas/{idea_id}_*.md ({len(found)}개)")
        rel = found[0].relative_to(ROOT).as_posix()
        if self.transition(rel, f"후보 {idea_id}", {"candidate", "exploring"}, target, {target}):
            self.table_row("ideas/index.md", idea_id, 2, target)
            if frontmatter_value(self.read(rel), "decision", rel, required=False) is not None:
                self.texts[rel] = set_frontmatter(self.read(rel), "decision", f"'{short}'", rel)

    def set_field(self, rel, key, value):
        """frontmatter 필드가 있으면 값을 바꾼다 (없으면 그대로)."""
        if not (ROOT / rel).is_file() and rel not in self.texts:
            return
        if frontmatter_value(self.read(rel), key, rel, required=False) is not None:
            self.texts[rel] = set_frontmatter(self.read(rel), key, value, rel)
            self.log.append(f"  {rel}: {key} → {value}")

    def set_section(self, rel, heading, body):
        """`## heading` 절의 내용을 바꾼다. 절이 없으면 그대로 둔다."""
        text = self.read(rel)
        m = re.search(rf"^## {re.escape(heading)}[ \t]*$", text, re.M)
        if not m:
            return
        end = text.find("\n## ", m.end())
        tail = "" if end == -1 else text[end:]
        self.texts[rel] = text[:m.end()] + "\n\n" + body.strip() + "\n" + tail
        self.log.append(f"  {rel}: {heading} 절에 확정 내용")

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


def milestone_ids():
    return sorted((p.name for p in (ROOT / "plan" / "milestones").glob("M*") if re.fullmatch(r"M\d+", p.name)),
                  key=lambda m: int(m[1:]))


def first_milestone():
    ids = milestone_ids()
    return ids[0] if ids else None


def last_milestone():
    """plan/milestones/ 아래 번호가 가장 큰 마일스톤 ID."""
    ids = milestone_ids()
    return ids[-1] if ids else None


ANCHOR = "plan/anchor.md"


def anchor_lock_task(plan):
    """앵커 문서의 lock_task (앵커가 없거나 비어 있으면 None)."""
    if not (ROOT / ANCHOR).is_file() and ANCHOR not in plan.texts:
        return None
    value = frontmatter_value(plan.read(ANCHOR), "lock_task", ANCHOR, required=False)
    return None if value in (None, "", "null", "~") else value


def anchor_lock_issues(text):
    """잠글 수 없는 이유 (앵커 사양 §8): 비어 있는 선정 필드, 목록에 없는 참고문헌, 한계 없음."""
    issues = []
    for key in ("reference", "task", "metric", "reported"):
        if frontmatter_value(text, key, ANCHOR, required=False) in (None, "", "null", "~"):
            issues.append(f"{key}가 비어 있음")
    ref = frontmatter_value(text, "reference", ANCHOR, required=False)
    catalog = ROOT / "references" / "catalog.md"
    if ref not in (None, "", "null", "~") and catalog.is_file() and not re.search(
            rf"^\|\s*`?{re.escape(ref)}`?\s*\|", catalog.read_text(encoding="utf-8"), re.M):
        issues.append(f"참고문헌 {ref}가 references/catalog.md에 없음")
    if not limitation_ids(text):
        issues.append("## 한계에 L<n>이 없음")
    return issues


def limitation_ids(text):
    m = re.search(r"^## 한계[ \t]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return re.findall(r"^\|\s*`?(L\d+)`?\s*\|", m.group(1), re.M) if m else []


def lock_anchor(plan, short):
    text = plan.read(ANCHOR)
    if frontmatter_value(text, "status", ANCHOR) == "draft":
        issues = anchor_lock_issues(text)
        if issues:
            raise CannotApply("앵커를 잠글 수 없습니다 (plan/anchor.md): " + ", ".join(issues)
                              + ". 앵커 문서를 채운 뒤 판정하거나, 앵커를 나중에 정하려면 lock_task에 앵커 선정 task를 적으세요")
    if plan.transition(ANCHOR, "앵커 잠금", {"draft"}, "locked", {"locked"}):
        plan.set_field(ANCHOR, "locked_commit", f"'{short}'")


def confirmed_contents(body, review_text, decisions):
    """결정 ID → 사람이 쓴 확정 내용. decide 커밋 본문의 `확정: …`(결정이 하나일 때),
    또는 review `### 확정 결정`의 `- D0.1: …` 줄."""
    out = {}
    if review_text:
        m = re.search(r"^### 확정 결정[ \t]*\n(.*?)(?=^#{2,3} |\Z)", review_text, re.M | re.S)
        for line in (m.group(1).splitlines() if m else []):
            found = re.match(r"^- (D\d+\.\d+): (.+)$", line.strip())
            if found:
                out[found.group(1)] = found.group(2).strip()
    lines = [l[len("확정: "):].strip() for l in (body or "").splitlines() if l.startswith("확정: ")]
    if len(decisions) == 1 and lines:
        out.setdefault(decisions[0], lines[0])
    return out


def plan_for(sha, ctype, scope, trailers, today, body=""):
    """한 사람 커밋의 반영 계획과 커밋 메시지."""
    plan = Plan(today)
    short = sha[:7]
    task = trailers.get("Task")
    for i in split_list(trailers.get("Select")):  # ideation (§26): gate·decide에만 있다
        plan.idea(i, "selected", short)
    for i in split_list(trailers.get("Drop")):
        plan.idea(i, "dropped", short)
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
        if verdict == "approve" and task.endswith("-T0"):
            plan.milestone(milestone, "착수", {"planned"}, "active", {"active", "closed"})
        if verdict == "approve" and task == "M0-T0" and (ROOT / "plan/criteria.md").is_file():
            # ideation: 첫 T0 게이트 승인이 평가 기준을 잠근다 (§26.6)
            if plan.transition("plan/criteria.md", "평가 기준 잠금", {"draft"}, "locked", {"locked"}):
                plan.set_field("plan/criteria.md", "locked_commit", f"'{short}'")
        lock_task = anchor_lock_task(plan)
        if verdict == "approve" and lock_task == task:
            # ideation: 앵커 선정 task의 승인이 앵커를 잠근다 (§27)
            lock_anchor(plan, short)
        mv = trailers.get("Milestone-Verdict")
        if mv:
            plan.milestone(milestone, "판정", {"active"}, "closed", {"closed"})
            plan.set_field(f"plan/milestones/{milestone}/milestone.md", "go_nogo", mv)
            if mv == "go" and lock_task is None and (ROOT / "plan/anchor.md").is_file() \
                    and milestone == first_milestone():
                # ideation: lock_task가 없으면 첫 마일스톤의 go가 앵커를 잠근다 (§27)
                lock_anchor(plan, short)
            if mv == "go" and (ROOT / "brief.md").is_file() and milestone == last_milestone():
                # ideation: 마지막 마일스톤의 go가 방향을 확정한다 (§26)
                plan.transition("brief.md", "방향 확정", {"draft"}, "confirmed", {"confirmed"})
        review_text = plan.review_text(task, "gate", trailers.get("Review"))
        decisions = split_list(trailers.get("Decisions"))
        contents = confirmed_contents(body, review_text, decisions)
        for d in decisions:
            plan.decision(d, short, contents.get(d))
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
        contents = confirmed_contents(body, None, decisions)
        for d in decisions:
            plan.decision(d, short, contents.get(d))
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


def preview(message):
    """아직 커밋하지 않은 사람 커밋 메시지 하나의 반영 계획 (§24.5.4). 아무것도 쓰지 않는다."""
    ctype, scope, header, trailers = parse(message)
    if not is_target(ctype, trailers):
        print(f"반영할 것이 없습니다: {header}")
        return 0
    try:
        plan, _ = plan_for("(새 커밋)", ctype, scope, trailers, datetime.date.today().isoformat(), message)
    except CannotApply as e:
        print(f"✗ 이 커밋은 반영할 수 없습니다: {e}", file=sys.stderr)
        return 1
    print(f"미리보기: {header}")
    print("\n".join(plan.log) if plan.log else "  (바뀐 파일 없음)")
    return 0


def main(argv):
    try:
        if "--tidy" in argv:
            state = last_apply()
            if state:
                print(json.dumps({"state": state[0], "applies": state[1], "paths": state[2]}, ensure_ascii=False))
            return 0
        if "--preview" in argv:
            return preview(sys.stdin.read())
        pending = unreflected()
        if "--check" in argv:
            for sha, _, _, header, _, _ in pending:
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
        sha, ctype, scope, header, trailers, body = pending[0]
        plan, message = plan_for(sha, ctype, scope, trailers, datetime.date.today().isoformat(), body)
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
