"""commit-msg hook과 agent-commit (설계 문서 §11, §12, 부록 C, §14.1 hook 사례).

hook을 임시 Git 저장소에 설치하고 실제 `git commit`으로 검사한다. hook의 `python3`는 PATH 맨 앞에
둔 인터프리터로 실행된다: 기본은 테스트를 돌리는 Python, 환경 변수 `HOOK_PYTHON`이 있으면 그것
(예: `HOOK_PYTHON=/path/to/python3.9`로 §4의 "hook은 Python ≥ 3.9" 확인).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import isolated_git_env
from labgate.render import read_static

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")

HUMAN = ("Human", "h@x.com")
AGENT = ("Agent", "a@x.local")
STRANGER = ("Stranger", "z@y.com")
FIRST_LINE = "✗ 커밋 메시지가 규약(specs/git-commit.md)에 맞지 않습니다:"

GATE_OK = (
    "gate(M1-T2): approve, next M1-T3\n\n"
    "Actor: human\nTask: M1-T2\nVerdict: approve\nSource: document\nNext: M1-T3\n"
)


class Repo:
    def __init__(self, root: Path, env: dict[str, str]):
        self.root, self.env = root, env

    def git(self, *args, author=None, check=True, input=None):
        env = dict(self.env)
        if author:
            env.update(GIT_AUTHOR_NAME=author[0], GIT_AUTHOR_EMAIL=author[1],
                       GIT_COMMITTER_NAME=author[0], GIT_COMMITTER_EMAIL=author[1])
        return subprocess.run(["git", *args], cwd=self.root, env=env, input=input,
                              capture_output=True, text=True, check=check)

    def commit(self, message, author=HUMAN, *extra):
        msg = self.root.parent / "msg.txt"
        msg.write_text(message, encoding="utf-8")
        before = self.count()
        result = self.git("commit", "--allow-empty", "-F", str(msg), *extra, author=author, check=False)
        assert (self.count() == before + 1) == (result.returncode == 0), result.stderr
        return result

    def count(self):
        r = self.git("rev-list", "--count", "HEAD", check=False)
        return int(r.stdout) if r.returncode == 0 else 0


@pytest.fixture
def repo(tmp_path):
    env = isolated_git_env(tmp_path)
    root = tmp_path / "proj"
    (root / ".lg/hooks").mkdir(parents=True)
    hook = root / ".lg/hooks/commit-msg"
    hook.write_text(read_static("dot-lg/hooks/commit-msg"), encoding="utf-8")
    hook.chmod(0o755)
    (root / "scripts").mkdir()
    agent_commit = root / "scripts/agent-commit"
    agent_commit.write_text(read_static("scripts/agent-commit"), encoding="utf-8")
    agent_commit.chmod(0o755)
    (root / ".lg/identities.json").write_text(json.dumps({
        "schema_version": 1,
        "humans": [{"name": HUMAN[0], "email": HUMAN[1]}],
        "agent": {"name": AGENT[0], "email": AGENT[1]},
    }), encoding="utf-8")

    r = Repo(root, env)
    r.git("init", "-q")
    r.git("config", "user.name", HUMAN[0])
    r.git("config", "user.email", HUMAN[1])
    r.git("config", "core.hooksPath", ".lg/hooks")
    return r


def assert_pass(result):
    assert result.returncode == 0, result.stderr


def assert_fail(result, *messages):
    assert result.returncode != 0
    err = result.stderr
    assert FIRST_LINE in err, err
    for m in messages:
        assert m in err, f"{m!r} not in:\n{err}"


# ---------------------------------------------------------------- §14.1 표


def test_hook_runs_with_expected_python(repo):
    """hook이 의도한 인터프리터로 실행되는지 (매트릭스가 hook도 검증하는 전제)."""
    expected = Path(os.environ.get("HOOK_PYTHON", sys.executable))
    out = subprocess.run(["python3", "-c", "import sys; print(sys.version_info[:2])"],
                         env=repo.env, capture_output=True, text=True, check=True).stdout
    want = subprocess.run([str(expected), "-c", "import sys; print(sys.version_info[:2])"],
                          capture_output=True, text=True, check=True).stdout
    assert out == want


def test_human_init(repo):
    assert_pass(repo.commit("init: initialize research project\n\nActor: human\n"))


def test_agent_task(repo):
    assert_pass(repo.commit("task(M1-T2): start signal validation\n\nActor: agent\nTask: M1-T2\n", AGENT))


def test_agent_cannot_use_human_type(repo):
    msg = "gate(M1-T2): approve\n\nActor: agent\nTask: M1-T2\nVerdict: approve\nSource: document\n"
    assert_fail(repo.commit(msg, AGENT), "'gate'는 사람 전용 타입입니다.")


def test_actor_mismatch(repo):
    msg = "task(M1-T2): x\n\nActor: human\nTask: M1-T2\n"
    assert_fail(repo.commit(msg, AGENT), "'task'는 에이전트 타입입니다.",
                "작성자 신원(agent)과 Actor(human)가 다릅니다.")


def test_human_gate(repo):
    assert_pass(repo.commit(GATE_OK))


def test_gate_without_source(repo):
    assert_fail(repo.commit(GATE_OK.replace("Source: document\n", "")),
                "'gate' 커밋에는 Source trailer가 필요합니다")


def test_gate_bad_verdict(repo):
    assert_fail(repo.commit(GATE_OK.replace("Verdict: approve", "Verdict: ok")),
                "gate 커밋에는 Verdict trailer가 필요합니다")


def test_scope_must_match_task(repo):
    msg = "task(M1-T3): x\n\nActor: agent\nTask: M1-T2\n"
    assert_fail(repo.commit(msg, AGENT), "scope(M1-T3)가 Task(M1-T2)와 같아야 합니다.")


def test_missing_actor(repo):
    assert_fail(repo.commit("exp: add model\n", AGENT), "Actor trailer가 필요합니다")


def test_unregistered_author(repo):
    msg = "chore: tidy\n\nActor: human\n"
    assert_fail(repo.commit(msg, STRANGER), "등록되지 않은 작성자입니다: <z@y.com>")


def test_human_decide(repo):
    msg = "decide(D1.3): confirm PR metric\n\nActor: human\nDecisions: D1.3\nSource: conversation\n"
    assert_pass(repo.commit(msg))


def test_human_plan_approve(repo):
    assert_pass(repo.commit("plan(M0-T0): approve initial task\n\nActor: human\nApprove: M0-T0\n"))


@pytest.mark.parametrize("author", [HUMAN, AGENT, STRANGER])
def test_merge_passes(repo, author):
    assert_pass(repo.commit("Merge branch 'x'\n", author))


def test_header_too_long(repo):
    header = "task(M1-T2): " + "x" * 60
    assert len(header) == 73
    assert_fail(repo.commit(f"{header}\n\nActor: agent\nTask: M1-T2\n", AGENT),
                "헤더가 72자를 넘습니다 (73자).")
    assert_pass(repo.commit(f"{header[:-1]}\n\nActor: agent\nTask: M1-T2\n", AGENT))


def test_scissors_line_and_diff_ignored(repo):
    """commit -v: Git은 cleanup 전에 hook을 실행하므로 가위 줄 아래 diff가 메시지에 붙어 온다."""
    msg = (GATE_OK + "# ------------------------ >8 ------------------------\n"
           "# Do not modify or remove the line above.\n"
           "diff --git a/x b/x\n+foo: bar\n+Actor: agent\n")
    assert_pass(repo.commit(msg, HUMAN, "--cleanup=scissors"))


# ---------------------------------------------------------------- §11의 나머지 규칙


@pytest.mark.parametrize(
    "message, error",
    [
        ("no colon here\n\nActor: human\n", "헤더 형식은"),
        ("chore:missing space\n\nActor: human\n", "헤더 형식은"),
        ("chore: x\nActor: human\n", "헤더 다음 줄은 비어 있어야 합니다."),
        ("feat: x\n\nActor: human\n", "알 수 없는 타입입니다: feat"),
        ("chore: x\n\nActor: human\nActor: human\n", "trailer 'Actor'가 중복되었습니다."),
        ("respond(M1-T2): x\n\nActor: human\nSource: document\n", "'respond' 커밋에는 Task trailer가 필요합니다."),
        ("respond(M1-T2): x\n\nActor: human\nTask: M1-T2\n", "'respond' 커밋에는 Source trailer가 필요합니다"),
        ("gate(M1-2): x\n\nActor: human\nTask: M1-2\nVerdict: approve\nSource: document\n", "Task 형식이 잘못되었습니다: M1-2"),
        ("decide: x\n\nActor: human\nSource: document\n", "decide 커밋에는 Decisions trailer가 필요합니다."),
        ("decide: x\n\nActor: human\nSource: document\nDecisions: D1.3, X2\n", "Decisions 형식이 잘못되었습니다: D1.3, X2"),
        ("plan: x\n\nActor: human\nApprove: M0-T0,\n", None),  # 빈 항목은 무시 → 통과
        ("plan: x\n\nActor: human\nApprove: T0\n", "Approve 형식이 잘못되었습니다: T0"),
        (GATE_OK.replace("Next: M1-T3", "Next: later"), "Next 형식이 잘못되었습니다: later"),
        (GATE_OK.replace("Next: M1-T3", "Next: none"), None),
        (GATE_OK + "Milestone-Verdict: maybe\n", "Milestone-Verdict 값이 잘못되었습니다: maybe"),
        (GATE_OK + "Milestone-Verdict: conditional\n", None),
        (GATE_OK + "Refs: anything goes here\nReview: M1-T2_gate-01\n", None),
        ("chore: x\n\nActor: human\nnot a trailer line\n", "Actor trailer가 필요합니다"),
        ("chore: x\n\n# 주석은 무시\nActor: human\n# 끝 주석\n", None),
        ("chore: x\n\n본문 문단.\n\nActor: human\n", None),
    ],
)
def test_other_rules(repo, message, error):
    result = repo.commit(message, HUMAN, "--cleanup=verbatim")
    if error is None:
        assert_pass(result)
    else:
        assert_fail(result, error)


@pytest.mark.parametrize("header", ["Revert \"x\"", "fixup! x", "squash! x", "amend! x"])
def test_passthrough_prefixes(repo, header):
    assert_pass(repo.commit(f"{header}\n", STRANGER))


def test_all_errors_reported_together(repo):
    msg = "gate(M1-T3): x\n\nActor: agent\nTask: M1-T2\nVerdict: ok\n"
    assert_fail(repo.commit(msg, AGENT), "사람 전용 타입", "scope(M1-T3)", "Source trailer", "Verdict trailer")


def test_author_email_case_insensitive(repo):
    assert_pass(repo.commit("chore: x\n\nActor: human\n", ("H", "H@X.COM")))


def test_author_flag_is_seen_by_hook(repo):
    """§12: hook은 --author로 지정한 작성자도 인식한다 (agent-commit이 --author를 막는 이유)."""
    result = repo.commit("chore: x\n\nActor: human\n", HUMAN, "--author", f"{AGENT[0]} <{AGENT[1]}>")
    assert_fail(result, "작성자 신원(agent)과 Actor(human)가 다릅니다.")


def test_broken_identities_reported(repo):
    (repo.root / ".lg/identities.json").write_text("{not json", encoding="utf-8")
    assert_fail(repo.commit("chore: x\n\nActor: human\n"), ".lg/identities.json을 읽지 못했습니다")


# ---------------------------------------------------------------- agent-commit (§12, C.2)


def agent_commit(repo, *args):
    return subprocess.run([str(repo.root / "scripts/agent-commit"), *args], cwd=repo.root,
                          env=repo.env, capture_output=True, text=True)


def test_agent_commit_uses_agent_identity(repo):
    result = agent_commit(repo, "--allow-empty", "-m", "log: test", "-m", "Actor: agent")
    assert result.returncode == 0, result.stderr
    ident = repo.git("log", "-1", "--format=%an <%ae>|%cn <%ce>").stdout.strip()
    assert ident == "Agent <a@x.local>|Agent <a@x.local>"


def test_agent_commit_rejected_by_hook_for_human_type(repo):
    result = agent_commit(repo, "--allow-empty", "-m", "gate(M0-T0): approve",
                          "-m", "Actor: agent\nTask: M0-T0\nVerdict: approve\nSource: document")
    assert_fail(result, "'gate'는 사람 전용 타입입니다.")


@pytest.mark.parametrize("flag", ["--no-verify", "-n", "--author", "--author=Human <h@x.com>"])
def test_agent_commit_blocks_flags(repo, flag):
    before = repo.count()
    result = agent_commit(repo, "--allow-empty", flag, "-m", "log: x", "-m", "Actor: agent")
    assert result.returncode == 2
    assert f"'{flag}' 옵션은 사용할 수 없습니다" in result.stderr
    assert repo.count() == before
