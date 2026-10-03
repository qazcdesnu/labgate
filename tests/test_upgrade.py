"""`lg upgrade` (설계 문서 §22).

옛 spec_version의 프로젝트는 그 버전을 만든 릴리즈 tag의 labgate로 실제로 만든다(v0.2.1 → 2, v0.3.0 → 3).
tag가 없는 환경(얕은 클론, 소스 배포판)에서는 그 테스트를 건너뛴다.
"""
import shutil
import subprocess
import sys
import tarfile

import pytest
import yaml
from typer.testing import CliRunner

from conftest import ROOT, isolated_git_env
from labgate import SPEC_VERSION, kinds
from labgate.cli import app
from labgate.plan import build_plan
from labgate.config import parse_config
from labgate.upgrade import MIGRATIONS, load_hashes

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")

TAGS = {2: "v0.2.1", 3: "v0.3.0"}
CONFIG = {
    "schema_version": 1,
    "project": {"name": "Upgrade test", "slug": "utest", "summary": "s", "research_question": "q?"},
    "people": {"humans": [{"name": "H", "email": "h@x.com"}]},
    "milestones": [{"title": "기반"}, {"title": "검증"}],
}


def has_tag(tag):
    return subprocess.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=ROOT,
                          capture_output=True).returncode == 0


def lg(*args):
    return CliRunner().invoke(app, [str(a) for a in args], catch_exceptions=False)


@pytest.fixture(scope="session")
def old_sources(tmp_path_factory):
    """tag별 src/labgate를 꺼낸 폴더 (없으면 None)."""
    out = {}
    for spec, tag in TAGS.items():
        if not has_tag(tag):
            out[spec] = None
            continue
        dest = tmp_path_factory.mktemp(f"src{spec}")
        archive = dest / "src.tar"
        subprocess.run(["git", "archive", "-o", str(archive), tag, "src/labgate"], cwd=ROOT, check=True)
        with tarfile.open(archive) as tar:
            tar.extractall(dest, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        out[spec] = dest / "src"
    return out


class Proj:
    def __init__(self, root, env):
        self.root, self.env = root, env

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True,
                              text=True, check=True).stdout.strip()

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        (self.root / rel).write_text(text, encoding="utf-8")

    def commit(self, message="spec: x\n\nActor: human"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def yaml(self):
        return yaml.safe_load(self.read(".lg/project.yaml"))


def make_old(tmp_path, git_sandbox, sources, spec, claude_code=True):
    """옛 labgate로 프로젝트를 만든다."""
    src = sources[spec]
    if src is None:
        pytest.skip(f"tag {TAGS[spec]} 없음")
    cfg = tmp_path / "cfg.yaml"
    data = dict(CONFIG, agent_tools={"claude_code": claude_code})
    cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    root = tmp_path / f"old{spec}"
    code = f"import sys; sys.path.insert(0, {str(src)!r}); from labgate.cli import app; app()"
    result = subprocess.run([sys.executable, "-c", code, "init", str(root), "--config", str(cfg)],
                            env=git_sandbox, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    p = Proj(root, git_sandbox)
    assert p.yaml()["generated"]["spec_version"] == spec
    return p


def fresh(tmp_path, claude_code=True):
    """현재 labgate가 같은 설정으로 만드는 파일 {경로: (내용, 권한)}."""
    data = dict(CONFIG, agent_tools={"claude_code": claude_code})
    import datetime
    return {str(f.path): (f.content, f.mode) for f in build_plan(parse_config(data), datetime.date.today().isoformat())}


def run_upgrade(p, *args):
    import os
    cwd = os.getcwd()
    os.chdir(p.root)
    try:
        return lg("upgrade", *args)
    finally:
        os.chdir(cwd)


# ---------------------------------------------------------------- 해시표와 분류


@pytest.mark.parametrize("spec", sorted(TAGS))
def test_hash_tables_match_release_tags(spec):
    """§22.4.3: 저장된 해시표가 그 tag의 템플릿에서 다시 만든 것과 같다."""
    if not has_tag(TAGS[spec]):
        pytest.skip(f"tag {TAGS[spec]} 없음")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/hash-templates.py"), TAGS[spec], str(spec), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_current_templates_frozen_if_released():
    """§22.2.2 규칙 2: 현재 spec_version이 릴리즈됐으면(해시표가 있으면) 템플릿이 그와 같다."""
    table = load_hashes(SPEC_VERSION)
    if table is None:
        pytest.skip(f"spec_version {SPEC_VERSION}는 아직 릴리즈 전 (해시표 없음)")
    for claude in (True, False):
        var = kinds.variant(claude)
        for path, (content, _) in fresh(None, claude).items():
            if kinds.classify(path) in (kinds.MANAGED, kinds.EDITABLE):
                assert kinds.digest(path, content) == table["files"][path][var], path


def test_every_generated_file_is_classified_and_none_lost():
    """모든 생성 파일에 분류가 있고, 지난 버전의 관리 문서가 소리 없이 사라지지 않는다."""
    current = set()
    for claude in (True, False):
        for path in fresh(None, claude):
            kind = kinds.classify(path)
            assert kind in (kinds.MANAGED, kinds.EDITABLE, kinds.GITIGNORE, kinds.RESEARCH, kinds.RECORD, kinds.OTHER)
            if kind in (kinds.MANAGED, kinds.EDITABLE):
                current.add(path)
    for spec in MIGRATIONS:
        assert set(load_hashes(spec)["files"]) <= current, spec


def test_normalize_and_carry_project_lines():
    a = "# x\n\n- 이름: A\n- 연구 질문: Q?\n- 에이전트 신원: a <a@x>\n"
    b = "# x\n\n- 이름: B\n- 연구 질문: R?\n- 에이전트 신원: b <b@x>\n"
    assert kinds.digest("AGENTS.md", a) == kinds.digest("AGENTS.md", b)
    assert kinds.digest("specs/README.md", "---\nupdated: 1\n---\n") == kinds.digest("specs/README.md", "---\nupdated: 2\n---\n")
    assert kinds.carry_project_lines("AGENTS.md", a, b + "추가\n") == a + "추가\n"


# ---------------------------------------------------------------- 갱신


@pytest.mark.parametrize("spec", sorted(TAGS))
@pytest.mark.parametrize("claude_code", [True, False])
def test_upgrade_old_project(tmp_path, git_sandbox, old_sources, spec, claude_code):
    p = make_old(tmp_path, git_sandbox, old_sources, spec, claude_code)
    result = run_upgrade(p)
    assert result.exit_code == 0, result.output
    expected = fresh(tmp_path, claude_code)
    for path, (content, mode) in expected.items():
        kind = kinds.classify(path)
        if kind in (kinds.MANAGED, kinds.EDITABLE, kinds.GITIGNORE):
            assert p.read(path) == content, path
            assert (p.root / path).stat().st_mode & 0o777 == mode, path
    for path in p.git("ls-files").splitlines():
        if path.endswith(".md") and p.read(path).startswith("---\n"):
            assert f"spec_version: {SPEC_VERSION}\n" in p.read(path) or "spec_version" not in p.read(path), path
    data = p.yaml()
    assert data["generated"]["spec_version"] == SPEC_VERSION
    assert data["upgrades"][-1]["from"] == spec and data["upgrades"][-1]["forced"] == []
    p.commit()  # hook을 통과한다
    assert run_upgrade(p).output.startswith(f"이미 spec_version {SPEC_VERSION}")


def test_human_edited_managed_fails_then_force(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("specs/workflow.md", p.read("specs/workflow.md") + "\n사람이 추가한 원칙\n")
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 3
    assert "specs/workflow.md" in result.output and "아무것도 바꾸지 않았습니다" in result.output
    assert p.git("status", "--porcelain") == ""
    assert "릴리즈된 spec_version 3과 다른 관리 문서" in result.output and "(지금 → 새 버전: +" in result.output
    diff = run_upgrade(p, "--diff")
    assert diff.exit_code == 0 and "-사람이 추가한 원칙" in diff.output and "--- specs/workflow.md (지금)" in diff.output
    assert p.git("status", "--porcelain") == ""
    result = run_upgrade(p, "--force")
    assert result.exit_code == 0, result.output
    assert "사람이 추가한 원칙" not in p.read("specs/workflow.md")
    assert "사람이 추가한 원칙" in p.read(".lg/pending/upgrade/specs/workflow.md")
    assert p.yaml()["upgrades"][-1]["forced"] == ["specs/workflow.md"]


def test_filled_stub_is_kept(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    stub = "specs/doc-types/catalog.spec.md"
    p.write(stub, p.read(stub).replace("status: stub", "status: complete") + "\n## 사람이 채운 내용\n")
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 0, result.output
    assert "사람이 채운 내용" in p.read(stub) and f"spec_version: {SPEC_VERSION}\n" in p.read(stub)
    assert "사람이 채운 것으로 봄" in result.output


def test_agents_project_lines_preserved(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 2)
    p.write("AGENTS.md", p.read("AGENTS.md").replace("- 이름: Upgrade test", "- 이름: 새 이름"))
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 0, result.output
    assert "- 이름: 새 이름\n" in p.read("AGENTS.md")


def test_gitignore_keeps_human_choices(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write(".gitignore", p.read(".gitignore").replace("wandb/\n", "") + "\n# 내 산출물\ncheckpoints/\n")
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 0, result.output
    text = p.read(".gitignore")
    assert text.startswith(kinds.BEGIN) and kinds.END in text
    assert "wandb/" not in text
    assert text.index("\ncheckpoints/\n") > text.index(kinds.END) and "# 내 산출물" in text
    assert "사람이 지운 labgate 줄은 다시 넣지 않았습니다: wandb/" in result.output
    # 다음 갱신의 기준: 관리 구역 안에 사람이 더한 줄은 밖으로 옮긴다 (§22.5.2)
    p.commit()


def test_research_doc_versions(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("notes/odd.md", '---\nspec_version: "3"\n---\n# x\n')
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 0, result.output
    assert "spec_version 형식이 아니라 그대로 두었습니다: notes/odd.md" in result.output
    assert p.read("notes/odd.md").startswith('---\nspec_version: "3"\n')
    assert p.read("STATUS.md").count(f"spec_version: {SPEC_VERSION}\n") == 1


def test_newer_research_doc_is_error(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("notes/new.md", "---\nspec_version: 99\n---\n")
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 2 and "notes/new.md" in result.output
    assert p.git("status", "--porcelain") == ""


def test_dry_run_changes_nothing(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    result = run_upgrade(p, "--dry-run")
    assert result.exit_code == 0 and "미리 보기" in result.output and "아무것도 바꾸지 않았습니다" in result.output
    assert p.git("status", "--porcelain") == ""


def test_requires_clean_tree_and_no_pending(tmp_path, git_sandbox, old_sources):
    p = make_old(tmp_path, git_sandbox, old_sources, 3)
    p.write("notes/wip.md", "x\n")
    assert run_upgrade(p).exit_code == 2
    (p.root / "notes/wip.md").unlink()
    (p.root / ".lg/pending").mkdir(exist_ok=True)
    p.write(".lg/pending/COMMIT_MSG", "x\n")
    result = run_upgrade(p)
    assert result.exit_code == 2 and "COMMIT_MSG" in result.output


def test_unsupported_source(tmp_path, git_sandbox, monkeypatch):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    root = tmp_path / "p"
    assert lg("init", root, "--config", cfg).exit_code == 0
    p = Proj(root, isolated_git_env(tmp_path))
    data = p.yaml()
    data["generated"]["spec_version"] = 1
    p.write(".lg/project.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    p.commit()
    result = run_upgrade(p)
    assert result.exit_code == 2 and "올릴 수 없습니다" in result.output
    # 해시표가 없는 spec_version (dev 버전으로 만든 프로젝트)
    monkeypatch.setitem(MIGRATIONS, 1, ())
    result = run_upgrade(p)
    assert result.exit_code == 2 and "해시표가 없습니다" in result.output


def test_already_latest(tmp_path, git_sandbox):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    root = tmp_path / "p"
    assert lg("init", root, "--config", cfg).exit_code == 0
    result = run_upgrade(Proj(root, git_sandbox))
    assert result.exit_code == 0 and result.output.startswith(f"이미 spec_version {SPEC_VERSION}")
