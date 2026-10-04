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

    def run(self, *args, check=True, input=None):
        return subprocess.run([str(a) for a in args], cwd=self.root, env=self.env, input=input,
                              capture_output=True, text=True, check=check)

    def git(self, *args, check=True):
        return self.run("git", *args, check=check).stdout.strip()

    def lg(self, *args):
        return lg(*args, cwd=self.root)

    def script(self, name, *args, check=False, input=None):
        """생성된 Python 스크립트 (`scripts/<name>`)."""
        return self.run("python3", self.root / "scripts" / name, *args, check=check, input=input)

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

    def apply(self, *args, input=None):
        return self.script("apply-human-commits", *args, input=input)

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


    # ------------------------------------------------------------ 에이전트 쪽 문서 (테스트 준비)

    def add_card(self, task, status="draft", title="다음 작업"):
        """카드와 마일스톤 표의 행을 더한다."""
        milestone = task.split("-")[0]
        base = self.read(f"plan/milestones/{milestone}/tasks/{milestone}-T0.md")  # 생성된 카드를 본뜬다
        text = re.sub(r"^id: .*$", f"id: {task}", base, count=1, flags=re.M)
        text = re.sub(r"^title: .*$", f'title: "{title}"', text, count=1, flags=re.M)
        text = re.sub(r"^status: .*$", f"status: {status}", text, count=1, flags=re.M)
        self.write(f"plan/milestones/{milestone}/tasks/{task}.md", text.replace(f"{milestone}-T0", task))
        table = f"plan/milestones/{milestone}/milestone.md"
        first = f"| `{milestone}-T0` |"
        self.write(table, self.read(table).replace(
            first, f"| `{task}` | {title} | {status} | [{task}](tasks/{task}.md) |\n{first}", 1))

    def add_decision(self, decision_id, status="proposed", title="코어"):
        self.write(f"decisions/{decision_id}_core.md",
                   f"---\nid: {decision_id}\ntype: decision\ntitle: \"{title}\"\nstatus: {status}\nupdated: 2026-01-01\n---\n# {decision_id}\n")
        self.write("decisions/index.md", self.read("decisions/index.md")
                   + f"| {decision_id} | {title} | {status} | M0 | – | [문서]({decision_id}_core.md) |\n")

    def request_gate(self, task="M0-T0", proposed_next=None, decisions=(), commit=True):
        """에이전트의 게이트 요청 (절차 task-gate): 카드를 in-review로, 요청서를 쓰고 커밋한다."""
        card = f"plan/milestones/{task.split('-')[0]}/tasks/{task}.md"
        review_id = f"{task}_gate-01"
        self.set_status(card, "in-review")
        self.write(f"reviews/open/{review_id}.md", review_doc(
            review_id, "gate", task, proposed_next, decisions,
            "## 요약\n\n했다.\n\n## 완료 기준 점검\n\n| 기준 | 충족 | 근거 |\n|---|---|---|\n| 끝낸다 | ✓ | `README.md` |\n\n"
            "## 예상과 달랐던 점\n\n없음\n\n## 확정이 필요한 결정\n\n없음\n\n## 다음 task 제안\n\n계획대로.\n"))
        if commit:
            self.agent(f"review({task}): request gate\n\nActor: agent\nTask: {task}\nReview: {review_id}",
                       card, f"reviews/open/{review_id}.md")
        return review_id

    def escalate(self, task="M0-T0", options=("A안", "B안"), decisions=()):
        """에이전트의 에스컬레이션 (절차 escalate): 카드를 blocked로, 요청서를 쓰고 커밋한다."""
        card = f"plan/milestones/{task.split('-')[0]}/tasks/{task}.md"
        review_id = f"{task}_esc-01"
        self.set_status(card, "blocked")
        body = "## 상황\n\n막혔다.\n\n## 선택지\n\n" + "".join(f"### {o}\n\n설명\n\n" for o in options)
        self.write(f"reviews/open/{review_id}.md",
                   review_doc(review_id, "escalation", task, None, decisions, body + "## 추천\n\nA안\n"))
        self.agent(f"review({task}): escalate\n\nActor: agent\nTask: {task}\nReview: {review_id}",
                   card, f"reviews/open/{review_id}.md")
        return review_id


def review_doc(review_id, kind, task, proposed_next, decisions, body):
    """specs/templates/review.md 모양의 요청서 (응답은 하위 제목만)."""
    return (f"---\nid: {review_id}\ntype: review\nspec_version: 5\nkind: {kind}\ntask: {task}\nstatus: open\n"
            f"requested: 2026-10-03\nanswered: null\nverdict: null\nsource: null\n"
            f"decisions: [{', '.join(decisions)}]\nproposed_next: {proposed_next or 'null'}\nupdated: 2026-10-03\n---\n"
            f"# {review_id}\n\n{body}\n## 응답\n\n### 판정\n\n### 코멘트\n\n### 확정 결정\n\n### 다음 task 승인\n")


def init_project(tmp_path, env, data=None, name="proj"):
    """`lg init --config`로 프로젝트를 만든다."""
    cfg = write_config(tmp_path / "cfg.yaml", data or project_config())
    root = tmp_path / name
    result = lg("init", root, "--config", cfg)
    assert result.exit_code == 0, result.output
    return Project(root, env)
