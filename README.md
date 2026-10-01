# labgate

사람이 task 경계의 승인 게이트마다 판정하고 에이전트가 그 사이를 수행하는 연구 프로젝트의 작업 공간을 한 번에 초기화하는 CLI. 명령은 `lg`.

설계: [labgate-design.md](labgate-design.md)

## 개발

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/pytest
```

지원 Python(3.10–3.13) 전체에서 최신 의존성과 최소 의존성(`pyproject.toml` 하한) 두 조합으로 테스트:

```bash
scripts/test-matrix.sh          # 전체
scripts/test-matrix.sh 3.13     # 특정 버전만
```

전체 실행에는 생성되는 commit-msg hook을 Python 3.9로 돌리는 검사도 포함된다 (hook은 Python ≥ 3.9 지원).

GitHub Actions가 push마다 같은 조합을 Linux와 macOS에서 돌린다 (`.github/workflows/test.yml`).

## 설치

```bash
pipx install .
lg --version
```
