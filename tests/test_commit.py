"""`lg commit`, `lg draft`, `scripts/session-check` (설계 문서 §17–§19)."""
import shutil
import subprocess

import pytest
import yaml
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from typer.testing import CliRunner

import labgate.commit as commit_module
import labgate.prompts as prompts
from labgate.cli import app

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")

ENTER, DOWN, SPACE = "\r", "\x1b[B", " "
HUMAN = "h@x.com"
CONFIG = {
    "schema_version": 1,
    "project": {"name": "Commit test", "slug": "ctest", "summary": "s", "research_question": "q?"},
    "people": {"humans": [{"name": "H", "email": HUMAN}]},
    "milestones": [{"title": "기반"}, {"title": "검증"}],
}


def lg(*args):
    return CliRunner().invoke(app, [str(a) for a in args], catch_exceptions=False)


def git(root, *args, check=True):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=check).stdout.strip()


@pytest.fixture
def proj(tmp_path, git_sandbox, monkeypatch):
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    root = tmp_path / "proj"
    assert lg("init", root, "--config", cfg).exit_code == 0
    monkeypatch.chdir(root)
    return root


@pytest.fixture
def tty(monkeypatch):
    monkeypatch.setattr(commit_module, "is_tty", lambda: True)


@pytest.fixture
def keys(monkeypatch, tty):
    """가짜 터미널 입력 (test_init.py와 같은 방식)."""
    with create_pipe_input() as pipe:
        monkeypatch.setattr(prompts, "IO", {"input": pipe, "output": DummyOutput()})

        def send(*parts):
            pipe.send_text("".join(parts))
            pipe.pipe.close_write()

        yield send


def session_check(root, env):
    return subprocess.run(["python3", str(root / "scripts/session-check")], cwd=root, env=env,
                          capture_output=True, text=True, check=True)


def write(root, rel, text="x\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def last_commit(root):
    return git(root, "log", "-1", "--format=%ae|%s")


# ---------------------------------------------------------------- 프로젝트 확인 (§18.3)


def test_outside_git_repo(tmp_path, git_sandbox, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "Git 저장소가 아닙니다" in result.output


def test_not_a_labgate_project(tmp_path, git_sandbox, monkeypatch):
    git(tmp_path, "init", "-q")
    monkeypatch.chdir(tmp_path)
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "labgate 프로젝트가 아닙니다" in result.output


def test_spec_version_1_project_is_refused(proj):
    path = proj / ".lg/project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["generated"]["spec_version"] = 1
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "spec_version 1" in result.output


def test_hook_without_contract_names_is_refused(proj):
    hook = proj / ".lg/hooks/commit-msg"
    hook.write_text(hook.read_text(encoding="utf-8").replace("def check(", "def _check("), encoding="utf-8")
    result = lg("draft", "--type", "exp", "--summary", "x")
    assert result.exit_code == 2 and "형식이 아닙니다" in result.output and "check" in result.output


def test_types_come_from_project_hook(proj, keys):
    """§18.3: 규칙의 원본은 프로젝트의 hook이다. hook을 바꾸면 lg의 판단도 따라 바뀐다."""
    hook = proj / ".lg/hooks/commit-msg"
    text = hook.read_text(encoding="utf-8").replace('"exp", "run", "result"', '"run", "result"')
    hook.write_text(text.replace('AGENT_TYPES = {"task"', 'AGENT_TYPES = {"exp", "task"'), encoding="utf-8")
    write(proj, "a.py")
    result = lg("draft", "--type", "exp", "--summary", "x", "a.py")
    assert result.exit_code == 2 and "사람 커밋에 쓸 수 없는 타입입니다: exp" in result.output


# ---------------------------------------------------------------- lg draft (§19)


def test_draft_with_paths(proj):
    write(proj, "experiments/src/model.py")
    write(proj, "notes/agent.md")  # 지정하지 않은 변경은 stage되지 않는다
    result = lg("draft", "--type", "exp", "--summary", "add model", "--body", "왜", "experiments/src/model.py")
    assert result.exit_code == 0, result.output
    assert git(proj, "diff", "--cached", "--name-only") == "experiments/src/model.py"
    assert (proj / ".lg/pending/COMMIT_MSG").read_text(encoding="utf-8") == "exp: add model\n\n왜\n\nActor: human\n"


def test_draft_paths_relative_to_cwd(proj, monkeypatch):
    write(proj, "experiments/src/model.py")
    monkeypatch.chdir(proj / "experiments")
    assert lg("draft", "--type", "exp", "--summary", "x", "src/model.py").exit_code == 0
    assert git(proj, "diff", "--cached", "--name-only") == "experiments/src/model.py"


def test_draft_scope_from_task_and_passes_hook(proj):
    write(proj, "results/M1/M1-T2_result.md")
    result = lg("draft", "--type", "result", "--summary", "add table", "--trailer", "Task=M1-T2",
                "results/M1/M1-T2_result.md")
    assert result.exit_code == 0, result.output
    message = (proj / ".lg/pending/COMMIT_MSG").read_text(encoding="utf-8")
    assert message.startswith("result(M1-T2): add table\n")
    git(proj, "commit", "-q", "-F", ".lg/pending/COMMIT_MSG")  # 사람이 git commit으로 확정해도 hook 통과
    assert last_commit(proj) == f"{HUMAN}|result(M1-T2): add table"


def test_draft_without_paths_uses_human_files_only(proj, git_sandbox):
    write(proj, "experiments/src/human.py")
    session_check(proj, git_sandbox)  # 세션 시작: 사람의 변경 기록
    write(proj, "notes/agent.md")  # 세션 도중 생긴 (에이전트의) 변경
    assert lg("draft", "--type", "exp", "--summary", "x").exit_code == 0
    assert git(proj, "diff", "--cached", "--name-only") == "experiments/src/human.py"


def test_draft_without_paths_needs_human_files(proj):
    write(proj, "a.py")
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
    write(proj, "a.py")
    result = lg("draft", *args, "a.py")
    assert result.exit_code == 2 and expected in result.output, result.output
    assert git(proj, "diff", "--cached", "--name-only") == ""
    assert not (proj / ".lg/pending/COMMIT_MSG").exists()


def test_draft_collects_all_errors(proj):
    result = lg("draft", "--type", "gate", "--summary", "x", "--trailer", "Task=M0-T0", "a.py")
    assert "Verdict trailer" in result.output and "Source trailer" in result.output


def test_draft_refuses_when_pending(proj):
    write(proj, "a.py")
    assert lg("draft", "--type", "exp", "--summary", "x", "a.py").exit_code == 0
    write(proj, "b.py")
    result = lg("draft", "--type", "exp", "--summary", "y", "b.py")
    assert result.exit_code == 3 and "사람 커밋 대기 상태" in result.output


def test_draft_refuses_other_staged_changes(proj):
    write(proj, "agent.md")
    git(proj, "add", "agent.md")
    write(proj, "a.py")
    result = lg("draft", "--type", "exp", "--summary", "x", "a.py")
    assert result.exit_code == 2 and "stage된 다른 변경" in result.output and "agent.md" in result.output
    assert git(proj, "diff", "--cached", "--name-only") == "agent.md"


def test_draft_nothing_to_stage(proj):
    result = lg("draft", "--type", "exp", "--summary", "x", "README.md")
    assert result.exit_code == 3 and "stage된 변경이 없습니다" in result.output


# ---------------------------------------------------------------- lg commit (§18)


def test_commit_requires_tty(proj):
    result = lg("commit")
    assert result.exit_code == 2 and "터미널에서 직접" in result.output


def test_commit_requires_registered_human(proj, tty):
    git(proj, "config", "user.email", "agent@ctest.local")
    result = lg("commit")
    assert result.exit_code == 2 and "humans 에 없습니다" in result.output


def test_commit_pending_without_draft(proj, tty):
    result = lg("commit", "--pending")
    assert result.exit_code == 3 and "초안이 없습니다" in result.output


def test_commit_draft_mode(proj, git_sandbox, keys):
    write(proj, "experiments/src/human.py")
    write(proj, "notes/later.md")
    session_check(proj, git_sandbox)
    assert lg("draft", "--type", "exp", "--summary", "add human code", "experiments/src/human.py").exit_code == 0
    keys(ENTER)  # 커밋
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert last_commit(proj) == f"{HUMAN}|exp: add human code"
    assert not (proj / ".lg/pending/COMMIT_MSG").exists()
    # 아직 커밋되지 않은 사람의 변경만 남는다
    assert (proj / ".lg/pending/HUMAN_FILES").read_text(encoding="utf-8") == "notes/later.md\n"


def test_commit_gate_approve_tags(proj, keys):
    write(proj, "reviews/open/M0-T0_gate-01.md")
    assert lg("draft", "--type", "gate", "--summary", "approve, next M1-T0",
              "--trailer", "Task=M0-T0", "--trailer", "Verdict=approve", "--trailer", "Source=conversation",
              "--trailer", "Next=M1-T0", "--trailer", "Milestone-Verdict=go", "reviews").exit_code == 0
    keys(ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert set(git(proj, "tag", "--points-at", "HEAD").split()) == {"gate/M0-T0", "milestone/M0-go"}


def test_commit_no_tag(proj, keys):
    write(proj, "r.md")
    lg("draft", "--type", "gate", "--summary", "approve", "--trailer", "Task=M0-T0",
       "--trailer", "Verdict=approve", "--trailer", "Source=document", "r.md")
    keys(ENTER)
    assert lg("commit", "--no-tag").exit_code == 0
    assert git(proj, "tag") == ""


def test_commit_cancel_keeps_draft(proj, keys):
    write(proj, "a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    keys(DOWN, DOWN, ENTER)  # 취소
    result = lg("commit")
    assert result.exit_code == 130 and "그대로 두었습니다" in result.output
    assert (proj / ".lg/pending/COMMIT_MSG").exists()
    assert git(proj, "diff", "--cached", "--name-only") == "a.py"


def test_commit_edit_is_revalidated(proj, keys, monkeypatch):
    write(proj, "a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    edits = iter(["task: agent only\n\nActor: human\n", "exp: fixed after edit\n\nActor: human\n"])
    monkeypatch.setattr(commit_module, "_edit", lambda project, text: next(edits))
    # 편집 → (규약 위반이라 선택지는 편집/취소) 편집 → 커밋
    keys(DOWN, ENTER, ENTER, ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert "'task'는 에이전트 전용 타입입니다." in result.output
    assert last_commit(proj) == f"{HUMAN}|exp: fixed after edit"


def test_commit_editor_uses_git_editor(proj, keys, monkeypatch):
    """§18.2 5: 편집기는 Git과 같은 규칙으로 고른다 (core.editor). 인자가 붙은 편집기 문자열도 동작."""
    editor = proj.parent / "fake-editor.sh"
    editor.write_text('#!/bin/sh\nprintf "exp: %s\\n\\nActor: human\\n" "$1" > "$2"\n', encoding="utf-8")
    editor.chmod(0o755)
    git(proj, "config", "core.editor", f"{editor} edited-by-editor")
    write(proj, "a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    keys(DOWN, ENTER, ENTER)  # 편집 → 커밋
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert last_commit(proj) == f"{HUMAN}|exp: edited-by-editor"


def test_commit_rejected_by_git_keeps_draft(proj, keys):
    hook = proj / ".lg/hooks/pre-commit"
    hook.write_text("#!/bin/sh\necho blocked >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    write(proj, "a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    keys(ENTER)
    result = lg("commit")
    assert result.exit_code == 4 and "blocked" in result.output
    assert (proj / ".lg/pending/COMMIT_MSG").exists()


def test_commit_compose_mode(proj, keys):
    write(proj, "experiments/src/a.py")
    # 파일 선택 → 타입 exp(목록의 6번째) → scope 생략 → 요약 → 커밋
    keys(SPACE, ENTER, DOWN * 5, ENTER, ENTER, "add a\r", ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert last_commit(proj) == f"{HUMAN}|exp: add a"
    assert git(proj, "status", "--porcelain") == ""


def trailers(root):
    return git(root, "log", "-1", "--format=%(trailers:only,unfold)")


def test_commit_plan_approve_empty(proj, keys):
    """첫 task 승인: 바뀐 파일 없이 plan + Approve. 하나만 고르면 scope도 그 Task."""
    # 타입 plan(목록의 3번째) → Approve M0-T0 선택 → 요약 → 커밋
    keys(DOWN * 2, ENTER, SPACE, ENTER, "approve initial task\r", ENTER)
    result = lg("commit", "--allow-empty")
    assert result.exit_code == 0, result.output
    assert last_commit(proj) == f"{HUMAN}|plan(M0-T0): approve initial task"
    assert trailers(proj) == "Actor: human\nApprove: M0-T0"
    assert git(proj, "show", "--name-only", "--format=") == ""


def test_commit_plan_approve_several(proj, keys):
    # 두 task를 고르면 scope는 따로 묻는다 (빈 입력이면 생략)
    keys(DOWN * 2, ENTER, SPACE, DOWN, SPACE, ENTER, ENTER, "approve tasks\r", ENTER)
    result = lg("commit", "--allow-empty")
    assert result.exit_code == 0, result.output
    assert last_commit(proj) == f"{HUMAN}|plan: approve tasks"
    assert trailers(proj) == "Actor: human\nApprove: M0-T0, M1-T0"


def test_commit_plan_without_approve(proj, keys):
    """로드맵만 바꾸는 plan 커밋은 Approve를 고르지 않는다."""
    write(proj, "plan/roadmap.md", "changed\n")
    keys(SPACE, ENTER, DOWN * 2, ENTER, ENTER, ENTER, "revise roadmap\r", ENTER)
    result = lg("commit")
    assert result.exit_code == 0, result.output
    assert last_commit(proj) == f"{HUMAN}|plan: revise roadmap"
    assert trailers(proj) == "Actor: human"


def test_commit_nothing_to_commit(proj, tty):
    result = lg("commit")
    assert result.exit_code == 3 and "커밋할 변경이 없습니다" in result.output


# ---------------------------------------------------------------- scripts/session-check (§17.2)


def test_session_check_clean(proj, git_sandbox):
    (proj / ".lg/pending").mkdir()
    (proj / ".lg/pending/HUMAN_FILES").write_text("old\n", encoding="utf-8")
    assert session_check(proj, git_sandbox).stdout == ""
    assert not (proj / ".lg/pending/HUMAN_FILES").exists()


def test_session_check_lists_and_records(proj, git_sandbox):
    write(proj, "notes/a.md")
    write(proj, "README.md", "changed\n")
    git(proj, "mv", "FILEMAP.md", "MAP.md")
    out = session_check(proj, git_sandbox).stdout
    assert "커밋되지 않은 사람의 변경" in out and "commit-prep.md" in out
    recorded = (proj / ".lg/pending/HUMAN_FILES").read_text(encoding="utf-8").splitlines()
    assert recorded == ["FILEMAP.md", "MAP.md", "README.md", "notes/a.md"]
    assert git(proj, "status", "--porcelain", "--", ".lg") == ""  # 기록 파일은 Git 제외


def test_session_check_truncates_long_list(proj, git_sandbox):
    for i in range(25):
        write(proj, f"notes/n{i:02}.md")
    out = session_check(proj, git_sandbox).stdout
    assert out.count("\n  - ") == 20 and "외 5개" in out
    assert len((proj / ".lg/pending/HUMAN_FILES").read_text(encoding="utf-8").splitlines()) == 25


def test_session_check_pending_does_not_record(proj, git_sandbox):
    write(proj, "a.py")
    lg("draft", "--type", "exp", "--summary", "x", "a.py")
    write(proj, "b.py")
    out = session_check(proj, git_sandbox).stdout
    assert "사람 커밋 대기 상태" in out
    assert not (proj / ".lg/pending/HUMAN_FILES").exists()


def test_session_check_outside_git_is_silent(tmp_path, git_sandbox):
    script = tmp_path / "scripts/session-check"
    script.parent.mkdir()
    shutil.copy(commit_module.__file__.replace("commit.py", "templates/static/scripts/session-check"), script)
    result = subprocess.run(["python3", str(script)], cwd=tmp_path, env=git_sandbox, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == ""


@pytest.mark.parametrize("message, from_draft, expected", [
    ("exp: a\n\nActor: human\n", True, "에이전트가 기다리고 있으면"),
    ("gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\n", False, "다음 세션 시작 때"),
    ("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0\n", False, "다음 세션 시작 때"),
    ("plan: revise roadmap\n\nActor: human\n", False, None),
    ("spec: upgrade\n\nActor: human\n", False, "규칙 문서가 바뀌었습니다"),
    ("exp: a\n\nActor: human\n", False, None),
])
def test_next_step_hint(proj, message, from_draft, expected):
    """§18.2 9: 에이전트에게 알릴 필요는 열린 세션이 기다릴 때뿐이다."""
    from labgate.project import find_project
    hint = commit_module.next_step_hint(find_project(proj), message, from_draft)
    assert (hint is None) if expected is None else (expected in hint)
