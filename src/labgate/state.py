"""프로젝트 문서의 지금 상태를 frontmatter에서 읽는다 (`lg status`, `lg answer`, 설계 문서 §24).

`STATUS.md`(에이전트의 서술)는 읽지 않는다. 사실은 각 문서의 frontmatter와 `.lg/pending/`에 있다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from .project import Project
from .verify import frontmatter_fields


@dataclass
class Doc:
    rel: str
    fields: dict[str, str]
    text: str

    @property
    def id(self) -> str:
        return self.fields.get("id") or Path(self.rel).stem

    @property
    def status(self) -> str:
        return self.fields.get("status", "")


def numeric_key(doc_id: str) -> tuple:
    """M0-T10이 M0-T2 뒤에, D1.10이 D1.2 뒤에 오게."""
    return [int(n) for n in re.findall(r"\d+", doc_id)], doc_id


def _docs(project: Project, pattern: str) -> list[Doc]:
    out = []
    for path in project.root.glob(pattern):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            out.append(Doc(path.relative_to(project.root).as_posix(), frontmatter_fields(text), text))
    return sorted(out, key=lambda d: numeric_key(d.id))


def cards(project: Project, milestone: Optional[str] = None) -> list[Doc]:
    found = _docs(project, f"plan/milestones/{milestone or '*'}/tasks/*.md")
    return [d for d in found if project.hook["TASK_ID_RE"].match(d.id)]


def milestones(project: Project) -> list[Doc]:
    return _docs(project, "plan/milestones/*/milestone.md")


def decisions(project: Project) -> list[Doc]:
    return [d for d in _docs(project, "decisions/*.md") if d.fields.get("type") == "decision"]


def ideas(project: Project) -> list[Doc]:
    """ideation 후보 (`ideas/I<n>_<slug>.md`)."""
    return [d for d in _docs(project, "ideas/I*_*.md") if d.fields.get("type") == "idea"]


def open_reviews(project: Project) -> list[Doc]:
    """`reviews/open/`의 review 문서 (요청한 날, 이름 순)."""
    found = [d for d in _docs(project, "reviews/open/*.md") if d.fields.get("type") == "review"]
    return sorted(found, key=lambda d: (d.fields.get("requested", ""), d.id))


def closed_review_ids(project: Project) -> set[str]:
    return {p.stem for p in (project.root / "reviews" / "closed").glob("*.md")}


def milestone_of(task_id: str) -> str:
    return task_id.split("-")[0]


def card_title(project: Project, task_id: str) -> str:
    found = [d for d in cards(project, milestone_of(task_id)) if d.id == task_id]
    return found[0].fields.get("title", "") if found else ""


def current_milestone(project: Project) -> Optional[Doc]:
    """active인 첫 마일스톤, 없으면 planned인 첫 마일스톤."""
    ms = milestones(project)
    for wanted in ("active", "planned"):
        for m in ms:
            if m.status == wanted:
                return m
    return ms[-1] if ms else None


def frontmatter_list(text: str, key: str) -> list[str]:
    """frontmatter의 목록 값 (`decisions: [D0.1, D1.1]` 또는 여러 줄 목록). 읽지 못하면 빈 목록."""
    if not text.startswith("---\n") or "\n---\n" not in text[3:]:
        return []
    try:
        data = yaml.safe_load(text[4:text.index("\n---\n", 3)]) or {}
    except yaml.YAMLError:
        return []
    value = data.get(key) if isinstance(data, dict) else None
    if isinstance(value, list):
        return [str(v) for v in value if v]
    if isinstance(value, str) and value.strip():
        return [v.strip() for v in value.split(",") if v.strip()]
    return []


def spec_version(project: Project) -> int:
    data = yaml.safe_load((project.root / ".lg" / "project.yaml").read_text(encoding="utf-8"))
    return int(data["generated"]["spec_version"])


def project_name(project: Project) -> str:
    data = yaml.safe_load((project.root / ".lg" / "project.yaml").read_text(encoding="utf-8"))
    return str(data.get("project", {}).get("slug") or project.root.name)
