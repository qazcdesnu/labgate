"""템플릿 원문(부록 A·B·C)이 설계 문서와 같고, 모든 조합에서 올바르게 렌더링되는지 검사한다."""
import copy
import importlib.util
import json
import re
import shutil
import subprocess
import zipfile
from importlib.resources import files

import pytest
import yaml

from conftest import BASE, ROOT, make_config
from labgate import SPEC_VERSION
from labgate.config import parse_config
from labgate.plan import build_plan
from labgate.render import base_context, milestone_context, read_static, render, stub_context
from labgate.stubs import STUBS

TEMPLATES = files("labgate").joinpath("templates")
JINJA = sorted(
    p.relative_to(ROOT / "src/labgate/templates/jinja").as_posix()
    for p in (ROOT / "src/labgate/templates/jinja").rglob("*.j2")
)
STATIC = sorted(
    p.relative_to(ROOT / "src/labgate/templates/static").as_posix()
    for p in (ROOT / "src/labgate/templates/static").rglob("*")
    if p.is_file()
)
PER_MILESTONE = {
    "plan/milestones/milestone.md.j2",
    "plan/milestones/tasks/T0.md.j2",
    "references/task-map.md.j2",
}
STUB_TEMPLATE = "specs/doc-types/_stub.spec.md.j2"
NO_FRONTMATTER = {"README.md.j2", "AGENTS.md.j2", "CLAUDE.md.j2"}  # conventions §4 예외


def load_sync_script():
    spec = importlib.util.spec_from_file_location("sync_templates", ROOT / "scripts/sync-templates.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_all(config):
    """{(템플릿, 변형): 결과}. 변형은 마일스톤 ID 또는 stub 이름."""
    base = base_context(config, "2026-10-01")
    out = {}
    for name in JINJA:
        if name in PER_MILESTONE:
            for i, m in enumerate(base["milestones"]):
                out[(name, m["id"])] = render(name, milestone_context(base, i))
        elif name == STUB_TEMPLATE:
            for stub in STUBS:
                out[(name, stub.name)] = render(name, stub_context(base, stub))
        else:
            out[(name, None)] = render(name, base)
    return out


def frontmatter(text):
    if not text.startswith("---\n"):
        return None
    end = text.index("\n---\n", 4)
    return yaml.safe_load(text[4:end])


SCENARIOS = {
    "M3-claude": dict(milestones=3, claude_code=True),
    "M1-noclaude": dict(milestones=1, claude_code=False),
    "M20-claude": dict(milestones=20, claude_code=True),
}


@pytest.fixture(scope="module", params=SCENARIOS, ids=list(SCENARIOS))
def rendered(request):
    return render_all(make_config(**SCENARIOS[request.param])), SCENARIOS[request.param]


# ---------------------------------------------------------------- 설계 문서와 일치


def test_templates_match_design_doc():
    sync = load_sync_script()
    assert sync.diff(sync.extract(sync.DOC.read_text(encoding="utf-8"))) == []


def test_stub_table_matches_design_doc():
    doc = (ROOT / "labgate-design.md").read_text(encoding="utf-8")
    section = doc[doc.index("## B.7") : doc.index("## B.8")]
    rows = re.findall(r"^\| `([\w-]+)` \| (.+?) \| (.+?) \| `(.+?)` \|$", section, re.M)
    assert [(s.name, s.title, s.purpose, s.location) for s in STUBS] == rows


def test_spec_index_lists_every_stub(config):
    index = render("specs/README.md.j2", base_context(config, "2026-10-01"))
    for stub in STUBS:
        assert f"[{stub.name}.spec.md](doc-types/{stub.name}.spec.md)" in index
        assert re.search(rf"^\| {re.escape(stub.name)} \|.*\| stub \|$", index, re.M), stub.name


# ---------------------------------------------------------------- 렌더링 결과


def test_every_template_renders_with_single_trailing_newline(rendered):
    for key, text in rendered[0].items():
        assert text.endswith("\n") and not text.endswith("\n\n"), key


def test_frontmatter_parses_and_has_common_fields(rendered):
    for (name, variant), text in rendered[0].items():
        fm = frontmatter(text)
        if name in NO_FRONTMATTER:
            assert fm is None, name
            continue
        assert isinstance(fm, dict), (name, variant)
        assert {"id", "type", "spec_version"} <= fm.keys(), (name, variant)
        assert fm["spec_version"] == SPEC_VERSION


def test_frontmatter_preserves_user_strings(rendered):
    results, scenario = rendered
    config = make_config(**scenario)
    for m in config.milestones:
        fm = frontmatter(results[("plan/milestones/milestone.md.j2", m.id)])
        assert fm["id"] == m.id and fm["title"] == m.title


def test_stub_frontmatter(rendered):
    for stub in STUBS:
        fm = frontmatter(rendered[0][(STUB_TEMPLATE, stub.name)])
        assert fm == {"id": stub.name, "type": "spec", "spec_version": SPEC_VERSION, "status": "stub"}


def test_tables_are_not_broken_by_conditionals(rendered):
    """`{% if %}` 줄이 표 중간에 빈 줄을 남기면 Markdown 표가 끊긴다."""
    for key, text in rendered[0].items():
        lines = text.splitlines()
        for i in range(1, len(lines) - 1):
            if lines[i] == "" and lines[i - 1].startswith("|") and lines[i + 1].startswith("|"):
                pytest.fail(f"{key}: {i + 1}행에서 표가 끊깁니다")


def test_claude_code_conditionals(rendered):
    results, scenario = rendered
    filemap, agents = results[("FILEMAP.md.j2", None)], results[("AGENTS.md.j2", None)]
    assert ("CLAUDE.md" in filemap) is scenario["claude_code"]
    assert ("`.claude/`" in filemap) is scenario["claude_code"]
    assert ("CLAUDE.md" in agents) is scenario["claude_code"]


def test_first_and_later_milestone_t0_differ(rendered):
    results, scenario = rendered
    first = results[("plan/milestones/tasks/T0.md.j2", "M0")]
    assert "`notes/`의 기존 계획 자료를" in first
    assert "이전 마일스톤 보고" not in first
    if scenario["milestones"] > 1:
        later = results[("plan/milestones/tasks/T0.md.j2", "M1")]
        assert "이전 마일스톤 보고: `results/M0/report.md`" in later
        assert "`notes/`의 기존 계획 자료를" not in later


def test_milestone_tables_list_every_milestone(rendered):
    results, scenario = rendered
    for name in ("FILEMAP.md.j2", "plan/roadmap.md.j2"):
        rows = re.findall(r"^\| `(M\d+)` \|", results[(name, None)], re.M)
        assert rows == [f"M{i}" for i in range(scenario["milestones"])], name


# ---------------------------------------------------------------- 정적 파일


def test_static_files_readable():
    assert len(STATIC) == 26
    for path in STATIC:
        text = read_static(path)
        assert text.endswith("\n") and not text.endswith("\n\n"), path
        assert "{{" not in text and "{%" not in text, path


def test_static_frontmatter():
    for path in STATIC:
        if path.startswith("specs/") and path.endswith(".md"):
            assert isinstance(frontmatter(read_static(path)), dict), path


def test_settings_json_valid():
    data = json.loads(read_static("dot-claude/settings.json"))
    deny = data["permissions"]["deny"]
    assert {"Bash(git commit *)", "Bash(git merge *)", "Bash(git cherry-pick *)"} <= set(deny)
    # 공동 작성자 줄 끄기: 빈 문자열(하위 호환). `false`는 v2.1.281 미만에서 파일 전체를 무시하게 한다
    assert data["attribution"] == {"commit": "", "pr": "", "sessionUrl": False}
    assert "includeCoAuthoredBy" not in data
    # §17.3: 에이전트는 lg commit을 실행하지 못하고, 세션 시작마다 session-check가 돈다
    assert "Bash(lg commit *)" in deny
    (group,) = data["hooks"]["SessionStart"]
    assert "matcher" not in group  # 시작·재개·/clear·compact 모두
    assert group["hooks"] == [{"type": "command", "command": '"$CLAUDE_PROJECT_DIR"/scripts/session-check'}]


@pytest.mark.parametrize("claude_code", [True, False])
def test_procedure_links_resolve(claude_code):
    """§16: AGENTS.md와 specs/README.md의 절차 링크가 모두 생성되는 절차 문서를 가리킨다."""
    files = {str(f.path): f.content for f in build_plan(make_config(claude_code=claude_code), "2026-10-01")}
    procedures = {p for p in files if p.startswith("specs/procedures/")}
    assert len(procedures) == 8
    agents = set(re.findall(r"\]\((specs/procedures/[\w-]+\.md)\)", files["AGENTS.md"]))
    index = {"specs/" + p for p in re.findall(r"\]\((procedures/[\w-]+\.md)\)", files["specs/README.md"])}
    assert agents == index == procedures
    for path in procedures:
        fm = frontmatter(files[path])
        assert fm == {"id": path.rsplit("/", 1)[1][:-3], "type": "procedure", "spec_version": SPEC_VERSION}
        body = files[path]
        assert "- 시작 조건:" in body and "- 푸는 일반 규칙:" in body and "- 끝나는 상태:" in body


def test_gitignore_excludes_claude_worktrees():
    assert ".claude/worktrees/" in read_static("dot-gitignore").splitlines()


def test_hook_is_valid_python():
    compile(read_static("dot-lg/hooks/commit-msg"), "commit-msg", "exec")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash 없음")
def test_agent_commit_is_valid_bash():
    subprocess.run(["bash", "-n"], input=read_static("scripts/agent-commit"), text=True, check=True)


# ---------------------------------------------------------------- 패키징


def test_wheel_contains_all_templates(tmp_path):
    hatch = pytest.importorskip("hatchling.builders.wheel")
    wheel = next(iter(hatch.WheelBuilder(str(ROOT)).build(directory=str(tmp_path), versions=["standard"])))
    names = set(zipfile.ZipFile(wheel).namelist())
    expected = {f"labgate/templates/jinja/{p}" for p in JINJA} | {
        f"labgate/templates/static/{p}" for p in STATIC
    }
    assert expected <= names, sorted(expected - names)


def test_user_input_with_template_like_braces_renders():
    """LaTeX(`x^{{2}}`)·BibTeX(`{{Transformer}}`)식 입력은 생성이 성공하고 출력에 그대로 들어간다 (§9)."""
    data = copy.deepcopy(BASE)
    data["project"]["name"] = "{{Transformer}} 분할 {% 연구"
    data["project"]["summary"] = "$O(n^{{2}})$ 를 줄인다"
    data["project"]["research_question"] = "{{BibTeX}} 와 $\\mathbf{{x}}$ 가 같은가?"
    data["people"]["humans"][0]["name"] = "{{홍}}"
    data["milestones"][0]["title"] = "{% raw %} 재현"
    results = render_all(parse_config(data))
    readme = results[("README.md.j2", None)]
    assert "# {{Transformer}} 분할 {% 연구" in readme
    assert "$O(n^{{2}})$ 를 줄인다" in readme
    fm = frontmatter(results[("plan/milestones/milestone.md.j2", "M0")])
    assert fm["title"] == "{% raw %} 재현"
