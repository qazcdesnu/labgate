# labgate

사람이 task 경계의 승인 게이트마다 판정하고 에이전트가 그 사이를 수행하는 연구 프로젝트의 작업 공간을 한 번에 초기화하고, 그 안에서 사람의 커밋을 돕는 CLI. 명령은 `lg`.

설계: [labgate-design.md](labgate-design.md)

사용자 작업 설명서: [docs/guide/](docs/guide/README.md) — 설치, 하루 작업, task 승인, 게이트 판정, 직접 고친 것 커밋 등 사람이 하는 일

명령 설명서: [docs/cli/](docs/cli/README.md) — `lg init`, `lg commit`, `lg draft`와 생성된 프로젝트의 스크립트

사용 시나리오: [Coconut을 읽고 CODI를 시작하는 연구자](docs/scenarios/codi.md) — 전통 방식과의 비교, Claude Code와의 시너지·충돌 점검

## 설치

Python 3.10 이상과 [pipx](https://pipx.pypa.io)가 필요하다.

```bash
# pipx가 없다면
sudo apt install pipx        # Ubuntu/Debian
brew install pipx            # macOS
pipx ensurepath              # ~/.local/bin을 PATH에 추가 — 실행 후 새 터미널을 연다

# labgate 설치 (릴리즈 태그 고정)
pipx install git+https://github.com/qazcdesnu/labgate.git@v0.2.1
lg --version
```

- 버전 목록과 변경 내용은 [Releases](https://github.com/qazcdesnu/labgate/releases)에서 본다. 명령의 `@v0.2.1`을 원하는 태그로 바꾼다.
- `lg: command not found`가 나오면 `pipx ensurepath` 후 새 터미널을 연다.
- 시스템 Python이 3.10 미만이면 `pipx install --python python3.12 git+...`처럼 버전을 지정한다.
- uv를 쓰고 있다면 `uv tool install git+https://github.com/qazcdesnu/labgate.git@v0.2.1`도 같다.
- 업데이트: `pipx install --force git+https://github.com/qazcdesnu/labgate.git@<새 태그>` / 삭제: `pipx uninstall labgate`

## 사용

| 명령 | 누가 | 하는 일 |
|---|---|---|
| `lg init [PATH]` | 사람 | 연구 프로젝트 작업 공간을 만든다 (대화형, 또는 `--config`) |
| `lg commit` | 사람 (터미널에서만) | 사람 신원으로 커밋한다. 타입과 필수 trailer를 묻거나, 에이전트가 준비한 초안을 확인해 확정한다. 게이트 승인이면 tag도 만든다 |
| `lg draft` | 에이전트·사람 | 사람 커밋의 초안을 준비한다 (stage와 `.lg/pending/COMMIT_MSG`). 커밋하지 않는다 |

생성된 프로젝트에서 사람이 코드·문서를 직접 고쳤다면, 에이전트 세션이 시작될 때 `scripts/session-check`가 이를 알리고 에이전트는 작업 전에 정리를 요청한다. 사람은 직접 `lg commit`을 하거나, 에이전트에게 초안을 부탁한 뒤 `lg commit`으로 확정한다. 자세한 흐름은 설계 문서 §16–§20.

`lg commit`, `lg draft`는 labgate 0.2 이상으로 만든 프로젝트(spec_version 2)에서 동작한다.

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

전체 실행에는 생성되는 commit-msg hook과 스크립트(session-check, apply-human-commits)를 Python 3.9로 돌리는 검사도 포함된다 (모두 Python ≥ 3.9 지원).

GitHub Actions가 push마다 같은 조합을 Linux와 macOS에서 돌린다 (`.github/workflows/test.yml`).
