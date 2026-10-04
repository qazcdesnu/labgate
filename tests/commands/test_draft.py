"""`lg draft` (설계 문서 §19): 사람 커밋의 초안(stage와 .lg/pending/COMMIT_MSG)을 준비한다."""
import pytest

from support.cli import lg
from support.configs import HUMAN


@pytest.fixture
def proj(project, monkeypatch):
    """프로젝트 폴더에서 lg를 실행한다."""
    monkeypatch.chdir(project.root)
    return project


def test_draft_with_paths(proj):
    proj.write("experiments/src/model.py")
    proj.write("notes/agent.md")  # 지정하지 않은 변경은 stage되지 않는다
    result = lg("draft", "--type", "exp", "--summary", "add model", "--body", "왜", "experiments/src/model.py")
    assert result.exit_code == 0, result.output
    assert proj.git("diff", "--cached", "--name-only") == "experiments/src/model.py"
    assert proj.read(".lg/pending/COMMIT_MSG") == "exp: add model\n\n왜\n\nActor: human\n"


def test_draft_paths_relative_to_cwd(proj, monkeypatch):
    proj.write("experiments/src/model.py")
    monkeypatch.chdir(proj / "experiments")
    assert lg("draft", "--type", "exp", "--summary", "x", "src/model.py").exit_code == 0
    assert proj.git("diff", "--cached", "--name-only") == "experiments/src/model.py"


def test_draft_scope_from_task_and_passes_hook(proj):
    proj.write("results/M1/M1-T2_result.md")
    result = lg("draft", "--type", "result", "--summary", "add table", "--trailer", "Task=M1-T2",
                "results/M1/M1-T2_result.md")
    assert result.exit_code == 0, result.output
    message = proj.read(".lg/pending/COMMIT_MSG")
    assert message.startswith("result(M1-T2): add table\n")
    proj.git("commit", "-q", "-F", ".lg/pending/COMMIT_MSG")  # 사람이 git commit으로 확정해도 hook 통과
    assert proj.last_commit() == f"{HUMAN}|result(M1-T2): add table"


def test_draft_without_paths_uses_human_files_only(proj):
    proj.write("experiments/src/human.py")
    proj.session_check()  # 세션 시작: 사람의 변경 기록
    proj.write("notes/agent.md")  # 세션 도중 생긴 (에이전트의) 변경
    assert lg("draft", "--type", "exp", "--summary", "x").exit_code == 0
    assert proj.git("diff", "--cached", "--name-only") == "experiments/src/human.py"


def test_draft_without_paths_needs_human_files(proj):
    proj.write("a.py")
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "경로를 지정하세요" in result.output


@pytest.mark.parametrize("args, expected", [
    (["--type", "task", "--summary", "x"], "사람 커밋에 쓸 수 없는 타입입니다: task"),
    (["--type", "review", "--summary", "x", "--trailer", "Task=M0-T0"], "사람 커밋에 쓸 수 없는 타입입니다: review"),
    (["--type", "exp", "--summary", "x", "--trailer", "Actor=agent"], "Actor trailer는 지정할 수 없습니다"),
    (["--type", "exp", "--summary", "x", "--trailer", "Task"], "KEY=VALUE 형식"),
    (["--type", "gate", "--summary", "approve", "--trailer", "Task=M0-T0"], "Verdict trailer"),
    (["--type", "result", "--summary", "x"], "Task trailer가 필요합니다"),
    (["--type", "exp", "--summary", "x" * 80], "헤더가 72자를 넘습니다"),
])
def test_draft_validation_changes_nothing(proj, args, expected):
    proj.write("a.py")
    result = lg("draft", *args, "a.py")
    assert result.exit_code == 2 and expected in result.output, result.output
    assert proj.git("diff", "--cached", "--name-only") == ""
    assert not (proj / ".lg/pending/COMMIT_MSG").exists()


def test_draft_collects_all_errors(proj):
    result = lg("draft", "--type", "gate", "--summary", "x", "--trailer", "Task=M0-T0", "a.py")
    assert "Verdict trailer" in result.output and "Source trailer" in result.output


def test_draft_refuses_when_pending(proj):
    proj.write("a.py")
    assert lg("draft", "--type", "exp", "--summary", "x", "a.py").exit_code == 0
    proj.write("b.py")
    result = lg("draft", "--type", "exp", "--summary", "y", "b.py")
    assert result.exit_code == 3 and "사람 커밋 대기 상태" in result.output


def test_draft_refuses_other_staged_changes(proj):
    proj.write("agent.md")
    proj.git("add", "agent.md")
    proj.write("a.py")
    result = lg("draft", "--type", "exp", "--summary", "x", "a.py")
    assert result.exit_code == 2 and "stage된 다른 변경" in result.output and "agent.md" in result.output
    assert proj.git("diff", "--cached", "--name-only") == "agent.md"


def test_draft_nothing_to_stage(proj):
    result = lg("draft", "--type", "exp", "--summary", "x", "README.md")
    assert result.exit_code == 3 and "stage된 변경이 없습니다" in result.output
