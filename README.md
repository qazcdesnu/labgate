# labgate

사람이 task 경계의 승인 게이트마다 판정하고 에이전트가 그 사이를 수행하는 연구 프로젝트의 작업 공간을 한 번에 초기화하는 CLI. 명령은 `lg`.

설계: [labgate-design.md](labgate-design.md)

사용 시나리오: [Coconut을 읽고 CODI를 시작하는 연구자](docs/scenarios/codi.md) — 전통 방식과의 비교, Claude Code와의 시너지·충돌 점검

## 설치

Python 3.10 이상과 [pipx](https://pipx.pypa.io)가 필요하다.

```bash
# pipx가 없다면
sudo apt install pipx        # Ubuntu/Debian
brew install pipx            # macOS
pipx ensurepath              # ~/.local/bin을 PATH에 추가 — 실행 후 새 터미널을 연다

# labgate 설치
git clone https://github.com/qazcdesnu/labgate.git
cd labgate
pipx install .
lg --version
```

- `lg: command not found`가 나오면 `pipx ensurepath` 후 새 터미널을 연다.
- 시스템 Python이 3.10 미만이면 `pipx install --python python3.12 .`처럼 버전을 지정한다.
- uv를 쓰고 있다면 `uv tool install .`도 같다.
- 업데이트: `git pull && pipx install --force .` / 삭제: `pipx uninstall labgate`

## 개발

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/pytest
```

지원 Python(3.10–3.14) 전체에서 최신 의존성과 최소 의존성(`pyproject.toml` 하한) 두 조합으로 테스트:

```bash
scripts/test-matrix.sh          # 전체
scripts/test-matrix.sh 3.13     # 특정 버전만
```

전체 실행에는 생성되는 commit-msg hook을 Python 3.9로 돌리는 검사도 포함된다 (hook은 Python ≥ 3.9 지원).

GitHub Actions가 push마다 같은 조합을 Linux와 macOS에서 돌린다 (`.github/workflows/test.yml`).
