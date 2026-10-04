"""`lg status` (설계 문서 §24.3): 사람이 할 일, 에이전트 몫, 진행을 파일과 이력에서 모은다. 읽기만 한다."""
import json

from support.releases import make_old


def status(project, *args):
    result = project.lg("status", *args)
    assert result.exit_code == 0, result.output
    return result.output


def test_fresh_project_waits_for_first_approval(project):
    """실사용(연습 프로젝트): 새 프로젝트에서 사람이 할 일은 M0-T0 승인이다."""
    out = status(project)
    assert out.startswith("ptest · spec_version 5 · M0 (planned)\n")
    assert "[승인]" in out and "M0-T0  draft, 승인 대기" in out and "lg commit --allow-empty" in out
    assert "에이전트 몫: 없음" in out and "draft       M0-T0" in out
    project.approve_and_start()
    assert "사람이 할 일: 없음" in status(project)


def test_open_gate_points_to_answer(project):
    project.approve_and_start()
    project.request_gate()
    out = status(project)
    assert "사람이 할 일 1건" in out
    assert "[gate]" in out and "M0-T0_gate-01  M0-T0 착수 계획 · 10-03 요청" in out
    assert "→ lg answer M0-T0_gate-01" in out
    assert "in-review   M0-T0" in out


def test_review_being_written_points_to_commit(project):
    project.approve_and_start()
    project.request_gate()
    project.write("reviews/open/M0-T0_gate-01.md", project.read("reviews/open/M0-T0_gate-01.md") + "\n승인\n")
    out = status(project)
    assert "응답 작성 중 (커밋 전)  → lg commit" in out and "lg answer" not in out
    assert "커밋되지 않은 변경" not in out  # 같은 파일을 두 번 세지 않는다


def test_draft_and_human_files(project):
    project.write(".lg/pending/COMMIT_MSG", "exp: add loader\n\nActor: human\n")
    project.write("a.py")
    project.write(".lg/pending/HUMAN_FILES", "a.py\n")
    out = status(project)
    assert "[초안]" in out and "exp: add loader" in out
    assert "커밋되지 않은 내 변경 1개 (a.py)" in out


def test_unreflected_human_commit_is_agents(project):
    project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    out = status(project)
    assert "사람이 할 일: 없음" in out
    assert "에이전트 몫 (다음 세션에서 자동)" in out and "plan(M0-T0): approve" in out
    assert "에이전트 세션을 시작하면 이어서 진행합니다." in out
    project.apply()
    assert "반영했지만 커밋 전" in status(project)


def test_decisions_and_json(project):
    project.add_decision("D0.1")
    project.agent("propose(D0.1): core\n\nActor: agent", "decisions")
    assert "proposed·discussing 1 (D0.1)" in status(project)
    data = json.loads(status(project, "--json"))
    assert data["milestone"] == "M0" and data["open_decisions"] == ["D0.1"]
    assert data["tasks"] == {"draft": ["M0-T0"]} and [h["kind"] for h in data["human"]] == ["approve"]


def test_spec2_project_without_apply_script(tmp_path, git_sandbox, old_sources):
    old = make_old(tmp_path, git_sandbox, old_sources, 2)
    out = status(old)
    assert "spec_version 2" in out and "scripts/apply-human-commits 없음" in out


def test_stale_copy_of_closed_review(project):
    """실사용: 반영 도구가 요청서를 closed/로 옮긴 직후 편집기가 open/에 다시 저장했다."""
    project.write("reviews/closed/M0-T0_gate-01.md", "---\nid: M0-T0_gate-01\ntype: review\nstatus: closed\n---\n")
    project.agent("log(M0-T0): close review\n\nActor: agent", "reviews/closed")
    project.write("reviews/open/M0-T0_gate-01.md", "---\nid: M0-T0_gate-01\ntype: review\nkind: gate\nstatus: answered\n---\n")
    out = status(project)
    assert "[사본]" in out and "rm reviews/open/M0-T0_gate-01.md" in out
    assert "응답 작성 중" not in out and "커밋되지 않은 변경" not in out
