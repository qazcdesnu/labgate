"""생성 계획 (설계 문서 §7, §8.4, §14.1 `plan`)."""
import json
import os
from pathlib import PurePosixPath

import pytest
import yaml

from conftest import ROOT, make_config
from labgate.config import parse_config
from labgate.plan import (
    MILESTONE_TEMPLATES,
    SINGLE_TEMPLATES,
    STATIC_FILES,
    STUB_TEMPLATE,
    build_plan,
    output_path,
)

TODAY = "2026-10-01"

# §7.1 트리를 그대로 옮긴 기대 경로 (plan.py와 독립적으로 작성)
COMMON = {
    "README.md", "FILEMAP.md", "AGENTS.md", "STATUS.md", ".gitignore",
    ".lg/project.yaml", ".lg/identities.json", ".lg/hooks/commit-msg",
    "specs/README.md", "specs/conventions.md", "specs/workflow.md", "specs/git-commit.md",
    "specs/doc-types/task-card.spec.md", "specs/doc-types/review.spec.md",
    *(f"specs/doc-types/{n}.spec.md" for n in (
        "roadmap", "milestone", "task-map", "catalog", "decision", "experiment-readme",
        "run-record", "task-result", "milestone-report", "worklog", "status",
    )),
    "specs/templates/task-card.md", "specs/templates/review.md",
    "plan/roadmap.md", "decisions/index.md", "references/catalog.md",
    "references/library/.gitkeep", "experiments/src/.gitkeep", "experiments/tests/.gitkeep",
    "runs/.gitkeep", "reviews/open/.gitkeep", "reviews/closed/.gitkeep", "logs/.gitkeep",
    "data/.gitkeep", "paper/.gitkeep", "notes/.gitkeep", "scripts/agent-commit", "env/.gitkeep",
}
CLAUDE = {
    "CLAUDE.md", ".claude/settings.json",
    *(f".claude/commands/{n}.md" for n in (
        "session-start", "task-start", "task-gate", "escalate", "session-close",
    )),
}


def per_milestone(m):
    return {
        f"plan/milestones/{m}/milestone.md", f"plan/milestones/{m}/tasks/{m}-T0.md",
        f"references/{m}/task-map.md", f"experiments/{m}/.gitkeep",
        f"results/{m}/figures/.gitkeep", f"results/{m}/tables/.gitkeep",
    }


def expected_paths(n, claude_code):
    paths = set(COMMON) | (CLAUDE if claude_code else set())
    for i in range(n):
        paths |= per_milestone(f"M{i}")
    return paths


def plan_for(n=3, claude_code=True):
    return build_plan(make_config(milestones=n, claude_code=claude_code), TODAY)


@pytest.mark.parametrize("n", [1, 3, 20])
@pytest.mark.parametrize("claude_code", [True, False])
def test_paths_match_design(n, claude_code):
    paths = {str(f.path) for f in plan_for(n, claude_code)}
    assert paths == expected_paths(n, claude_code)


@pytest.mark.parametrize("n, claude_code, count", [(3, True, 67), (1, True, 55), (20, True, 169), (3, False, 60)])
def test_file_count_formula(n, claude_code, count):
    """§7.2: claude_code면 49 + 6N, 아니면 42 + 6N. 예시 N=3 → 67."""
    assert len(plan_for(n, claude_code)) == count == (49 if claude_code else 42) + 6 * n


def test_no_claude_files_without_claude_code():
    paths = [str(f.path) for f in plan_for(claude_code=False)]
    assert not any(p == "CLAUDE.md" or p.startswith(".claude/") for p in paths)


def test_modes():
    modes = {str(f.path): f.mode for f in plan_for()}
    assert {p for p, m in modes.items() if m == 0o755} == {".lg/hooks/commit-msg", "scripts/agent-commit"}
    assert set(modes.values()) == {0o644, 0o755}


def test_paths_are_relative_and_clean():
    for f in plan_for():
        assert isinstance(f.path, PurePosixPath)
        assert not f.path.is_absolute() and ".." not in f.path.parts, f.path


def test_sorted_and_unique():
    paths = [f.path for f in plan_for()]
    assert paths == sorted(paths, key=lambda p: p.parts) and len(paths) == len(set(paths))


def test_text_files_end_with_single_newline():
    for f in plan_for():
        if f.path.name == ".gitkeep":
            assert f.content == ""
        else:
            assert f.content.endswith("\n") and not f.content.endswith("\n\n"), f.path
            assert "\r" not in f.content, f.path


def test_markdown_frontmatter_parses():
    """frontmatter가 있는 모든 .md는 YAML로 파싱되고 공통 필드를 갖는다 (§14.1)."""
    no_frontmatter = {"README.md", "AGENTS.md", "CLAUDE.md"}
    for f in plan_for():
        if f.path.suffix != ".md":
            continue
        if f.content.startswith("---\n"):
            fm = yaml.safe_load(f.content[4 : f.content.index("\n---\n", 4)])
            assert isinstance(fm, dict) and {"id", "type", "spec_version"} <= fm.keys(), f.path
        else:
            assert str(f.path) in no_frontmatter or f.path.parts[0] == ".claude", f.path


def test_task_card_ids_match_paths():
    for f in plan_for():
        if f.path.parent.name == "tasks":
            fm = yaml.safe_load(f.content[4 : f.content.index("\n---\n", 4)])
            assert fm["id"] == f.path.stem and fm["milestone"] == f.path.parts[2]


def test_identities_json():
    content = {str(f.path): f.content for f in plan_for()}[".lg/identities.json"]
    assert json.loads(content) == {
        "schema_version": 1,
        "humans": [{"name": "홍길동", "email": "gildong@example.com"}],
        "agent": {"name": "research-agent", "email": "agent@cap-partition.local"},
    }
    assert "홍길동" in content and content.endswith("}\n")


def test_project_yaml_roundtrips():
    config = make_config()
    content = {str(f.path): f.content for f in build_plan(config, TODAY)}[".lg/project.yaml"]
    data = yaml.safe_load(content)
    assert data["generated"]["created"] == TODAY
    assert parse_config(data).project == config.project


def test_static_content_is_copied_verbatim():
    files = {str(f.path): f.content for f in plan_for()}
    src = ROOT / "src/labgate/templates/static"
    assert files[".gitignore"] == (src / "dot-gitignore").read_text(encoding="utf-8")
    assert files[".lg/hooks/commit-msg"] == (src / "dot-lg/hooks/commit-msg").read_text(encoding="utf-8")


def test_every_template_is_used():
    """템플릿 폴더의 모든 파일이 계획 표 어딘가에 있다 (빠뜨린 템플릿 감지)."""
    tdir = ROOT / "src/labgate/templates"
    jinja = {p.relative_to(tdir / "jinja").as_posix() for p in (tdir / "jinja").rglob("*.j2")}
    static = {p.relative_to(tdir / "static").as_posix() for p in (tdir / "static").rglob("*") if p.is_file()}
    used_jinja = {t for t, _ in SINGLE_TEMPLATES} | {t for t, _ in MILESTONE_TEMPLATES} | {STUB_TEMPLATE}
    assert used_jinja == jinja
    assert {s for s, _, _ in STATIC_FILES} == static


@pytest.mark.parametrize(
    "template, expected",
    [
        ("dot-claude/commands/x.md", ".claude/commands/x.md"),
        ("dot-gitignore", ".gitignore"),
        ("dot-lg/hooks/commit-msg", ".lg/hooks/commit-msg"),
        ("plan/roadmap.md.j2", "plan/roadmap.md"),
        ("specs/doc-types/task-card.spec.md", "specs/doc-types/task-card.spec.md"),
    ],
)
def test_output_path(template, expected):
    assert output_path(template) == PurePosixPath(expected)


def test_build_plan_is_pure(tmp_path, monkeypatch):
    """§8.4: 부작용 없음. 같은 입력이면 같은 결과이고 파일 시스템에 아무것도 쓰지 않는다."""
    monkeypatch.chdir(tmp_path)
    config = make_config()
    first = build_plan(config, TODAY)
    assert build_plan(config, TODAY) == first
    assert os.listdir(tmp_path) == []
    assert config == make_config()  # 입력 설정도 바뀌지 않는다
