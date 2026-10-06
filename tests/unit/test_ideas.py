"""ideation 평가 기준·평가표 읽기와 검사 (`labgate.ideas`, 설계 문서 §26.6)."""
from labgate.ideas import Criterion, evaluation_issues, parse_criteria, parse_evaluation
from labgate.plan import build_plan
from support.configs import make_config

C = [Criterion("C1", "독창성", False, 3, True), Criterion("C8", "적합성", True, 2, False)]


def test_default_criteria_parse():
    files = {str(f.path): f.content for f in build_plan(make_config(kind="ideation"), "2026-10-01")}
    crit = parse_criteria(files["plan/criteria.md"])
    assert [c.id for c in crit] == [f"C{i}" for i in range(1, 9)]
    assert [c.weight for c in crit] == [3, 3, 2, 2, 2, 2, 1, 2]
    assert [c.id for c in crit if c.human] == ["C8"]
    assert [c.id for c in crit if c.knockout] == ["C1", "C3", "C5"]
    assert all(f"### C{i}." in files["plan/criteria.md"] for i in range(1, 9))  # 수준별 근거 조건


def test_parse_evaluation():
    text = ("# I1\n\n## 평가 (기준 3f2a1c9)\n\n| 기준 | 점수 | 근거 | 확신 |\n|---|---|---|---|\n"
            "| C1 | 4 | `ref` Table 1 | 중 |\n| C8 | (사람) | | |\n\n## 판단 기록\n")
    has, commit, scores = parse_evaluation(text)
    assert has and commit == "3f2a1c9"
    assert scores["C1"].value == 4 and scores["C1"].evidence == "`ref` Table 1" and scores["C8"].value is None
    assert parse_evaluation("# I1\n\n## 한 줄 주장\n")[0] is False


def test_evaluation_issues():
    _, _, ok = parse_evaluation("## 평가 (기준 abc1234)\n\n| C1 | 4 | `ref` | 중 |\n| C8 | (사람) | | |\n")
    assert evaluation_issues(C, True, "abc1234", "abc1234", ok) == []
    assert evaluation_issues(C, False, "abc1234", "abc1234", ok) == ["기준이 잠기기 전의 평가"]
    assert "기준 변경 전" in evaluation_issues(C, True, "def5678", "abc1234", ok)[0]
    _, _, bad = parse_evaluation("## 평가 (기준 abc1234)\n\n| C1 | 9 | `ref` | 중 |\n| C2 | 3 | x | 상 |\n")
    issues = evaluation_issues(C, True, "abc1234", "abc1234", bad)
    assert "평가하지 않은 기준: C8" in issues and "기준 문서에 없는 기준: C2" in issues
    assert "C1: 점수가 1–5가 아님 (9)" in issues
    _, _, empty = parse_evaluation("## 평가 (기준 abc1234)\n\n| C1 | 4 |  | 중 |\n| C8 | (사람) | | |\n")
    assert evaluation_issues(C, True, "abc1234", "abc1234", empty) == ["C1: 근거 없는 점수 (무효)"]


def test_anchor_issues():
    from labgate.ideas import Anchor, anchor_issues
    locked = Anchor("locked", "shen2025-codi", "GSM8K", "accuracy", "43.7", "def5678")
    good = "## 앵커 대비\n\n앵커 + X\n\n## 평가 (기준 abc1234, 앵커 def5678)\n\n| C1 | 4 | `ref` | 중 |\n"
    assert anchor_issues(locked, good) == []
    assert anchor_issues(None, good) == []                                  # spec_version 7 ideation: 앵커 없음
    assert anchor_issues(locked, "# I1\n\n한 줄\n") == []                     # 평가 전
    assert anchor_issues(Anchor("draft", "", "", "", "", None), good) == ["앵커가 잠기기 전의 평가"]
    assert "앵커 변경 전" in anchor_issues(Anchor("locked", "x", "", "", "", "aaa1111"), good)[0]
    no_vs = good.replace("## 앵커 대비\n\n앵커 + X\n\n", "")
    assert anchor_issues(locked, no_vs)[0].startswith("앵커 대비 절 없음")
    old = good.replace(", 앵커 def5678", "")
    assert anchor_issues(locked, old) == ["평가 표 머리에 앵커 버전이 없음"]
