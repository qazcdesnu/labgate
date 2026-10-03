"""`lg status`: 사람이 할 일, 에이전트 몫, 진행 상황을 파일과 이력에서 모은다 (설계 문서 §24.3). 읽기만 한다."""
from __future__ import annotations

import json
import subprocess
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from . import state
from .project import Project, find_project

OPEN_DECISION = ("proposed", "discussing")


@dataclass
class Item:
    kind: str       # gate, escalation, answered, draft, human-files, unreflected, apply-pending
    label: str
    hint: str = ""


@dataclass
class Status:
    project: str
    spec_version: int
    milestone: Optional[str]
    milestone_status: Optional[str]
    human: list[Item] = field(default_factory=list)
    agent: list[Item] = field(default_factory=list)
    tasks: dict[str, list[str]] = field(default_factory=dict)   # 상태 → Task ID (현재 마일스톤)
    open_decisions: list[str] = field(default_factory=list)
    uncommitted: int = 0     # 누구의 것인지 모르는 커밋되지 않은 변경 (HUMAN_FILES가 없을 때)
    notes: list[str] = field(default_factory=list)


def collect(project: Project) -> Status:
    current = state.current_milestone(project)
    st = Status(
        project=state.project_name(project),
        spec_version=state.spec_version(project),
        milestone=current.id if current else None,
        milestone_status=current.status if current else None,
    )
    _human(project, st)
    _agent(project, st)
    if current:
        by_status: dict[str, list[str]] = {}
        for card in state.cards(project, current.id):
            by_status.setdefault(card.status or "?", []).append(card.id)
        st.tasks = by_status
    st.open_decisions = [d.id for d in state.decisions(project) if d.status in OPEN_DECISION]
    return st


def _human(project: Project, st: Status) -> None:
    changed = set(project.changed_paths())
    closed = state.closed_review_ids(project)
    for review in state.open_reviews(project):
        if review.id in closed:  # 반영 도구가 옮긴 뒤 편집기가 다시 저장한 경우 등
            st.human.append(Item("stale", f"{review.id}  닫힌 review의 사본이 reviews/open/에 남음",
                                 f"내용을 확인하고 지우기 (rm {review.rel})"))
            continue
        kind = review.fields.get("kind", "")
        task = review.fields.get("task", "")
        title = state.card_title(project, task)
        when = review.fields.get("requested", "")
        label = f"{review.id}  {task} {title}".rstrip() + (f" · {when[5:]} 요청" if len(when) == 10 else "")
        if review.rel in changed:  # 사람이 요청서에 직접 응답을 쓰는 중
            st.human.append(Item("answered", f"{review.id}  응답 작성 중 (커밋 전)", "lg commit"))
        elif review.status == "open":
            st.human.append(Item("gate" if kind == "gate" else "escalation", label, f"lg answer {review.id}"))
    if project.draft_path.exists():
        header = project.draft_path.read_text(encoding="utf-8").split("\n", 1)[0]
        st.human.append(Item("draft", f".lg/pending/COMMIT_MSG  {header}", "lg commit"))
    if project.human_files_path.exists():
        files = [l for l in project.human_files_path.read_text(encoding="utf-8").splitlines() if l]
        if files:
            shown = ", ".join(files[:3]) + (f" 외 {len(files) - 3}개" if len(files) > 3 else "")
            st.human.append(Item("human-files", f"커밋되지 않은 내 변경 {len(files)}개 ({shown})", "lg commit"))
    elif not project.draft_path.exists():
        shown = {r.rel for r in state.open_reviews(project)}  # 위에서 이미 보여 준 요청서
        st.uncommitted = len(changed - shown)


def _agent(project: Project, st: Status) -> None:
    script = project.root / "scripts" / "apply-human-commits"
    if not script.is_file():  # spec_version 2: 반영 도구가 없다
        st.notes.append("반영 대기는 알 수 없습니다 (scripts/apply-human-commits 없음, lg upgrade로 올리면 생깁니다)")
        return
    check = _run(script, "--check")
    if check is not None:
        for line in check.splitlines():
            if line.strip():
                sha, _, header = line.partition(" ")
                st.agent.append(Item("unreflected", f"반영 대기  {header} ({sha})"))
    tidy = _run(script, "--tidy")
    if tidy:
        try:
            data = json.loads(tidy)
        except ValueError:
            data = {}
        if data.get("state") == "pending":
            st.agent.append(Item("apply-pending", f"반영했지만 커밋 전 ({data.get('applies', '')})"))


def _run(script: Path, *args: str) -> Optional[str]:
    result = subprocess.run([sys.executable, str(script), *args], cwd=script.parent.parent,
                            capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else None


# ---------------------------------------------------------------- 출력

KIND_LABEL = {"gate": "gate", "escalation": "질문", "answered": "응답", "draft": "초안", "human-files": "변경",
              "stale": "사본"}
STATUS_ORDER = ("in-progress", "blocked", "in-review", "revise", "approved", "draft", "redirected", "closed")


def _cells(text: str) -> int:
    """터미널 칸 수 (한글은 두 칸)."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(width - _cells(text), 0)


def render(st: Status) -> str:
    head = f"{st.project} · spec_version {st.spec_version}"
    if st.milestone:
        head += f" · {st.milestone} ({st.milestone_status})"
    lines = [head, ""]

    if st.human:
        lines.append(f"사람이 할 일 {len(st.human)}건")
        width = max(_cells(i.label) for i in st.human)
        for item in st.human:
            tag = f"[{KIND_LABEL.get(item.kind, item.kind)}]"
            lines.append(f"  {_pad(tag, 8)} {_pad(item.label, width)}  → {item.hint}")
    else:
        lines.append("사람이 할 일: 없음")
    lines.append("")

    if st.agent:
        lines.append("에이전트 몫 (다음 세션에서 자동)")
        lines += [f"  {item.label}" for item in st.agent]
    else:
        lines.append("에이전트 몫: 없음")
    lines += [f"  ! {n}" for n in st.notes]
    lines.append("")

    lines.append("진행")
    for status in sorted(st.tasks, key=lambda s: STATUS_ORDER.index(s) if s in STATUS_ORDER else len(STATUS_ORDER)):
        ids = st.tasks[status]
        lines.append(f"  {_pad(status, 11)} {_ids(ids)}")
    if st.open_decisions:
        lines.append(f"  {_pad('결정', 11)} proposed·discussing {len(st.open_decisions)} ({' '.join(st.open_decisions)})"
                     f"  → 확정: lg answer <ID>")
    if st.uncommitted:
        lines.append(f"  커밋되지 않은 변경 {st.uncommitted}개 (세션 시작 때 session-check가 사람의 변경인지 기록한다)")

    if not st.human and st.agent:
        lines += ["", "에이전트 세션을 시작하면 이어서 진행합니다."]
    return "\n".join(lines)


def _ids(ids: list[str]) -> str:
    return ", ".join(ids) if len(ids) <= 4 else f"{ids[0]} … {ids[-1]} ({len(ids)})"


def run_status(as_json: bool = False, cwd: Optional[Path] = None) -> str:
    st = collect(find_project(cwd))
    if as_json:
        return json.dumps(asdict(st), ensure_ascii=False, indent=2)
    return render(st)
