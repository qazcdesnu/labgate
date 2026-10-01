#!/usr/bin/env bash
# 지원하는 모든 Python 버전에서, 최신 의존성과 최소 의존성(pyproject 하한) 두 조합으로 테스트한다.
# 사용법: scripts/test-matrix.sh [버전 ...]   (기본: 3.10 3.11 3.12 3.13)
# 필요: uv
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSIONS=("${@:-3.10 3.11 3.12 3.13}")
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

if ((${#failed[@]})); then
  echo "실패: ${failed[*]}"; exit 1
fi
