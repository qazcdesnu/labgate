import pytest
import yaml

from labgate import SPEC_VERSION, __version__
from labgate.render import (
    RenderError,
    base_context,
    check_residue,
    milestone_context,
    render,
    stub_context,
    yq,
)
from labgate.stubs import STUBS


@pytest.mark.parametrize(
    "value",
    ['따옴표 "안" 과 \'홑\'', "콜론: 뒤 공백", "- 대시로 시작", "# 해시", "null", "true", "123", "역슬래시 \\ 끝"],
)
def test_yq_roundtrips_through_yaml(value):
    assert yaml.safe_load(f"title: {yq(value)}")["title"] == value


def test_yq_keeps_korean_readable():
    assert yq("한글") == '"한글"'


def test_strict_undefined_detects_missing_variable():
    with pytest.raises(RenderError, match="정의되지 않은 변수"):
        render("README.md.j2", {})


def test_missing_template():
    with pytest.raises(RenderError, match="템플릿이 없습니다"):
        render("nope.md.j2", {})


@pytest.mark.parametrize("text", ["a {{ b }}", "x\n{% if y %}"])
def test_residue_detected(text):
    with pytest.raises(RenderError, match="남아 있습니다"):
        check_residue("t", text)


def test_residue_reports_line():
    with pytest.raises(RenderError, match="2행"):
        check_residue("t", "ok\n{{ x")


def test_base_context(config):
    ctx = base_context(config, "2026-10-01")
    assert ctx["milestones"][1] == {"id": "M1", "index": 1, "title": config.milestones[1].title}
    assert ctx["agent"] == {"name": "research-agent", "email": "agent@cap-partition.local"}
    assert ctx["humans"] == [{"name": "홍길동", "email": "gildong@example.com"}]
    assert ctx["claude_code"] is True
    assert (ctx["labgate_version"], ctx["spec_version"]) == (__version__, SPEC_VERSION)


def test_milestone_context_prev(config):
    base = base_context(config, "2026-10-01")
    assert milestone_context(base, 0)["prev"] is None
    ctx = milestone_context(base, 2)
    assert ctx["m"]["id"] == "M2" and ctx["prev"]["id"] == "M1"


def test_stub_context(config):
    ctx = stub_context(base_context(config, "2026-10-01"), STUBS[0])
    assert ctx["stub"]["name"] == "roadmap"
