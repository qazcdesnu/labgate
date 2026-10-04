"""`lg init --from`: ideation 프로젝트에서 확정한 방향으로 새 프로젝트를 만든다 (설계 문서 §26.8).

ideation 프로젝트는 읽기만 한다. 넘기는 것은 커밋된 내용이어야 하므로 그 작업 트리가 깨끗해야 한다.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from . import gitops
from .errors import EXIT_USAGE, Fail

FIRST_SPEC = 7  # ideation이 생긴 spec_version


@dataclass
class Source:
    root: Path
    commit: str
    brief: dict[str, Any]
    brief_text: str
    project: dict[str, Any]


def read_source(path: Path) -> Source:
    root = Path(path).expanduser().resolve()
    try:
        data = yaml.safe_load((root / ".lg" / "project.yaml").read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        raise Fail(EXIT_USAGE, f"✗ --from: labgate 프로젝트가 아닙니다 ({root}).") from None
    project = data.get("project", {}) if isinstance(data, dict) else {}
    if project.get("kind") != "ideation":
        raise Fail(EXIT_USAGE, f"✗ --from: ideation 프로젝트가 아닙니다 (kind: {project.get('kind', 'research')}).")
    if int(data.get("generated", {}).get("spec_version", 0)) < FIRST_SPEC:
        raise Fail(EXIT_USAGE, f"✗ --from: spec_version {FIRST_SPEC} 이상의 ideation 프로젝트만 읽습니다.")
    status = gitops.run(["status", "--porcelain"], cwd=root)
    if status.returncode != 0 or status.stdout.strip():
        raise Fail(EXIT_USAGE, "✗ --from: ideation 프로젝트에 커밋되지 않은 변경이 있습니다. 넘기는 내용이 커밋된 것과 같도록 먼저 커밋하세요.")
    text = (root / "brief.md").read_text(encoding="utf-8") if (root / "brief.md").is_file() else ""
    brief = _frontmatter(text)
    if brief.get("status") != "confirmed":
        raise Fail(EXIT_USAGE, (
            f"✗ --from: 방향 확정 문서가 아직 확정되지 않았습니다 (brief.md status: {brief.get('status')}).\n"
            "  ideation 프로젝트의 마지막 마일스톤 게이트를 Milestone-Verdict go 로 판정하고, 반영된 뒤에 하세요."
        ))
    missing = [k for k in ("question", "summary", "milestones") if not brief.get(k)]
    if missing:
        raise Fail(EXIT_USAGE, f"✗ --from: brief.md 에 비어 있는 값이 있습니다: {', '.join(missing)}")
    commit = gitops.run(["rev-parse", "--short", "HEAD"], cwd=root).stdout.strip()
    return Source(root, commit, brief, text, data)


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n") or "\n---\n" not in text[3:]:
        return {}
    try:
        data = yaml.safe_load(text[4:text.index("\n---\n", 3)])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def config_data(source: Source, base: Optional[dict[str, Any]], kind: Optional[str],
                name: Optional[str], slug: Optional[str]) -> dict[str, Any]:
    """설정 dict. 설정 파일(`base`)의 값이 우선하고, 없는 값은 brief와 ideation 프로젝트에서 채운다."""
    data = dict(base or {"schema_version": 1})
    project = dict(data.get("project") or {})
    if name:
        project.setdefault("name", name)
    if slug:
        project.setdefault("slug", slug)
    project.setdefault("summary", source.brief["summary"])
    project.setdefault("research_question", source.brief["question"])
    if kind:
        project["kind"] = kind
    else:
        project.setdefault("kind", source.brief.get("kind") or "research")
    data["project"] = project
    people = dict(data.get("people") or {})
    people.setdefault("humans", source.project.get("people", {}).get("humans", []))
    data["people"] = people
    data.setdefault("agent_tools", source.project.get("agent_tools", {"claude_code": True}))
    data.setdefault("milestones", [{"title": str(t)} for t in source.brief["milestones"]])
    data["origin"] = {"path": str(source.root), "commit": source.commit, "brief": "brief.md"}
    return data


def carry(source: Source, target: Path) -> list[str]:
    """brief, 고른 후보, 넘길 참고문헌을 옮긴다. 옮기거나 바꾼 경로 목록 (프로젝트 기준)."""
    changed: list[str] = []

    def copy(src: Path, rel: str) -> None:
        dest = target / rel
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        changed.append(rel)

    copy(source.root / "brief.md", "notes/ideation-brief.md")
    for idea in source.brief.get("selected") or []:
        for path in sorted((source.root / "ideas").glob(f"{idea}_*.md")):
            copy(path, f"notes/ideation/{path.name}")

    refs = [str(r) for r in source.brief.get("references") or []]
    rows = _catalog_rows(source.root / "references" / "catalog.md", refs)
    for ref in refs:
        for path in sorted((source.root / "references" / "library").glob(f"{ref}.*")):
            copy(path, f"references/library/{path.name}")
    catalog = target / "references" / "catalog.md"
    if rows and catalog.is_file():
        text = catalog.read_text(encoding="utf-8")
        with open(catalog, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text.rstrip("\n") + "\n" + "".join(r + "\n" for r in rows))
        changed.append("references/catalog.md")
    return changed


def _catalog_rows(path: Path, refs: list[str]) -> list[str]:
    if not path.is_file() or not refs:
        return []
    wanted = set(refs)
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*`?([\w.-]+)`?\s*\|", line)
        if m and m.group(1) in wanted:
            out.append(line)
    return out
