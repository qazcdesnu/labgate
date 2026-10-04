"""생성 파일의 분류와 비교 (`labgate.kinds`, 설계 문서 §22.3)."""
from labgate import kinds


def test_normalize_and_carry_project_lines():
    a = "# x\n\n- 이름: A\n- 연구 질문: Q?\n- 에이전트 신원: a <a@x>\n"
    b = "# x\n\n- 이름: B\n- 연구 질문: R?\n- 에이전트 신원: b <b@x>\n"
    assert kinds.digest("AGENTS.md", a) == kinds.digest("AGENTS.md", b)
    assert kinds.digest("specs/README.md", "---\nupdated: 1\n---\n") == kinds.digest("specs/README.md", "---\nupdated: 2\n---\n")
    assert kinds.carry_project_lines("AGENTS.md", a, b + "추가\n") == a + "추가\n"


def test_variant_names():
    """연구는 spec_version 2부터 쓰던 이름 그대로 (옛 해시표와 맞아야 한다)."""
    assert kinds.variant(True) == "claude_code" and kinds.variant(False) == "no_claude_code"
    assert kinds.variant(True, "proposal") == "proposal_claude_code"


def test_proposal_question_line_is_normalized():
    a = "- 이름: A\n- 제안 핵심 질문: Q?\n"
    b = "- 이름: B\n- 제안 핵심 질문: R?\n"
    assert kinds.digest("AGENTS.md", a) == kinds.digest("AGENTS.md", b)
