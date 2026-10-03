"""`lg upgrade` (설계 문서 §22).

옛 spec_version의 프로젝트는 그 버전을 만든 릴리즈 tag의 labgate로 실제로 만든다 (support.releases).
tag가 없는 환경(얕은 클론, 소스 배포판)에서는 그 테스트를 건너뛴다.
"""
import pytest
import yaml

from labgate import SPEC_VERSION, kinds
from labgate.upgrade import MIGRATIONS

from support.configs import PROJECT_NAME
from support.releases import TAGS, current_files, make_old

OLDER = sorted(s for s in TAGS if s < SPEC_VERSION)


# ---------------------------------------------------------------- 갱신


@pytest.mark.parametrize("spec", OLDER)
@pytest.mark.parametrize("claude_code", [True, False])
def test_upgrade_old_project(tmp_path, git_sandbox, old_sources, spec, claude_code):
    p = make_old(tmp_path, git_sandbox, old_sources, spec, claude_code)
    result = p.lg("upgrade")
    assert result.exit_code == 0, result.output
    expected = current_files(claude_code)
    for path, (content, mode) in expected.items():
        kind = kinds.classify(path)
        if kind in (kinds.MANAGED, kinds.EDITABLE, kinds.GITIGNORE):
            assert p.read(path) == content, path
            assert (p.root / path).stat().st_mode & 0o777 == mode, path
    for path in p.git("ls-files").splitlines():
        if path.endswith(".md") and p.read(path).startswith("---\n"):
            assert f"spec_version: {SPEC_VERSION}\n" in p.read(path) or "spec_version" not in p.read(path), path
    data = p.yaml()
    assert data["generated"]["spec_version"] == SPEC_VERSION
    assert data["upgrades"][-1]["from"] == spec and data["upgrades"][-1]["forced"] == []
    p.human("spec: x\n\nActor: human", all=True)  # hook을 통과한다
    assert p.lg("upgrade").output.startswith(f"이미 spec_version {SPEC_VERSION}")


def test_human_edited_managed_fails_then_force(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("specs/workflow.md", p.read("specs/workflow.md") + "\n사람이 추가한 원칙\n")
    p.human("spec: x\n\nActor: human", all=True)
    result = p.lg("upgrade")
    assert result.exit_code == 3
    assert "specs/workflow.md" in result.output and "아무것도 바꾸지 않았습니다" in result.output
    assert p.git("status", "--porcelain") == ""
    assert "릴리즈된 spec_version 3과 다른 관리 문서" in result.output and "(지금 → 새 버전: +" in result.output
    diff = p.lg("upgrade", "--diff")
    assert diff.exit_code == 0 and "-사람이 추가한 원칙" in diff.output and "--- specs/workflow.md (지금)" in diff.output
    assert p.git("status", "--porcelain") == ""
    result = p.lg("upgrade", "--force")
    assert result.exit_code == 0, result.output
    assert "사람이 추가한 원칙" not in p.read("specs/workflow.md")
    assert "사람이 추가한 원칙" in p.read(".lg/pending/upgrade/specs/workflow.md")
    assert p.yaml()["upgrades"][-1]["forced"] == ["specs/workflow.md"]


def test_filled_stub_is_kept(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    stub = "specs/doc-types/catalog.spec.md"
    p.write(stub, p.read(stub).replace("status: stub", "status: complete") + "\n## 사람이 채운 내용\n")
    p.human("spec: x\n\nActor: human", all=True)
    result = p.lg("upgrade")
    assert result.exit_code == 0, result.output
    assert "사람이 채운 내용" in p.read(stub) and f"spec_version: {SPEC_VERSION}\n" in p.read(stub)
    assert "사람이 채운 것으로 봄" in result.output


def test_agents_project_lines_preserved(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 2)
    p.write("AGENTS.md", p.read("AGENTS.md").replace(f"- 이름: {PROJECT_NAME}", "- 이름: 새 이름"))
    p.human("spec: x\n\nActor: human", all=True)
    result = p.lg("upgrade")
    assert result.exit_code == 0, result.output
    assert "- 이름: 새 이름\n" in p.read("AGENTS.md")


def test_gitignore_keeps_human_choices(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write(".gitignore", p.read(".gitignore").replace("wandb/\n", "") + "\n# 내 산출물\ncheckpoints/\n")
    p.human("spec: x\n\nActor: human", all=True)
    result = p.lg("upgrade")
    assert result.exit_code == 0, result.output
    text = p.read(".gitignore")
    assert text.startswith(kinds.BEGIN) and kinds.END in text
    assert "wandb/" not in text
    assert text.index("\ncheckpoints/\n") > text.index(kinds.END) and "# 내 산출물" in text
    assert "사람이 지운 labgate 줄은 다시 넣지 않았습니다: wandb/" in result.output
    # 다음 갱신의 기준: 관리 구역 안에 사람이 더한 줄은 밖으로 옮긴다 (§22.5.2)
    p.human("spec: x\n\nActor: human", all=True)


def test_research_doc_versions(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("notes/odd.md", '---\nspec_version: "3"\n---\n# x\n')
    p.human("spec: x\n\nActor: human", all=True)
    result = p.lg("upgrade")
    assert result.exit_code == 0, result.output
    assert "spec_version 형식이 아니라 그대로 두었습니다: notes/odd.md" in result.output
    assert p.read("notes/odd.md").startswith('---\nspec_version: "3"\n')
    assert p.read("STATUS.md").count(f"spec_version: {SPEC_VERSION}\n") == 1


def test_newer_research_doc_is_error(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("notes/new.md", "---\nspec_version: 99\n---\n")
    p.human("spec: x\n\nActor: human", all=True)
    result = p.lg("upgrade")
    assert result.exit_code == 2 and "notes/new.md" in result.output
    assert p.git("status", "--porcelain") == ""


def test_dry_run_changes_nothing(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    result = p.lg("upgrade", "--dry-run")
    assert result.exit_code == 0 and "미리 보기" in result.output and "아무것도 바꾸지 않았습니다" in result.output
    assert p.git("status", "--porcelain") == ""


def test_requires_clean_tree_and_no_pending(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("notes/wip.md", "x\n")
    assert p.lg("upgrade").exit_code == 2
    (p.root / "notes/wip.md").unlink()
    (p.root / ".lg/pending").mkdir(exist_ok=True)
    p.write(".lg/pending/COMMIT_MSG", "x\n")
    result = p.lg("upgrade")
    assert result.exit_code == 2 and "COMMIT_MSG" in result.output


def test_unsupported_source(project, monkeypatch):
    data = project.yaml()
    data["generated"]["spec_version"] = 1
    project.write(".lg/project.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    project.human("spec: x\n\nActor: human", all=True)
    result = project.lg("upgrade")
    assert result.exit_code == 2 and "올릴 수 없습니다" in result.output
    # 해시표가 없는 spec_version (dev 버전으로 만든 프로젝트)
    monkeypatch.setitem(MIGRATIONS, 1, ())
    result = project.lg("upgrade")
    assert result.exit_code == 2 and "해시표가 없습니다" in result.output


def test_already_latest(project):
    result = project.lg("upgrade")
    assert result.exit_code == 0 and result.output.startswith(f"이미 spec_version {SPEC_VERSION}")
