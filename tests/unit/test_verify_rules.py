"""`lg verify`의 판정 함수 (설계 문서 §23): 사람 몫의 전이, 근거, 요청서의 근거 경로."""
import pytest

from labgate import verify
from labgate.verify import human_transition, justifies


def test_transition_rules():
    assert human_transition("task-card", "draft", "in-progress")
    assert human_transition("task-card", "in-review", "closed")
    assert not human_transition("task-card", "approved", "in-progress")
    assert not human_transition("task-card", "in-progress", "in-review")
    assert human_transition("decision", "proposed", "confirmed")
    assert human_transition("milestone", "planned", "active")
    assert not human_transition("review", "open", "closed")
    assert justifies("task-card", "M0-T0", "approved", "plan", {"Approve": "M0-T0, M0-T1"})
    assert justifies("task-card", "M0-T1", "approved", "gate", {"Task": "M0-T0", "Next": "M0-T1"})
    assert justifies("task-card", "M0-T0", "revise", "gate", {"Task": "M0-T0", "Verdict": "revise"})
    assert not justifies("task-card", "M0-T0", "closed", "gate", {"Task": "M0-T0", "Verdict": "revise"})
    assert justifies("decision", "D0.1", "confirmed", "decide", {"Decisions": "D0.1"})
    assert justifies("milestone", "M0", "active", "gate", {"Task": "M0-T0", "Verdict": "approve"})


@pytest.mark.parametrize("token, expected", [
    ("plan/milestones/M0/tasks/M0-T1.md", "plan/milestones/M0/tasks/M0-T1.md"),
    ("references/library/", "references/library/"),
    ("M0-T5.md", "M0-T5.md"),
    ("results/M0/r.md#요약", "results/M0/r.md"),
    ("src/a.py:12-20", "src/a.py"),
    ("## Go / No-go 기준", None),
    ("D1.1", None),
    ("https://arxiv.org/abs/1", None),
    ("v0.4.1", None),
])
def test_evidence_path(token, expected):
    """요청서 근거 칸에서 경로가 아닌 것(섹션 인용, ID, URL)을 경로로 읽지 않는다."""
    assert verify._evidence_path(token) == expected


def test_evidence_bare_file_name_found_anywhere(tmp_path):
    (tmp_path / "plan" / "M0").mkdir(parents=True)
    (tmp_path / "plan" / "M0" / "M0-T5.md").write_text("x")
    assert verify._exists(tmp_path, "M0-T5.md")
    assert not verify._exists(tmp_path, "M0-T6.md")
