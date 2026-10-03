"""`lg answer` (설계 문서 §24.4): 열린 review를 보여 주고 판정을 물어, `## 응답`과 사람 커밋을 함께 만든다."""
import pytest

import labgate.commit as commit_module
from support.cli import DOWN, ENTER, SPACE
from support.configs import HUMAN
from support.releases import make_old

CARD0 = "plan/milestones/M0/tasks/M0-T0.md"
MILESTONE0 = "plan/milestones/M0/milestone.md"
GATE = "reviews/open/M0-T0_gate-01.md"


@pytest.fixture
def gate(project):
    """M0-T0을 끝내고 게이트를 요청한 상태. 다음 후보 M0-T1(제안), M0-T2."""
    project.approve_and_start()
    project.add_card("M0-T1", title="정독")
    project.add_card("M0-T2", title="대조")
    project.agent("propose(M0-T0): add tasks\n\nActor: agent", "plan")
    project.request_gate(proposed_next="M0-T1")
    return project


def commits_since(project, n):
    return project.git("log", f"-{n}", "--reverse", "--format=%ae|%s").splitlines()


# ---------------------------------------------------------------- gate


def test_approve_with_several_next_tasks_makes_gate_and_plan(gate, keys):
    # 판정 approve → 다음 task: M0-T1(미리 골라 둠) + M0-T2 → 코멘트 없음 → 커밋 (2개)
    keys(ENTER, DOWN, SPACE, ENTER, ENTER, ENTER)
    result = gate.lg("answer")
    assert result.exit_code == 0, result.output
    out = result.output
    assert "## 요약" in out or "요약" in out                      # 요청서를 보여 준다
    assert "✓ lg verify --task M0-T0: 위반 없음" in out
    assert f"{CARD0}: status in-review → closed" in out           # 미리보기 (프로젝트의 반영 도구)
    assert f"{MILESTONE0}: status planned → active" in out
    assert "M0-T2.md: status draft → approved" in out
    assert commits_since(gate, 2) == [f"{HUMAN}|gate(M0-T0): approve, next M0-T1",
                                      f"{HUMAN}|plan: approve M0-T2"]
    gate_trailers = gate.git("log", "-1", "--skip=1", "--format=%(trailers:only,unfold)")
    assert gate_trailers == ("Actor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: M0-T1\n"
                             "Review: M0-T0_gate-01")
    assert gate.trailers() == "Actor: human\nApprove: M0-T2"
    assert gate.git("tag", "--points-at", "HEAD~1") == "gate/M0-T0"
    review = gate.read(GATE)
    assert "status: answered" in review and "verdict: approve" in review and "source: document" in review
    assert "### 판정\napprove\n" in review and "### 다음 task 승인\nM0-T1, M0-T2\n" in review
    assert gate.git("status", "--porcelain") == ""
    assert "다음 세션 시작 때 에이전트가 자동으로 반영합니다" in out


def test_preview_matches_what_the_agent_applies(gate, keys):
    """미리보기에 나온 변화가 실제 반영 결과와 같다 (같은 도구가 계산하므로)."""
    keys(ENTER, DOWN, SPACE, ENTER, ENTER, ENTER)
    assert gate.lg("answer").exit_code == 0
    gate.commit_apply(gate.apply())
    gate.commit_apply(gate.apply())
    assert gate.status(CARD0) == "closed" and gate.status(MILESTONE0) == "active"
    assert gate.status("plan/milestones/M0/tasks/M0-T1.md") == "approved"
    assert gate.status("plan/milestones/M0/tasks/M0-T2.md") == "approved"
    assert gate.status("reviews/closed/M0-T0_gate-01.md") == "closed"
    assert gate.apply("--check").stdout == ""


def test_revise_requires_comment(gate, keys):
    # revise → 빈 코멘트는 거부되고 다시 입력 → 커밋
    keys(DOWN, ENTER, ENTER, "결과 표를 다시\r", ENTER)
    result = gate.lg("answer")
    assert result.exit_code == 0, result.output
    assert gate.last_commit() == f"{HUMAN}|gate(M0-T0): revise"
    assert "Next" not in gate.trailers()
    assert "### 코멘트\n결과 표를 다시\n" in gate.read(GATE)
    assert gate.git("tag") == ""


def test_last_task_asks_milestone_verdict(project, keys):
    project.approve_and_start()
    project.request_gate()
    # approve → (다음 후보 없음) 마일스톤 판정 go → 코멘트 없음 → 커밋
    keys(ENTER, DOWN, ENTER, ENTER, ENTER)
    result = project.lg("answer", "M0-T0_gate-01")
    assert result.exit_code == 0, result.output
    assert "Milestone-Verdict: go" in project.trailers() and "Next: none" in project.trailers()
    assert set(project.git("tag", "--points-at", "HEAD").split()) == {"gate/M0-T0", "milestone/M0-go"}
    assert "### 판정\napprove\n마일스톤 M0: go\n" in project.read(GATE)


def test_decisions_are_confirmed_with_text(gate, keys):
    gate.add_decision("D0.1")
    gate.agent("propose(D0.1): core\n\nActor: agent", "decisions")
    # approve → 다음 task 그대로(M0-T1) → 결정 D0.1 선택 → 확정 내용 → 코멘트 → 커밋
    keys(ENTER, ENTER, SPACE, ENTER, "Mamba-2로\r", ENTER, ENTER)
    result = gate.lg("answer")
    assert result.exit_code == 0, result.output
    assert "Decisions: D0.1" in gate.trailers()
    assert "### 확정 결정\n- D0.1: Mamba-2로\n" in gate.read(GATE)


def test_edited_response_is_rechecked(gate, keys, monkeypatch):
    edits = iter([
        "## 응답\n\n### 판정\nrevise\n\n### 코멘트\n없음\n\n### 확정 결정\n없음\n\n### 다음 task 승인\nM0-T1\n",
        "## 응답\n\n### 판정\napprove\n\n### 코멘트\n잘했다\n\n### 확정 결정\n없음\n\n### 다음 task 승인\nM0-T1\n",
    ])
    monkeypatch.setattr(commit_module, "_edit", lambda project, text: next(edits))
    # approve → M0-T1 → 코멘트 없음 → 편집(판정을 바꿈: 거부) → 편집 → 커밋
    keys(ENTER, ENTER, ENTER, DOWN, ENTER, ENTER, ENTER, ENTER)
    result = gate.lg("answer")
    assert result.exit_code == 0, result.output
    assert "판정(revise)이 고른 판정(approve)과 다릅니다" in result.output
    assert "### 코멘트\n잘했다\n" in gate.read(GATE)


def test_cancel_changes_nothing(gate, keys):
    keys(ENTER, ENTER, ENTER, DOWN, DOWN, ENTER)  # … → 취소
    head = gate.git("rev-parse", "HEAD")
    result = gate.lg("answer")
    assert result.exit_code == 130 and "아무것도 바꾸지 않았습니다" in result.output
    assert gate.git("rev-parse", "HEAD") == head and gate.git("status", "--porcelain") == ""


def test_unappliable_judgement_stops_before_writing(project, keys):
    """카드가 in-review가 아닌데 요청서만 있으면, 미리보기가 반영할 수 없다고 하고 아무것도 쓰지 않는다."""
    project.request_gate(commit=False)
    project.set_status(CARD0, "in-progress")
    project.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD0, GATE)
    keys(ENTER, ENTER, ENTER)
    result = project.lg("answer")
    assert result.exit_code == 3 and "반영할 수 없습니다" in result.output
    assert project.git("status", "--porcelain") == ""


# ---------------------------------------------------------------- escalation


@pytest.fixture
def esc(project):
    project.approve_and_start()
    project.escalate(options=("A안: 작게", "B안: 크게"))
    return project


def test_escalation_choice_becomes_respond(esc, keys):
    # 선택 B안 → 코멘트 없음 → 요약(기본값: 선택) → 커밋
    keys(DOWN, ENTER, ENTER, ENTER, ENTER)
    result = esc.lg("answer")
    assert result.exit_code == 0, result.output
    assert esc.last_commit() == f"{HUMAN}|respond(M0-T0): B안: 크게"
    assert esc.trailers() == "Actor: human\nTask: M0-T0\nSource: document\nReview: M0-T0_esc-01"
    review = esc.read("reviews/open/M0-T0_esc-01.md")
    assert "### 판정\nB안: 크게\n" in review and "verdict: null" in review
    assert "plan/milestones/M0/tasks/M0-T0.md: status blocked → in-progress" in result.output


def test_escalation_decision_adds_decide_commit(esc, keys):
    esc.add_decision("D0.1")
    esc.agent("propose(D0.1): core\n\nActor: agent", "decisions")
    # A안 → D0.1 선택 → 확정 내용 → 코멘트 → 요약 → 커밋 (2개)
    keys(ENTER, SPACE, ENTER, "작게 간다\r", ENTER, ENTER, ENTER)
    result = esc.lg("answer")
    assert result.exit_code == 0, result.output
    assert commits_since(esc, 2) == [f"{HUMAN}|respond(M0-T0): A안: 작게", f"{HUMAN}|decide(D0.1): confirm"]
    assert esc.trailers() == "Actor: human\nDecisions: D0.1\nSource: document"


# ---------------------------------------------------------------- 전제 (§24.4.1)


def test_requires_terminal(gate):
    result = gate.lg("answer")
    assert result.exit_code == 2 and "터미널에서 직접" in result.output


def test_nothing_to_answer(project, tty):
    result = project.lg("answer")
    assert result.exit_code == 3 and "기다리는 review가 없습니다" in result.output


def test_unknown_review_id(gate, tty):
    result = gate.lg("answer", "M9-T9_gate-01")
    assert result.exit_code == 3 and "열린 review: M0-T0_gate-01" in result.output


def test_pending_draft_blocks(gate, tty):
    gate.write(".lg/pending/COMMIT_MSG", "exp: x\n\nActor: human\n")
    result = gate.lg("answer")
    assert result.exit_code == 3 and "lg commit" in result.output


def test_human_editing_review_is_not_overwritten(gate, tty):
    gate.write(GATE, gate.read(GATE) + "\n내가 쓰는 중\n")
    result = gate.lg("answer")
    assert result.exit_code == 3 and "덮어쓰지 않습니다" in result.output
    assert gate.read(GATE).endswith("내가 쓰는 중\n")


def test_other_staged_changes_block(gate, tty):
    gate.write("notes/a.md")
    gate.git("add", "notes/a.md")
    result = gate.lg("answer")
    assert result.exit_code == 2 and "notes/a.md" in result.output


# ---------------------------------------------------------------- spec_version 4 프로젝트 (미리보기 없음)


def test_spec4_project_answers_without_preview(tmp_path, git_sandbox, old_sources, keys):
    old = make_old(tmp_path, git_sandbox, old_sources, 4)
    old.approve_and_start()
    old.request_gate()
    keys(ENTER, ENTER, ENTER, ENTER)  # approve → 마일스톤 판정 하지 않음 → 코멘트 → 커밋
    result = old.lg("answer")
    assert result.exit_code == 0, result.output
    assert "spec_version 5 이상에서 됩니다" in result.output
    assert old.last_commit() == f"{HUMAN}|gate(M0-T0): approve"
