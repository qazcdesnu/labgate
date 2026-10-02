"""`scripts/apply-human-commits`와 확장된 `scripts/session-check` (설계 문서 §17.2, §21).

스크립트는 생성된 프로젝트에서 `python3`(테스트 환경에서는 HOOK_PYTHON)로 실행한다.
"""
import re
import shutil
import subprocess

import pytest
import yaml
from typer.testing import CliRunner

from labgate.cli import app

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")

HUMAN = "h@x.com"
CONFIG = {
    "schema_version": 1,
    "project": {"name": "Apply test", "slug": "atest", "summary": "s", "research_question": "q?"},
    "people": {"humans": [{"name": "H", "email": HUMAN}]},
    "milestones": [{"title": "기반"}, {"title": "검증"}],
}


class Proj:
    def __init__(self, root, env):
        self.root, self.env = root, env

    def run(self, *args, check=True):
        return subprocess.run(list(args), cwd=self.root, env=self.env, capture_output=True, text=True, check=check)

    def git(self, *args):
        return self.run("git", *args).stdout.strip()

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def status(self, rel):
        return re.search(r"^status: *(\S+)", self.read(rel), re.M).group(1)

    def set_status(self, rel, status):
        self.write(rel, re.sub(r"^status: *\S+", f"status: {status}", self.read(rel), count=1, flags=re.M))

    def human(self, message, *paths):
        if paths:
            self.git("add", "--", *paths)
        self.run("git", "commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def agent(self, message, *paths):
        if paths:  # 새 파일은 pathspec 커밋에 쓸 수 없으므로 먼저 stage한다
            self.git("add", "-A", "--", *paths)
        self.run(str(self.root / "scripts/agent-commit"), "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def apply(self, *args):
        return self.run("python3", str(self.root / "scripts/apply-human-commits"), *args, check=False)

    def commit_apply(self, result):
        """출력된 커밋 명령을 그대로 실행한다 (에이전트가 하는 일)."""
        command = re.search(r"^커밋: (scripts/agent-commit [^(]+?)\s*(\(|$)", result.stdout, re.M).group(1)
        self.run("bash", "-c", command)
        return self.git("rev-parse", "HEAD")

    def session_check(self):
        return self.run("python3", str(self.root / "scripts/session-check")).stdout


@pytest.fixture
def p(tmp_path, git_sandbox):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    root = tmp_path / "proj"
    assert CliRunner().invoke(app, ["init", str(root), "--config", str(cfg)]).exit_code == 0
    return Proj(root, git_sandbox)


CARD0 = "plan/milestones/M0/tasks/M0-T0.md"
MILESTONE0 = "plan/milestones/M0/milestone.md"


def card(task, status="draft"):
    return f"---\nid: {task}\ntype: task-card\nstatus: {status}\nupdated: 2026-01-01\n---\n# {task}\n\n## 게이트 이력\n"


def add_task(p, task):
    p.write(f"plan/milestones/M0/tasks/{task}.md", card(task))
    p.write(MILESTONE0, p.read(MILESTONE0).replace(
        "| `M0-T0` |", f"| `{task}` | 다음 | draft | [{task}](tasks/{task}.md) |\n| `M0-T0` |", 1))


def to_review(p):
    """M0-T0을 in-review로 만들고 게이트 요청서를 낸다 (에이전트의 일)."""
    p.set_status(CARD0, "in-review")
    p.write("reviews/open/M0-T0_gate-01.md", "---\nid: M0-T0_gate-01\ntype: review\nstatus: answered\n---\n# x\n")
    add_task(p, "M0-T1")
    p.write("decisions/D0.1_core.md", "---\nid: D0.1\ntype: decision\nstatus: proposed\nupdated: 2026-01-01\n---\n# D0.1\n")
    p.write("decisions/index.md", p.read("decisions/index.md") + "| D0.1 | 코어 | proposed | M0 | – | [문서](D0.1_core.md) |\n")
    p.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD0, MILESTONE0, "reviews",
            "plan/milestones/M0/tasks/M0-T1.md", "decisions")


# ---------------------------------------------------------------- plan + Approve


def test_nothing_to_apply(p):
    result = p.apply()
    assert result.returncode == 0 and "반영할 사람 커밋이 없습니다" in result.stdout
    assert p.apply("--check").stdout == ""


def test_plan_approve(p):
    sha = p.human("plan(M0-T0): approve initial task\n\nActor: human\nApprove: M0-T0")
    assert p.apply("--check").stdout == f"{sha[:7]} plan(M0-T0): approve initial task\n"
    result = p.apply()
    assert result.returncode == 0, result.stderr
    assert p.status(CARD0) == "approved"
    assert "| `M0-T0` | 착수 계획 | approved |" in p.read(MILESTONE0)
    assert p.read(".lg/pending/APPLY_MSG") == f"log(M0-T0): apply plan {sha[:7]}\n\nActor: agent\nApplies: {sha[:7]}\n"
    head = p.commit_apply(result)
    assert p.git("log", "-1", "--format=%ae|%s", head) == f"agent@atest.local|log(M0-T0): apply plan {sha[:7]}"
    assert p.git("status", "--porcelain") == ""
    assert p.apply("--check").stdout == ""


def test_already_satisfied_records_empty_apply(p):
    """v0.2 프로젝트: 에이전트가 판단으로 이미 반영한 승인은 건너뛰고 Applies만 남긴다."""
    sha = p.human("plan(M0-T0): approve initial task\n\nActor: human\nApprove: M0-T0")
    p.set_status(CARD0, "in-progress")
    p.agent(f"task(M0-T0): start\n\nActor: agent\nTask: M0-T0\nRefs: {sha[:7]}", CARD0)
    result = p.apply()
    assert result.returncode == 0 and "이미 반영됨" in result.stdout and "--allow-empty" in result.stdout
    assert p.git("status", "--porcelain") == ""
    p.commit_apply(result)
    assert p.git("log", "-1", "--format=%(trailers:key=Applies,valueonly)").strip() == sha[:7]
    assert p.apply("--check").stdout == ""


def test_oldest_first_one_at_a_time(p):
    add_task(p, "M0-T1")
    p.agent("chore: add card\n\nActor: agent", "plan")
    first = p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    second = p.human("plan(M0-T1): approve\n\nActor: human\nApprove: M0-T1")
    assert [l.split()[0] for l in p.apply("--check").stdout.splitlines()] == [first[:7], second[:7]]
    result = p.apply()
    assert "남은 사람 커밋 1개" in result.stdout
    assert p.status(CARD0) == "approved" and p.status("plan/milestones/M0/tasks/M0-T1.md") == "draft"
    p.commit_apply(result)
    assert p.apply("--check").stdout.split()[0] == second[:7]


def test_agent_commits_are_not_targets(p):
    """사람 커밋만 반영 대상이다 (에이전트는 plan 커밋을 만들 수 없지만, 신원으로 거른다)."""
    p.agent("log: note\n\nActor: agent")
    assert p.apply("--check").stdout == ""


# ---------------------------------------------------------------- gate, respond, decide


def test_gate_approve_full(p):
    to_review(p)
    sha = p.human("gate(M0-T0): approve, next M0-T1\n\nActor: human\nTask: M0-T0\nVerdict: approve\n"
                  "Source: document\nNext: M0-T1\nMilestone-Verdict: go\nDecisions: D0.1")
    result = p.apply()
    assert result.returncode == 0, result.stderr
    assert p.status(CARD0) == "closed"
    assert p.status("plan/milestones/M0/tasks/M0-T1.md") == "approved"
    assert p.status(MILESTONE0) == "closed"  # T0 승인으로 active, Milestone-Verdict로 closed
    assert p.status("decisions/D0.1_core.md") == "confirmed"
    assert f"| D0.1 | 코어 | confirmed | M0 | `{sha[:7]}` |" in p.read("decisions/index.md")
    assert not (p.root / "reviews/open/M0-T0_gate-01.md").exists()
    assert p.status("reviews/closed/M0-T0_gate-01.md") == "closed"
    assert re.search(rf"^- \d{{4}}-\d\d-\d\d gate approve `{sha[:7]}`$", p.read(CARD0), re.M)
    p.commit_apply(result)
    assert p.git("status", "--porcelain") == ""
    assert p.apply("--check").stdout == ""


def test_gate_t0_approve_activates_milestone(p):
    to_review(p)
    p.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none")
    assert p.apply().returncode == 0
    assert p.status(MILESTONE0) == "active"


def test_gate_revise(p):
    to_review(p)
    p.human("gate(M0-T0): revise\n\nActor: human\nTask: M0-T0\nVerdict: revise\nSource: conversation")
    result = p.apply()
    assert result.returncode == 0, result.stderr
    assert p.status(CARD0) == "revise" and p.status(MILESTONE0) == "planned"


def test_respond(p):
    p.set_status(CARD0, "blocked")
    p.write("reviews/open/M0-T0_esc-01.md", "---\nid: M0-T0_esc-01\ntype: review\nstatus: answered\n---\n# x\n")
    p.agent("review(M0-T0): escalate\n\nActor: agent\nTask: M0-T0", CARD0, "reviews")
    sha = p.human("respond(M0-T0): option 2\n\nActor: human\nTask: M0-T0\nSource: document")
    result = p.apply()
    assert result.returncode == 0, result.stderr
    assert p.status(CARD0) == "in-progress"
    assert (p.root / "reviews/closed/M0-T0_esc-01.md").exists()
    assert p.read(".lg/pending/APPLY_MSG").startswith(f"task(M0-T0): resume after response {sha[:7]}\n")
    p.commit_apply(result)
    assert p.git("log", "-1", "--format=%s") == f"task(M0-T0): resume after response {sha[:7]}"


def test_decide(p):
    p.write("decisions/D0.1_core.md", "---\nid: D0.1\ntype: decision\nstatus: discussing\nupdated: 2026-01-01\n---\n")
    p.agent("propose(D0.1): core\n\nActor: agent", "decisions")
    sha = p.human("decide(D0.1): use mamba-2\n\nActor: human\nDecisions: D0.1\nSource: conversation")
    result = p.apply()
    assert result.returncode == 0, result.stderr
    assert p.status("decisions/D0.1_core.md") == "confirmed"
    assert p.read(".lg/pending/APPLY_MSG").startswith(f"log(D0.1): apply decide {sha[:7]}\n")


# ---------------------------------------------------------------- 반영할 수 없음, 환경 오류


def test_cannot_apply_changes_nothing(p):
    """판정 대상 카드가 in-review가 아니면 반영할 수 없다. 다른 전이도 하나도 하지 않는다."""
    add_task(p, "M0-T1")
    p.agent("chore: add card\n\nActor: agent", "plan")
    p.set_status(CARD0, "in-progress")
    p.agent("task(M0-T0): start\n\nActor: agent\nTask: M0-T0", CARD0)
    p.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: M0-T1")
    result = p.apply()
    assert result.returncode == 1
    assert "in-progress" in result.stderr and "아무것도 바꾸지 않았습니다" in result.stderr
    assert p.git("status", "--porcelain") == ""
    assert not (p.root / ".lg/pending/APPLY_MSG").exists()


def test_missing_card_cannot_apply(p):
    p.human("plan(M1-T5): approve\n\nActor: human\nApprove: M1-T5")
    result = p.apply()
    assert result.returncode == 1 and "파일이 없습니다" in result.stderr


def test_pending_draft_blocks(p):
    p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    p.write(".lg/pending/COMMIT_MSG", "exp: x\n\nActor: human\n")
    result = p.apply()
    assert result.returncode == 2 and "사람 커밋 대기 상태" in result.stderr


def test_dirty_target_blocks(p):
    p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    p.write(CARD0, p.read(CARD0) + "\n메모\n")
    result = p.apply()
    assert result.returncode == 2 and "커밋되지 않은 변경" in result.stderr
    assert p.status(CARD0) == "draft"


def test_applies_prefix_marks_reflected(p):
    sha = p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    p.agent(f"log: manual\n\nActor: agent\nApplies: {sha[:10]}")
    assert p.apply("--check").stdout == ""


def test_hook_checks_applies_format(p):
    result = p.run(str(p.root / "scripts/agent-commit"), "--allow-empty", "-m", "log: x",
                   "-m", "Actor: agent\nApplies: not-a-hash", check=False)
    assert result.returncode != 0 and "Applies 형식이 잘못되었습니다" in result.stderr


# ---------------------------------------------------------------- session-check (§17.2)


def test_session_check_reports_unreflected(p):
    sha = p.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    out = p.session_check()
    assert "반영되지 않은 사람 커밋" in out and "gate-apply.md" in out and sha[:7] in out


def test_session_check_cleans_committed_draft(p):
    message = "exp: add a\n\nActor: human\n"
    p.write("a.py", "x\n")
    p.git("add", "a.py")
    p.write(".lg/pending/COMMIT_MSG", message)
    p.run("git", "commit", "-q", "-F", ".lg/pending/COMMIT_MSG")  # lg commit 대신 git commit
    out = p.session_check()
    assert "이미 커밋한 초안을 정리했습니다" in out
    assert not (p.root / ".lg/pending/COMMIT_MSG").exists()
    assert "사람 커밋 대기 상태" not in out


def test_session_check_keeps_uncommitted_draft(p):
    p.write(".lg/pending/COMMIT_MSG", "exp: not yet\n\nActor: human\n")
    out = p.session_check()
    assert "사람 커밋 대기 상태" in out and (p.root / ".lg/pending/COMMIT_MSG").exists()
