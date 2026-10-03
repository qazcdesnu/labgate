# labgate

연구 프로젝트에서 **사람은 task 경계의 게이트마다 판정하고, 에이전트(Claude Code)는 그 사이를 수행**하게 하는 CLI. 명령은 `lg`.

`lg init`이 그 방식대로 일하는 연구 작업 공간을 만든다: 계획 문서(로드맵·마일스톤·task 카드), 에이전트가 따를 규칙과 절차, 그리고 규칙을 지키게 하는 hook과 스크립트. 그 뒤로 사람은 승인·판정만 커밋하고, 나머지(코드, 실행, 기록, 상태 갱신)는 에이전트가 한다. 모든 판단이 커밋과 문서로 남아, 어떤 결과가 어떤 승인에서 나왔는지 거슬러 올라갈 수 있다.

## 설치

Python 3.10 이상과 [pipx](https://pipx.pypa.io)가 필요하다.

```bash
# pipx가 없다면
sudo apt install pipx        # Ubuntu/Debian
brew install pipx            # macOS
pipx ensurepath              # ~/.local/bin을 PATH에 추가 — 실행 후 새 터미널을 연다

# labgate 설치 (릴리즈 태그 고정)
pipx install git+https://github.com/qazcdesnu/labgate.git@v0.4.1
lg --version
```

- 버전 목록과 변경 내용은 [Releases](https://github.com/qazcdesnu/labgate/releases)에서 본다. 명령의 `@v0.4.1`을 원하는 태그로 바꾼다.
- `lg: command not found`가 나오면 `pipx ensurepath` 후 새 터미널을 연다.
- 시스템 Python이 3.10 미만이면 `pipx install --python python3.12 git+...`처럼 버전을 지정한다.
- uv를 쓰고 있다면 `uv tool install git+https://github.com/qazcdesnu/labgate.git@v0.4.1`도 같다.
- 업데이트: `pipx install --force git+https://github.com/qazcdesnu/labgate.git@<새 태그>` / 삭제: `pipx uninstall labgate`

## 사용

### 1. 프로젝트 만들고 첫 task 승인하기

```bash
lg init ~/research/my-study            # 대화형으로 연구 질문, 마일스톤, 에이전트 신원 등을 묻는다
cd ~/research/my-study
# STATUS.md와 첫 task 카드(plan/milestones/M0/tasks/M0-T0.md)를 읽고, 필요하면 고친다
lg commit --allow-empty                # 타입 plan, Approve: M0-T0 → 첫 task 승인
```

### 2. 터미널 두 개로 일하기

| 터미널 | 여는 법 | 하는 일 |
|---|---|---|
| A (사람) | `cd ~/research/my-study` | `lg status`, `lg answer`, `lg commit`, `lg verify` |
| B (에이전트) | `cd ~/research/my-study && claude` | `/session-start`, `/task-start M0-T0`, 작업 지시와 질문에 답하기 |

Claude Code는 반드시 프로젝트 폴더에서 연다. 그래야 그 프로젝트의 규칙(`CLAUDE.md`), 차단 규칙과 세션 시작 hook(`.claude/settings.json`), 슬래시 명령이 적용된다.

### 3. 한 task의 흐름

```
사람: 승인 (plan + Approve) ──▶ 에이전트: 착수, 작업, 커밋, 일지
                                   │  범위·예산을 넘거나 판단이 필요하면 멈추고 질문 (에스컬레이션)
                                   │  ──▶ 사람: lg answer (respond) ──▶ 에이전트: 재개
                                   ▼
                             에이전트: 게이트 요청서 (reviews/open/) 내고 멈춤
                                   ▼
사람: lg answer (gate: approve / revise / redirect, 다음 task 승인) ──▶ 에이전트: 반영하고 다음 task
```

사람이 하는 일은 승인, 판정, 응답, 결정 확정, 계획·규칙 변경이고, 모두 사람 신원의 커밋으로 남는다. 무엇을 할지는 `lg status`가 알려 준다. 판정과 응답은 `lg answer`가 요청서를 보여 주고 물어서, 응답 문서와 커밋을 함께 만든다. 터미널 B에서 말로 판정해도 된다. 에이전트가 요청서에 옮기고 커밋 초안을 만들면 사람이 `lg commit`으로 확인해 확정한다.

### 4. init 뒤에 저절로 돌아가는 것

`lg init`이 프로젝트 안에 설치한 것들이 매 세션, 매 커밋마다 규칙을 지키게 한다. 스크립트와 hook은 Python 표준 라이브러리만 쓰므로 `lg`가 없는 컴퓨터에서도 동작한다.

| 언제 | 무엇이 | 하는 일 |
|---|---|---|
| 세션 시작 | `scripts/session-check` (Claude Code hook) | 아직 반영하지 않은 사람 커밋과 커밋되지 않은 사람 변경을 찾아 에이전트에게 알린다. 그래서 사람이 커밋한 승인·판정은 다음 세션에서 자동으로 이어진다 |
| 모든 커밋 | `.lg/hooks/commit-msg` | 커밋 규약과 작성자 신원을 검사한다. 에이전트는 승인·판정 같은 사람 몫의 커밋을 만들 수 없다 |
| 에이전트 커밋 | `scripts/agent-commit` | 작성자를 에이전트 신원으로 고정한다. 검사 우회(`--no-verify`), 작성자 바꾸기, 사람의 미커밋 변경까지 담는 `-a`는 거부한다 |
| 항상 | `.claude/settings.json` | 에이전트가 `git commit`·`git tag`·`lg commit`·`lg upgrade`, 이력 재작성, 일괄 stage(`git add -A` 등)를 쓰지 못하게 막는다 |
| 항상 | `AGENTS.md`, `specs/` | 에이전트가 따르는 규칙과 절차. 규칙 문서는 사람만 고친다. 이것처럼 도구가 막지 못하는 규칙은 `lg verify`가 이력으로 확인한다 |
| 사람 커밋 뒤 | `scripts/apply-human-commits` | 에이전트가 승인·판정·응답을 task 카드, review, 결정 문서의 상태에 반영할 때 쓴다 |

### 5. 사람이 쓰는 명령

| 명령 | 언제 | 하는 일 |
|---|---|---|
| `lg init [PATH]` | 연구마다 한 번 | 작업 공간을 만들고 `init` 커밋 (대화형, 또는 `--config`) |
| `lg status` | 수시로 | 내가 할 일(열린 요청, 커밋 대기), 에이전트가 반영할 것, 진행 상황을 다음 명령과 함께 보여 준다. 읽기만 함 |
| `lg answer [ID]` | 에이전트가 게이트 요청·질문을 내고 멈췄을 때 | 요청서를 터미널에 보여 주고 판정을 물어, `## 응답`과 사람 커밋(+ tag)을 함께 만든다. 판정이 만들 상태 변화를 먼저 보여 준다. 터미널에서만 동작 |
| `lg commit` | 사람의 모든 커밋 | 타입과 필수 trailer를 물어 커밋하거나, 에이전트가 준비한 초안을 확인해 확정한다. 게이트 승인이면 tag를 만들고, 그 task의 `lg verify` 요약을 보여 준다. 터미널에서만 동작 |
| `lg verify` | 게이트 판정 전, 다른 컴퓨터에서 작업한 뒤 | 에이전트가 규칙을 지켰는지(신원, 사람 몫의 상태 전이, 규칙 파일, 문서 형식) 이력으로 확인한다. 읽기만 함 |
| `lg upgrade` | labgate를 새 마이너 버전으로 올린 뒤 | 프로젝트의 규칙·절차·스크립트를 새 버전으로 바꾼다. 사람이 고친 문서는 덮어쓰지 않고 알린다. 커밋은 `lg commit`(타입 `spec`)으로 |
| `lg draft` | (주로 에이전트) | 사람 커밋의 초안을 준비한다. 커밋하지 않는다 |

`lg` 명령은 labgate 0.2 이상으로 만든 프로젝트에서 동작한다(`lg answer`의 반영 미리보기는 spec_version 5 이상).

### 더 보기

- [사용자 작업 설명서](docs/guide/README.md): 상황별 따라 하기 (설치, 하루 작업, task 승인, 게이트 판정, 에스컬레이션 응답, 직접 고친 것 커밋, 계획 변경, 바로잡기, 업데이트)
- [명령 설명서](docs/cli/README.md): `lg` 명령과 프로젝트 스크립트의 옵션, 종료 코드
- [사용 시나리오](docs/scenarios/codi.md): Coconut을 읽고 CODI를 시작하는 가상의 연구자. 전통 방식과의 비교, Claude Code와의 시너지·충돌 점검
- [설계 문서](labgate-design.md): 규칙, 커밋 규약, 생성 파일의 전체 사양

## 개발

개발은 `dev` 브랜치에서 하고, 릴리즈할 때 `main`에 병합해 태그를 단다.

```bash
git clone -b dev https://github.com/qazcdesnu/labgate.git
cd labgate
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/pytest
```

지원 Python(3.10–3.14) 전체에서 최신 의존성과 최소 의존성(`pyproject.toml` 하한) 두 조합으로 테스트:

```bash
scripts/test-matrix.sh          # 전체
scripts/test-matrix.sh 3.13     # 특정 버전만
```

전체 실행에는 생성되는 commit-msg hook과 스크립트(`tests/tools`)를 Python 3.9로 돌리는 검사도 포함된다 (모두 Python ≥ 3.9 지원).

테스트는 실행하는 것에 따라 다섯 계층(`unit`, `contract`, `tools`, `commands`, `e2e`)으로 나뉜다. `pytest -m unit`처럼 계층만 돌릴 수 있다. 새 테스트를 둘 곳, 공용 도구, 겹침과 obsolete 정리 규칙: [tests/README.md](tests/README.md).

릴리즈할 때 현재 spec_version이 처음 릴리즈되는 것이면, 그 템플릿의 해시표를 만들어 함께 커밋한다(`lg upgrade`가 쓴다, 설계 문서 §22.4.3). 그 뒤로 그 spec_version의 템플릿은 바꾸지 않는다(테스트가 막는다).

```bash
scripts/hash-templates.py WORKTREE <spec_version>
```

GitHub Actions가 push마다 같은 조합을 Linux와 macOS에서 돌린다 (`.github/workflows/test.yml`).
