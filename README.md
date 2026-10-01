# labgate

사람이 task 경계의 승인 게이트마다 판정하고 에이전트가 그 사이를 수행하는 연구 프로젝트의 작업 공간을 한 번에 초기화하는 CLI. 명령은 `lg`.

설계: [labgate-design.md](labgate-design.md)

## 개발

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
.venv/bin/pytest
```

## 설치

```bash
pipx install .
lg --version
```
