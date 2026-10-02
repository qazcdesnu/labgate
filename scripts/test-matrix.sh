#!/usr/bin/env bash
# 지원하는 모든 Python 버전에서, 최신 의존성과 최소 의존성(pyproject 하한) 두 조합으로 테스트한다.
# 전체 실행이면 생성되는 hook과 스크립트를 Python 3.9로도 테스트한다.
# 사용법: scripts/test-matrix.sh [버전 ...]   (기본: 3.10 3.11 3.12 3.13 3.14)
# 필요: uv
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEFAULT="3.10 3.11 3.12 3.13 3.14"
VERSIONS=("${@:-$DEFAULT}")
read -r -a VERSIONS <<< "${VERSIONS[*]}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

failed=()
for v in "${VERSIONS[@]}"; do
  for res in highest lowest-direct; do
    env="$WORK/$v-$res"
    label="py$v/$res"
    if ! uv venv -q --python "$v" "$env" \
       || ! uv pip install -q --python "$env/bin/python" --resolution "$res" -e "$ROOT[dev]"; then
      echo "✗ $label: 설치 실패"; failed+=("$label"); continue
    fi
    if out="$(cd "$ROOT" && "$env/bin/python" -m pytest -q -p no:cacheprovider 2>&1)"; then
      echo "✓ $label: $(tail -1 <<< "$out")"
    else
      echo "✗ $label"; tail -20 <<< "$out"; failed+=("$label")
    fi
  done
done

# 생성되는 hook은 Python ≥ 3.9를 지원한다 (설계 문서 §4): hook·session-check·apply-human-commits 테스트만 3.9 인터프리터로 실행
if [[ "${VERSIONS[*]}" == "$DEFAULT" ]]; then
  py39="$(uv python find 3.9 2>/dev/null || { uv python install -q 3.9 && uv python find 3.9; })"
  env="$WORK/${VERSIONS[0]}-highest"
  if out="$(cd "$ROOT" && HOOK_PYTHON="$py39" "$env/bin/python" -m pytest -q -p no:cacheprovider tests/test_hook.py tests/test_commit.py tests/test_apply.py 2>&1)"; then
    echo "✓ hook/py3.9: $(tail -1 <<< "$out")"
  else
    echo "✗ hook/py3.9"; tail -20 <<< "$out"; failed+=("hook/py3.9")
  fi
fi

if ((${#failed[@]})); then
  echo "실패: ${failed[*]}"; exit 1
fi
