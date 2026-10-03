"""`scripts/session-check` (설계 문서 §17.2): 세션 시작 때 사람의 변경, 초안, 반영 상태를 알린다."""
import shutil

from support.env import STATIC_DIR

CARD0 = "plan/milestones/M0/tasks/M0-T0.md"
MILESTONE0 = "plan/milestones/M0/milestone.md"


# ---------------------------------------------------------------- 사람의 변경


def test_clean_tree_prints_nothing_and_clears_record(project):
    project.write(".lg/pending/HUMAN_FILES", "old\n")
    assert project.session_check() == ""
    assert not (project / ".lg/pending/HUMAN_FILES").exists()


def test_lists_and_records_human_changes(project):
    project.write("notes/a.md")
    project.write("README.md", "changed\n")
    project.git("mv", "FILEMAP.md", "MAP.md")
    out = project.session_check()
    assert "커밋되지 않은 사람의 변경" in out and "commit-prep.md" in out
    recorded = project.read(".lg/pending/HUMAN_FILES").splitlines()
    assert recorded == ["FILEMAP.md", "MAP.md", "README.md", "notes/a.md"]
    assert project.git("status", "--porcelain", "--", ".lg") == ""  # 기록 파일은 Git 제외


def test_truncates_long_list(project):
    for i in range(25):
        project.write(f"notes/n{i:02}.md")
    out = project.session_check()
    assert out.count("\n  - ") == 20 and "외 5개" in out
    assert len(project.read(".lg/pending/HUMAN_FILES").splitlines()) == 25


def test_outside_git_is_silent(tmp_path, git_sandbox):
    from support.project import Project
    script = tmp_path / "scripts/session-check"
    script.parent.mkdir()
    shutil.copy(STATIC_DIR / "scripts/session-check", script)
    result = Project(tmp_path, git_sandbox).script("session-check")
    assert result.returncode == 0 and result.stdout == ""


# ---------------------------------------------------------------- 초안과 반영 (사람 커밋 대기, 반영 대기)


def test_reports_unreflected_human_commits(project):
    sha = project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    out = project.session_check()
    assert "반영되지 않은 사람 커밋" in out and "gate-apply.md" in out and sha[:7] in out


def test_cleans_draft_committed_with_git(project):
    message = "exp: add a\n\nActor: human\n"
    project.write("a.py", "x\n")
    project.git("add", "a.py")
    project.write(".lg/pending/COMMIT_MSG", message)
    project.run("git", "commit", "-q", "-F", ".lg/pending/COMMIT_MSG")  # lg commit 대신 git commit
    out = project.session_check()
    assert "이미 커밋한 초안을 정리했습니다" in out
    assert not (project.root / ".lg/pending/COMMIT_MSG").exists()
    assert "사람 커밋 대기 상태" not in out


def test_pending_draft_is_kept_and_not_recorded(project):
    """초안이 있으면(사람 커밋 대기 상태) 초안을 두고, 사람의 변경을 기록하지 않는다."""
    project.write("a.py")
    project.git("add", "a.py")
    project.write(".lg/pending/COMMIT_MSG", "exp: x\n\nActor: human\n")  # lg draft가 만드는 상태
    project.write("b.py")
    out = project.session_check()
    assert "사람 커밋 대기 상태" in out
    assert (project / ".lg/pending/COMMIT_MSG").exists()
    assert not (project / ".lg/pending/HUMAN_FILES").exists()


def test_tidy_cleans_after_commit(project):
    project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    result = project.apply()
    assert project.read(".lg/pending/APPLY_PATHS").splitlines() == [MILESTONE0, CARD0]
    project.commit_apply(result)
    out = project.session_check()
    assert "커밋된 반영 기록을 정리했습니다" in out
    assert not (project.root / ".lg/pending/APPLY_MSG").exists() and not (project.root / ".lg/pending/APPLY_PATHS").exists()
    assert project.session_check() == ""


def test_interrupted_apply_is_not_human_change(project):
    """반영한 뒤 커밋 전에 세션이 끝났다: 그 변경은 사람의 변경이 아니라 커밋 대기 중인 반영이다."""
    sha = project.human("plan(M0-T0): approve\n\nActor: human\nApprove: M0-T0")
    project.apply()
    project.write("notes/mine.md", "사람 메모\n")  # 진짜 사람의 변경은 그대로 잡힌다
    out = project.session_check()
    assert f"사람 커밋({sha[:7]})을 반영했지만 아직 커밋하지 않았습니다" in out
    assert f"scripts/agent-commit -F .lg/pending/APPLY_MSG -- {MILESTONE0} {CARD0}" in out
    assert "반영되지 않은 사람 커밋" not in out
    assert (project.root / ".lg/pending/HUMAN_FILES").read_text(encoding="utf-8").splitlines() == ["notes/mine.md"]


