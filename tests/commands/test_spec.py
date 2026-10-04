"""`lg spec adopt` (설계 문서 §24.8): 사양 초안을 stub 사양에 합쳐 spec 커밋으로 확정한다."""
from support.cli import DOWN, ENTER
from support.configs import HUMAN

CATALOG = "specs/doc-types/catalog.spec.md"
DRAFT = "notes/spec-drafts/catalog.md"


def draft(*numbers, extra=""):
    return "# catalog 사양 초안\n\n" + "".join(f"## {n}. 절 {n}\n\n초안 {n}의 내용.\n\n" for n in numbers) + extra


def test_adopt_merges_numbered_sections(project, keys):
    project.write(DRAFT, draft(3, 4, 5, 6, 7))
    project.agent("propose: catalog spec draft\n\nActor: agent", "notes")
    keys(ENTER)  # 커밋
    result = project.lg("spec", "adopt", DRAFT)
    assert result.exit_code == 0, result.output
    spec = project.read(CATALOG)
    assert "status: complete" in spec and "(stub)" not in spec and "이 사양은 아직 공통 구조만" not in spec
    assert "## 1. 목적\n\n참고문헌마다" in spec            # 초안에 없는 절은 그대로
    assert "## 3. Frontmatter\n\n초안 3의 내용.\n" in spec  # 제목은 사양의 것, 내용은 초안의 것
    assert "> TODO" not in spec
    assert "| catalog |" in project.read("specs/README.md")
    assert [l for l in project.read("specs/README.md").splitlines() if l.startswith("| catalog |")][0].endswith("| complete |")
    assert project.last_commit() == f"{HUMAN}|spec: adopt catalog spec"
    assert project.git("log", "-1", "--format=%b").startswith(f"초안: {DRAFT}")
    assert project.git("status", "--porcelain") == ""
    assert "규칙 문서가 바뀌었습니다" in result.output
    assert "--- specs/doc-types/catalog.spec.md (지금)" in result.output  # 차이를 보여 준다


def test_adopt_several_and_name_from_frontmatter(project, keys):
    project.write("notes/a.md", "---\nid: decision\n---\n" + draft(3, 4, 5, 6, 7))
    project.write(DRAFT, draft(3, 4, 5, 6, 7))
    project.agent("propose: drafts\n\nActor: agent", "notes")
    keys(ENTER)
    result = project.lg("spec", "adopt", "notes/a.md", DRAFT)
    assert result.exit_code == 0, result.output
    assert project.last_commit() == f"{HUMAN}|spec: adopt decision, catalog specs"
    assert "status: complete" in project.read("specs/doc-types/decision.spec.md")


def test_todo_left_is_refused(project, tty):
    project.write(DRAFT, draft(3))
    result = project.lg("spec", "adopt", DRAFT)
    assert result.exit_code == 2 and "§4, §5, §6, §7" in result.output
    assert "status: stub" in project.read(CATALOG)


def test_unnumbered_section_is_refused(project, tty):
    project.write(DRAFT, draft(3, 4, 5, 6, 7, extra="## 메모\n\n어디로?\n"))
    result = project.lg("spec", "adopt", DRAFT)
    assert result.exit_code == 2 and "## 메모" in result.output


def test_unknown_name(project, tty):
    project.write("notes/other.md", draft(3))
    result = project.lg("spec", "adopt", "notes/other.md")
    assert result.exit_code == 2 and "stub 사양 이름이 아닙니다 (other)" in result.output
    project.write("notes/other.md", draft(3, 4, 5, 6, 7))
    assert project.lg("spec", "adopt", "notes/other.md", "--name", "catalog").exit_code == 130  # 이름을 주면 진행 (키 없음 → 중단)


def test_cancel_and_dirty_target(project, keys):
    project.write(DRAFT, draft(3, 4, 5, 6, 7))
    keys(DOWN, ENTER)  # 취소
    result = project.lg("spec", "adopt", DRAFT)
    assert result.exit_code == 130 and "status: stub" in project.read(CATALOG)
    project.write(CATALOG, project.read(CATALOG) + "\n사람이 고치는 중\n")
    result = project.lg("spec", "adopt", DRAFT)
    assert result.exit_code == 3 and "덮어쓰지 않습니다" in result.output


def test_requires_terminal(project):
    project.write(DRAFT, draft(3, 4, 5, 6, 7))
    result = project.lg("spec", "adopt", DRAFT)
    assert result.exit_code == 2 and "터미널에서 직접" in result.output
