# `rp` CLI 설계 문서 — v1 (`rp init`)

> 문서 버전: 1.1 · 대상: CLI 구현자(사람 또는 코딩 에이전트)
> 이 문서만으로 `rp init`을 구현·테스트할 수 있어야 한다. 생성될 모든 파일의 원문은 부록 A·B에 있다.

**1.1 변경 (2026-10-01, 구현 전 검토 반영)**

- §5.3: 폴더·Git 검사를 입력 수집 앞으로 이동, dry-run은 경고만, 상위 폴더 자동 생성, Ctrl-C → 130
- §5.4, §7.2: 생성 파일 수 정정(83 → 67)과 계산식 추가
- §8.1: 점(`.`)으로 시작하는 템플릿은 `dot-` 접두어로 저장
- §11.1, C.1: commit-msg hook이 가위 줄(`commit -v`) 아래를 무시. §14.1에 사례 추가
- §12: `--author` 금지 이유 정정
- A.5: 권한 규칙을 공백 형식으로 바꾸고 `git push -f` 추가, 한계 명시
- B.2 §4: frontmatter 예외 목록과 `type` 값 표 정리. stub 사양 `catalog-entry` → `catalog`
- B.3 §6.2, A.3, A.6: 대화 경로의 `.rp/pending/` 쓰기 허용, "사람 커밋 대기 상태"에서는 에이전트 커밋 금지

---

## 0. 읽는 법

- §1–3: 무엇을 왜 만드는가 (범위, 확정된 결정, 용어)
- §4–13: 어떻게 만드는가 (명령, 설정, 생성 결과, 모듈, Git, hook, 오류)
- §14–15: 무엇으로 완성을 판단하는가 (테스트, 수용 기준), 이후 확장
- 부록 A: 프로젝트 루트·계획·참고문헌 등 생성 문서 템플릿 원문
- 부록 B: `specs/` 문서 원문 (완성 사양 5종, stub 생성 규칙, 양식)
- 부록 C: commit-msg hook, agent-commit 스크립트 원문

표기: `<...>`는 값 자리, `{{ ... }}`/`{% ... %}`는 Jinja2 템플릿 문법이다.

---

## 1. 목적과 범위

### 1.1 목적

에이전트(초기에는 Claude Code)가 작업하고 사람이 task 경계마다 승인하는 연구 프로젝트의 작업 공간을 한 번의 명령으로 초기화한다. 초기화 결과에는 폴더 구조, 문서 사양, 에이전트 규칙, 커밋 규약 검사 hook, 초기 Git 커밋이 포함된다.

### 1.2 v1 범위

| 포함 | 제외 (§15 향후 확장) |
|---|---|
| `rp init` (대화형 / 설정 파일) | `rp gate`, `rp status`, `rp validate`, `rp upgrade` |
| 폴더·문서 생성, 완성 사양 5종, stub 사양 11종 | 기존 계획서 자동 가져오기 |
| `commit-msg` hook, `scripts/agent-commit` | 문서 내용 검증 도구 |
| Claude Code 연결 파일 (선택) | 다른 에이전트 도구 연결 |
| Git 저장소 초기화, 사람 신원의 `init` 커밋 | 원격 저장소 설정 |
| 문서 언어: 한국어 | 다국어 템플릿 |

---

## 2. 확정된 설계 결정

| 항목 | 결정 |
|---|---|
| 브랜치 | `main` 하나의 선형 이력. task 브랜치 없음. 게이트 지점은 tag(`gate/<Task>`, `milestone/<M>-<verdict>`)로 표시 |
| 승인 단위 | task = 승인 게이트 사이의 작업 단위. 게이트 1회가 "현재 task 판정 + 다음 task 승인"을 함께 처리 |
| 사람/에이전트 구분 | (1) 커밋 작성자 신원 분리, (2) 사람 전용 커밋 타입. hook으로 둘의 일치를 강제 |
| 대화로 전달된 판정 | 에이전트는 변경을 stage하고 커밋 메시지 초안만 작성. 커밋은 사람이 실행 |
| 참고문헌 원본 | 전부 Git에 포함 (비공개 저장소 전제). `references/library/`에 ID 파일명으로 한 번만 저장 |
| 사양 작성 순서 | `conventions`, `workflow`, `git-commit`, `task-card`, `review` 5종은 완성본으로 생성. 나머지 11종은 stub으로 생성 후 M0 진행 중 보완 |
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

---

## 4. 기술 스택과 실행 환경

| 항목 | 선택 |
|---|---|
| 언어 | Python ≥ 3.10 (CLI). 생성되는 hook은 Python ≥ 3.9 표준 라이브러리만 사용 |
| 명령 구조 | `typer` ≥ 0.12 |
| 대화형 입력 | `questionary` ≥ 2.0 |
| 템플릿 | `jinja2` ≥ 3.1 |
| 설정 | `pyyaml` ≥ 6.0, 검증은 `pydantic` ≥ 2.6 |
| 테스트 | `pytest` |
| 배포 | `pipx install .` (패키지명 `rp-research`, 명령명 `rp`) |
| 외부 의존 | `git` 실행 파일 (`--no-git`이면 불필요), 생성된 프로젝트에서 `python3`, `bash` |
| 지원 OS | macOS, Linux. Windows는 Git Bash 환경에서 최선 노력(공식 지원 아님) |

명령명 `rp`와 패키지명은 임시이며 바꿔도 이 문서의 다른 내용에는 영향이 없다.

---

## 5. 명령 사양: `rp init`

### 5.1 형식

```
rp init [PATH] [--config FILE] [--force] [--dry-run] [--no-git] [--yes]
rp --version
```

| 인자/옵션 | 설명 |
|---|---|
| `PATH` | 생성할 프로젝트 폴더. 생략 시 대화형으로 묻는다. `--config` 사용 시 필수 |
| `--config FILE` | 설정 파일(§6.1 형식)로 모든 입력을 받는다. 대화형 질문 없음 |
| `--force` | 비어 있지 않은 폴더에도 생성을 허용한다. **기존 파일을 덮어쓰지는 않는다** (§5.3) |
| `--dry-run` | 생성될 파일 트리와 개수만 출력하고 아무것도 쓰지 않는다 |
| `--no-git` | Git 초기화, hook 경로 설정, 초기 커밋을 하지 않는다 |
| `--yes` | 대화형 모드의 마지막 확인 질문을 건너뛴다 |

Typer는 명령이 하나뿐인 앱에서 하위 명령을 생략해 버리므로, `@app.callback()`으로 빈 콜백을 등록해 `rp init` 형태를 유지한다.

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

어느 단계에서든 Ctrl-C(`KeyboardInterrupt`, questionary가 `None`을 돌려주는 경우 포함)는 쓰기 전이면 그대로, 쓰기 중이면 §8.3 롤백 후 코드 130으로 끝낸다. Typer/click의 기본 `Abort` 처리(코드 1)에 맡기지 않는다.

### 5.4 성공 시 출력 예

```
✓ 프로젝트를 만들었습니다: /home/me/research/cap-partition
  파일 67개, 초기 커밋 3f2a1c9 (init)

다음 단계:
  1. notes/ 에 기존 계획 자료를 넣으세요.
  2. STATUS.md 를 확인하고, M0-T0 을 승인하세요:
       git commit --allow-empty -m "plan(M0-T0): approve initial task" -m "Actor: human
     Approve: M0-T0"
     (M0-T0 카드의 status 를 approved 로 바꿔 함께 커밋해도 됩니다)
  3. 에이전트 세션을 시작하세요 (Claude Code: /session-start)
```

---

## 6. 설정

### 6.1 설정 파일 형식 (`--config`, 그리고 생성되는 `.rp/project.yaml`)

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
- 생성되는 `.rp/project.yaml`에는 위 내용에 다음이 추가된다:
  ```yaml
  generated:
    rp_version: "0.1.0"
    spec_version: 1
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
├── .rp/
│   ├── project.yaml
│   ├── identities.json
│   └── hooks/
│       └── commit-msg                 # 실행 권한
├── .claude/                           # claude_code=true
│   ├── settings.json
│   └── commands/
│       ├── session-start.md
│       ├── task-start.md
│       ├── task-gate.md
│       ├── escalate.md
│       └── session-close.md
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
│   └── templates/
│       ├── task-card.md
│       └── review.md
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
│   └── agent-commit                   # 실행 권한
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
| `.claude/commands/<name>.md` | S | A.6 | claude_code, 5개 | 644 |
| `STATUS.md` | J | A.7 | | 644 |
| `.gitignore` | S | A.8 | | 644 |
| `.rp/project.yaml` | G | §6.1 | | 644 |
| `.rp/identities.json` | G | §10.3 | | 644 |
| `.rp/hooks/commit-msg` | S | C.1 | | 755 |
| `scripts/agent-commit` | S | C.2 | | 755 |
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
| `.gitkeep` 들 | G | 빈 파일 | §7.1의 빈 폴더마다 | 644 |

`.gitkeep` 목록: `references/library/`, `experiments/src/`, `experiments/tests/`, `experiments/<M>/`, `runs/`, `results/<M>/figures/`, `results/<M>/tables/`, `reviews/open/`, `reviews/closed/`, `logs/`, `data/`, `paper/`, `notes/`, `env/`.

모든 텍스트 파일은 UTF-8, LF 줄바꿈, 파일 끝 개행 1개로 쓴다.

생성 파일 수 (마일스톤 N개): `claude_code=true`이면 `49 + 6N`, `false`이면 `42 + 6N` (`CLAUDE.md`와 `.claude/` 7개 제외). 마일스톤 하나당 6개는 `milestone.md`, `<M>-T0.md`, `task-map.md`, `.gitkeep` 3개(`experiments/<M>/`, `results/<M>/figures/`, `results/<M>/tables/`)다. 예: N=3, Claude Code 사용 → 67개.

---

## 8. 패키지 구조와 모듈 책임

### 8.1 소스 트리

```
rp-research/
├── pyproject.toml
├── README.md
├── src/rp/
│   ├── __init__.py          # __version__ = "0.1.0", SPEC_VERSION = 1
│   ├── cli.py               # Typer 앱, init 명령, 종료 코드 처리
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

`templates/` 아래 파일 이름은 출력 경로를 따른다. 예: `jinja/plan/milestones/milestone.md.j2`, `static/specs/workflow.md`. 반복 생성되는 파일은 `plan.py`가 템플릿 하나를 여러 경로로 렌더링한다. 템플릿은 `importlib.resources.files("rp") / "templates"`로 읽는다.

예외: 출력 경로가 `.`으로 시작하는 파일·폴더는 템플릿 쪽에서 앞의 `.`을 빼고 `dot-`를 붙여 저장한다 (`static/dot-gitignore` → `.gitignore`, `static/dot-claude/settings.json` → `.claude/settings.json`, `static/dot-rp/hooks/commit-msg` → `.rp/hooks/commit-msg`). 이유: (1) `templates/static/.gitignore`를 그대로 두면 이 CLI 저장소의 Git이 그것을 실제 ignore 규칙으로 적용해 템플릿 폴더 안의 파일을 무시한다. (2) 빌드 도구가 숨김 파일·VCS 무시 파일을 패키지에서 빼는 경우가 있다. 변환은 `plan.py`의 경로 매핑 한 곳에서만 한다. 패키지 테스트에서 wheel에 모든 템플릿이 들어갔는지 확인한다.

### 8.2 `pyproject.toml`

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "rp-research"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
  "typer>=0.12",
  "questionary>=2.0",
  "jinja2>=3.1",
  "pyyaml>=6.0",
  "pydantic>=2.6",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
rp = "rp.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/rp"]
```

### 8.3 쓰기 규칙 (`writer.py`)

- **대상이 존재하지 않을 때:** 부모 폴더가 없으면 먼저 `os.makedirs`로 만들고, 이때 새로 만든 상위 폴더를 기록해 둔다. 같은 부모 폴더에 `.<name>.rp-tmp-<8자리 hex>` 임시 폴더를 만들어 모두 쓴 뒤 `os.rename`으로 대상 이름으로 바꾼다. 중간 실패 시 임시 폴더와 새로 만든 상위 폴더를 삭제한다.
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
- 렌더링 후 결과에 `{{` 또는 `{%`가 남아 있으면 오류로 처리한다 (템플릿 실수 감지).

공통 컨텍스트:

| 이름 | 내용 |
|---|---|
| `project` | `name`, `slug`, `summary`, `research_question` |
| `humans` | `[{name, email}]` |
| `agent` | `{name, email}` |
| `milestones` | `[{id: "M0", index: 0, title}]` |
| `claude_code` | bool |
| `today` | `YYYY-MM-DD` (로컬 날짜) |
| `rp_version`, `spec_version` | 문자열, 정수 |

마일스톤별 템플릿(A.10, A.11, A.14)에는 추가로 `m`(해당 마일스톤), `prev`(직전 마일스톤 또는 `None`)를 넘긴다. stub 사양 템플릿(B.7)에는 `stub`(B.7 표의 한 행)을 넘긴다.

---

## 10. Git 연동 (`gitops.py`)

### 10.1 순서 (`--no-git`이 아닐 때)

1. `git init` 후 `git symbolic-ref HEAD refs/heads/main` (Git 버전과 무관하게 기본 브랜치를 `main`으로).
2. `git config user.name "<humans[0].name>"`, `git config user.email "<humans[0].email>"` (저장소 로컬 설정).
3. `git config core.hooksPath .rp/hooks`.
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

### 10.3 `.rp/identities.json`

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
- 헤더가 `Merge `, `Revert `, `fixup! `, `squash! `, `amend! `로 시작하면 검사하지 않고 통과.

### 11.2 타입

| 분류 | 타입 | 허용 Actor |
|---|---|---|
| 사람 전용 | `gate`, `decide`, `plan`, `spec`, `respond` | `human` |
| 에이전트 | `task`, `exp`, `run`, `result`, `ref`, `propose`, `review`, `log` | `agent` |
| 공통 | `init`, `chore` | 둘 다 |

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

`git commit --no-verify`는 막을 수 없다. 규약상 사람만 긴급 시 사용할 수 있고(`specs/git-commit.md`), 에이전트는 사용 금지(`AGENTS.md`).

---

## 12. `scripts/agent-commit`

원문은 부록 C.2. `identities.json`의 에이전트 이름·이메일을 `GIT_AUTHOR_*`, `GIT_COMMITTER_*` 환경 변수로 설정하고 `git commit "$@"`을 실행한다. 에이전트는 `git commit` 대신 이것만 사용한다. Claude Code에서는 `.claude/settings.json`이 `git commit` 직접 실행을 막는다. `--author` 옵션은 막는다. hook은 `--author`로 지정한 작성자도 그대로 인식하므로(Git이 hook 실행 시 `GIT_AUTHOR_*`를 내보냄) 판별 자체는 문제가 없다. 막는 이유는 에이전트가 `--author`로 사람 이메일을 넣으면 사람 전용 타입 커밋을 만들 수 있기 때문이다. 이 스크립트는 작성자를 항상 에이전트로 고정한다.

---

## 13. 오류 메시지 원칙

- 무엇이 잘못되었는지, 어떤 값이었는지, 어떻게 고치는지를 한 줄씩.
- 검증 오류는 모아서 한 번에 출력.
- 예외 traceback은 `RP_DEBUG=1` 환경 변수가 있을 때만 출력.

---

## 14. 테스트 계획과 수용 기준

### 14.1 단위 테스트

| 대상 | 내용 |
|---|---|
| `config` | 정상 설정 로드, 각 검증 규칙 위반 시 해당 필드 경로가 오류에 포함, 이메일 소문자화, 마일스톤 ID 자동 부여, `id` 불일치 오류, 에이전트 기본값 |
| `render` | `yq` 필터가 따옴표·콜론·한글을 안전하게 처리, StrictUndefined로 누락 변수 감지, 잔여 `{{` 감지 |
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
| h | `gate(M1-T2): approve, next M1-T3` + `Actor: human`, `Task: M1-T2`, `Verdict: approve`, `Source: document`, `Next: M1-T3` | 통과 |
| h | 위에서 `Source` 누락 | 실패 |
| h | 위에서 `Verdict: ok` | 실패 |
| a | `task(M1-T3): x` + `Actor: agent`, `Task: M1-T2` | 실패 (scope 불일치) |
| a | `exp: add model` (trailer 없음) | 실패 (Actor 누락) |
| 등록 안 된 `z@y.com` | 정상 형식 | 실패 (등록되지 않은 작성자) |
| h | `decide(D1.3): confirm PR metric` + `Actor: human`, `Decisions: D1.3`, `Source: conversation` | 통과 |
| h | `plan(M0-T0): approve initial task` + `Actor: human`, `Approve: M0-T0` | 통과 |
| 아무나 | `Merge branch 'x'` | 통과 |
| a | 헤더 73자 이상 | 실패 |
| h | 통과하는 `gate` 메시지 뒤에 가위 줄과 diff(`+foo: bar` 같은 줄 포함)가 붙음 | 통과 |

### 14.2 통합 테스트

1. 설정 파일로 `rp init <tmp>/proj --config cfg.yaml` → 종료 코드 0, `git log`에 커밋 1개, 작성자 = 사람, `git config core.hooksPath` = `.rp/hooks`.
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
- 생성된 모든 Markdown 문서에 렌더링되지 않은 템플릿 문법이 없음.
- 생성 직후 `git status`가 깨끗함.
- 사람이 §5.4의 안내대로 `M0-T0` 승인 커밋을 실행하면 hook을 통과함.

---

## 15. 향후 확장 (v1 범위 밖, 설계 시 고려만)

| 명령 | 역할 | v1에서 미리 지킬 것 |
|---|---|---|
| `rp gate <verdict> <Task>` | review 응답 기록, 카드 상태 변경, 사람 신원 `gate` 커밋, tag 생성을 한 번에 | 상태값·trailer를 사양대로 고정 |
| `rp status` | frontmatter와 커밋 이력으로 `STATUS.md` 재생성 | 모든 문서에 frontmatter |
| `rp validate` | 문서를 사양의 검증 규칙으로 검사 | 사양마다 §7 검증 규칙 섹션 유지 |
| `rp upgrade` | 사양 버전 갱신 | `spec_version` 필드 |
| `rp doctor` | hooksPath 등 로컬 설정 점검·복구 | `.rp/` 안에 필요한 정보 보관 |
| 계획서 가져오기 | Markdown 계획서 → roadmap, milestone, decisions | — |


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
- 게이트를 통과시키면 tag를 남긴다: `git tag gate/<Task>`.

## 저장소를 새로 클론했을 때

```bash
git config core.hooksPath .rp/hooks
git config user.name "<이름>"
git config user.email "<.rp/identities.json에 등록된 이메일>"
```

<sub>rp {{ rp_version }}로 {{ today }}에 초기화됨 · spec_version {{ spec_version }}</sub>
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
| `.rp/` | 프로젝트 설정, 신원, Git hook | 수정하지 않음 (`.rp/pending/`만 예외: 사람 커밋 대기 중인 메시지 초안, Git 제외) |
{% if claude_code %}
| `.claude/` | Claude Code 설정과 슬래시 커맨드 | |
{% endif %}
| `specs/` | 문서 사양, 워크플로우, 커밋 규약, 양식 | `doc-types/<유형>.spec.md` |
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
| `scripts/` | 프로젝트 도구 (`agent-commit` 등) | |
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

에이전트는 **승인된 task의 범위 안에서** 자율적으로 일한다. 판정·확정·계획 변경은 사람의 몫이다. 상세 절차는 [specs/workflow.md](specs/workflow.md).

## 세션 시작 절차

1. `.rp/pending/COMMIT_MSG`가 있으면 사람 커밋 대기 상태다. workflow.md §6.2의 "사람 커밋 대기 상태"를 따른다.
2. `STATUS.md`를 읽는다.
3. 현재 task 카드(`plan/milestones/<M>/tasks/<Task>.md`)를 읽는다. 상태가 `approved`, `in-progress`, `revise` 중 하나가 아니면 작업하지 않고 STATUS에 이유를 적은 뒤 종료한다.
4. `reviews/`에서 이 task와 관련해 사람이 응답한 문서(`status: answered`)가 있는지 확인하고, 있으면 먼저 반영한다.
5. 카드에 연결된 결정(`decisions/`)과 `references/<M>/task-map.md`를 읽는다.
6. `logs/`의 최근 일지 1–2개를 읽는다.
7. 이번 세션에 쓸 문서 유형의 사양(`specs/doc-types/`)을 읽는다.

## 반드시 지킬 규칙

1. 문서는 `specs/`의 사양을 따른다. 사양이 `stub`이면 `specs/conventions.md`의 공통 규칙을 지키고, 사용한 구조를 작업 일지에 남긴다.
2. 커밋은 `scripts/agent-commit`으로만 한다. `git commit`을 직접 실행하지 않는다. `--no-verify`, `--author`를 쓰지 않는다.
3. 사람 전용 커밋 타입(`gate`, `decide`, `plan`, `spec`, `respond`)을 쓰지 않는다.
4. 다음은 하지 않는다. 단, 현재 task 카드의 "범위 › 포함"에 명시된 경우는 예외다.
   - task 상태를 `draft → approved`, `in-review → closed | revise | redirected`로 바꾸기 (사람 커밋을 반영하는 경우 제외, workflow.md §6.3)
   - 결정의 상태를 `confirmed`로 바꾸기
   - review 문서의 `## 응답` 섹션 작성 (대화 경로 예외: workflow.md §6.2)
   - `plan/roadmap.md`와 `active` 이상인 마일스톤의 목표·기준 변경 (변경 제안은 `propose` 커밋)
   - `specs/`, `AGENTS.md`{% if claude_code %}, `CLAUDE.md`, `.claude/`{% endif %}, `.rp/` 수정 (변경 제안은 `notes/`에 쓰고 `propose` 커밋). 단, 대화 경로의 커밋 메시지 초안 `.rp/pending/COMMIT_MSG`는 쓸 수 있다 (workflow.md §6.2)
   - tag 생성, 이력 재작성(rebase, 사람 커밋 amend, force push)
5. task 범위 밖의 작업이 필요하거나, 결과가 미확정 결정에 크게 좌우되거나, 자원 예산을 넘어야 하면 멈추고 에스컬레이션한다 (workflow.md §7).
6. 실험 실행은 task 카드의 자원 예산 안에서만 한다.
7. 본문은 한국어로 쓴다. 식별자, frontmatter 키, 상태값, 커밋 타입은 영어로 쓴다.
8. 사실과 추측을 구분해 쓴다. 확인하지 않은 서지 정보나 수치를 지어내지 않는다.

## 세션 종료 절차

1. 작업 일지 `logs/YYYY-MM-DD_sNN.md`를 쓴다.
2. task 카드의 "진행 메모"와 `updated`를 갱신한다.
3. `STATUS.md`를 갱신한다.
4. `log` 타입으로 커밋해 작업 트리를 깨끗하게 남긴다. 단, 사람 커밋 대기 상태(`.rp/pending/COMMIT_MSG` 있음)이면 커밋하지 않고, 사람이 실행할 명령을 다시 알린 뒤 끝낸다 (workflow.md §6.2).

## 참고

- 작업 절차: [specs/workflow.md](specs/workflow.md)
- 커밋 규약: [specs/git-commit.md](specs/git-commit.md)
- 공통 규칙: [specs/conventions.md](specs/conventions.md)
~~~~

## A.4 `CLAUDE.md` (J, claude_code)

~~~~markdown
# Claude Code 지침

이 저장소의 규칙 원본은 `AGENTS.md`다. 아래 import로 읽어 들인다.

@AGENTS.md

## Claude Code 고유 사항

- 커밋은 `scripts/agent-commit`으로만 한다. `git commit` 직접 실행은 `.claude/settings.json`에서 차단되어 있다.
- 워크플로우 단계는 슬래시 커맨드로 실행한다:
  - `/session-start`: 세션 시작 절차
  - `/task-start <Task>`: 승인된 task 착수
  - `/task-gate <Task>`: task 완료와 게이트 요청 제출
  - `/escalate <Task>`: 에스컬레이션 제출
  - `/session-close`: 세션 종료 절차
~~~~

## A.5 `.claude/settings.json` (S, claude_code)

규칙 문법은 Claude Code 문서(code.claude.com/docs/en/permissions)의 `Bash(<prefix> *)` 형식이다 (2026-10 확인. `:*` 형식도 같은 뜻이지만 공백 형식이 표준). 복합 명령(`cd x && git commit …`)은 하위 명령마다 검사되므로 막힌다. 그러나 `git -C . commit`처럼 프로그램과 하위 명령 사이에 옵션을 넣으면 일치하지 않는다. 즉 이 파일은 실수 방지 장치이고 보안 경계가 아니다. 실제 강제는 commit-msg hook(신원·타입 검사)이 한다.

~~~~json
{
  "permissions": {
    "deny": [
      "Bash(git commit *)",
      "Bash(git tag *)",
      "Bash(git rebase *)",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(git reset --hard *)"
    ]
  }
}
~~~~

## A.6 `.claude/commands/*.md` (S, claude_code)

`session-start.md`

~~~~markdown
AGENTS.md의 "세션 시작 절차"를 순서대로 수행하라. 끝나면 다음을 3–5줄로 보고하라: 현재 task와 상태, 반영할 사람 응답 유무, 이번 세션에 할 일.
~~~~

`task-start.md`

~~~~markdown
task $ARGUMENTS 를 착수한다. specs/workflow.md §5.1을 따른다.
1. 카드 상태가 approved 또는 revise인지 확인한다. 아니면 중단하고 이유를 보고한다.
2. 카드 상태를 in-progress로 바꾸고 updated를 갱신한다.
3. STATUS.md를 갱신한다.
4. scripts/agent-commit 으로 `task($ARGUMENTS): start` 커밋을 만든다 (Actor: agent, Task: $ARGUMENTS).
5. 카드의 완료 기준을 기준으로 이번 세션 작업 계획을 보고한다.
~~~~

`task-gate.md`

~~~~markdown
task $ARGUMENTS 의 게이트 요청을 제출한다. specs/workflow.md §5.4와 specs/doc-types/review.spec.md를 따른다.
1. 완료 기준을 하나씩 점검한다. 충족하지 못한 기준이 있으면 게이트 대신 계속 작업할지 사용자에게 묻는다.
2. task 결과 문서(results/<M>/$ARGUMENTS_result.md)를 쓴다.
3. specs/templates/review.md 로 reviews/open/$ARGUMENTS_gate-NN.md 를 쓴다 (kind: gate).
4. 카드 상태를 in-review로, STATUS.md의 "사람 판단 대기"에 항목을 추가한다.
5. `review($ARGUMENTS): request gate` 커밋 (Actor: agent, Task: $ARGUMENTS, Review: <review id>).
6. 사람에게 무엇을 판정해야 하는지 요약해 보고하고 멈춘다.
~~~~

`escalate.md`

~~~~markdown
task $ARGUMENTS 에서 에스컬레이션을 제출한다. specs/workflow.md §7을 따른다.
1. specs/templates/review.md 로 reviews/open/$ARGUMENTS_esc-NN.md 를 쓴다 (kind: escalation). 무엇이 막혔는지, 선택지, 각 선택지의 영향, 추천안을 쓴다.
2. 카드 상태를 blocked로, STATUS.md의 "막힘"과 "사람 판단 대기"를 갱신한다.
3. `review($ARGUMENTS): escalate <요약>` 커밋 (Actor: agent, Task: $ARGUMENTS).
4. 사람에게 질문을 요약해 보고하고 멈춘다.
~~~~

`session-close.md`

~~~~markdown
AGENTS.md의 "세션 종료 절차"를 수행하라. 마지막에 `git status`가 깨끗한지 확인하라(사람 커밋 대기 상태이면 stage된 변경만 남아 있어야 한다). 이번 세션 요약을 3줄로 보고하라.
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
.rp/pending/

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
| [workflow.md](workflow.md) | task 상태 기계, 세션·게이트·에스컬레이션 절차 | complete |
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

## 모든 사양의 구조

1. 목적 · 2. 위치와 파일명 · 3. frontmatter · 4. 본문 구조 · 5. 작성·수정 권한 · 6. 생성·갱신 시점 · 7. 검증 규칙
~~~~

## B.2 `specs/conventions.md` (S)

~~~~markdown
---
id: conventions
type: spec
spec_version: 1
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
| `spec_version` | ✓ | 따르는 사양 버전 (현재 1) |
| `status` | 유형별 | §5의 상태값 |
| `created` | 유형별 | 생성일 |
| `updated` | ✓ (사양 문서 제외) | 마지막 수정일. 사양 문서(`type: spec`)의 변경 시점은 `spec` 커밋 이력으로 본다 |

`type` 값:

| 구분 | `type` |
|---|---|
| 사양이 있는 문서 | `specs/doc-types/`의 사양 이름과 같다: `task-card`, `review`, `roadmap`, `milestone`, `task-map`, `catalog`, `decision`, `experiment-readme`, `run-record`, `task-result`, `milestone-report`, `worklog`, `status` |
| 사양 문서 자신 | `spec` |
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
spec_version: 1
status: complete
---
# 워크플로우

## 1. 원칙

1. **Task는 승인 게이트 사이의 작업 단위다.** 에이전트는 승인된 task 범위 안에서 자율적으로 일하고, 경계에서 사람이 판정한다.
2. **사실의 원본은 Git 커밋이다.** 특히 사람의 판정·확정은 사람 신원의 커밋(trailer 포함)이 원본이다. 문서의 상태 필드는 이를 반영한 것이며, 둘이 다르면 커밋이 우선한다.
3. **이력은 `main` 하나로 선형이다.** 게이트 지점은 tag로 표시한다.

## 2. 역할

| 주체 | 하는 일 |
|---|---|
| 사람 | task 승인, 게이트 판정, 에스컬레이션 응답, 결정 확정, 계획·사양 변경, tag 생성 |
| 에이전트 | 승인된 task 수행, 문서·코드·실행 기록 작성, 결정·계획·사양 변경 제안, 게이트 요청, 에스컬레이션, 사람 커밋의 결과를 문서에 반영 |

## 3. Task 상태 기계

```
draft ──▶ approved ──▶ in-progress ──▶ in-review ──┬──▶ closed
                          │   ▲                    ├──▶ revise ──▶ in-progress
                          ▼   │                    └──▶ redirected
                         blocked
```

| 전이 | 주체 | 기록하는 커밋 |
|---|---|---|
| `draft → approved` | 사람 | 이전 task의 `gate` 커밋 `Next:`, 또는 `plan` 커밋 `Approve:` |
| `approved → in-progress` | 에이전트 | `task` |
| `in-progress → blocked` | 에이전트 | `review` (에스컬레이션 제출) |
| `blocked → in-progress` | 에이전트 | `task` (사람의 `respond` 커밋 이후에만) |
| `in-progress → in-review` | 에이전트 | `review` (게이트 요청 제출) |
| `in-review → closed / revise / redirected` | 사람 | `gate` (`Verdict:`) |
| `revise → in-progress` | 에이전트 | `task` |

- `redirected`는 끝 상태다. 대체 계획은 사람의 `plan` 커밋으로 반영한다.
- 카드의 `status` 필드는 사람이 해당 커밋에서 직접 바꾸거나, 에이전트가 다음 커밋에서 반영한다.

마일스톤 상태: `planned → active`는 그 마일스톤 T0의 게이트 승인 시(T0 동안에는 `planned`이므로 에이전트가 목표·기준 초안을 쓸 수 있다), `active → closed`는 마지막 task의 `gate` 커밋에 `Milestone-Verdict:`가 있을 때.

## 4. 세션 절차

시작·종료 절차는 [AGENTS.md](../AGENTS.md)에 있다. 모든 세션은 깨끗한 작업 트리로 끝난다. 예외는 사람 커밋 대기 상태(§6.2)뿐이다.

## 5. Task 실행

### 5.1 착수

1. 카드가 `approved` 또는 `revise`인지 확인한다.
2. 카드 `status`를 `in-progress`로 바꾸고 STATUS를 갱신해 `task(<Task>): start` 커밋.
3. `revise`에서 시작하는 경우, 해당 gate review의 `## 응답`을 먼저 반영한다.

### 5.2 진행

- 작업 단위마다 알맞은 타입으로 커밋한다 (`exp`, `run`, `result`, `ref`, `task` …).
- 새로운 결정이 필요하면 `decisions/`에 `proposed`로 쓰고 `propose` 커밋한다. 확정은 하지 않는다.
- 실행은 카드의 자원 예산 안에서만 한다. 실행마다 run-record를 남긴다.

### 5.3 에스컬레이션이 필요한 경우

§7을 따른다.

### 5.4 완료와 게이트 요청

1. 완료 기준을 하나씩 점검한다.
2. task 결과 문서 `results/<M>/<Task>_result.md`를 쓴다.
3. `reviews/open/<Task>_gate-NN.md`를 쓴다 (`kind: gate`, [review.spec.md](doc-types/review.spec.md)).
4. 카드를 `in-review`로, STATUS의 "사람 판단 대기"에 추가.
5. `review(<Task>): request gate` 커밋. 이후 이 task에서 작업하지 않는다.

## 6. 게이트 절차

### 6.1 문서 경로 (사람이 직접 작성)

1. 사람이 review 문서의 `## 응답`을 작성하고 frontmatter `verdict`, `source: document`, `status: answered`, `answered`를 채운다.
2. 필요하면 같은 커밋에서 카드 `status`, 결정 `status`, 다음 task 카드 `status: approved`를 바꾼다.
3. 사람 신원으로 `gate(<Task>): <verdict>…` 커밋 ([git-commit.md](git-commit.md) §4).
4. 승인이면 tag: `git tag gate/<Task>`.

### 6.2 대화 경로 (사람이 대화로 판정)

1. 에이전트가 사람의 발언을 그대로 반영해 `## 응답`을 작성하고 `verdict`, `source: conversation`, `status: answered`를 채운다. 사람이 말하지 않은 내용을 추가하지 않는다.
2. 에이전트가 관련 변경(카드·결정 상태 등)을 stage하고, 커밋 메시지 초안을 `.rp/pending/COMMIT_MSG`에 쓴다. `.rp/pending/`은 Git에서 제외되며, 에이전트가 쓸 수 있는 `.rp/` 안의 유일한 위치다.
3. 에이전트는 사람에게 `git diff --cached` 확인과 다음 명령 실행을 요청하고 멈춘다 (tag는 `approve`일 때만):
   `git commit -F .rp/pending/COMMIT_MSG && rm .rp/pending/COMMIT_MSG && git tag gate/<Task>`
4. 사람이 확인 후 실행한다. 내용이 다르면 수정 후 커밋한다.

같은 방식이 `decide`, `respond` 커밋의 대화 경로에도 적용된다.

**사람 커밋 대기 상태.** `.rp/pending/COMMIT_MSG`가 있는 동안 stage된 변경은 사람의 커밋을 기다리는 것이다. 이 상태에서 에이전트는:

- 어떤 커밋도 하지 않는다 (stage된 변경이 에이전트 커밋에 섞이기 때문). 세션 종료 시에도 `log` 커밋을 하지 않고, 작업 트리가 깨끗하지 않은 채로 끝내며 그 이유를 보고한다 (§4 "깨끗한 작업 트리"의 유일한 예외).
- 세션 시작 시 이 파일이 있으면, `git log`에 그 메시지로 된 사람 커밋이 이미 있는지 확인한다. 있으면 파일을 지우고 §6.3으로 간다. 없으면 사람에게 커밋 실행을 다시 요청하고 다른 작업을 하지 않는다.

### 6.3 판정 후 정리 (에이전트)

다음 세션에서 에이전트가 사람의 `gate` 커밋을 확인하고:

1. review 문서를 `reviews/closed/`로 옮기고(`git mv`) `status: closed`.
2. 카드·결정·마일스톤 문서의 상태 필드가 커밋 trailer와 다르면 맞춘다.
3. 카드의 "게이트 이력"에 판정과 커밋 해시를 추가한다.
4. STATUS 갱신 후 `log(<Task>): apply gate <해시>` 커밋.

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

### 7.2 절차

1. `reviews/open/<Task>_esc-NN.md` (`kind: escalation`): 상황, 선택지, 영향, 추천안.
2. 카드 `blocked`, STATUS 갱신, `review(<Task>): escalate …` 커밋.
3. 사람이 응답하고 `respond(<Task>): …` 커밋 (§6.1 또는 §6.2와 같은 방식, `Verdict` 없음).
4. 에이전트가 응답을 반영해 `in-progress`로 돌아가고, 문서를 `closed/`로 옮긴다.

## 8. 마일스톤 착수와 종료

- **착수:** 모든 마일스톤은 T0(착수 계획)으로 시작한다. T0의 게이트에서 사람이 task 분해를 승인하면 `Next: <M>-T1`, 마일스톤은 `active`.
- **종료:** 마지막 task의 게이트 요청에 마일스톤 보고(`results/<M>/report.md`)와 Go/No-go 근거를 포함한다. 사람의 `gate` 커밋에 `Milestone-Verdict:`를 넣고 tag `milestone/<M>-<go|nogo|conditional>`을 만든다. 다음 마일스톤 T0의 승인도 같은 커밋 `Next:`로 한다.
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
spec_version: 1
status: complete
---
# 커밋 규약

이 규약은 `.rp/hooks/commit-msg`가 검사한다.

## 1. 신원

| 주체 | 커밋 방법 | 작성자 |
|---|---|---|
| 사람 | `git commit` (저장소 로컬 설정) | `.rp/identities.json`의 `humans` 중 하나 |
| 에이전트 | `scripts/agent-commit` | `.rp/identities.json`의 `agent` |

작성자 이메일이 둘 중 어디에도 없으면 커밋이 거부된다.

## 2. 메시지 형식

```
<type>(<scope>): <요약>

<본문 (선택)>

Actor: human | agent
<기타 trailer>
```

- 헤더는 72자 이하. 요약은 무엇을 했는지 한 문장.
- 본문은 왜 했는지, 무엇이 달라졌는지.
- 마지막 문단은 trailer 블록(`Key: value` 줄만).
- scope: task 관련 타입은 Task ID와 같아야 한다. 그 밖에는 선택(결정 ID, 마일스톤 ID 등).

## 3. 타입

| 분류 | 타입 | 용도 |
|---|---|---|
| 사람 전용 | `gate` | task 게이트 판정 |
| | `decide` | 결정 확정 |
| | `plan` | 로드맵·마일스톤 변경, 첫 task 승인 |
| | `spec` | 사양·규칙 문서 변경 확정 |
| | `respond` | 에스컬레이션 응답 |
| 에이전트 | `task` | task 상태 전이, 카드 갱신 |
| | `exp` | 실험 코드 |
| | `run` | 실행 기록 |
| | `result` | 결과 문서, 그림, 표 |
| | `ref` | 참고문헌 추가, 매핑 문서 |
| | `propose` | 결정·계획·사양 변경 제안 |
| | `review` | 게이트 요청, 에스컬레이션 제출 |
| | `log` | 작업 일지, STATUS, 사람 커밋 반영 |
| 공통 | `init` | 초기화 |
| | `chore` | 위에 속하지 않는 잡무 |

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

첫 task 승인:

```
plan(M0-T0): approve initial task

Actor: human
Approve: M0-T0
```

## 6. Tag

| 시점 | tag | 만드는 사람 |
|---|---|---|
| task 게이트 `approve` | `gate/<Task>` | 사람 |
| 마일스톤 판정 | `milestone/<M>-<go\|nogo\|conditional>` | 사람 |

tag는 해당 `gate` 커밋에 붙인다.

## 7. 금지

- 에이전트: `git commit` 직접 실행, `--no-verify`, `--author`, 사람 전용 타입, tag, 이력 재작성.
- 사람: 이력 재작성 (실수는 `git revert`).
- `--no-verify`는 사람이 긴급할 때만 쓰고, 다음 커밋 본문에 이유를 남긴다.
~~~~

## B.5 `specs/doc-types/task-card.spec.md` (S)

~~~~markdown
---
id: task-card
type: spec
spec_version: 1
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
| `spec_version` | ✓ | `1` |
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
spec_version: 1
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
| `spec_version` | ✓ | `1` |
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
| `## 응답` | 대화 경로에서 사람 발언 그대로 기록만 (workflow §6.2) | 작성 |
| `verdict`, `source`, `answered`, `status: answered` | 대화 경로에서만 기록 | 작성 |
| `status: closed`, 폴더 이동 | 사람 커밋 이후 수행 | 가능 |

## 6. 생성·갱신 시점

- 생성: 게이트 요청(workflow §5.4), 에스컬레이션(§7.2).
- 응답: 사람의 `gate` / `respond` 커밋과 같은 커밋.
- 종료: 다음 세션에서 에이전트가 `closed/`로 이동(§6.3).

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
spec_version: 1
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
spec_version: 1
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

---

# 부록 C. 실행 파일 원문

## C.1 `.rp/hooks/commit-msg` (S, 755)

~~~~python
#!/usr/bin/env python3
"""rp commit-msg hook (spec_version 1).

specs/git-commit.md 규약을 검사한다. 표준 라이브러리만 사용한다.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HUMAN_TYPES = {"gate", "decide", "plan", "spec", "respond"}
AGENT_TYPES = {"task", "exp", "run", "result", "ref", "propose", "review", "log"}
COMMON_TYPES = {"init", "chore"}
ALL_TYPES = HUMAN_TYPES | AGENT_TYPES | COMMON_TYPES

TASK_REQUIRED = {"gate", "respond", "task", "run", "result", "review"}
SOURCE_REQUIRED = {"gate", "decide", "respond"}
PASSTHROUGH_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")

HEADER_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^()\s]+)\))?: (?P<summary>\S.*)$")
TRAILER_RE = re.compile(r"^(?P<key>[A-Z][A-Za-z-]*): (?P<value>\S.*)$")
TASK_ID_RE = re.compile(r"^M\d+-T\d+$")
DECISION_ID_RE = re.compile(r"^D\d+\.\d+$")
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
    path = root / ".rp" / "identities.json"
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
    return header, trailers, errors


def check_identity(actor, errors):
    try:
        ids = load_identities()
    except (OSError, ValueError, subprocess.CalledProcessError) as e:
        errors.append(f".rp/identities.json을 읽지 못했습니다: {e}")
        return
    email = author_email()
    humans = {h["email"].lower() for h in ids.get("humans", [])}
    agent = ids.get("agent", {}).get("email", "").lower()
    if email and email == agent:
        role = "agent"
    elif email in humans:
        role = "human"
    else:
        errors.append(f"등록되지 않은 작성자입니다: <{email}> (.rp/identities.json 확인)")
        return
    if role != actor:
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


def main():
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    header, trailers, errors = parse(text)
    if header is None:
        return report(errors)
    if header.startswith(PASSTHROUGH_PREFIXES):
        return 0

    m = HEADER_RE.match(header)
    if not m:
        errors.append("헤더 형식은 '<type>(<scope>): <요약>' 입니다.")
        return report(errors)
    ctype, scope = m.group("type"), m.group("scope")

    if len(header) > MAX_HEADER:
        errors.append(f"헤더가 {MAX_HEADER}자를 넘습니다 ({len(header)}자).")
    if ctype not in ALL_TYPES:
        errors.append(f"알 수 없는 타입입니다: {ctype}")
        return report(errors)

    actor = trailers.get("Actor")
    if actor not in ("human", "agent"):
        errors.append("Actor trailer가 필요합니다 (human | agent).")
    else:
        if ctype in HUMAN_TYPES and actor != "human":
            errors.append(f"'{ctype}'는 사람 전용 타입입니다.")
        if ctype in AGENT_TYPES and actor != "agent":
            errors.append(f"'{ctype}'는 에이전트 타입입니다.")
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

    return report(errors)


if __name__ == "__main__":
    sys.exit(main())
~~~~

## C.2 `scripts/agent-commit` (S, 755)

~~~~bash
#!/usr/bin/env bash
# 에이전트 신원으로 커밋한다.
# 사용법: scripts/agent-commit -m "<헤더>" -m "<trailer 블록>"
#         scripts/agent-commit -F <메시지 파일>
# 나머지 인자는 git commit에 그대로 전달된다. --author, --no-verify는 쓰지 않는다.
set -euo pipefail

for arg in "$@"; do
  case "$arg" in
    --no-verify|-n|--author|--author=*)
      echo "agent-commit: '$arg' 옵션은 사용할 수 없습니다." >&2
      exit 2
      ;;
  esac
done

ROOT="$(git rev-parse --show-toplevel)"
CFG="$ROOT/.rp/identities.json"

field() {
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["agent"][sys.argv[2]])' "$CFG" "$1"
}

NAME="$(field name)"
EMAIL="$(field email)"

export GIT_AUTHOR_NAME="$NAME" GIT_AUTHOR_EMAIL="$EMAIL"
export GIT_COMMITTER_NAME="$NAME" GIT_COMMITTER_EMAIL="$EMAIL"
exec git commit "$@"
~~~~

> 참고: `-n`은 `git commit`에서 `--no-verify`의 짧은 형식이라 함께 막는다. 메시지를 여러 `-m`으로 줄 때 마지막 `-m`이 trailer 블록이 되도록 한다(각 `-m`은 빈 줄로 구분된 문단이 된다).
