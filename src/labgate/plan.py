"""생성 계획: 만들 파일의 목록과 내용 (설계 문서 §7, §8.4). 부작용이 없다."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import PurePosixPath

from . import SPEC_VERSION, __version__
from .config import Config, dump_project_yaml
from .render import base_context, milestone_context, read_static, render, stub_context
from .stubs import STUBS

EXECUTABLE = 0o755
REGULAR = 0o644


@dataclass(frozen=True)
class PlannedFile:
    path: PurePosixPath  # 프로젝트 루트 기준 상대 경로
    content: str
    mode: int = REGULAR


# §7.2의 S(그대로 복사) 파일: (templates/static 기준 경로, 권한, claude_code일 때만)
STATIC_FILES: tuple[tuple[str, int, bool], ...] = (
    ("dot-claude/settings.json", REGULAR, True),
    ("dot-claude/commands/session-start.md", REGULAR, True),
    ("dot-claude/commands/task-start.md", REGULAR, True),
    ("dot-claude/commands/task-gate.md", REGULAR, True),
    ("dot-claude/commands/escalate.md", REGULAR, True),
    ("dot-claude/commands/session-close.md", REGULAR, True),
    ("dot-claude/commands/commit-prep.md", REGULAR, True),
    ("dot-gitignore", REGULAR, False),
    ("dot-lg/hooks/commit-msg", EXECUTABLE, False),
    ("scripts/agent-commit", EXECUTABLE, False),
    ("scripts/session-check", EXECUTABLE, False),
    ("scripts/apply-human-commits", EXECUTABLE, False),
    ("specs/conventions.md", REGULAR, False),
    ("specs/workflow.md", REGULAR, False),
    ("specs/git-commit.md", REGULAR, False),
    ("specs/doc-types/task-card.spec.md", REGULAR, False),
    ("specs/doc-types/review.spec.md", REGULAR, False),
    ("specs/templates/task-card.md", REGULAR, False),
    ("specs/templates/review.md", REGULAR, False),
) + tuple(
    (f"specs/procedures/{name}.md", REGULAR, False)
    for name in (
        "session-start", "session-close", "commit-prep", "task-start",
        "task-gate", "escalate", "gate-conversation", "gate-apply",
    )
)

# §7.2의 J(Jinja) 파일 중 한 번만 렌더링하는 것: (templates/jinja 기준 경로, claude_code일 때만)
SINGLE_TEMPLATES: tuple[tuple[str, bool], ...] = (
    ("README.md.j2", False),
    ("FILEMAP.md.j2", False),
    ("AGENTS.md.j2", False),
    ("CLAUDE.md.j2", True),
    ("STATUS.md.j2", False),
    ("plan/roadmap.md.j2", False),
    ("decisions/index.md.j2", False),
    ("references/catalog.md.j2", False),
    ("specs/README.md.j2", False),
)

# ideation 종류에서만 만드는 파일 (§26): Jinja와 정적 파일
IDEATION_TEMPLATES: tuple[str, ...] = ("plan/criteria.md.j2", "plan/baseline.md.j2", "ideas/index.md.j2", "brief.md.j2")
IDEATION_STATIC: tuple[str, ...] = (
    "specs/doc-types/idea.spec.md", "specs/doc-types/criteria.spec.md",
    "specs/doc-types/brief.spec.md", "specs/doc-types/baseline.spec.md", "specs/templates/idea.md",
)

# 마일스톤마다 렌더링하는 템플릿 → 출력 경로 형식
MILESTONE_TEMPLATES: tuple[tuple[str, str], ...] = (
    ("plan/milestones/milestone.md.j2", "plan/milestones/{m}/milestone.md"),
    ("plan/milestones/tasks/T0.md.j2", "plan/milestones/{m}/tasks/{m}-T0.md"),
    ("references/task-map.md.j2", "references/{m}/task-map.md"),
)

STUB_TEMPLATE = "specs/doc-types/_stub.spec.md.j2"

# 빈 폴더를 Git에 남기기 위한 .gitkeep (§7.2)
GITKEEP_DIRS = (
    "references/library", "experiments/src", "experiments/tests", "runs",
    "reviews/open", "reviews/closed", "logs", "data", "notes", "env",
)
# 산출 원고 폴더: 연구는 논문, 제안서는 제출물 (§25), ideation은 없음 (§26)
OUTPUT_DIR = {"research": "paper", "proposal": "deliverables", "ideation": None}
GITKEEP_MILESTONE_DIRS = ("experiments/{m}", "results/{m}/figures", "results/{m}/tables")


def output_path(template_path: str) -> PurePosixPath:
    """템플릿 경로 → 출력 경로. 경로 조각의 `dot-` 접두어는 `.`으로, `.j2`는 뗀다 (§8.1)."""
    parts = ["." + p[4:] if p.startswith("dot-") else p for p in template_path.split("/")]
    if parts[-1].endswith(".j2"):
        parts[-1] = parts[-1][:-3]
    return PurePosixPath(*parts)


def identities_json(config: Config) -> str:
    """`.lg/identities.json` (§10.3). hook과 agent-commit이 표준 라이브러리로 읽는다."""
    data = {
        "schema_version": 1,
        "humans": [h.model_dump() for h in config.humans],
        "agent": config.agent.model_dump(),
    }
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def build_plan(config: Config, today: str) -> list[PlannedFile]:
    """만들 파일 목록을 경로 순으로 돌려준다. 파일 시스템을 건드리지 않는다."""
    claude = config.agent_tools.claude_code
    base = base_context(config, today)
    files: list[PlannedFile] = []

    for template, claude_only in SINGLE_TEMPLATES:
        if claude or not claude_only:
            files.append(PlannedFile(output_path(template), render(template, base)))

    if config.project.kind == "ideation":
        files += [PlannedFile(output_path(t), render(t, base)) for t in IDEATION_TEMPLATES]
        files += [PlannedFile(output_path(src), read_static(src)) for src in IDEATION_STATIC]

    for i, m in enumerate(base["milestones"]):
        ctx = milestone_context(base, i)
        for template, out in MILESTONE_TEMPLATES:
            files.append(PlannedFile(PurePosixPath(out.format(m=m["id"])), render(template, ctx)))

    for stub in STUBS:
        path = PurePosixPath(f"specs/doc-types/{stub.name}.spec.md")
        files.append(PlannedFile(path, render(STUB_TEMPLATE, stub_context(base, stub))))

    for source, mode, claude_only in STATIC_FILES:
        if claude or not claude_only:
            files.append(PlannedFile(output_path(source), read_static(source), mode))

    files.append(PlannedFile(
        PurePosixPath(".lg/project.yaml"),
        dump_project_yaml(config, __version__, SPEC_VERSION, today),
    ))
    files.append(PlannedFile(PurePosixPath(".lg/identities.json"), identities_json(config)))

    dirs = [*GITKEEP_DIRS, *filter(None, [OUTPUT_DIR[config.project.kind]])]
    for m in base["milestones"]:
        dirs += [d.format(m=m["id"]) for d in GITKEEP_MILESTONE_DIRS]
    files += [PlannedFile(PurePosixPath(d) / ".gitkeep", "") for d in dirs]

    paths = [f.path for f in files]
    assert len(paths) == len(set(paths)), "생성 계획에 중복 경로가 있습니다"
    return sorted(files, key=lambda f: f.path.parts)
