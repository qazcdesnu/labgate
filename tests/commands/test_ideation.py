"""ideation (설계 문서 §26): 기준 잠그기 → 후보 평가 → lg ideas → 고르기 → brief 확정 → lg init --from."""
import re

import pytest
import yaml

from support.cli import DOWN, ENTER, SPACE, lg
from support.configs import HUMAN, project_config, write_config
from support.project import init_project

CRITERIA = "plan/criteria.md"


@pytest.fixture
def idea_project(tmp_path, git_sandbox):
    return init_project(tmp_path, git_sandbox, project_config(kind="ideation", milestones=()), name="idea")


def gate(p, task, extra="", review=None):
    """사람의 gate 승인 커밋을 만들고 반영까지 한다 (에이전트가 하는 반영 포함)."""
    card = f"plan/milestones/{task.split('-')[0]}/tasks/{task}.md"
    if p.status(card) == "draft":
        p.approve_and_start(task)
    p.set_status(card, "in-review")
    p.agent(f"review({task}): request gate\n\nActor: agent\nTask: {task}", card)
    p.human(f"gate({task}): approve\n\nActor: human\nTask: {task}\nVerdict: approve\nSource: document\n"
            f"Next: none{extra}")
    p.commit_apply(p.apply())


def write_idea(p, n, title, scores, criteria_commit, status="candidate"):
    rows = "".join(f"| {c} | {v} | {e} | 중 |\n" for c, (v, e) in scores.items())
    p.write(f"ideas/I{n}_{title}.md",
            f"---\nid: I{n}\ntype: idea\nspec_version: 7\ntitle: \"{title}\"\nstatus: {status}\norigin: agent\n"
            f"merged_into: null\ndecision: null\ncreated: 2026-10-05\nupdated: 2026-10-05\n---\n# I{n}. {title}\n\n"
            f"## 한 줄 주장\n\n주장\n\n## 평가 (기준 {criteria_commit})\n\n| 기준 | 점수 | 근거 | 확신 |\n|---|---|---|---|\n"
            f"{rows}\n## 판단 기록\n\n")


def scores(c1, rest=3, evidence="`ref1` Table 1"):
    s = {"C1": (c1, evidence)}
    s.update({f"C{i}": (rest, evidence) for i in range(2, 8)})
    s["C8"] = ("(사람)", "")
    return s


# ---------------------------------------------------------------- 만들기


def test_init_ideation_defaults(idea_project):
    p = idea_project
    assert [m["title"] for m in p.yaml()["milestones"]] == ["지형 파악과 후보 생성", "후보 검증과 방향 선택"]
    for path in (CRITERIA, "ideas/index.md", "brief.md", "specs/doc-types/idea.spec.md", "specs/doc-types/criteria.spec.md"):
        assert (p / path).exists(), path
    assert not (p / "paper").exists()
    agents = p.read("AGENTS.md")
    assert "- 탐색 주제: " in agents and "`plan/criteria.md`" in agents and "`→ selected | dropped`" in agents
    assert p.status(CRITERIA) == "draft"
    assert "C8 | 연구자 적합성" in p.read(CRITERIA)


# ---------------------------------------------------------------- 기준 잠그기와 평가


def test_first_gate_locks_criteria(idea_project):
    p = idea_project
    gate(p, "M0-T0")
    assert p.status(CRITERIA) == "locked"
    locked = re.search(r"^locked_commit: '?([0-9a-f]+)'?$", p.read(CRITERIA), re.M).group(1)
    assert p.git("log", "--format=%h", "--grep", "gate(M0-T0)").startswith(locked[:7])
    assert p.lg("verify").exit_code == 0  # 반영 커밋은 G4 위반이 아니다 (Applies 근거)


def test_evaluation_before_lock_is_flagged(idea_project):
    p = idea_project
    write_idea(p, 1, "early", scores(4), "0000000")
    p.agent("propose(I1): early idea\n\nActor: agent", "ideas")
    out = p.lg("ideas").output
    assert "기준이 잠기기 전" in out
    result = p.lg("verify", "--all")
    assert result.exit_code == 3 and "기준이 잠기기 전의 평가" in result.output


def test_lg_ideas_compares_ranks_and_flags(idea_project):
    p = idea_project
    gate(p, "M0-T0")
    current = re.search(r"기준 버전 ([0-9a-f]+)", p.lg("ideas").output).group(1)
    assert not p.git("log", "-1", "--format=%s", current).startswith("log(M0-T0): apply")
    assert f"## 평가 (기준 {current})" in p.lg("ideas").output
    write_idea(p, 1, "cost", scores(2, rest=3), current)
    write_idea(p, 2, "expressivity", scores(5, rest=4), current)
    write_idea(p, 3, "scooped", scores(1, rest=5), current)            # C1 결격
    bad = scores(4)
    bad["C2"] = (5, "")                                                # 근거 없는 점수
    write_idea(p, 4, "noevidence", bad, current)
    p.agent("propose(M1): evaluate candidates\n\nActor: agent", "ideas")
    result = p.lg("ideas")
    assert result.exit_code == 0, result.output
    lines = {l.split()[0]: l for l in result.output.splitlines() if re.match(r"^  I\d", l)}
    assert lines["I2"].rstrip().endswith(" 1") and lines["I1"].rstrip().endswith(" 3")  # 순위: I2, I4, I1
    assert "결격" in lines["I3"]
    assert "5!" in lines["I4"] and "I4: C2: 근거 없는 점수 (무효)" in result.output
    data = __import__("json").loads(p.lg("ideas", "--json").output)
    assert {r["id"]: r["total"] for r in data["ideas"]}["I2"] == pytest.approx(4.2)  # (3·5 + 4·(3+2+2+2+1)) / 15
    # 기준이 바뀌면 모든 평가가 '기준 변경 전'이 되고 순위에서 빠진다
    p.write(CRITERIA, p.read(CRITERIA).replace("| C7 | 결과의 견고성 | 가설이 틀려도(음성 결과) 논문·학위 논문의 한 장이 되는가 | 에이전트 | 1 |",
                                               "| C7 | 결과의 견고성 | 가설이 틀려도(음성 결과) 논문·학위 논문의 한 장이 되는가 | 에이전트 | 2 |"))
    p.human("plan: raise C7 weight\n\nActor: human", CRITERIA)
    out = p.lg("ideas").output
    assert out.count("기준 변경 전의 평가") == 4


def test_agent_cannot_lock_or_edit_criteria(idea_project):
    p = idea_project
    p.set_status(CRITERIA, "locked")
    p.agent("chore: lock\n\nActor: agent", CRITERIA)
    out = p.lg("verify").output
    assert "✗ V2" in out and "draft → locked" in out
    assert "✗ V4" in out and "plan/criteria.md" in out


# ---------------------------------------------------------------- 고르기와 brief


def fill_brief(p, refs=("ref1",)):
    text = p.read("brief.md")
    text = text.replace("question: null", 'question: "표현력이 정확도를 정하는가?"').replace("summary: null", 'summary: "표현력 연구"')
    text = text.replace("milestones: []", 'milestones: ["기준선 재현", "표현력 사다리"]')
    text = text.replace("selected: []", "selected: [I2]").replace("dropped: []", "dropped: [I1]")
    text = text.replace("references: []", f"references: [{', '.join(refs)}]")
    p.write("brief.md", text)


def test_last_gate_selects_drops_and_confirms_brief(idea_project, keys):
    p = idea_project
    gate(p, "M0-T0")
    current = re.search(r"기준 버전 ([0-9a-f]+)", p.lg("ideas").output).group(1)
    write_idea(p, 1, "cost", scores(2), current)
    write_idea(p, 2, "expressivity", scores(5, rest=4), current)
    p.write("ideas/index.md", p.read("ideas/index.md") + "| `I1` | cost | candidate | agent | [I1](I1_cost.md) |\n"
                                                         "| `I2` | expressivity | candidate | agent | [I2](I2_expressivity.md) |\n")
    fill_brief(p)
    p.agent("propose(M1): candidates and brief\n\nActor: agent", "ideas", "brief.md")
    p.approve_and_start("M1-T0")
    review = p.request_gate("M1-T0", commit=False)
    path = f"reviews/open/{review}.md"
    p.write(path, p.read(path).replace("decisions: []", "decisions: []\nideas: [I1, I2]"))
    p.agent("review(M1-T0): request gate\n\nActor: agent\nTask: M1-T0", "plan", path)
    # approve → 마일스톤 판정 go → 고를 후보: I2 → 버릴 후보: I1 → 이유 → 코멘트 → 커밋
    keys(ENTER, DOWN, ENTER, DOWN, SPACE, ENTER, SPACE, ENTER, "선점됨\r", ENTER, ENTER)
    result = p.lg("answer")
    assert result.exit_code == 0, result.output
    assert "Select: I2" in p.trailers() and "Drop: I1" in p.trailers() and "Milestone-Verdict: go" in p.trailers()
    assert "ideas/I2_expressivity.md: status candidate → selected" in result.output
    assert "brief.md: status draft → confirmed" in result.output
    p.commit_apply(p.apply())
    assert p.status("ideas/I2_expressivity.md") == "selected" and p.status("ideas/I1_cost.md") == "dropped"
    assert "| `I2` | expressivity | selected |" in p.read("ideas/index.md")
    assert p.status("brief.md") == "confirmed"
    assert "go_nogo: go" in p.read("plan/milestones/M1/milestone.md")
    assert "- 버림: I1 (선점됨)" in p.read(f"reviews/closed/{review}.md")


# ---------------------------------------------------------------- lg init --from


@pytest.fixture
def confirmed(idea_project):
    p = idea_project
    p.write("references/library/ref1.pdf", "pdf")
    p.write("references/catalog.md", p.read("references/catalog.md") + "| `ref1` | 제목 | 저자 | 2026 | [pdf](library/ref1.pdf) | M0 | 요약 |\n")
    write_idea(p, 2, "expressivity", scores(5, rest=4), "0000000", status="selected")
    fill_brief(p)
    p.set_status("brief.md", "confirmed")
    p.human("chore: ideation result\n\nActor: human", all=True, no_verify=True)  # 흐름은 위 테스트에서 확인
    return p


def test_init_from_carries_direction(tmp_path, confirmed):
    cfg = write_config(tmp_path / "study.yaml", {"schema_version": 1, "project": {"name": "Study", "slug": "study"}})
    target = tmp_path / "study"
    result = lg("init", target, "--config", cfg, "--from", confirmed.root)
    assert result.exit_code == 0, result.output
    data = yaml.safe_load((target / ".lg/project.yaml").read_text(encoding="utf-8"))
    assert data["project"]["research_question"] == "표현력이 정확도를 정하는가?" and data["project"]["kind"] == "research"
    assert [m["title"] for m in data["milestones"]] == ["기준선 재현", "표현력 사다리"]
    assert data["people"]["humans"][0]["email"] == HUMAN
    assert data["origin"]["path"] == str(confirmed.root) and data["origin"]["commit"]
    assert "출발: ideation 프로젝트" in (target / "README.md").read_text(encoding="utf-8")
    assert "notes/ideation-brief.md" in (target / "plan/milestones/M0/tasks/M0-T0.md").read_text(encoding="utf-8")
    assert (target / "notes/ideation-brief.md").exists() and (target / "notes/ideation/I2_expressivity.md").exists()
    assert (target / "references/library/ref1.pdf").exists()
    assert "| `ref1` | 제목 |" in (target / "references/catalog.md").read_text(encoding="utf-8")
    import subprocess
    staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=target, capture_output=True, text=True).stdout
    assert "notes/ideation-brief.md" in staged and "references/catalog.md" in staged
    count = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=target, capture_output=True, text=True).stdout
    assert count.strip() == "1"


def test_init_from_refusals(tmp_path, idea_project, confirmed):
    cfg = write_config(tmp_path / "s.yaml", {"schema_version": 1, "project": {"name": "S", "slug": "s"}})
    confirmed.set_status("brief.md", "draft")
    result = lg("init", tmp_path / "a", "--config", cfg, "--from", confirmed.root)
    assert result.exit_code == 2 and "커밋되지 않은 변경" in result.output
    confirmed.human("chore: back to draft\n\nActor: human", all=True)
    result = lg("init", tmp_path / "a", "--config", cfg, "--from", confirmed.root)
    assert result.exit_code == 2 and "확정되지 않았습니다" in result.output
    (tmp_path / "r").mkdir()
    research = init_project(tmp_path / "r", confirmed.env, project_config(), name="research")
    result = lg("init", tmp_path / "b", "--config", cfg, "--from", research.root)
    assert result.exit_code == 2 and "ideation 프로젝트가 아닙니다" in result.output
    assert lg("init", tmp_path / "c", "--config", cfg, "--from", confirmed.root, "--kind", "ideation").exit_code == 2


def test_brief_is_confirmed_only_at_last_milestone(idea_project):
    """M0을 go로 닫아도 방향 확정 문서는 그대로다. 마지막 마일스톤(M1)의 go에서만 확정된다."""
    p = idea_project
    gate(p, "M0-T0", extra="\nMilestone-Verdict: go")
    assert p.status("plan/milestones/M0/milestone.md") == "closed"
    assert p.status("brief.md") == "draft"
