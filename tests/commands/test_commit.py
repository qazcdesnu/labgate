"""`lg commit` (설계 문서 §18): 사람 신원의 커밋. 초안 모드와 작성 모드, tag, gate의 lg verify 요약, 다음 할 일 안내."""
import pytest

import labgate.commit as commit_module

from support.cli import DOWN, ENTER, SPACE, lg
from support.configs import HUMAN


@pytest.fixture
def proj(project, monkeypatch):
    """프로젝트 폴더에서 lg를 실행한다."""
    monkeypatch.chdir(project.root)
    return project


def test_commit_requires_tty(proj):
    result = lg("commit")
    assert result.exit_code == 2 and "터미널에서 직접" in result.output


def test_commit_requires_registered_human(proj, tty):
    proj.git("config", "user.email", proj.agent_email)
    result = lg("commit")
    assert result.exit_code == 2 and "humans 에 없습니다" in result.output


def test_commit_pending_without_draft(proj, tty):
    result = lg("commit", "--pending")
    assert result.exit_code == 3 and "초안이 없습니다" in result.output


def test_commit_draft_mode(proj, keys):
    proj.write("experiments/src/human.py")
    proj.write("notes/later.md")
    proj.session_check()
    assert lg("draft", "--type", "exp", "--summary", "add human code", "experiments/src/human.py").exit_code == 0
    keys(ENTER)  # 커밋
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert proj.last_commit() == f"{HUMAN}|exp: add human code"
    assert not (proj / ".lg/pending/COMMIT_MSG").exists()
    # 아직 커밋되지 않은 사람의 변경만 남는다
    assert proj.read(".lg/pending/HUMAN_FILES") == "notes/later.md\n"


def test_commit_gate_approve_tags(proj, keys):
    proj.write("reviews/open/M0-T0_gate-01.md")
    assert lg("draft", "--type", "gate", "--summary", "approve, next M1-T0",
              "--trailer", "Task=M0-T0", "--trailer", "Verdict=approve", "--trailer", "Source=conversation",
              "--trailer", "Next=M1-T0", "--trailer", "Milestone-Verdict=go", "reviews").exit_code == 0
    keys(ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert set(proj.git("tag", "--points-at", "HEAD").split()) == {"gate/M0-T0", "milestone/M0-go"}


def test_commit_no_tag(proj, keys):
    proj.write("r.md")
    lg("draft", "--type", "gate", "--summary", "approve", "--trailer", "Task=M0-T0",
       "--trailer", "Verdict=approve", "--trailer", "Source=document", "r.md")
    keys(ENTER)
    assert lg("commit", "--no-tag").exit_code == 0
    assert proj.git("tag") == ""


def test_commit_cancel_keeps_draft(proj, keys):
    proj.write("a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    keys(DOWN, DOWN, ENTER)  # 취소
    result = lg("commit")
    assert result.exit_code == 130 and "그대로 두었습니다" in result.output
    assert (proj / ".lg/pending/COMMIT_MSG").exists()
    assert proj.git("diff", "--cached", "--name-only") == "a.py"


def test_commit_edit_is_revalidated(proj, keys, monkeypatch):
    proj.write("a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    edits = iter(["task: agent only\n\nActor: human\n", "exp: fixed after edit\n\nActor: human\n"])
    monkeypatch.setattr(commit_module, "_edit", lambda project, text: next(edits))
    # 편집 → (규약 위반이라 선택지는 편집/취소) 편집 → 커밋
    keys(DOWN, ENTER, ENTER, ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert "'task'는 에이전트 전용 타입입니다." in result.output
    assert proj.last_commit() == f"{HUMAN}|exp: fixed after edit"


def test_commit_editor_uses_git_editor(proj, keys, monkeypatch):
    """§18.2 5: 편집기는 Git과 같은 규칙으로 고른다 (core.editor). 인자가 붙은 편집기 문자열도 동작."""
    editor = proj.root.parent / "fake-editor.sh"
    editor.write_text('#!/bin/sh\nprintf "exp: %s\\n\\nActor: human\\n" "$1" > "$2"\n', encoding="utf-8")
    editor.chmod(0o755)
    proj.git("config", "core.editor", f"{editor} edited-by-editor")
    proj.write("a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    keys(DOWN, ENTER, ENTER)  # 편집 → 커밋
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert proj.last_commit() == f"{HUMAN}|exp: edited-by-editor"


def test_commit_rejected_by_git_keeps_draft(proj, keys):
    hook = proj / ".lg/hooks/pre-commit"
    hook.write_text("#!/bin/sh\necho blocked >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    proj.write("a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    keys(ENTER)
    result = lg("commit")
    assert result.exit_code == 4 and "blocked" in result.output
    assert (proj / ".lg/pending/COMMIT_MSG").exists()


def test_commit_compose_mode(proj, keys):
    proj.write("experiments/src/a.py")
    # 파일 선택 → 타입 exp(목록의 6번째) → scope 생략 → 요약 → 커밋
    keys(SPACE, ENTER, DOWN * 5, ENTER, ENTER, "add a\r", ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert proj.last_commit() == f"{HUMAN}|exp: add a"
    assert proj.git("status", "--porcelain") == ""


def test_commit_plan_approve_empty(proj, keys):
    """첫 task 승인: 바뀐 파일 없이 plan + Approve. 하나만 고르면 scope도 그 Task."""
    # 타입 plan(목록의 3번째) → Approve M0-T0 선택 → 요약 → 커밋
    keys(DOWN * 2, ENTER, SPACE, ENTER, "approve initial task\r", ENTER)
    result = lg("commit", "--allow-empty")
    assert result.exit_code == 0, result.output
    assert proj.last_commit() == f"{HUMAN}|plan(M0-T0): approve initial task"
    assert proj.trailers() == "Actor: human\nApprove: M0-T0"
    assert proj.git("show", "--name-only", "--format=") == ""


def test_commit_plan_approve_several(proj, keys):
    # 두 task를 고르면 scope는 따로 묻는다 (빈 입력이면 생략)
    keys(DOWN * 2, ENTER, SPACE, DOWN, SPACE, ENTER, ENTER, "approve tasks\r", ENTER)
    result = lg("commit", "--allow-empty")
    assert result.exit_code == 0, result.output
    assert proj.last_commit() == f"{HUMAN}|plan: approve tasks"
    assert proj.trailers() == "Actor: human\nApprove: M0-T0, M1-T0"


def test_commit_plan_without_approve(proj, keys):
    """로드맵만 바꾸는 plan 커밋은 Approve를 고르지 않는다."""
    proj.write("plan/roadmap.md", "changed\n")
    keys(SPACE, ENTER, DOWN * 2, ENTER, ENTER, ENTER, "revise roadmap\r", ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert proj.last_commit() == f"{HUMAN}|plan: revise roadmap"
    assert proj.trailers() == "Actor: human"


def test_commit_nothing_to_commit(proj, tty):
    result = lg("commit")
    assert result.exit_code == 3 and "커밋할 변경이 없습니다" in result.output


@pytest.mark.parametrize("message, from_draft, expected", [
    ("exp: a\n\nActor: human\n", True, "에이전트가 기다리고 있으면"),
    ("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\n", False, "다음 세션 시작 때"),
    ("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0\n", False, "다음 세션 시작 때"),
    ("plan: revise roadmap\n\nActor: human\n", False, None),
    ("spec: upgrade\n\nActor: human\n", False, "규칙 문서가 바뀌었습니다"),
    ("exp: a\n\nActor: human\n", False, None),
])
def test_next_step_hint(proj, message, from_draft, expected):
    """§18.2 9: 에이전트에게 알릴 필요는 열린 세션이 기다릴 때뿐이다."""
    from labgate.project import find_project
    hint = commit_module.next_step_hint(find_project(proj.root), message, from_draft)
    assert (hint is None) if expected is None else (expected in hint)


# ---------------------------------------------------------------- gate 커밋의 lg verify 요약 (§23.5)

CARD = "plan/milestones/M0/tasks/M0-T0.md"


def gate_draft(proj):
    """사람 커밋 대기 상태의 gate 초안 (에이전트가 lg draft로 만든 것과 같다)."""
    proj.write("reviews/open/M0-T0_gate-01.md", "x\n")
    proj.git("add", "reviews")
    proj.write(".lg/pending/COMMIT_MSG",
               "gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\n")


def test_commit_gate_shows_violations_but_does_not_block(proj, keys):
    proj.set_status(CARD, "in-review")
    proj.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD)  # draft → in-review: 근거 없음
    gate_draft(proj)
    keys(ENTER)  # 첫 선택지: 커밋 (위반 1건 있음)
    result = proj.lg("commit")
    assert result.exit_code == 0, result.output
    assert "✗ lg verify --task M0-T0: 위반 1건" in result.output
    assert "자세히: lg verify --task M0-T0" in result.output


def test_commit_gate_clean_one_line(proj, keys):
    proj.approve_and_start()
    proj.set_status(CARD, "in-review")
    proj.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD)
    gate_draft(proj)
    keys(ENTER)
    result = proj.lg("commit")
    assert result.exit_code == 0, result.output
    assert "✓ lg verify --task M0-T0: 위반 없음" in result.output


def test_commit_non_gate_does_not_verify(proj, keys):
    proj.write("a.py", "x\n")
    proj.git("add", "a.py")
    proj.write(".lg/pending/COMMIT_MSG", "exp: a\n\nActor: human\n")
    keys(ENTER)
    result = proj.lg("commit")
    assert result.exit_code == 0 and "lg verify" not in result.output


def test_compose_gate_skips_milestone_verdict_mid_milestone(proj, keys):
    """§18.4: 마일스톤의 마지막 task가 아니면 Milestone-Verdict를 묻지 않는다 (실사용: M0-T0에서 go를 고를 뻔함)."""
    proj.add_card("M0-T1")
    proj.agent("propose(M0-T0): add card\n\nActor: agent", "plan")
    proj.write("reviews/open/M0-T0_gate-01.md")
    # 파일 → gate → M0-T0 → approve → document → Next M0-T1 → (마일스톤 질문 없음) 요약 → 커밋
    keys(SPACE, ENTER, ENTER, ENTER, ENTER, ENTER, "M0-T1\r", "approve, next M0-T1\r", ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert "Milestone-Verdict" not in proj.trailers() and "Next: M0-T1" in proj.trailers()


def test_compose_gate_asks_milestone_verdict_for_last_task(proj, keys):
    proj.write("reviews/open/M0-T0_gate-01.md")
    # … Next none → 마일스톤 판정 go → 요약 → 커밋
    keys(SPACE, ENTER, ENTER, ENTER, ENTER, ENTER, "none\r", DOWN, ENTER, "approve\r", ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert "Milestone-Verdict: go" in proj.trailers()
