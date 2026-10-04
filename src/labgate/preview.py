"""사람 커밋이 반영되면 생길 일 (설계 문서 §24.5.4). `lg answer`와 `lg commit`이 쓴다.

계산은 프로젝트의 `scripts/apply-human-commits --preview`가 한다. 그래서 실제 반영과 같다.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Optional

from . import state
from .project import Project

PREVIEW_SPEC = 5  # apply-human-commits --preview가 있는 첫 spec_version
REFLECTED = ("gate", "respond", "decide")


def is_reflected(project: Project, message: str) -> bool:
    """다음 세션에 에이전트가 반영하는 사람 커밋인가 (gate, respond, decide, plan+Approve)."""
    ctype = project.header_type(message)
    return ctype in REFLECTED or (ctype == "plan" and "Approve" in project.trailers(message))


def preview(project: Project, messages: list[str]) -> tuple[list[str], Optional[str]]:
    """(보여 줄 줄, 반영할 수 없는 이유 또는 None). 반영 대상이 아니면 빈 목록."""
    messages = [m for m in messages if is_reflected(project, m)]
    if not messages:
        return [], None
    script = project.root / "scripts" / "apply-human-commits"
    if state.spec_version(project) < PREVIEW_SPEC or not script.is_file():
        trailers = [f"  {k}: {v}" for m in messages for k, v in project.trailers(m).items() if k != "Actor"]
        return ["반영 미리보기는 spec_version 5 이상에서 됩니다 (lg upgrade). 커밋할 trailer:", *trailers], None
    out = ["이 커밋이 반영되면 (다음 세션에서 에이전트가):"]
    for m in messages:
        result = subprocess.run([sys.executable, str(script), "--preview"], input=m, cwd=project.root,
                                capture_output=True, text=True)
        if result.returncode != 0:
            return out, (result.stderr or result.stdout).strip()
        out += [l for l in result.stdout.splitlines() if l.startswith("  ")]
    trailers = project.trailers(messages[0])
    if project.header_type(messages[0]) == "gate":
        if trailers.get("Verdict") == "approve":
            out.append(f"  tag: gate/{trailers.get('Task', '')}")
        if trailers.get("Milestone-Verdict"):
            out.append(f"  tag: milestone/{state.milestone_of(trailers.get('Task', ''))}-{trailers['Milestone-Verdict']}")
    return out, None
