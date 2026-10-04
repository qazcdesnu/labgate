"""`lg answer`의 응답 만들기와 검사, 선택지 읽기, 커밋 메시지 (설계 문서 §24.4)."""
import re
from types import SimpleNamespace

import pytest

from labgate.answer import Answer, build_messages, check_response, parse_options, response_text
from labgate.state import Doc

REVIEW = Doc("reviews/open/M0-T0_gate-01.md", {"id": "M0-T0_gate-01"}, "")


def answer(**kw):
    return Answer(REVIEW, kw.pop("kind", "gate"), "M0-T0", **kw)


def fake_project(max_header=72):
    """build_messages가 쓰는 것만: hook의 MAX_HEADER."""
    return SimpleNamespace(hook={"MAX_HEADER": max_header, "TASK_ID_RE": re.compile(r"^M\d+-T\d+$")})


def test_response_has_every_subsection_in_order():
    text = response_text(answer(verdict="approve", next_tasks=["M0-T1", "M0-T2"], milestone_verdict=None,
                                decisions={"D0.1": "Mamba-2"}, comment="좋다"))
    assert text == ("## 응답\n\n### 판정\napprove\n\n### 코멘트\n좋다\n\n### 확정 결정\n- D0.1: Mamba-2\n\n"
                    "### 다음 task 승인\nM0-T1, M0-T2\n")


def test_empty_parts_say_none():
    text = response_text(answer(verdict="revise", comment="고쳐"))
    assert "### 확정 결정\n없음\n" in text and "### 다음 task 승인\n없음\n" in text


def test_check_response():
    ans = answer(verdict="approve")
    assert check_response(ans, response_text(ans)) == []
    assert any("다릅니다" in e for e in check_response(ans, response_text(ans).replace("approve", "revise")))
    assert any("비어 있습니다" in e for e in check_response(ans, response_text(ans).replace("approve\n", "")))
    assert any("하위 섹션이 없습니다: 코멘트" in e for e in check_response(ans, response_text(ans).replace("### 코멘트", "")))


@pytest.mark.parametrize("section, expected", [
    ("### A안: 작게\n\n설명\n\n### **B안**\n\n설명", ["A안: 작게", "B안"]),
    ("1. 첫째 안\n   자세히\n2. 둘째 안", ["첫째 안", "둘째 안"]),
    ("- **A**: 작게\n- B", ["A: 작게", "B"]),
    ("자유 서술만 있다.", []),
])
def test_parse_options(section, expected):
    assert parse_options(section) == expected


def test_gate_messages():
    first, plan = build_messages(fake_project(), answer(verdict="approve", next_tasks=["M0-T1", "M0-T2", "M0-T3"],
                                                        decisions={"D0.1": "x"}))
    assert first.startswith("gate(M0-T0): approve, next M0-T1\n\n")
    assert first.endswith("Next: M0-T1\nDecisions: D0.1\nReview: M0-T0_gate-01\n")
    assert plan == "plan: approve M0-T2, M0-T3\n\nActor: human\nApprove: M0-T2, M0-T3\n"


def test_gate_without_next_and_long_headers_shrink():
    (only,) = build_messages(fake_project(), answer(verdict="approve"))
    assert only.startswith("gate(M0-T0): approve\n") and "Next: none" in only
    _, plan = build_messages(fake_project(max_header=30), answer(verdict="approve", next_tasks=[f"M0-T{i}" for i in range(1, 9)]))
    assert plan.startswith("plan: approve 7 tasks after M0-T0 gate\n")
    (revise,) = build_messages(fake_project(), answer(verdict="revise", comment="x"))
    assert "Next" not in revise


def test_escalation_messages():
    respond, decide = build_messages(fake_project(), answer(kind="escalation", verdict="B안", summary="B안으로",
                                                            decisions={"D0.1": "x", "D1.1": "y"}))
    assert respond == ("respond(M0-T0): B안으로\n\nActor: human\nTask: M0-T0\nSource: document\n"
                       "Review: M0-T0_gate-01\n")
    assert decide.startswith("decide: confirm D0.1, D1.1\n\nM0-T0_gate-01 응답에서 확정.\n\n")
    assert decide.endswith("Decisions: D0.1, D1.1\nSource: document\n")
