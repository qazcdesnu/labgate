"""생성 파일의 분류와 비교 (`labgate.kinds`, 설계 문서 §22.3)."""
from labgate import kinds


def test_normalize_and_carry_project_lines():
    a = "# x\n\n- 이름: A\n- 연구 질문: Q?\n- 에이전트 신원: a <a@x>\n"
    b = "# x\n\n- 이름: B\n- 연구 질문: R?\n- 에이전트 신원: b <b@x>\n"
    assert kinds.digest("AGENTS.md", a) == kinds.digest("AGENTS.md", b)
    assert kinds.digest("specs/README.md", "---\nupdated: 1\n---\n") == kinds.digest("specs/README.md", "---\nupdated: 2\n---\n")
    assert kinds.carry_project_lines("AGENTS.md", a, b + "추가\n") == a + "추가\n"
