"""`lg verify` (설계 문서 §23): 커밋 이력으로 에이전트가 규칙을 지켰는지 사후에 확인한다."""
import pytest

from labgate.verify import project_rules

from support.releases import TAGS, make_old

CARD = "plan/milestones/M0/tasks/M0-T0.md"


def verify(project, *args):
    return project.lg("verify", *args)


def test_rules_read_from_project_specs(project):
    rules = project_rules(project.root)
    assert {"task-card", "review", "spec", "procedure", "filemap"} <= rules["types"]
    assert rules["statuses"]["task-card"] >= {"draft", "approved", "in-progress", "closed"}
    assert "budget" in rules["required"]["task-card"] and "verdict" in rules["required"]["review"]


# ---------------------------------------------------------------- 정상 흐름


def test_normal_flow_has_no_violations(project):
    project.approve_and_start()
    result = verify(project)
    assert result.exit_code == 0, result.output
    assert "위반 없음." in result.output


def test_refs_basis_v02_style_is_accepted(project):
    """v0.2 방식: 에이전트가 판단으로 draft → in-progress, 근거를 Refs로 남김."""
    sha = project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.set_status(CARD, "in-progress")
    project.agent(f"task(M0-T0): start\n\nActor: agent\nTask: M0-T0\nRefs: {sha[:7]}", CARD)
    result = verify(project)
    assert "✓ V2" in result.output, result.output


# ---------------------------------------------------------------- 위반 검출


def test_v1_bypassed_hook(project):
    project.agent("gate(M0-T0): approve\n\nActor: agent\nTask: M0-T0\nVerdict: approve\nSource: document", no_verify=True)
    result = verify(project)
    assert result.exit_code == 3
    assert "✗ V1" in result.output and "사람 전용 타입" in result.output


def test_v1_unregistered_author(project):
    project.git("-c", "user.email=z@y.com", "commit", "-q", "--allow-empty", "--no-verify", "-m", "chore: x\n\nActor: human")
    assert "등록되지 않은 작성자 <z@y.com>" in verify(project).output


def test_v2_unjustified_transition(project):
    project.set_status(CARD, "approved")
    sha = project.agent("task(M0-T0): self approve\n\nActor: agent\nTask: M0-T0", CARD)
    result = verify(project)
    assert result.exit_code == 3
    assert "✗ V2" in result.output and sha[:7] in result.output and "draft → approved" in result.output


def test_v2_wrong_basis(project):
    """근거가 있어도 그 전이를 정하지 않으면 위반 (revise 판정인데 closed로 바꿈)."""
    project.set_status(CARD, "in-review")
    project.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD)
    sha = project.human("gate(M0-T0): revise\n\nActor: human\nTask: M0-T0\nVerdict: revise\nSource: document")
    project.set_status(CARD, "closed")
    project.agent(f"log(M0-T0): apply gate {sha[:7]}\n\nActor: agent\nApplies: {sha[:7]}", CARD)
    result = verify(project)
    assert "in-review → closed" in result.output and sha[:7] in result.output


def test_v3_agent_writes_response(project):
    review = "reviews/open/M0-T0_gate-01.md"
    project.write(review, "---\nid: M0-T0_gate-01\n---\n# r\n\n## 응답\n\n")
    project.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", review)
    project.write(review, project.read(review) + "승인합니다.\n")
    project.agent("log(M0-T0): note\n\nActor: agent", review)
    result = verify(project)
    assert "✗ V3" in result.output and "## 응답 이 바뀜" in result.output


def test_v3_follows_rename_without_change(project):
    """반영 도구가 review를 closed/로 옮기는 것은 응답을 바꾸지 않는다."""
    review = "reviews/open/M0-T0_gate-01.md"
    project.write(review, "---\nid: M0-T0_gate-01\nstatus: answered\n---\n# r\n\n## 응답\n\n승인\n")
    project.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none", all=True)
    project.git("mv", review, "reviews/closed/M0-T0_gate-01.md")
    project.agent("log(M0-T0): close review\n\nActor: agent")
    assert "✓ V3" in verify(project).output


def test_v4_agent_edits_rules(project):
    project.write("specs/workflow.md", project.read("specs/workflow.md") + "\n추가\n")
    project.agent("chore: tweak workflow\n\nActor: agent\nTask: M0-T0", "specs/workflow.md")
    result = verify(project)
    assert "✗ V4" in result.output and "specs/workflow.md" in result.output
    assert "카드 M0-T0 범위 › 포함" in result.output  # 범위 원문을 함께 보여 준다


def test_v4_human_spec_commit_is_fine(project):
    project.write("specs/workflow.md", project.read("specs/workflow.md") + "\n추가\n")
    project.human("spec: tweak workflow\n\nActor: human", all=True)
    assert "✓ V4" in verify(project).output


def test_v5_document_format(project):
    project.write("notes/bad.md", "---\ntype: task-card\nid: X\nstatus: maybe\n---\n")
    project.write("notes/broken.md", "---\nkey: [unclosed\n---\n")
    project.human("chore: notes\n\nActor: human", all=True)
    out = verify(project).output
    assert "notes/bad.md: task-card 상태값이 아님 (maybe)" in out
    assert "notes/bad.md: 필수 필드 없음 (budget)" in out
    assert "notes/bad.md: id(X)가 파일 이름과 다름" in out
    assert "notes/broken.md: frontmatter를 YAML로 읽을 수 없음" in out


# ---------------------------------------------------------------- 범위


def test_default_range_since_last_gate_tag(project):
    project.set_status(CARD, "approved")
    project.agent("task(M0-T0): self approve\n\nActor: agent\nTask: M0-T0", CARD)  # 위반
    project.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none")
    project.git("tag", "gate/M0-T0")
    assert "✓ V2" in verify(project).output                       # 게이트 이후만
    assert "✗ V2" in verify(project, "--all").output


def test_task_scope_and_checklist(project):
    project.approve_and_start()
    project.write("notes/other.md", "x\n")
    project.agent("log: unrelated\n\nActor: agent", "notes/other.md")
    result = verify(project, "--task", "M0-T0")
    assert "task M0-T0, 커밋 3개" in result.output  # 승인, 반영, 착수. init과 무관한 커밋은 제외
    assert "완료 기준: 0/" in result.output


def test_range_options_are_exclusive(project):
    result = verify(project, "--all", "--task", "M0-T0")
    assert result.exit_code == 2


# ---------------------------------------------------------------- 옛 spec_version 프로젝트 (릴리즈 tag로 생성)


@pytest.mark.parametrize("spec", sorted(TAGS))
def test_old_projects_rules_and_clean_run(tmp_path, git_sandbox, old_sources, spec):
    old = make_old(tmp_path, git_sandbox, old_sources, spec)
    rules = project_rules(old.root)
    assert rules["statuses"]["task-card"] >= {"draft", "approved", "closed"}
    assert "budget" in rules["required"]["task-card"]
    result = old.lg("verify")
    assert result.exit_code == 0, result.output
