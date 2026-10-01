"""수용 기준 (설계 문서 §14.3). 설치된 `lg` 실행 파일을 별도 프로세스로 실행해 사람이 쓰는 그대로 확인한다."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from conftest import isolated_git_env

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git 없음")

LG = Path(sys.executable).with_name("lg")
NO_FRONTMATTER = {"README.md", "AGENTS.md", "CLAUDE.md"}  # conventions §4 예외 (+ .claude/ 아래)


def config_yaml(milestones, claude_code, **project):
    return {
        "schema_version": 1,
        "project": {
            "name": "Capacity-Driven Adaptive State Partitioning",
            "slug": "cap-partition",
            "summary": "Fenwick 분할을 적응 분할로 대체하는 연구",
            "research_question": "같은 state 예산에서 recall이 개선되는가?",
            **project,
        },
        "people": {"humans": [{"name": "홍길동", "email": "gildong@example.com"}]},
        "agent_tools": {"claude_code": claude_code},
        "milestones": [{"title": f"마일스톤 {i}"} for i in range(milestones)],
    }


class Project:
    def __init__(self, tmp_path, data):
        self.env = isolated_git_env(tmp_path)
        cfg = tmp_path / "cfg.yaml"
        cfg.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        self.root = tmp_path / "proj"
        self.result = subprocess.run([str(LG), "init", str(self.root), "--config", str(cfg)],
                                     env=self.env, capture_output=True, text=True)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env,
                              capture_output=True, text=True, check=True).stdout.strip()

    def sh(self, command):
        return subprocess.run(["bash", "-c", command], cwd=self.root, env=self.env,
                              capture_output=True, text=True)

    def markdown(self):
        return [p for p in self.root.rglob("*.md") if ".git" not in p.relative_to(self.root).parts]


def approve_command(output):
    """§5.4 안내문에서 M0-T0 승인 명령(두 줄)을 그대로 꺼낸다."""
    lines = output.splitlines()
    i = next(n for n, l in enumerate(lines) if "git commit --allow-empty" in l)
    return lines[i].strip() + "\n" + lines[i + 1].strip()


@pytest.mark.parametrize("milestones", [1, 20])
@pytest.mark.parametrize("claude_code", [True, False], ids=["claude", "no-claude"])
def test_acceptance(tmp_path, milestones, claude_code):
    p = Project(tmp_path, config_yaml(milestones, claude_code))

    # 생성 성공 (마일스톤 1개, 20개)
    assert p.result.returncode == 0, p.result.stderr
    count = (49 if claude_code else 42) + 6 * milestones
    assert f"파일 {count}개" in p.result.stdout
    assert len(p.git("ls-files").splitlines()) == count

    # 생성 직후 git status가 깨끗함
    assert p.git("status", "--porcelain", "--ignored") == ""

    # 모든 Markdown에 렌더링되지 않은 템플릿 문법이 없고, frontmatter가 파싱된다
    for md in p.markdown():
        text = md.read_text(encoding="utf-8")
        rel = md.relative_to(p.root)
        assert "{{" not in text and "{%" not in text, rel
        if text.startswith("---\n"):
            fm = yaml.safe_load(text[4 : text.index("\n---\n", 4)])
            assert {"id", "type", "spec_version"} <= fm.keys(), rel
        else:
            assert str(rel) in NO_FRONTMATTER or rel.parts[0] in (".claude",), rel

    # §5.4 안내대로 M0-T0 승인 커밋을 실행하면 hook을 통과한다
    command = approve_command(p.result.stdout)
    run = p.sh(command)
    assert run.returncode == 0, f"{command}\n{run.stderr}"
    assert p.git("log", "--format=%s|%ae").splitlines() == [
        "plan(M0-T0): approve initial task|gildong@example.com",
        "init: initialize research project|gildong@example.com",
    ]
    assert p.git("log", "-1", "--format=%(trailers:only,unfold)") == "Actor: human\nApprove: M0-T0"


def test_approve_together_with_card_status(tmp_path):
    """§5.4 괄호 안내: M0-T0 카드의 status를 approved로 바꿔 같은 plan 커밋에 넣어도 통과한다."""
    p = Project(tmp_path, config_yaml(3, True))
    card = p.root / "plan/milestones/M0/tasks/M0-T0.md"
    card.write_text(card.read_text(encoding="utf-8").replace("status: draft", "status: approved", 1),
                    encoding="utf-8")
    run = p.sh(f"git add {card.relative_to(p.root)} && " + approve_command(p.result.stdout).replace(
        "--allow-empty ", ""))
    assert run.returncode == 0, run.stderr
    assert p.git("show", "--stat", "--format=%s").splitlines()[0] == "plan(M0-T0): approve initial task"
    assert p.git("status", "--porcelain") == ""


def test_user_braces_are_kept_and_generation_succeeds(tmp_path):
    """사용자 입력의 `{{`, `{%`는 출력에 그대로 들어가고 생성은 성공한다 (§9, §14.3)."""
    name = "{{Transformer}} 분할 $O(n^{{2}})$"
    p = Project(tmp_path, config_yaml(1, True, name=name, research_question="{% 주석 %} 질문?"))
    assert p.result.returncode == 0, p.result.stderr
    assert (p.root / "README.md").read_text(encoding="utf-8").startswith(f"# {name}\n")
    assert p.git("log", "-1", "--format=%B").splitlines()[2] == name
    assert p.git("status", "--porcelain") == ""


def test_lg_version_entry_point(tmp_path):
    from labgate import __version__

    out = subprocess.run([str(LG), "--version"], capture_output=True, text=True, check=True).stdout
    assert re.fullmatch(rf"labgate {re.escape(__version__)}\n", out)


def test_worktree_for_experiment_isolation(tmp_path):
    """시나리오 §6.3: 워크트리는 실험 격리용. 안에서도 hook이 돌고, main은 깨끗하며, 병합은 막힌다."""
    p = Project(tmp_path, config_yaml(1, True))
    assert p.result.returncode == 0, p.result.stderr
    p.git("worktree", "add", "-q", ".claude/worktrees/exp", "-b", "worktree-exp")
    wt = p.root / ".claude/worktrees/exp"
    agent_commit = [str(wt / "scripts/agent-commit"), "--allow-empty"]

    ok = subprocess.run(agent_commit + ["-m", "exp: try idea", "-m", "Actor: agent"],
                        cwd=wt, env=p.env, capture_output=True, text=True)
    assert ok.returncode == 0, ok.stderr
    bad = subprocess.run(agent_commit + ["-m", "exp: no trailer"],
                         cwd=wt, env=p.env, capture_output=True, text=True)
    assert bad.returncode != 0 and "Actor trailer가 필요합니다" in bad.stderr

    assert p.git("status", "--porcelain") == ""  # .claude/worktrees/ 는 무시된다

    merge = p.sh("GIT_AUTHOR_NAME=research-agent GIT_AUTHOR_EMAIL=agent@cap-partition.local "
                 "git merge --no-ff worktree-exp -m \"Merge branch 'worktree-exp'\"")
    assert merge.returncode != 0 and "에이전트는 병합 커밋을 만들 수 없습니다" in merge.stderr


def test_claude_code_attribution_disabled(tmp_path):
    """시나리오 §6.2: 생성된 Claude Code 설정이 공동 작성자 줄을 끈다."""
    import json

    p = Project(tmp_path, config_yaml(1, True))
    settings = json.loads((p.root / ".claude/settings.json").read_text(encoding="utf-8"))
    assert settings["attribution"]["commit"] == ""
