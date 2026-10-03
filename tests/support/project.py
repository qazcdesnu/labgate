"""`lg init`으로 만든 실제 프로젝트를 다루는 `Project`.

사람 커밋은 `git commit`(hook 통과), 에이전트 커밋은 `scripts/agent-commit`으로 만든다. 생성 스크립트는
`python3`(= HOOK_PYTHON)로 실행한다. 모든 명령은 격리된 Git 환경(`isolated_git_env`)에서 돈다.
"""
import json
import re
import subprocess

import yaml

from support.cli import lg
from support.configs import project_config, write_config

APPLY_COMMAND = re.compile(r"^커밋: (scripts/agent-commit [^(]+?)\s*(\(|$)", re.M)


class Project:
    def __init__(self, root, env):
        self.root, self.env = root, env

    def __truediv__(self, rel):
        return self.root / rel

    # ------------------------------------------------------------ 파일

    def read(self, rel):
        return (self.root / rel).read_text(encoding="utf-8")

    def write(self, rel, text="x\n"):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def status(self, rel):
        """문서 frontmatter의 status."""
        return re.search(r"^status: *(\S+)", self.read(rel), re.M).group(1)

    def set_status(self, rel, value):
        self.write(rel, re.sub(r"^status: *\S+", f"status: {value}", self.read(rel), count=1, flags=re.M))

    def yaml(self):
        return yaml.safe_load(self.read(".lg/project.yaml"))

    @property
    def agent_email(self):
        return json.loads(self.read(".lg/identities.json"))["agent"]["email"]

    # ------------------------------------------------------------ 명령

    def run(self, *args, check=True):
        return subprocess.run([str(a) for a in args], cwd=self.root, env=self.env,
                              capture_output=True, text=True, check=check)

    def git(self, *args, check=True):
        return self.run("git", *args, check=check).stdout.strip()

    def lg(self, *args):
        return lg(*args, cwd=self.root)

    def script(self, name, *args, check=False):
        """생성된 Python 스크립트 (`scripts/<name>`)."""
        return self.run("python3", self.root / "scripts" / name, *args, check=check)

    # ------------------------------------------------------------ 커밋

    def human(self, message, *paths, all=False, no_verify=False):
        """사람 신원 커밋. paths만 stage한다 (all이면 전부). 빈 커밋도 된다."""
        if all:
            self.git("add", "-A")
        elif paths:
            self.git("add", "--", *paths)
        self.git("commit", "-q", "--allow-empty", *(["--no-verify"] if no_verify else []), "-m", message)
        return self.git("rev-parse", "HEAD")

    def agent(self, message, *paths, no_verify=False):
        """에이전트 신원 커밋 (`scripts/agent-commit`). no_verify면 hook을 우회한 커밋을 git으로 직접 만든다
        (agent-commit은 우회를 거부하므로)."""
        if paths:  # 새 파일은 pathspec 커밋에 쓸 수 없으므로 먼저 stage한다
            self.git("add", "-A", "--", *paths)
        if no_verify:
            self.git("-c", "user.name=research-agent", "-c", f"user.email={self.agent_email}",
                     "commit", "-q", "--allow-empty", "--no-verify", "-m", message)
        else:
            self.run(self.root / "scripts/agent-commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def last_commit(self):
        return self.git("log", "-1", "--format=%ae|%s")

    def trailers(self):
        return self.git("log", "-1", "--format=%(trailers:only,unfold)")

    # ------------------------------------------------------------ 반영 (에이전트가 하는 일)

    def session_check(self):
        return self.script("session-check", check=True).stdout

    def apply(self, *args):
        return self.script("apply-human-commits", *args)

    def commit_apply(self, result):
        """apply-human-commits가 출력한 커밋 명령을 그대로 실행한다."""
        self.run("bash", "-c", APPLY_COMMAND.search(result.stdout).group(1))
        return self.git("rev-parse", "HEAD")

    def approve_and_start(self, task="M0-T0"):
        """정상 흐름: 사람 승인 → 반영 → 착수."""
        self.human(f"plan({task}): approve\n\nActor: human\nApprove: {task}")
        self.commit_apply(self.apply())
        card = f"plan/milestones/{task.split('-')[0]}/tasks/{task}.md"
        self.set_status(card, "in-progress")
        self.agent(f"task({task}): start\n\nActor: agent\nTask: {task}", card)


def init_project(tmp_path, env, data=None, name="proj"):
    """`lg init --config`로 프로젝트를 만든다."""
    cfg = write_config(tmp_path / "cfg.yaml", data or project_config())
    root = tmp_path / name
    result = lg("init", root, "--config", cfg)
    assert result.exit_code == 0, result.output
    return Project(root, env)
