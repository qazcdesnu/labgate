"""`lg verify`와 `lg commit`의 gate 검사 (설계 문서 §23)."""
import os
import re
import shutil
import subprocess

import pytest
import yaml
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import labgate.commit as commit_module
import labgate.prompts as prompts
from conftest import ROOT
from labgate.cli import app
from labgate import verify
from labgate.verify import human_transition, justifies, project_rules

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")

CONFIG = {
    "schema_version": 1,
    "project": {"name": "Verify test", "slug": "vtest", "summary": "s", "research_question": "q?"},
    "people": {"humans": [{"name": "H", "email": "h@x.com"}]},
    "milestones": [{"title": "기반"}],
}
CARD = "plan/milestones/M0/tasks/M0-T0.md"


def lg(*args):
    return CliRunner().invoke(app, [str(a) for a in args], catch_exceptions=False)


class P:
    def __init__(self, root, env):
        self.root, self.env = root, env

    def run(self, *args):
        return subprocess.run(list(args), cwd=self.root, env=self.env, capture_output=True, text=True, check=True)

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def status(self, rel, value):
        self.write(rel, re.sub(r"^status: *\S+", f"status: {value}", self.read(rel), count=1, flags=re.M))

    def human(self, message, *, no_verify=False):
        self.run("git", "add", "-A")
        self.run("git", "commit", "-q", "--allow-empty", *(["--no-verify"] if no_verify else []), "-m", message)
        return self.run("git", "rev-parse", "HEAD").stdout.strip()

    def agent(self, message, *paths, no_verify=False):
        self.run("git", "add", "-A", "--", *paths) if paths else None
        env_args = ["-c", "user.name=research-agent", "-c", "user.email=agent@vtest.local"]
        if no_verify:  # hook을 우회한 커밋 (agent-commit은 이를 막으므로 git으로 직접)
            self.run("git", *env_args, "commit", "-q", "--allow-empty", "--no-verify", "-m", message)
        else:
            self.run(str(self.root / "scripts/agent-commit"), "-q", "--allow-empty", "-m", message)
        return self.run("git", "rev-parse", "HEAD").stdout.strip()

    def verify(self, *args):
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            return lg("verify", *args)
        finally:
            os.chdir(cwd)


@pytest.fixture
def p(tmp_path, git_sandbox):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    root = tmp_path / "proj"
    assert lg("init", root, "--config", cfg).exit_code == 0
    return P(root, git_sandbox)


def approve_and_start(p):
    """정상 흐름: 사람 승인 → 반영 도구 → 착수."""
    p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    out = p.run("python3", "scripts/apply-human-commits").stdout
    command = re.search(r"^커밋: (scripts/agent-commit [^(]+?)\s*(\(|$)", out, re.M).group(1)
    p.run("bash", "-c", command)
    p.status(CARD, "in-progress")
    p.agent("task(M0-T0): start\n\nActor: agent\nTask: M0-T0", CARD)


# ---------------------------------------------------------------- 판정 함수


def test_transition_rules():
    assert human_transition("task-card", "draft", "in-progress")
    assert human_transition("task-card", "in-review", "closed")
    assert not human_transition("task-card", "approved", "in-progress")
    assert not human_transition("task-card", "in-progress", "in-review")
    assert human_transition("decision", "proposed", "confirmed")
    assert human_transition("milestone", "planned", "active")
    assert not human_transition("review", "open", "closed")
    assert justifies("task-card", "M0-T0", "approved", "plan", {"Approve": "M0-T0, M0-T1"})
    assert justifies("task-card", "M0-T1", "approved", "gate", {"Task": "M0-T0", "Next": "M0-T1"})
    assert justifies("task-card", "M0-T0", "revise", "gate", {"Task": "M0-T0", "Verdict": "revise"})
    assert not justifies("task-card", "M0-T0", "closed", "gate", {"Task": "M0-T0", "Verdict": "revise"})
    assert justifies("decision", "D0.1", "confirmed", "decide", {"Decisions": "D0.1"})
    assert justifies("milestone", "M0", "active", "gate", {"Task": "M0-T0", "Verdict": "approve"})


def test_rules_read_from_project_specs(p):
    rules = project_rules(p.root)
    assert {"task-card", "review", "spec", "procedure", "filemap"} <= rules["types"]
    assert rules["statuses"]["task-card"] >= {"draft", "approved", "in-progress", "closed"}
    assert "budget" in rules["required"]["task-card"] and "verdict" in rules["required"]["review"]


# ---------------------------------------------------------------- 정상 흐름


def test_normal_flow_has_no_violations(p):
    approve_and_start(p)
    result = p.verify()
    assert result.exit_code == 0, result.output
    assert "위반 없음." in result.output


def test_refs_basis_v02_style_is_accepted(p):
    """v0.2 방식: 에이전트가 판단으로 draft → in-progress, 근거를 Refs로 남김."""
    sha = p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    p.status(CARD, "in-progress")
    p.agent(f"task(M0-T0): start\n\nActor: agent\nTask: M0-T0\nRefs: {sha[:7]}", CARD)
    result = p.verify()
    assert "✓ V2" in result.output, result.output


# ---------------------------------------------------------------- 위반 검출


def test_v1_bypassed_hook(p):
    p.agent("gate(M0-T0): approve\n\nActor: agent\nTask: M0-T0\nVerdict: approve\nSource: document", no_verify=True)
    result = p.verify()
    assert result.exit_code == 3
    assert "✗ V1" in result.output and "사람 전용 타입" in result.output


def test_v1_unregistered_author(p):
    p.run("git", "-c", "user.email=z@y.com", "commit", "-q", "--allow-empty", "--no-verify", "-m", "chore: x\n\nActor: human")
    assert "등록되지 않은 작성자 <z@y.com>" in p.verify().output


def test_v2_unjustified_transition(p):
    p.status(CARD, "approved")
    sha = p.agent("task(M0-T0): self approve\n\nActor: agent\nTask: M0-T0", CARD)
    result = p.verify()
    assert result.exit_code == 3
    assert f"✗ V2" in result.output and sha[:7] in result.output and "draft → approved" in result.output


def test_v2_wrong_basis(p):
    """근거가 있어도 그 전이를 정하지 않으면 위반 (revise 판정인데 closed로 바꿈)."""
    p.status(CARD, "in-review")
    p.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD)
    sha = p.human("gate(M0-T0): revise\n\nActor: human\nTask: M0-T0\nVerdict: revise\nSource: document")
    p.status(CARD, "closed")
    p.agent(f"log(M0-T0): apply gate {sha[:7]}\n\nActor: agent\nApplies: {sha[:7]}", CARD)
    result = p.verify()
    assert "in-review → closed" in result.output and sha[:7] in result.output


def test_v3_agent_writes_response(p):
    review = "reviews/open/M0-T0_gate-01.md"
    p.write(review, "---\nid: M0-T0_gate-01\n---\n# r\n\n## 응답\n\n")
    p.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", review)
    p.write(review, p.read(review) + "승인합니다.\n")
    p.agent("log(M0-T0): note\n\nActor: agent", review)
    result = p.verify()
    assert "✗ V3" in result.output and "## 응답 이 바뀜" in result.output


def test_v3_follows_rename_without_change(p):
    """반영 도구가 review를 closed/로 옮기는 것은 응답을 바꾸지 않는다."""
    review = "reviews/open/M0-T0_gate-01.md"
    p.write(review, "---\nid: M0-T0_gate-01\nstatus: answered\n---\n# r\n\n## 응답\n\n승인\n")
    p.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none")
    p.run("git", "mv", review, "reviews/closed/M0-T0_gate-01.md")
    p.agent("log(M0-T0): close review\n\nActor: agent")
    assert "✓ V3" in p.verify().output


def test_v4_agent_edits_rules(p):
    p.write("specs/workflow.md", p.read("specs/workflow.md") + "\n추가\n")
    p.agent("chore: tweak workflow\n\nActor: agent\nTask: M0-T0", "specs/workflow.md")
    result = p.verify()
    assert "✗ V4" in result.output and "specs/workflow.md" in result.output
    assert "카드 M0-T0 범위 › 포함" in result.output  # 범위 원문을 함께 보여 준다


def test_v4_human_spec_commit_is_fine(p):
    p.write("specs/workflow.md", p.read("specs/workflow.md") + "\n추가\n")
    p.human("spec: tweak workflow\n\nActor: human")
    assert "✓ V4" in p.verify().output


def test_v5_document_format(p):
    p.write("notes/bad.md", "---\ntype: task-card\nid: X\nstatus: maybe\n---\n")
    p.write("notes/broken.md", "---\nkey: [unclosed\n---\n")
    p.human("chore: notes\n\nActor: human")
    out = p.verify().output
    assert "notes/bad.md: task-card 상태값이 아님 (maybe)" in out
    assert "notes/bad.md: 필수 필드 없음 (budget)" in out
    assert "notes/bad.md: id(X)가 파일 이름과 다름" in out
    assert "notes/broken.md: frontmatter를 YAML로 읽을 수 없음" in out


# ---------------------------------------------------------------- 범위


def test_default_range_since_last_gate_tag(p):
    p.status(CARD, "approved")
    p.agent("task(M0-T0): self approve\n\nActor: agent\nTask: M0-T0", CARD)  # 위반
    p.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none")
    p.run("git", "tag", "gate/M0-T0")
    assert "✓ V2" in p.verify().output                       # 게이트 이후만
    assert "✗ V2" in p.verify("--all").output


def test_task_scope_and_checklist(p):
    approve_and_start(p)
    p.write("notes/other.md", "x\n")
    p.agent("log: unrelated\n\nActor: agent", "notes/other.md")
    result = p.verify("--task", "M0-T0")
    assert "task M0-T0, 커밋 3개" in result.output  # 승인, 반영, 착수. init과 무관한 커밋은 제외
    assert "완료 기준: 0/" in result.output


def test_range_options_are_exclusive(p):
    result = p.verify("--all", "--task", "M0-T0")
    assert result.exit_code == 2


# ---------------------------------------------------------------- lg commit 연결


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setattr(commit_module, "is_tty", lambda: True)
    with create_pipe_input() as pipe:
        monkeypatch.setattr(prompts, "IO", {"input": pipe, "output": DummyOutput()})

        def send(*parts):
            pipe.send_text("".join(parts))
            pipe.pipe.close_write()

        yield send


def commit_in(p, *args):
    cwd = os.getcwd()
    os.chdir(p.root)
    try:
        return lg("commit", *args)
    finally:
        os.chdir(cwd)


def gate_draft(p):
    """사람 커밋 대기 상태의 gate 초안 (에이전트가 lg draft로 만든 것과 같다)."""
    p.write("reviews/open/M0-T0_gate-01.md", "x\n")
    p.run("git", "add", "reviews")
    p.write(".lg/pending/COMMIT_MSG",
            "gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\n")


def test_commit_gate_shows_violations_but_does_not_block(p, keys):
    p.status(CARD, "in-review")
    p.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD)  # draft → in-review: 근거 없음
    gate_draft(p)
    keys("\r")  # 첫 선택지: 커밋 (위반 1건 있음)
    result = commit_in(p)
    assert result.exit_code == 0, result.output
    assert "✗ lg verify --task M0-T0: 위반 1건" in result.output
    assert "자세히: lg verify --task M0-T0" in result.output


def test_commit_gate_clean_one_line(p, keys):
    approve_and_start(p)
    p.status(CARD, "in-review")
    p.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD)
    gate_draft(p)
    keys("\r")
    result = commit_in(p)
    assert result.exit_code == 0, result.output
    assert "✓ lg verify --task M0-T0: 위반 없음" in result.output


def test_commit_non_gate_does_not_verify(p, keys):
    p.write("a.py", "x\n")
    p.run("git", "add", "a.py")
    p.write(".lg/pending/COMMIT_MSG", "exp: a\n\nActor: human\n")
    keys("\r")
    result = commit_in(p)
    assert result.exit_code == 0 and "lg verify" not in result.output


# ---------------------------------------------------------------- 옛 spec_version 프로젝트 (tag로 생성)

from test_upgrade import make_old, old_sources  # noqa: E402,F401  (fixture 재사용)


@pytest.mark.parametrize("spec", [2, 3])
def test_old_projects_rules_and_clean_run(tmp_path, git_sandbox, old_sources, spec):  # noqa: F811
    old = make_old(tmp_path, git_sandbox, old_sources, spec)
    rules = project_rules(old.root)
    assert rules["statuses"]["task-card"] >= {"draft", "approved", "closed"}
    assert "budget" in rules["required"]["task-card"]
    cwd = os.getcwd()
    os.chdir(old.root)
    try:
        result = lg("verify")
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0, result.output


def test_rules_match_agents_md():
    """§23.3: verify의 G4 전이와 G7 보호 경로가 현재 AGENTS.md의 G4·G7과 같은 내용이다."""
    from labgate.plan import build_plan
    from labgate.config import parse_config
    from labgate.verify import PROTECTED
    agents = {str(f.path): f.content for f in build_plan(parse_config(dict(CONFIG, agent_tools={"claude_code": True})),
                                                          "2026-01-01")}["AGENTS.md"]
    g4 = next(l for l in agents.splitlines() if l.startswith("- **G4.**"))
    g7 = next(l for l in agents.splitlines() if l.startswith("- **G7.**"))
    for path in PROTECTED:
        assert f"`{path}`" in g7, path
    for transition in ("`draft → approved`", "`in-review → closed | revise | redirected`", "`→ confirmed`",
                       "`planned → active → closed`"):
        assert transition in g4, transition


@pytest.mark.parametrize("token, expected", [
    ("plan/milestones/M0/tasks/M0-T1.md", "plan/milestones/M0/tasks/M0-T1.md"),
    ("references/library/", "references/library/"),
    ("M0-T5.md", "M0-T5.md"),
    ("results/M0/r.md#요약", "results/M0/r.md"),
    ("src/a.py:12-20", "src/a.py"),
    ("## Go / No-go 기준", None),
    ("D1.1", None),
    ("https://arxiv.org/abs/1", None),
    ("v0.4.1", None),
])
def test_evidence_path(token, expected):
    """요청서 근거 칸에서 경로가 아닌 것(섹션 인용, ID, URL)을 경로로 읽지 않는다."""
    assert verify._evidence_path(token) == expected


def test_evidence_bare_file_name_found_anywhere(tmp_path):
    (tmp_path / "plan" / "M0").mkdir(parents=True)
    (tmp_path / "plan" / "M0" / "M0-T5.md").write_text("x")
    assert verify._exists(tmp_path, "M0-T5.md")
    assert not verify._exists(tmp_path, "M0-T6.md")
