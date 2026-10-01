import copy

import pytest
import yaml

from labgate.config import (
    ConfigError,
    Email,
    Slug,
    check_value,
    dump_project_yaml,
    load_config,
    parse_config,
    suggest_slug,
)

VALID = {
    "schema_version": 1,
    "project": {
        "name": "Capacity-Driven Adaptive State Partitioning",
        "slug": "cap-partition",
        "summary": "Log-linear attention의 Fenwick 분할을 적응 분할로 대체하는 연구",
        "research_question": "같은 state 예산에서 capacity 기반 분할이 recall을 개선하는가?",
    },
    "people": {
        "humans": [{"name": "홍길동", "email": "gildong@example.com"}],
        "agent": {"name": "research-agent", "email": "agent@cap-partition.local"},
    },
    "agent_tools": {"claude_code": True},
    "milestones": [
        {"title": "기반 구축 및 재현"},
        {"title": "디텍터 신호 유효성 검증"},
        {"title": "Split-only 적응 분할"},
    ],
}


def cfg(**changes):
    """VALID를 복사하고 'a.b.c' 경로의 값을 바꾼다. 값이 DELETE면 키를 지운다."""
    data = copy.deepcopy(VALID)
    for path, value in changes.items():
        keys = path.split("__")
        node = data
        for k in keys[:-1]:
            node = node[int(k)] if isinstance(node, list) else node[k]
        last = keys[-1]
        if value is DELETE:
            del node[last]
        elif isinstance(node, list):
            node[int(last)] = value
        else:
            node[last] = value
    return data


DELETE = object()


def errors_of(data):
    with pytest.raises(ConfigError) as exc:
        parse_config(data)
    return exc.value.errors


# ---------------------------------------------------------------- 정상


def test_valid_config_loads(tmp_path):
    p = tmp_path / "cfg.yaml"
    p.write_text(yaml.safe_dump(VALID, allow_unicode=True), encoding="utf-8")
    c = load_config(p)
    assert c.project.slug == "cap-partition"
    assert [m.id for m in c.milestones] == ["M0", "M1", "M2"]
    assert c.agent_tools.claude_code is True


def test_agent_defaults():
    c = parse_config(cfg(people__agent=DELETE))
    assert c.agent.name == "research-agent"
    assert c.agent.email == "agent@cap-partition.local"


def test_agent_tools_default_true():
    c = parse_config(cfg(agent_tools=DELETE))
    assert c.agent_tools.claude_code is True


def test_emails_lowercased():
    data = cfg(people__humans__0__email="GilDong@Example.COM")
    data["people"]["agent"]["email"] = "Agent@X.Local"
    c = parse_config(data)
    assert c.humans[0].email == "gildong@example.com"
    assert c.agent.email == "agent@x.local"


def test_matching_milestone_ids_accepted():
    data = cfg()
    for i, m in enumerate(data["milestones"]):
        m["id"] = f"M{i}"
    assert [m.id for m in parse_config(data).milestones] == ["M0", "M1", "M2"]


def test_strings_are_stripped():
    c = parse_config(cfg(project__name="  이름  "))
    assert c.project.name == "이름"


# ---------------------------------------------------------------- 위반


@pytest.mark.parametrize(
    "changes, path",
    [
        ({"schema_version": 2}, "schema_version"),
        ({"project__name": ""}, "project.name"),
        ({"project__name": "x" * 101}, "project.name"),
        ({"project__name": "a\nb"}, "project.name"),
        ({"project__slug": "Cap"}, "project.slug"),
        ({"project__slug": "-cap"}, "project.slug"),
        ({"project__slug": "a" * 41}, "project.slug"),
        ({"project__summary": "x" * 201}, "project.summary"),
        ({"project__research_question": "x" * 501}, "project.research_question"),
        ({"project__research_question": DELETE}, "project.research_question"),
        ({"people__humans": []}, "people.humans"),
        ({"people__humans__0__name": "x" * 61}, "people.humans.0.name"),
        ({"people__humans__0__email": "no-at-sign"}, "people.humans.0.email"),
        ({"people__humans__0__email": "a b@x.com"}, "people.humans.0.email"),
        ({"people__agent__name": ""}, "people.agent.name"),
        ({"agent_tools__claude_code": "maybe"}, "agent_tools.claude_code"),
        ({"milestones": []}, "milestones"),
        ({"milestones": [{"title": f"m{i}"} for i in range(21)]}, "milestones"),
        ({"milestones__0__title": "x" * 81}, "milestones.0.title"),
        ({"project__unknown": 1}, "project.unknown"),
    ],
)
def test_rule_violation_reports_field_path(changes, path):
    errs = errors_of(cfg(**changes))
    assert any(e.startswith(f"{path}:") for e in errs), errs


def test_all_field_errors_collected_at_once():
    errs = errors_of(cfg(project__slug="BAD", people__humans__0__email="bad", milestones=[]))
    paths = {e.split(":")[0] for e in errs}
    assert {"project.slug", "people.humans.0.email", "milestones"} <= paths


def test_milestone_id_mismatch():
    data = cfg()
    data["milestones"][1]["id"] = "M5"
    errs = errors_of(data)
    assert any(e.startswith("milestones.1.id:") and "M1" in e for e in errs), errs


def test_duplicate_human_emails():
    data = cfg()
    data["people"]["humans"].append({"name": "둘", "email": "GILDONG@example.com"})
    errs = errors_of(data)
    assert any(e.startswith("people.humans.1.email:") for e in errs), errs


def test_agent_email_equal_to_human():
    errs = errors_of(cfg(people__agent__email="gildong@example.com"))
    assert any(e.startswith("people.agent.email:") for e in errs), errs


def test_top_level_must_be_mapping():
    assert errors_of(["a"])[0].startswith("(최상위)")


def test_yaml_syntax_error(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("project: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigError) as exc:
        load_config(p)
    assert "YAML" in exc.value.errors[0]


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "none.yaml")


# ---------------------------------------------------------------- 도우미


@pytest.mark.parametrize(
    "path, expected",
    [
        ("/x/cap-partition", "cap-partition"),
        ("/x/My Project_2", "my-project-2"),
        ("/x/연구", None),  # 결과가 '--'라 규칙 위반
        ("/x/" + "a" * 41, None),
    ],
)
def test_suggest_slug(path, expected):
    assert suggest_slug(path) == expected


def test_check_value():
    assert check_value(Email, " A@B.C ") == ("a@b.c", None)
    _, err = check_value(Slug, "Bad Slug")
    assert err and "하이픈" in err


def test_dump_project_yaml_roundtrip():
    c = parse_config(cfg(people__agent=DELETE))
    text = dump_project_yaml(c, "0.1.0", 1, "2026-10-01")
    data = yaml.safe_load(text)
    assert data["generated"] == {"labgate_version": "0.1.0", "spec_version": 1, "created": "2026-10-01"}
    assert data["people"]["agent"]["email"] == "agent@cap-partition.local"
    assert [m["id"] for m in data["milestones"]] == ["M0", "M1", "M2"]
    assert "홍길동" in text  # allow_unicode
    again = parse_config(data)
    assert again.model_dump() == c.model_dump() | {"generated": again.generated.model_dump()}


def test_cross_field_errors_reported_with_field_errors():
    data = cfg(project__slug="BAD")
    data["milestones"][0]["id"] = "M3"
    data["people"]["humans"].append({"name": "둘", "email": "gildong@example.com"})
    paths = {e.split(":")[0] for e in errors_of(data)}
    assert {"project.slug", "milestones.0.id", "people.humans.1.email"} <= paths


def test_default_agent_email_collision():
    errs = errors_of(cfg(people__agent=DELETE, people__humans__0__email="agent@cap-partition.local"))
    assert any(e.startswith("people.agent.email") for e in errs), errs


def test_error_messages_are_readable():
    errs = errors_of(cfg(project__name="x" * 101, project__slug="Cap X", milestones=[]))
    joined = "\n".join(errs)
    assert "100자 이하" in joined and "현재 101자" in joined
    assert "'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx…'" in joined  # 40자로 잘림
    assert "(입력값: 'Cap X')" in joined
    assert "milestones: 1개 이상" in joined
