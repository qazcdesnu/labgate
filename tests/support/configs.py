"""설정 두 가지.

- `BASE`/`make_config`: 렌더링이 까다로운 값(따옴표, 콜론, 한글)을 담은 설정. 생성 내용을 검사하는
  unit·contract 계층이 쓴다. 파싱된 Config를 돌려준다.
- `project_config`: 실제 프로젝트를 만들어 쓰는 tools·commands 계층의 기본 설정(dict). 사람 `h@x.com`,
  마일스톤 둘(M0, M1). 에이전트 이메일은 `agent@<slug>.local`이므로 `Project.agent_email`로 읽는다.
"""
import copy

import yaml

from labgate.config import parse_config

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


HUMAN_NAME, HUMAN = "H", "h@x.com"
PROJECT_NAME, PROJECT_SLUG = "Test project", "ptest"


def project_config(claude_code=True, milestones=("기반", "검증")):
    return {
        "schema_version": 1,
        "project": {"name": PROJECT_NAME, "slug": PROJECT_SLUG, "summary": "s", "research_question": "q?"},
        "people": {"humans": [{"name": HUMAN_NAME, "email": HUMAN}]},
        "agent_tools": {"claude_code": claude_code},
        "milestones": [{"title": t} for t in milestones],
    }


def write_config(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path
