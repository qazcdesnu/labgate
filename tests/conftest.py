import copy
from pathlib import Path

import pytest

from labgate.config import parse_config

ROOT = Path(__file__).resolve().parent.parent

BASE = {
    "schema_version": 1,
    "project": {
        "name": "Capacity-Driven: \"Adaptive\" 분할",  # 따옴표·콜론·한글
        "slug": "cap-partition",
        "summary": "Fenwick 분할을 적응 분할로 대체하는 연구",
        "research_question": "같은 state 예산에서 recall이 개선되는가?",
    },
    "people": {"humans": [{"name": "홍길동", "email": "gildong@example.com"}]},
    "milestones": [
        {"title": "기반 구축: 재현"},
        {"title": "디텍터 신호 \"유효성\" 검증"},
        {"title": "Split-only 적응 분할"},
    ],
}


def make_config(milestones=3, claude_code=True):
    data = copy.deepcopy(BASE)
    data["agent_tools"] = {"claude_code": claude_code}
    data["milestones"] = [
        BASE["milestones"][i] if i < 3 else {"title": f"마일스톤 {i}"} for i in range(milestones)
    ]
    return parse_config(data)


@pytest.fixture
def config():
    return make_config()
