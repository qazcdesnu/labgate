#!/usr/bin/env python3
"""릴리즈된 spec_version의 관리 문서 해시표를 만든다 (설계 문서 §22.4).

사용법:
  scripts/hash-templates.py <tag> <spec_version>          # src/labgate/hashes/<spec_version>.json 을 쓴다
  scripts/hash-templates.py <tag> <spec_version> --check  # 이미 있는 해시표와 같은지 확인 (다르면 종료 코드 1)
  scripts/hash-templates.py WORKTREE <spec_version> ...    # tag 대신 작업 트리의 템플릿 (릴리즈 직전에 쓴다)

tag의 src/labgate를 임시 폴더에 꺼내 그 버전의 생성 계획으로 시험용 설정을 렌더링하고,
현재 코드의 분류·정규화 규칙(labgate.kinds)으로 해시한다.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from labgate.kinds import build_table  # noqa: E402

CONFIG = {
    "schema_version": 1,
    "project": {"name": "hash", "slug": "hash", "summary": "s", "research_question": "q?"},
    "people": {"humans": [{"name": "H", "email": "h@x.com"}]},
    "milestones": [{"title": "m"}],
}

RENDER = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
from labgate import __version__
from labgate.config import parse_config, Project
try:
    from labgate.config import KINDS
except ImportError:
    KINDS = ("research", "proposal")
from labgate.plan import build_plan
cfg = json.loads(sys.argv[2])
out = {"labgate_version": __version__, "variants": {}}
# 프로젝트 종류(§25)가 있는 버전이면 종류마다. 이름은 kinds.variant와 같다 (연구는 예전 이름 그대로)
kinds = KINDS if "kind" in Project.model_fields else ("research",)
for kind in kinds:
    for claude in (True, False):
        cfg["agent_tools"] = {"claude_code": claude}
        if kind != "research":
            cfg["project"]["kind"] = kind
        plan = build_plan(parse_config(cfg), "2026-01-01")
        name = "claude_code" if claude else "no_claude_code"
        out["variants"][name if kind == "research" else f"{kind}_{name}"] = {str(f.path): f.content for f in plan}
print(json.dumps(out))
"""


def render(src: Path) -> dict:
    result = subprocess.run([sys.executable, "-c", RENDER, str(src), json.dumps(CONFIG)],
                            capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    tag, spec_version = argv[0], int(argv[1])
    with tempfile.TemporaryDirectory() as tmp:
        if tag == "WORKTREE":
            src = ROOT / "src"
        else:
            archive = Path(tmp) / "src.tar"
            subprocess.run(["git", "archive", "-o", str(archive), tag, "src/labgate"], cwd=ROOT, check=True)
            with tarfile.open(archive) as tar:
                tar.extractall(tmp, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
            src = Path(tmp) / "src"
        rendered = render(src)
    table = build_table(rendered["variants"], spec_version, rendered["labgate_version"])
    text = json.dumps(table, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    out = ROOT / "src" / "labgate" / "hashes" / f"{spec_version}.json"
    if "--check" in argv:
        same = out.exists() and out.read_text(encoding="utf-8") == text
        print("같음" if same else f"다름: {out.relative_to(ROOT)}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"썼습니다: {out.relative_to(ROOT)} (관리 문서 {len(table['files'])}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
