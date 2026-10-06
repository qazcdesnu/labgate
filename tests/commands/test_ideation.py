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


def gate(p, task, extra="", review=None, apply=True):
    """사람의 gate 승인 커밋을 만들고 반영까지 한다 (에이전트가 하는 반영 포함)."""
    card = f"plan/milestones/{task.split('-')[0]}/tasks/{task}.md"
    if p.status(card) == "draft":
        p.approve_and_start(task)
    p.set_status(card, "in-review")
    p.agent(f"review({task}): request gate\n\nActor: agent\nTask: {task}", card)
    p.human(f"gate({task}): approve\n\nActor: human\nTask: {task}\nVerdict: approve\nSource: document\n"
            f"Next: none{extra}")
    if apply:
        p.commit_apply(p.apply())


def write_idea(p, n, title, scores, head, status="candidate", versus="앵커 + X: 같은 GSM8K 설정에서 +2%p, L1을 푼다"):
    """head: 평가 표 머리의 괄호 안 (lg ideas가 보여 주는 것, 예: '기준 abc, 앵커 def')."""
    rows = "".join(f"| {c} | {v} | {e} | 중 |\n" for c, (v, e) in scores.items())
    vs = f"## 앵커 대비\n\n{versus}\n\n" if versus else ""
    p.write(f"ideas/I{n}_{title}.md",
            f"---\nid: I{n}\ntype: idea\nspec_version: 8\ntitle: \"{title}\"\nstatus: {status}\norigin: agent\n"
            f"merged_into: null\ndecision: null\ncreated: 2026-10-05\nupdated: 2026-10-05\n---\n# I{n}. {title}\n\n"
            f"## 한 줄 주장\n\n주장\n\n{vs}## 평가 ({head})\n\n| 기준 | 점수 | 근거 | 확신 |\n|---|---|---|---|\n"
            f"{rows}\n## 판단 기록\n\n")


def set_anchor(p, lock_task=None, limitations=True):
    """에이전트가 앵커 추천(선정, 참고문헌 등록, 한계)을 채운다 (잠기기 전)."""
    text = p.read("plan/anchor.md")
    for k, v in (("reference", "shen2025-codi"), ("task", "GSM8K"), ("metric", "accuracy"), ("reported", '"43.7 (Table 2)"'),
                 ("lock_task", lock_task)):
        if v:
            text = re.sub(rf"^{k}: null$", f"{k}: {v}", text, count=1, flags=re.M)
    if limitations:
        text = text.replace("| ID | 한계 | 근거 | 연구 질문과의 관계 |\n|---|---|---|---|\n",
                            "| ID | 한계 | 근거 | 연구 질문과의 관계 |\n|---|---|---|---|\n"
                            "| L1 | latent 단계 수가 고정 | `shen2025-codi` §6 | 단계 수와 표현력 |\n")
    p.write("plan/anchor.md", text)
    p.write("references/catalog.md", p.read("references/catalog.md")
            + "| shen2025-codi | CODI | Shen | 2025 | library/shen2025-codi.pdf | M0 | 자기 증류 latent CoT |\n")
    p.agent("propose(M0): anchor recommendation\n\nActor: agent", "plan/anchor.md", "references/catalog.md")


def lock_both(p):
    """M0을 go로 닫는다: 기준(M0-T0 승인)과 앵커(M0의 go)이 함께 잠긴다. 평가 표 머리를 돌려준다."""
    set_anchor(p)
    gate(p, "M0-T0", extra="\nMilestone-Verdict: go")
    return re.search(r"평가 표 머리: ## 평가 \((.+)\)", p.lg("ideas").output).group(1)


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
    write_idea(p, 1, "early", scores(4), "기준 0000000")
    p.agent("propose(I1): early idea\n\nActor: agent", "ideas")
    out = p.lg("ideas").output
    assert "기준이 잠기기 전" in out
    result = p.lg("verify", "--all")
    assert result.exit_code == 3 and "기준이 잠기기 전의 평가" in result.output


def test_lg_ideas_compares_ranks_and_flags(idea_project):
    p = idea_project
    current = lock_both(p)
    criteria_version = re.search(r"기준 ([0-9a-f]+)", current).group(1)
    assert not p.git("log", "-1", "--format=%s", criteria_version).startswith("log(M0-T0): apply")
    assert "앵커: shen2025-codi · GSM8K · accuracy 43.7 (Table 2) (locked)" in p.lg("ideas").output
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


def test_ideas_need_locked_anchor_and_versus_section(idea_project):
    """§27: 모든 후보는 잠근 앵커 하나와 비교한다. 앵커 대비가 없거나 앵커가 잠기기 전이면 순위에서 뺀다."""
    p = idea_project
    head = lock_both(p)
    write_idea(p, 1, "ok", scores(4), head)
    write_idea(p, 2, "scattered", scores(5), head, versus=None)          # 앵커 대비 없음
    write_idea(p, 3, "oldheader", scores(5), head.split(",")[0])          # 앵커 버전 없음
    p.agent("propose(M1): evaluate\n\nActor: agent", "ideas")
    out = p.lg("ideas").output
    rows = {l.split()[0]: l for l in out.splitlines() if re.match(r"^  I\d", l)}
    assert rows["I1"].rstrip().endswith(" 1") and not rows["I2"].rstrip().endswith(("1", "2"))
    assert "I2: 앵커 대비 절 없음" in out and "I3: 평가 표 머리에 앵커 버전이 없음" in out
    # 잠긴 앵커를 에이전트가 고치면 V4
    p.write("plan/anchor.md", p.read("plan/anchor.md").replace("task: GSM8K", "task: MATH"))
    p.agent("chore: switch anchor task\n\nActor: agent", "plan/anchor.md")
    result = p.lg("verify")
    assert "✗ V4" in result.output and "plan/anchor.md" in result.output


def test_versus_must_name_a_anchor_limitation(idea_project):
    """§27: 앵커는 기여의 기준점이다. 후보는 앵커의 어느 한계(L<n>)를 푸는지 적는다."""
    p = idea_project
    head = lock_both(p)
    write_idea(p, 1, "ok", scores(4), head)
    write_idea(p, 2, "nolimit", scores(5), head, versus="앵커 + X: 같은 GSM8K 설정에서 +2%p")
    p.agent("propose(M1): evaluate\n\nActor: agent", "ideas")
    out = p.lg("ideas").output
    assert "앵커의 한계: L1" in out
    rows = {l.split()[0]: l for l in out.splitlines() if re.match(r"^  I\d", l)}
    assert rows["I1"].rstrip().endswith(" 1") and not rows["I2"].rstrip().endswith(("1", "2"))
    assert "I2: 앵커 대비에 푸는 한계 없음" in out
    result = p.lg("verify", "--all")
    assert result.exit_code == 3 and "앵커 대비에 푸는 한계 없음" in result.output


def test_lock_task_approve_locks_anchor(idea_project):
    """§27: M0이 끝난 뒤에도 앵커 선정 task(lock_task)의 게이트 approve가 앵커를 잠근다."""
    p = idea_project
    set_anchor(p, lock_task="M1-T0")
    gate(p, "M0-T0", extra="\nMilestone-Verdict: go")
    assert p.status("plan/anchor.md") == "draft"  # lock_task가 있으면 첫 마일스톤의 go로 잠그지 않는다
    assert "M1-T0 게이트를 approve하면 잠기고" in p.lg("ideas").output
    gate(p, "M1-T0")
    assert p.status("plan/anchor.md") == "locked"
    locked = re.search(r"^locked_commit: '?([0-9a-f]+)'?$", p.read("plan/anchor.md"), re.M).group(1)
    assert p.git("log", "--format=%h", "--grep", "gate(M1-T0)").startswith(locked[:7])
    assert p.lg("verify", "--all").exit_code == 0  # 잠금 반영의 근거는 lock_task의 approve (V2)


def test_incomplete_anchor_is_not_locked(idea_project):
    """§27: 선정 필드·참고문헌·한계가 없는 앵커는 잠그지 않는다. 반영 도구가 아무것도 바꾸지 않고 멈춘다."""
    p = idea_project
    set_anchor(p, lock_task="M0-T0", limitations=False)
    message = "gate(M0-T0): approve\n\nActor: human\nTask: M0-T0\nVerdict: approve\nSource: document\nNext: none\n"
    p.approve_and_start("M0-T0")
    p.set_status("plan/milestones/M0/tasks/M0-T0.md", "in-review")
    preview = p.apply("--preview", input=message)  # lg answer·lg commit이 판정 커밋 전에 보는 것
    assert preview.returncode != 0 and "앵커를 잠글 수 없습니다" in preview.stdout + preview.stderr
    gate(p, "M0-T0", apply=False)
    result = p.apply()
    out = result.stdout + result.stderr
    assert result.returncode != 0 and "앵커를 잠글 수 없습니다" in out and "## 한계에 L<n>이 없음" in out
    assert p.status("plan/anchor.md") == "draft" and p.status(CRITERIA) == "draft"
    # 사람이 직접 잠가도 lg verify가 잡는다
    p.set_status("plan/anchor.md", "locked")
    p.human("plan: lock anchor by hand\n\nActor: human", "plan/anchor.md")
    assert "잠긴 앵커: 앵커 ## 한계에 L<n>이 없음" in p.lg("verify", "--all").output


def test_anchor_before_lock_is_agents_to_draft(idea_project):
    """잠기기 전에는 에이전트가 앵커 추천을 써도 위반이 아니다."""
    p = idea_project
    set_anchor(p)
    assert "✓ V4" in p.lg("verify", "--all").output


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
    text = text.replace("milestones: []", 'milestones: ["앵커 재현", "표현력 사다리"]')
    text = text.replace("selected: []", "selected: [I2]").replace("dropped: []", "dropped: [I1]")
    text = text.replace("references: []", f"references: [{', '.join(refs)}]").replace("anchor: null", "anchor: ref1")
    p.write("brief.md", text)


def test_last_gate_selects_drops_and_confirms_brief(idea_project, keys):
    p = idea_project
    current = lock_both(p)
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
    write_idea(p, 2, "expressivity", scores(5, rest=4), "기준 0000000", status="selected")
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
    assert [m["title"] for m in data["milestones"]] == ["앵커 재현", "표현력 사다리"]
    assert data["people"]["humans"][0]["email"] == HUMAN
    assert data["origin"]["path"] == str(confirmed.root) and data["origin"]["commit"]
    assert "출발: ideation 프로젝트" in (target / "README.md").read_text(encoding="utf-8")
    assert "notes/ideation-brief.md" in (target / "plan/milestones/M0/tasks/M0-T0.md").read_text(encoding="utf-8")
    assert (target / "notes/ideation-brief.md").exists() and (target / "notes/ideation/I2_expressivity.md").exists()
    assert (target / "references/library/ref1.pdf").exists() and (target / "notes/ideation-anchor.md").exists()
    assert "앵커 연구(`notes/ideation-anchor.md`" in (target / "plan/milestones/M0/tasks/M0-T0.md").read_text(encoding="utf-8")
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
    set_anchor(p)
    gate(p, "M0-T0", extra="\nMilestone-Verdict: go")
    assert p.status("plan/milestones/M0/milestone.md") == "closed"
    assert p.status("brief.md") == "draft"


def test_upgrade_adds_anchor_to_spec7_ideation(idea_project):
    """§27: spec_version 7로 만든 ideation 프로젝트를 올리면 plan/anchor.md가 새로 생긴다 (연구 문서지만 이 버전에서 생긴 것)."""
    p = idea_project
    p.run("git", "rm", "-q", "plan/anchor.md", "specs/doc-types/anchor.spec.md")
    data = p.yaml()
    data["generated"]["spec_version"] = 7
    p.write(".lg/project.yaml", yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    p.human("chore: pretend spec 7\n\nActor: human", all=True, no_verify=True)
    from labgate import upgrade
    plan_new = upgrade.NEW_RESEARCH_DOCS[8]
    assert plan_new == ("plan/anchor.md",)
    result = p.lg("upgrade", "--dry-run")
    assert "plan/anchor.md" in result.output
