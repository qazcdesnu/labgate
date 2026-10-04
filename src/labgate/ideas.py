"""ideation 후보 평가 (설계 문서 §26.6): 기준 문서와 후보의 평가표를 읽고, 비교표·합계·순위를 계산한다.

합계와 순위는 이 모듈이 계산한다. 에이전트가 손으로 더하거나 순위를 매기지 않는다.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from . import gitops, state
from .errors import EXIT_USAGE, Fail
from .project import Project, find_project
from .verify import frontmatter_fields, section

CRITERIA = "plan/criteria.md"
EVAL_HEADING = re.compile(r"^## 평가(?: \(기준 ([0-9a-f]{7,40})\))?[ \t]*$", re.M)
HUMAN_SCORE = "(사람)"


@dataclass
class Criterion:
    id: str
    name: str
    human: bool
    weight: int
    knockout: bool


@dataclass
class Score:
    value: Optional[int]       # None: 사람 기준이 아직 비었거나 읽을 수 없음
    evidence: str
    confidence: str
    raw: str


@dataclass
class Row:
    id: str
    title: str
    status: str
    scores: dict[str, Score]
    criteria_commit: Optional[str]
    total: Optional[float] = None
    knocked_out: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_criteria(text: str) -> list[Criterion]:
    """`## 기준` 표: ID | 기준 | 묻는 것 | 누가 | 가중치 | 결격."""
    out = []
    for line in section(text, "기준").splitlines():
        cells = _cells(line)
        if len(cells) >= 6 and re.fullmatch(r"C\d+", cells[0]):
            try:
                weight = int(cells[4])
            except ValueError:
                weight = 0
            out.append(Criterion(cells[0], cells[1], cells[3] == "사람", weight, cells[5] not in ("", "—", "-")))
    return out


def parse_evaluation(text: str) -> tuple[bool, Optional[str], dict[str, Score]]:
    """(평가 절이 있나, 기준 커밋, 기준 ID → 점수)."""
    m = EVAL_HEADING.search(text)
    if not m:
        return False, None, {}
    rest = text[m.end():]
    end = re.search(r"^## ", rest, re.M)
    body = rest[:end.start()] if end else rest
    scores = {}
    for line in body.splitlines():
        cells = _cells(line)
        if len(cells) >= 2 and re.fullmatch(r"C\d+", cells[0]):
            raw = cells[1]
            value = int(raw) if re.fullmatch(r"[1-5]", raw) else None
            scores[cells[0]] = Score(value, cells[2] if len(cells) > 2 else "", cells[3] if len(cells) > 3 else "", raw)
    return True, m.group(1), scores


LOCK_LINE = re.compile(r"^(status|locked_commit|updated):.*$", re.M)


def criteria_version(project: Project) -> Optional[str]:
    """기준 버전: 기준 **내용**을 마지막으로 바꾼 커밋. 잠금 반영처럼 `status`·`locked_commit`·`updated`만
    바꾼 커밋은 건너뛴다 (그래야 잠가도 버전이 바뀌지 않는다)."""
    log = gitops.run(["log", "--format=%h", "--", CRITERIA], cwd=project.root)
    if log.returncode != 0:
        return None
    for sha in log.stdout.split():
        after = gitops.run(["show", f"{sha}:{CRITERIA}"], cwd=project.root)
        before = gitops.run(["show", f"{sha}^:{CRITERIA}"], cwd=project.root)
        if before.returncode != 0 or LOCK_LINE.sub("", before.stdout) != LOCK_LINE.sub("", after.stdout):
            return sha
    return None


def criteria_state(project: Project) -> tuple[Optional[str], list[Criterion], Optional[str]]:
    """(status, 기준, 기준 버전)."""
    path = project.root / CRITERIA
    if not path.is_file():
        return None, [], None
    text = path.read_text(encoding="utf-8")
    return frontmatter_fields(text).get("status"), parse_criteria(text), criteria_version(project)


def evaluation_issues(criteria: list[Criterion], locked: bool, current: Optional[str],
                      commit: Optional[str], scores: dict[str, Score]) -> list[str]:
    """평가표 검사 (§26.6, lg verify V5와 lg ideas가 같이 쓴다)."""
    issues = []
    if not locked:
        issues.append("기준이 잠기기 전의 평가")
    elif commit and current and not (current.startswith(commit) or commit.startswith(current)):
        issues.append(f"기준 변경 전의 평가 (기준 {commit}, 지금 {current}): 다시 매겨야 한다")
    ids = {c.id for c in criteria}
    missing = sorted(ids - set(scores), key=lambda x: int(x[1:]))
    if missing:
        issues.append("평가하지 않은 기준: " + ", ".join(missing))
    extra = sorted(set(scores) - ids)
    if extra:
        issues.append("기준 문서에 없는 기준: " + ", ".join(extra))
    for c in criteria:
        s = scores.get(c.id)
        if s is None:
            continue
        if c.human:
            if s.raw not in (HUMAN_SCORE, "") and s.value is None:
                issues.append(f"{c.id}: 점수가 1–5가 아님 ({s.raw})")
            continue
        if s.value is None:
            issues.append(f"{c.id}: 점수가 1–5가 아님 ({s.raw or '빈칸'})")
        elif not s.evidence.strip():
            issues.append(f"{c.id}: 근거 없는 점수 (무효)")
    return issues


def compare(project: Project) -> tuple[Optional[str], list[Criterion], list[Row], Optional[str]]:
    status, criteria, current = criteria_state(project)
    if status is None:
        raise Fail(EXIT_USAGE, "✗ plan/criteria.md 가 없습니다. ideation 프로젝트(lg init --kind ideation)에서 씁니다.")
    rows = []
    for path in sorted((project.root / "ideas").glob("I*_*.md"), key=lambda p: state.numeric_key(p.stem)):
        text = path.read_text(encoding="utf-8")
        fields = frontmatter_fields(text)
        has_eval, commit, scores = parse_evaluation(text)
        row = Row(fields.get("id") or path.stem.split("_")[0], fields.get("title", ""), fields.get("status", ""),
                  scores, commit)
        if has_eval:
            row.issues = evaluation_issues(criteria, status == "locked", current, commit, scores)
            agent_scores = {c.id: scores[c.id].value for c in criteria if c.id in scores}
            if not any(i.startswith(("기준이 잠기기", "기준 변경 전")) for i in row.issues):  # 무효한 평가는 순위에 넣지 않는다
                row.knocked_out = [c.id for c in criteria if c.knockout and agent_scores.get(c.id) == 1]
                valid = [c for c in criteria if agent_scores.get(c.id) is not None
                         and (c.human or scores[c.id].evidence.strip())]
                weight = sum(c.weight for c in valid)
                if weight:
                    row.total = round(sum(c.weight * agent_scores[c.id] for c in valid) / weight, 2)
        rows.append(row)
    return status, criteria, rows, current


def render(status: Optional[str], criteria: list[Criterion], rows: list[Row], version: Optional[str] = None) -> str:
    lines = [f"평가 기준: plan/criteria.md ({status}) · 기준 버전 {version or '없음'} · 후보 {len(rows)}개"]
    if status == "locked" and version:
        lines.append(f"  평가 표 머리: ## 평가 (기준 {version})")
    if status != "locked":
        lines.append("  ! 기준이 잠기기 전입니다. 첫 T0 게이트에서 사람이 확정하면 잠기고, 그 뒤에 평가합니다.")
    if not rows:
        return "\n".join(lines + ["", "후보가 없습니다 (ideas/)."])
    head = ["ID", "상태"] + [f"{c.id}×{c.weight}" + ("(사람)" if c.human else "") for c in criteria] + ["평균", "순위"]
    ranked = sorted([r for r in rows if r.total is not None and not r.knocked_out], key=lambda r: -r.total)
    rank = {r.id: i + 1 for i, r in enumerate(ranked)}
    table = []
    for r in rows:
        cells = [r.id, r.status]
        for c in criteria:
            s = r.scores.get(c.id)
            mark = "" if s is None else (s.raw if s.value is None else str(s.value))
            if s is not None and s.value is not None and not c.human and not s.evidence.strip():
                mark += "!"
            elif s is not None and s.confidence == "하":
                mark += "?"
            cells.append(mark or "·")
        cells.append("결격" if r.knocked_out else ("" if r.total is None else f"{r.total:.2f}"))
        cells.append(str(rank.get(r.id, "")))
        table.append(cells)
    widths = [max(len(str(x)) for x in col) for col in zip(head, *table)]
    fmt = lambda cells: "  " + "  ".join(str(c).ljust(w) for c, w in zip(cells, widths)).rstrip()  # noqa: E731
    lines += ["", fmt(head)] + [fmt(c) for c in table]
    lines += ["", "평균: 근거가 있는 점수의 가중 평균. 결격: 결격이 있는 기준에서 1점. !: 근거 없는 점수(무효), ?: 확신 하, ·: 아직 없음"]
    notes = [f"  {r.id}: {i}" for r in rows for i in r.issues]
    if notes:
        lines += ["", "확인할 것:"] + notes
    lines.append("방향은 사람이 정합니다. 순위와 다르게 고르면 이유를 남기세요 (lg answer 코멘트, brief.md).")
    return "\n".join(lines)


def run_ideas(as_json: bool = False, cwd: Optional[Path] = None) -> str:
    project = find_project(cwd)
    status, criteria, rows, version = compare(project)
    if as_json:
        return json.dumps({"criteria_status": status, "criteria_version": version, "criteria": [asdict(c) for c in criteria],
                           "ideas": [asdict(r) for r in rows]}, ensure_ascii=False, indent=2)
    return render(status, criteria, rows, version)
