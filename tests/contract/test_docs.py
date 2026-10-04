"""명령 설명서(docs/cli/)가 코드와 어긋나지 않는지 검사한다 (v0.3 초안 §3.3)."""
import re
import runpy

import pytest
import typer.main

from labgate import errors
from labgate.cli import app

from support.env import ROOT
from support.markdown import section, table_column

DOCS = ROOT / "docs" / "cli"
STATIC = ROOT / "src" / "labgate" / "templates" / "static"
EXIT_CODES = {errors.EXIT_OK, errors.EXIT_ERROR, errors.EXIT_USAGE, errors.EXIT_TARGET,
              errors.EXIT_GIT, errors.EXIT_ABORT}

COMMANDS = typer.main.get_command(app).commands


def test_every_command_has_a_page_and_overview_row():
    overview = (DOCS / "README.md").read_text(encoding="utf-8")
    for name in COMMANDS:
        assert (DOCS / f"lg-{name}.md").exists(), name
        assert f"`lg {name}" in overview, name
    assert "`lg --version`" in overview


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_options_documented(name):
    """모든 옵션·인자가 '인자와 옵션' 표에 있고, 표에는 없는 옵션이 없다."""
    names = table_column(section((DOCS / f"lg-{name}.md").read_text(encoding="utf-8"), "인자와 옵션"))
    documented = {tok for cell in names for tok in re.findall(r"`([^`]+)`", cell)}
    actual = set()
    command = COMMANDS[name]
    params = [p for sub in getattr(command, "commands", {}).values() for p in sub.params] or command.params  # lg spec adopt
    for param in params:
        if param.param_type_name == "argument":
            actual.add(param.name.upper().rstrip("S") if param.nargs == -1 else param.name.upper())
        else:
            actual.update(o for o in param.opts + param.secondary_opts if o != "--help")
    assert documented == actual


@pytest.mark.parametrize("name", sorted(COMMANDS))
def test_exit_codes_documented(name):
    """명령이 쓰는 코드만 적는다. 공통 체계(README) 밖의 코드는 없고, 0·1·130은 모든 명령에 있다."""
    codes = {int(c) for c in table_column(section((DOCS / f"lg-{name}.md").read_text(encoding="utf-8"), "종료 코드"))}
    assert codes <= EXIT_CODES and {errors.EXIT_OK, errors.EXIT_ERROR, errors.EXIT_ABORT} <= codes


def test_overview_exit_codes_match_errors_module():
    codes = table_column(section((DOCS / "README.md").read_text(encoding="utf-8"), "공통 종료 코드"))
    assert {int(c) for c in codes} == EXIT_CODES


def test_hook_types_match_documentation():
    """project-scripts.md의 타입 표가 생성되는 hook의 상수와 같다."""
    hook = runpy.run_path(str(STATIC / "dot-lg" / "hooks" / "commit-msg"), run_name="labgate_hook")
    text = (DOCS / "project-scripts.md").read_text(encoding="utf-8")
    block = text[text.index("### 타입"): text.index("### Trailer")]
    rows = {r[0]: set(re.findall(r"`([a-z]+)`", r[1])) for r in
            ([c.strip() for c in l.strip("|").split("|")] for l in block.splitlines()[4:] if l.startswith("|"))}
    assert rows == {"사람 전용": hook["HUMAN_TYPES"], "에이전트 전용": hook["AGENT_TYPES"],
                    "공통": hook["COMMON_TYPES"]}
    required = {k: v for k, v in (
        (r[0].strip("`"), set(re.findall(r"`([a-z]+)`", r[1].split("(")[0])))
        for r in ([c.strip() for c in l.strip("|").split("|")]
                  for l in text[text.index("### Trailer"):].splitlines() if l.startswith("| `")))}
    assert required["Task"] == hook["TASK_REQUIRED"]
    assert required["Source"] == hook["SOURCE_REQUIRED"]


def test_agent_commit_rejected_options_documented():
    script = (STATIC / "scripts" / "agent-commit").read_text(encoding="utf-8")
    text = (DOCS / "project-scripts.md").read_text(encoding="utf-8")
    long_line = next(l for l in script.splitlines() if 'reject "$arg"' in l)
    long_opts = {o.strip() for o in long_line.split(")")[0].split("|") if not o.strip().endswith("*")}
    short_line = next(l for l in script.splitlines() if 'reject "-$c"' in l)
    short_opts = {"-" + c.strip() for c in short_line.split(")")[0].split("|")}
    assert long_opts == {"--no-verify", "--author", "--all"} and short_opts == {"-a", "-n"}
    for opt in long_opts | short_opts:
        assert f"`{opt}`" in text, opt


# ---------------------------------------------------------------- 사용자 작업 설명서 (docs/guide/)

GUIDE = ROOT / "docs" / "guide"
LINK_RE = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")


def test_guide_index_lists_every_page():
    index = (GUIDE / "README.md").read_text(encoding="utf-8")
    for page in GUIDE.glob("*.md"):
        if page.name != "README.md":
            assert f"]({page.name})" in index, page.name


@pytest.mark.parametrize("page", sorted(p.name for p in (ROOT / "docs").rglob("*.md")
                                        if p.parent.name in ("guide", "cli")))
def test_relative_links_resolve(page):
    """docs/cli·docs/guide 안의 상대 링크가 실제 파일을 가리킨다."""
    path = next(p for p in (ROOT / "docs").rglob(page) if p.parent.name in ("guide", "cli"))
    for target in LINK_RE.findall(path.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://")):
            continue
        assert (path.parent / target).exists(), f"{path.name}: {target}"


def test_guide_pages_follow_format():
    """작업 문서마다 같은 형식 (v0.3 초안 §4)."""
    for page in GUIDE.glob("*.md"):
        if page.name == "README.md":
            continue
        text = page.read_text(encoding="utf-8")
        assert "- 언제:" in text and "- 결과:" in text, page.name
        for heading in ("## 순서", "## 확인", "## 잘 안 될 때"):
            assert heading in text, (page.name, heading)


def test_every_project_script_documented():
    """생성되는 scripts/ 의 모든 스크립트가 명령 개요와 project-scripts.md에 있다."""
    overview = (DOCS / "README.md").read_text(encoding="utf-8")
    scripts_doc = (DOCS / "project-scripts.md").read_text(encoding="utf-8")
    for script in (STATIC / "scripts").iterdir():
        assert f"`scripts/{script.name}`" in overview, script.name
        assert f"\n## scripts/{script.name}\n" in scripts_doc, script.name


def test_hook_trailers_documented():
    """hook이 형식을 검사하는 trailer가 project-scripts.md의 Trailer 표에 모두 있다."""
    hook = (STATIC / "dot-lg" / "hooks" / "commit-msg").read_text(encoding="utf-8")
    checked = set(re.findall(r'check_list\(trailers, "([A-Za-z-]+)"', hook))
    text = (DOCS / "project-scripts.md").read_text(encoding="utf-8")
    for key in checked:
        assert f"| `{key}` |" in text, key
