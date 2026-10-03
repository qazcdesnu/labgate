#!/usr/bin/env python3
"""설계 문서 부록 A·B·C의 원문을 src/labgate/templates/ 로 옮긴다.

설계 문서가 템플릿 원문의 원본이다. 템플릿을 고칠 때는 설계 문서를 고치고 이 스크립트를 실행한다.

사용법:
  scripts/sync-templates.py           # 템플릿 파일을 쓴다
  scripts/sync-templates.py --check   # 설계 문서와 다르면 목록을 출력하고 종료 코드 1
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "labgate-design.md"
TEMPLATES = ROOT / "src" / "labgate" / "templates"

# 부록 절 번호 → 템플릿 경로 (templates/ 기준). A.6, B.10은 블록마다 앞 줄의 파일명을 쓴다.
SECTIONS = {
    "A.1": "jinja/README.md.j2",
    "A.2": "jinja/FILEMAP.md.j2",
    "A.3": "jinja/AGENTS.md.j2",
    "A.4": "jinja/CLAUDE.md.j2",
    "A.5": "static/dot-claude/settings.json",
    "A.6": "static/dot-claude/commands/{label}",
    "A.7": "jinja/STATUS.md.j2",
    "A.8": "static/dot-gitignore",
    "A.9": "jinja/plan/roadmap.md.j2",
    "A.10": "jinja/plan/milestones/milestone.md.j2",
    "A.11": "jinja/plan/milestones/tasks/T0.md.j2",
    "A.12": "jinja/decisions/index.md.j2",
    "A.13": "jinja/references/catalog.md.j2",
    "A.14": "jinja/references/task-map.md.j2",
    "B.1": "jinja/specs/README.md.j2",
    "B.2": "static/specs/conventions.md",
    "B.3": "static/specs/workflow.md",
    "B.4": "static/specs/git-commit.md",
    "B.5": "static/specs/doc-types/task-card.spec.md",
    "B.6": "static/specs/doc-types/review.spec.md",
    "B.7": "jinja/specs/doc-types/_stub.spec.md.j2",
    "B.8": "static/specs/templates/task-card.md",
    "B.9": "static/specs/templates/review.md",
    "B.10": "static/specs/procedures/{label}",
    "C.1": "static/dot-lg/hooks/commit-msg",
    "C.2": "static/scripts/agent-commit",
    "C.3": "static/scripts/session-check",
    "C.4": "static/scripts/apply-human-commits",
}

HEADING_RE = re.compile(r"^## ([ABC]\.\d+) ")
LABEL_RE = re.compile(r"^`([\w.-]+)`$")
FENCE = "~~~~"


def extract(doc_text: str) -> dict[str, str]:
    """{템플릿 경로: 내용}. 절마다 `~~~~` 울타리 안을 꺼낸다."""
    out: dict[str, str] = {}
    found: set[str] = set()
    section = label = None
    block: list[str] | None = None
    for line in doc_text.splitlines():
        if block is not None:
            if line == FENCE:
                if section not in SECTIONS:
                    raise SystemExit(f"{section}: 경로 매핑이 없습니다")
                path = SECTIONS[section].format(label=label)
                if path in out:
                    raise SystemExit(f"{section}: 블록이 둘 이상입니다 ({path})")
                out[path] = "\n".join(block) + "\n"
                found.add(section)
                block = None
            else:
                block.append(line)
            continue
        if m := HEADING_RE.match(line):
            section, label = m.group(1), None
        elif line.startswith("# "):
            section = None
        elif m := LABEL_RE.match(line):
            label = m.group(1)
        elif line.startswith(FENCE) and section:
            block = []
    missing = set(SECTIONS) - found
    if missing:
        raise SystemExit(f"원문을 찾지 못한 절: {sorted(missing)}")
    return out


def diff(expected: dict[str, str]) -> list[str]:
    problems = []
    for path, content in sorted(expected.items()):
        f = TEMPLATES / path
        if not f.exists():
            problems.append(f"없음: {path}")
        elif f.read_text(encoding="utf-8") != content:
            problems.append(f"다름: {path}")
    actual = {p.relative_to(TEMPLATES).as_posix() for p in TEMPLATES.rglob("*") if p.is_file()}
    problems += [f"설계 문서에 없음: {p}" for p in sorted(actual - set(expected))]
    return problems


def main(argv: list[str]) -> int:
    expected = extract(DOC.read_text(encoding="utf-8"))
    if "--check" in argv:
        problems = diff(expected)
        for p in problems:
            print(p)
        if problems:
            print("설계 문서와 템플릿이 다릅니다. scripts/sync-templates.py 를 실행하세요.", file=sys.stderr)
        return 1 if problems else 0
    for path, content in expected.items():
        f = TEMPLATES / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content, encoding="utf-8", newline="\n")
    print(f"템플릿 {len(expected)}개를 썼습니다: {TEMPLATES.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
