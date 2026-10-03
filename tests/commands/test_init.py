"""`lg init` 통합 테스트 (설계 문서 §5, §6.3, §10, §14.2)."""
import subprocess
import traceback

import pytest
import yaml

import labgate.cli as cli
import labgate.gitops as gitops
import labgate.writer as writer

from support.cli import CLEAR, CTRL_C, ENTER, lg

CONFIG = {  # init 결과(커밋 본문, AGENTS.md)를 실제 이름으로 확인하므로 support.configs와 따로 둔다
    "schema_version": 1,
    "project": {
        "name": "Capacity-Driven Adaptive State Partitioning",
        "slug": "cap-partition",
        "summary": "Fenwick 분할을 적응 분할로 대체하는 연구",
        "research_question": "같은 state 예산에서 recall이 개선되는가?",
    },
    "people": {"humans": [{"name": "홍길동", "email": "gildong@example.com"}]},
    "milestones": [{"title": "기반 구축"}, {"title": "신호 검증"}, {"title": "적응 분할"}],
}


@pytest.fixture
def cfg(tmp_path):
    path = tmp_path / "cfg.yaml"
    path.write_text(yaml.safe_dump(CONFIG, allow_unicode=True), encoding="utf-8")
    return path


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=check).stdout.strip()


# ---------------------------------------------------------------- §14.2


def test_init_with_config(tmp_path, cfg, git_sandbox):
    target = tmp_path / "proj"
    result = lg("init", target, "--config", cfg)
    assert result.exit_code == 0, result.output
    assert git(target, "rev-list", "--count", "HEAD") == "1"
    assert git(target, "log", "-1", "--format=%an <%ae>|%cn <%ce>") == \
        "홍길동 <gildong@example.com>|홍길동 <gildong@example.com>"
    assert git(target, "log", "-1", "--format=%B") == \
        "init: initialize research project\n\nCapacity-Driven Adaptive State Partitioning\n\nActor: human"
    assert git(target, "config", "core.hooksPath") == ".lg/hooks"
    assert git(target, "branch", "--show-current") == "main"
    assert git(target, "status", "--porcelain") == ""  # §14.3: 생성 직후 깨끗함
    assert len(git(target, "ls-files").splitlines()) == 78
    short = git(target, "rev-parse", "--short", "HEAD")
    assert f"파일 78개, 초기 커밋 {short} (init)" in result.output
    assert "/session-start" in result.output


def test_agent_commit_in_generated_project(tmp_path, cfg, git_sandbox):
    """§14.2 2–3: 만든 프로젝트에서 에이전트 신원과 hook이 연결되어 있다 (hook 규칙 자체는 tools/test_hook.py)."""
    target = tmp_path / "proj"
    assert lg("init", target, "--config", cfg).exit_code == 0
    run = subprocess.run([target / "scripts/agent-commit", "--allow-empty", "-m", "log: test", "-m", "Actor: agent"],
                         cwd=target, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert git(target, "log", "-1", "--format=%an <%ae>") == "research-agent <agent@cap-partition.local>"

    run = subprocess.run([target / "scripts/agent-commit", "--allow-empty", "-m", "gate(M0-T0): approve",
                          "-m", "Actor: agent\nTask: M0-T0\nVerdict: approve\nSource: document"],
                         cwd=target, capture_output=True, text=True)
    assert run.returncode != 0 and "사람 전용 타입" in run.stderr
    assert git(target, "rev-list", "--count", "HEAD") == "2"


def test_dry_run_writes_nothing(tmp_path, cfg, git_sandbox):
    target = tmp_path / "a/proj"
    result = lg("init", target, "--config", cfg, "--dry-run")
    assert result.exit_code == 0, result.output
    assert not (tmp_path / "a").exists()
    assert "파일 78개" in result.output
    assert "│       └── commit-msg *" in result.output  # 트리, 실행 파일 표시


def test_no_git(tmp_path, cfg, git_sandbox):
    target = tmp_path / "proj"
    result = lg("init", target, "--config", cfg, "--no-git")
    assert result.exit_code == 0, result.output
    assert not (target / ".git").exists()
    assert (target / ".lg/hooks/commit-msg").exists()
    assert "Git 초기화 안 함" in result.output and "git init" in result.output


def test_inside_existing_repo(tmp_path, cfg, git_sandbox):
    git(tmp_path, "init", "-q")
    target = tmp_path / "sub/proj"
    result = lg("init", target, "--config", cfg)
    assert result.exit_code == 4
    assert "이미 Git 저장소 안" in result.output and "--no-git" in result.output
    assert not (tmp_path / "sub").exists()
    # --no-git이면 그 저장소 안에 파일만 만든다
    assert lg("init", target, "--config", cfg, "--no-git").exit_code == 0
    # dry-run이면 경고만
    dry = lg("init", tmp_path / "other", "--config", cfg, "--dry-run")
    assert dry.exit_code == 0 and "! 대상이 이미 Git 저장소 안" in dry.output


# ---------------------------------------------------------------- 사용법·대상 폴더 오류


def test_config_requires_path(cfg, git_sandbox):
    result = lg("init", "--config", cfg)
    assert result.exit_code == 2 and "PATH 가 필요합니다" in result.output


def test_invalid_config_lists_all_errors(tmp_path, git_sandbox):
    bad = tmp_path / "bad.yaml"
    data = {**CONFIG, "project": {**CONFIG["project"], "slug": "Bad Slug"}, "milestones": []}
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    result = lg("init", tmp_path / "proj", "--config", bad)
    assert result.exit_code == 2
    assert "project.slug:" in result.output and "milestones:" in result.output
    assert not (tmp_path / "proj").exists()


def test_missing_config_file(tmp_path, git_sandbox):
    result = lg("init", tmp_path / "proj", "--config", tmp_path / "none.yaml")
    assert result.exit_code == 2 and "설정 파일을 읽지 못했습니다" in result.output


def test_target_not_empty(tmp_path, cfg, git_sandbox):
    target = tmp_path / "proj"
    target.mkdir()
    (target / "notes.txt").write_text("mine")
    result = lg("init", target, "--config", cfg)
    assert result.exit_code == 3 and "--force" in result.output


def test_force_adds_files_and_keeps_existing(tmp_path, cfg, git_sandbox):
    target = tmp_path / "proj"
    (target / "notes").mkdir(parents=True)
    (target / "notes/plan.md").write_text("기존 계획")
    result = lg("init", target, "--config", cfg, "--force")
    assert result.exit_code == 0, result.output
    assert (target / "notes/plan.md").read_text() == "기존 계획"
    assert git(target, "status", "--porcelain") == ""


def test_force_with_conflicting_file(tmp_path, cfg, git_sandbox):
    target = tmp_path / "proj"
    target.mkdir()
    (target / "README.md").write_text("mine")
    result = lg("init", target, "--config", cfg, "--force")
    assert result.exit_code == 3
    assert "겹칩니다 (1개)" in result.output and "  README.md" in result.output
    assert sorted(p.name for p in target.iterdir()) == ["README.md"]
    assert (target / "README.md").read_text() == "mine"


def test_target_is_a_file(tmp_path, cfg, git_sandbox):
    (tmp_path / "proj").write_text("x")
    assert lg("init", tmp_path / "proj", "--config", cfg).exit_code == 3


# ---------------------------------------------------------------- Git 오류


def test_git_missing(tmp_path, cfg, git_sandbox, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "_bin"))  # python3만 있음
    result = lg("init", tmp_path / "proj", "--config", cfg)
    assert result.exit_code == 4 and "git 을 실행할 수 없습니다" in result.output


def test_initial_commit_failure_keeps_files(tmp_path, cfg, git_sandbox, monkeypatch):
    monkeypatch.setattr(gitops, "init_message", lambda config: "not a valid message\n")
    target = tmp_path / "proj"
    result = lg("init", target, "--config", cfg)
    assert result.exit_code == 4
    out = result.output
    assert "'초기 커밋 (hook 검사 포함)' 단계가 실패했습니다" in out
    assert "| ✗ 커밋 메시지가 규약" in out  # hook stderr를 그대로 보여 준다
    assert 'git commit -m "init: initialize research project" -m "Actor: human"' in out
    assert (target / "README.md").exists()


# ---------------------------------------------------------------- 중단·예기치 못한 오류


def test_ctrl_c_while_writing_rolls_back(tmp_path, cfg, git_sandbox, monkeypatch):
    real, calls = writer._write_file, {"n": 0}

    def interrupt(path, f):
        calls["n"] += 1
        if calls["n"] == 10:
            raise KeyboardInterrupt
        real(path, f)

    monkeypatch.setattr(writer, "_write_file", interrupt)
    result = lg("init", tmp_path / "proj", "--config", cfg)
    assert result.exit_code == 130 and "중단했습니다" in result.output
    assert sorted(p.name for p in tmp_path.iterdir()) == ["_bin", "cfg.yaml"]


def test_unexpected_error(tmp_path, cfg, git_sandbox, monkeypatch):
    def boom(*a):
        raise ValueError("터졌다")

    monkeypatch.setattr(cli, "build_plan", boom)
    result = lg("init", tmp_path / "proj", "--config", cfg)
    assert result.exit_code == 1
    assert "예기치 못한 오류: ValueError: 터졌다" in result.output and "LG_DEBUG=1" in result.output

    printed = []
    monkeypatch.setattr(traceback, "print_exc", lambda: printed.append(True))
    monkeypatch.setenv("LG_DEBUG", "1")
    assert lg("init", tmp_path / "proj", "--config", cfg).exit_code == 1
    assert printed == [True]


# ---------------------------------------------------------------- 대화형 (§6.3)

def answers(*, path=None, claude=ENTER, extra_humans=(), milestones=("기반 구축",), confirm=ENTER):
    """§6.3 질문 순서대로의 입력. 기본값을 받을 곳은 ENTER."""
    seq = [] if path is None else [f"{path}{ENTER}"]
    seq += ["연구 이름\r", ENTER, "한 줄 요약\r", "연구 질문인가?\r", "홍길동\r", "h@x.com\r"]
    for name, email in extra_humans:
        seq += ["y", f"{name}\r", f"{email}\r"]
    seq += ["n", ENTER, ENTER, claude]
    seq += [f"{t}\r" for t in milestones] + [ENTER, confirm]
    return seq


def test_interactive_creates_project(tmp_path, git_sandbox, keys):
    target = tmp_path / "My Study"
    keys(*answers(extra_humans=[("김철수", "c@x.com")], milestones=("기반 구축", "검증")))
    result = lg("init", target)
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((target / ".lg/project.yaml").read_text(encoding="utf-8"))
    assert data["project"]["slug"] == "my-study"  # 경로에서 만든 기본값
    assert [h["email"] for h in data["people"]["humans"]] == ["h@x.com", "c@x.com"]
    assert data["people"]["agent"] == {"name": "research-agent", "email": "agent@my-study.local"}
    assert [m["title"] for m in data["milestones"]] == ["기반 구축", "검증"]
    assert "이대로 만들까요" not in result.output  # questionary 출력은 DummyOutput으로 간다
    assert "경로:" in result.output and "마일스톤: M0 기반 구축, M1 검증" in result.output


def test_interactive_asks_path_and_uses_git_identity(tmp_path, git_sandbox, keys, monkeypatch):
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = Global Name\n\temail = global@x.com\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    target = tmp_path / "proj"
    seq = answers(path=target)
    seq[5:7] = [ENTER, ENTER]  # 사람 이름·이메일: git 전역 설정 기본값
    keys(*seq)
    result = lg("init", "--no-git")
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((target / ".lg/project.yaml").read_text(encoding="utf-8"))
    assert data["people"]["humans"] == [{"name": "Global Name", "email": "global@x.com"}]


def test_interactive_reasks_invalid_answers(tmp_path, git_sandbox, keys):
    target = tmp_path / "proj"
    keys(
        "연구 이름\r",
        CLEAR, "Bad Slug\r", CLEAR, "good-slug\r",  # slug 규칙 위반 → 다시
        "한 줄 요약\r", "연구 질문?\r", "홍길동\r",
        "not-an-email\r", CLEAR, "h@x.com\r",       # 이메일 형식 → 다시
        "y", "둘\r", "H@X.COM\r", CLEAR, "two@x.com\r",  # 같은 사람 이메일 → 다시
        "n", ENTER, CLEAR, "h@x.com\r", CLEAR, "bot@x.local\r",  # 에이전트 = 사람 이메일 → 다시
        "n",                                         # Claude Code 안 씀
        ENTER, "기반\r", ENTER,                       # 첫 마일스톤 빈 입력 → 다시
        ENTER,
    )
    result = lg("init", target, "--no-git")
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((target / ".lg/project.yaml").read_text(encoding="utf-8"))
    assert data["project"]["slug"] == "good-slug"
    assert [h["email"] for h in data["people"]["humans"]] == ["h@x.com", "two@x.com"]
    assert data["people"]["agent"]["email"] == "bot@x.local"
    assert data["agent_tools"]["claude_code"] is False and not (target / ".claude").exists()
    assert [m["title"] for m in data["milestones"]] == ["기반"]


def test_interactive_checks_target_before_other_questions(tmp_path, git_sandbox, keys):
    target = tmp_path / "proj"
    target.mkdir()
    (target / "x").write_text("x")
    keys(f"{target}\r")  # 경로만 입력: 이름 등을 묻기 전에 실패해야 한다
    result = lg("init")
    assert result.exit_code == 3 and "비어 있지 않습니다" in result.output


def test_interactive_ctrl_c(tmp_path, git_sandbox, keys):
    keys("연구 이름\r", CTRL_C)
    result = lg("init", tmp_path / "proj")
    assert result.exit_code == 130 and "중단했습니다" in result.output
    assert not (tmp_path / "proj").exists()


def test_interactive_decline_confirmation(tmp_path, git_sandbox, keys):
    keys(*answers(confirm="n"))
    result = lg("init", tmp_path / "proj")
    assert result.exit_code == 130 and "만들지 않았습니다" in result.output
    assert not (tmp_path / "proj").exists()


def test_interactive_yes_skips_confirmation(tmp_path, git_sandbox, keys):
    keys(*answers(confirm=""))
    assert lg("init", tmp_path / "proj", "--yes", "--no-git").exit_code == 0


def test_interactive_requires_tty(tmp_path, git_sandbox):
    result = lg("init", tmp_path / "proj")
    assert result.exit_code == 2 and "터미널이 필요합니다" in result.output


def test_interactive_input_closed_counts_as_abort(tmp_path, git_sandbox, keys):
    keys("연구 이름\r")  # 다음 질문에서 입력이 끝남
    result = lg("init", tmp_path / "proj")
    assert result.exit_code == 130 and not (tmp_path / "proj").exists()


def test_user_git_identity_env_does_not_leak_into_init_commit(tmp_path, cfg, git_sandbox, monkeypatch):
    """§10.1: 사용자 환경의 GIT_AUTHOR_*/GIT_COMMITTER_*가 있어도 초기 커밋은 사람 신원."""
    for role in ("AUTHOR", "COMMITTER"):
        monkeypatch.setenv(f"GIT_{role}_NAME", "research-agent")
        monkeypatch.setenv(f"GIT_{role}_EMAIL", "agent@cap-partition.local")
    target = tmp_path / "proj"
    assert lg("init", target, "--config", cfg).exit_code == 0
    assert git(target, "log", "-1", "--format=%ae|%ce") == "gildong@example.com|gildong@example.com"
