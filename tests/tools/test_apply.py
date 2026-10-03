"""`scripts/apply-human-commits` (설계 문서 §21): 사람 커밋을 문서 상태에 반영한다."""
import json
import re

CARD0 = "plan/milestones/M0/tasks/M0-T0.md"
MILESTONE0 = "plan/milestones/M0/milestone.md"


def card(task, status="draft"):
    return f"---\nid: {task}\ntype: task-card\nstatus: {status}\nupdated: 2026-01-01\n---\n# {task}\n\n## 게이트 이력\n"


def add_task(project, task):
    project.write(f"plan/milestones/M0/tasks/{task}.md", card(task))
    project.write(MILESTONE0, project.read(MILESTONE0).replace(
        "| `M0-T0` |", f"| `{task}` | 다음 | draft | [{task}](tasks/{task}.md) |\n| `M0-T0` |", 1))


def to_review(project):
    """M0-T0을 in-review로 만들고 게이트 요청서를 낸다 (에이전트의 일)."""
    project.set_status(CARD0, "in-review")
    project.write("reviews/open/M0-T0_gate-01.md", "---\nid: M0-T0_gate-01\ntype: review\nstatus: answered\n---\n# x\n")
    add_task(project, "M0-T1")
    project.write("decisions/D0.1_core.md", "---\nid: D0.1\ntype: decision\nstatus: proposed\nupdated: 2026-01-01\n---\n# D0.1\n")
    project.write("decisions/index.md", project.read("decisions/index.md") + "| D0.1 | 코어 | proposed | M0 | – | [문서](D0.1_core.md) |\n")
    project.agent("review(M0-T0): request gate\n\nActor: agent\nTask: M0-T0", CARD0, MILESTONE0, "reviews",
            "plan/milestones/M0/tasks/M0-T1.md", "decisions")


# ---------------------------------------------------------------- plan + Approve


def test_nothing_to_apply(project):
    result = project.apply()
    assert result.returncode == 0 and "반영할 사람 커밋이 없습니다" in result.stdout
    assert project.apply("--check").stdout == ""


def test_plan_approve(project):
    sha = project.human("plan(M0-T0): approve initial task\n\nActor: human\nApprove: M0-T0")
    assert project.apply("--check").stdout == f"{sha[:7]} plan(M0-T0): approve initial task\n"
    result = project.apply()
    assert result.returncode == 0, result.stderr
    assert project.status(CARD0) == "approved"
    assert "| `M0-T0` | 착수 계획 | approved |" in project.read(MILESTONE0)
    assert project.read(".lg/pending/APPLY_MSG") == f"log(M0-T0): apply plan {sha[:7]}\n\nActor: agent\nApplies: {sha[:7]}\n"
    head = project.commit_apply(result)
    assert project.git("log", "-1", "--format=%ae|%s", head) == f"{project.agent_email}|log(M0-T0): apply plan {sha[:7]}"
    assert project.git("status", "--porcelain") == ""
    assert project.apply("--check").stdout == ""


def test_already_satisfied_records_empty_apply(project):
    """v0.2 프로젝트: 에이전트가 판단으로 이미 반영한 승인은 건너뛰고 Applies만 남긴다."""
    sha = project.human("plan(M0-T0): approve initial task\n\nActor: human\nApprove: M0-T0")
    project.set_status(CARD0, "in-progress")
    project.agent(f"task(M0-T0): start\n\nActor: agent\nTask: M0-T0\nRefs: {sha[:7]}", CARD0)
    result = project.apply()
    assert result.returncode == 0 and "이미 반영됨" in result.stdout and "--allow-empty" in result.stdout
    assert "Applies 기록이 없어" in result.stdout and "Refs 등 다른 trailer는" in result.stdout
    assert project.git("status", "--porcelain") == ""
    project.commit_apply(result)
    assert project.git("log", "-1", "--format=%(trailers:key=Applies,valueonly)").strip() == sha[:7]
    assert project.apply("--check").stdout == ""


def test_oldest_first_one_at_a_time(project):
    add_task(project, "M0-T1")
    project.agent("chore: add card\n\nActor: agent", "plan")
    first = project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    second = project.human("plan(M0-T1): approve\n\nActor: human\nApprove: M0-T1")
    assert [l.split()[0] for l in project.apply("--check").stdout.splitlines()] == [first[:7], second[:7]]
    result = project.apply()
    assert "남은 사람 커밋 1개" in result.stdout
    assert project.status(CARD0) == "approved" and project.status("plan/milestones/M0/tasks/M0-T1.md") == "draft"
    project.commit_apply(result)
    assert project.apply("--check").stdout.split()[0] == second[:7]


def test_agent_commits_are_not_targets(project):
    """사람 커밋만 반영 대상이다 (에이전트는 plan 커밋을 만들 수 없지만, 신원으로 거른다)."""
    project.agent("log: note\n\nActor: agent")
    assert project.apply("--check").stdout == ""


# ---------------------------------------------------------------- gate, respond, decide


def test_gate_approve_full(project):
    to_review(project)
    sha = project.human("gate(M0-T0): approve, next M0-T1\n\nActor: human\nTask: M0-T0\nVerdict: approve\n"
                  "Source: document\nNext: M0-T1\nMilestone-Verdict: go\nDecisions: D0.1")
    result = project.apply()
    assert result.returncode == 0, result.stderr
    assert project.status(CARD0) == "closed"
    assert project.status("plan/milestones/M0/tasks/M0-T1.md") == "approved"
    assert project.status(MILESTONE0) == "closed"  # T0 승인으로 active, Milestone-Verdict로 closed
    assert "| `M0` |" in project.read("plan/roadmap.md") and "| closed |" in project.read("plan/roadmap.md")
    assert project.status("decisions/D0.1_core.md") == "confirmed"
    assert f"| D0.1 | 코어 | confirmed | M0 | `{sha[:7]}` |" in project.read("decisions/index.md")
    assert not (project.root / "reviews/open/M0-T0_gate-01.md").exists()
    assert project.status("reviews/closed/M0-T0_gate-01.md") == "closed"
    assert re.search(rf"^- \d{{4}}-\d\d-\d\d gate approve `{sha[:7]}`$", project.read(CARD0), re.M)
    project.commit_apply(result)
    assert project.git("status", "--porcelain") == ""
    assert project.apply("--check").stdout == ""


def test_gate_t0_approve_activates_milestone(project):
    """마일스톤 문서와 로드맵 표의 그 행이 함께 바뀐다 (실사용: 로드맵 표만 planned로 남았다)."""
    to_review(project)
    project.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none")
    result = project.apply()
    assert result.returncode == 0, result.stderr
    assert project.status(MILESTONE0) == "active"
    roadmap = project.read("plan/roadmap.md")
    assert re.search(r"^\| `M0` \| [^|]+ \| active \|", roadmap, re.M)
    assert re.search(r"^\| `M1` \| [^|]+ \| planned \|", roadmap, re.M)
    assert "plan/roadmap.md" in project.read(".lg/pending/APPLY_PATHS")


def test_gate_revise(project):
    to_review(project)
    project.human("gate(M0-T0): revise\n\nActor: human\nTask: M0-T0\nVerdict: revise\nSource: conversation")
    result = project.apply()
    assert result.returncode == 0, result.stderr
    assert project.status(CARD0) == "revise" and project.status(MILESTONE0) == "planned"


def test_respond(project):
    project.set_status(CARD0, "blocked")
    project.write("reviews/open/M0-T0_esc-01.md", "---\nid: M0-T0_esc-01\ntype: review\nstatus: answered\n---\n# x\n")
    project.agent("review(M0-T0): escalate\n\nActor: agent\nTask: M0-T0", CARD0, "reviews")
    sha = project.human("respond(M0-T0): option 2\n\nActor: human\nTask: M0-T0\nSource: document")
    result = project.apply()
    assert result.returncode == 0, result.stderr
    assert project.status(CARD0) == "in-progress"
    assert (project.root / "reviews/closed/M0-T0_esc-01.md").exists()
    assert project.read(".lg/pending/APPLY_MSG").startswith(f"task(M0-T0): resume after response {sha[:7]}\n")
    project.commit_apply(result)
    assert project.git("log", "-1", "--format=%s") == f"task(M0-T0): resume after response {sha[:7]}"


def test_decide(project):
    project.write("decisions/D0.1_core.md", "---\nid: D0.1\ntype: decision\nstatus: discussing\nupdated: 2026-01-01\n---\n")
    project.agent("propose(D0.1): core\n\nActor: agent", "decisions")
    sha = project.human("decide(D0.1): use mamba-2\n\nActor: human\nDecisions: D0.1\nSource: conversation")
    result = project.apply()
    assert result.returncode == 0, result.stderr
    assert project.status("decisions/D0.1_core.md") == "confirmed"
    assert project.read(".lg/pending/APPLY_MSG").startswith(f"log(D0.1): apply decide {sha[:7]}\n")


# ---------------------------------------------------------------- 반영할 수 없음, 환경 오류


def test_cannot_apply_changes_nothing(project):
    """판정 대상 카드가 in-review가 아니면 반영할 수 없다. 다른 전이도 하나도 하지 않는다."""
    add_task(project, "M0-T1")
    project.agent("chore: add card\n\nActor: agent", "plan")
    project.set_status(CARD0, "in-progress")
    project.agent("task(M0-T0): start\n\nActor: agent\nTask: M0-T0", CARD0)
    project.human("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: M0-T1")
    result = project.apply()
    assert result.returncode == 1
    assert "in-progress" in result.stderr and "아무것도 바꾸지 않았습니다" in result.stderr
    assert project.git("status", "--porcelain") == ""
    assert not (project.root / ".lg/pending/APPLY_MSG").exists()


def test_missing_card_cannot_apply(project):
    project.human("plan(M1-T5): approve\n\nActor: human\nApprove: M1-T5")
    result = project.apply()
    assert result.returncode == 1 and "파일이 없습니다" in result.stderr


def test_pending_draft_blocks(project):
    project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.write(".lg/pending/COMMIT_MSG", "exp: x\n\nActor: human\n")
    result = project.apply()
    assert result.returncode == 2 and "사람 커밋 대기 상태" in result.stderr


def test_dirty_target_blocks(project):
    project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.write(CARD0, project.read(CARD0) + "\n메모\n")
    result = project.apply()
    assert result.returncode == 2 and "커밋되지 않은 변경" in result.stderr
    assert project.status(CARD0) == "draft"


def test_applies_prefix_marks_reflected(project):
    sha = project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.agent(f"log: manual\n\nActor: agent\nApplies: {sha[:10]}")
    assert project.apply("--check").stdout == ""


def test_apply_refuses_while_last_apply_uncommitted(project):
    project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.apply()
    result = project.apply()
    assert result.returncode == 2 and "아직 커밋되지 않았습니다" in result.stderr
    assert "scripts/agent-commit -F .lg/pending/APPLY_MSG --" in result.stderr


def test_tidy_reports_json(project):
    assert project.apply("--tidy").stdout == ""
    sha = project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.apply()
    state = json.loads(project.apply("--tidy").stdout)
    assert state == {"state": "pending", "applies": sha[:7], "paths": [MILESTONE0, CARD0]}


# ---------------------------------------------------------------- --preview (§24.5.4, lg answer가 쓴다)

GATE_APPROVE = ("gate(M0-T0): approve, next M0-T1\n\nActor: human\nTask: M0-T0\nVerdict: approve\n"
                "Source: document\nNext: M0-T1\nReview: M0-T0_gate-01\n")


def test_preview_lists_changes_and_writes_nothing(project):
    to_review(project)
    result = project.apply("--preview", input=GATE_APPROVE)
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert out.startswith("미리보기: gate(M0-T0): approve, next M0-T1\n")
    assert f"{CARD0}: status in-review → closed" in out
    assert "plan/milestones/M0/tasks/M0-T1.md: status draft → approved" in out
    assert f"{MILESTONE0}: status planned → active" in out
    assert "reviews/open/M0-T0_gate-01.md → reviews/closed/M0-T0_gate-01.md" in out
    assert project.git("status", "--porcelain") == ""
    assert not (project / ".lg/pending/APPLY_MSG").exists()


def test_preview_refuses_what_cannot_be_applied(project):
    """카드가 in-review가 아니면 반영할 수 없다. 커밋 전에 알 수 있다."""
    result = project.apply("--preview", input=GATE_APPROVE.replace("Next: M0-T1\n", ""))
    assert result.returncode == 1
    assert "반영할 수 없습니다" in result.stderr and "draft" in result.stderr


def test_preview_of_non_target_commit(project):
    result = project.apply("--preview", input="exp: x\n\nActor: human\n")
    assert result.returncode == 0 and result.stdout.startswith("반영할 것이 없습니다")
