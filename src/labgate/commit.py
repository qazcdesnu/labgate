"""`lg commit`: 사람 신원의 커밋을 터미널에서 확인하고 확정한다 (설계 문서 §18)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import typer

from . import gitops, prompts
from .errors import EXIT_ABORT, EXIT_GIT, EXIT_TARGET, EXIT_USAGE, Fail
from . import verify as verify_module
from .project import Project, build_message, find_project

COMMIT, EDIT, CANCEL = "커밋", "편집기로 수정", "취소"
NONE = "(없음)"


def is_tty() -> bool:
    """§18.2 2: 표준 입력과 출력이 모두 터미널인가. 에이전트의 셸은 터미널이 아니다."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_commit(pending: Optional[bool], no_tag: bool, allow_empty: bool = False,
               cwd: Optional[Path] = None) -> str:
    """§18.2. 성공하면 출력할 안내를 돌려준다."""
    project = find_project(cwd)

    if not is_tty():
        raise Fail(EXIT_USAGE, (
            "✗ lg commit 은 사람이 터미널에서 직접 실행합니다.\n"
            "  에이전트는 lg draft 로 초안만 준비합니다."
        ))

    result = gitops.run(["config", "user.email"], cwd=project.root)
    email = result.stdout.strip().lower() if result.returncode == 0 else ""
    if email not in project.human_emails():
        raise Fail(EXIT_USAGE, (
            f"✗ 현재 Git 사용자({email or '설정 없음'})가 .lg/identities.json 의 humans 에 없습니다.\n"
            '  git config user.email "<등록된 이메일>" 로 설정하세요.'
        ))

    has_draft = project.draft_path.exists()
    if pending and not has_draft:
        raise Fail(EXIT_TARGET, "✗ 초안이 없습니다 (.lg/pending/COMMIT_MSG).")
    use_draft = has_draft if pending is None else pending

    message = _from_draft(project, allow_empty) if use_draft else _compose(project, allow_empty)
    message = _confirm(project, message)
    sha = _commit(project, message, allow_empty)

    if use_draft:
        project.draft_path.unlink()
    project.refresh_human_files()
    tags = [] if no_tag else _tag(project, message)

    lines = [f"✓ 커밋했습니다: {sha} {message.split(chr(10), 1)[0]}"]
    lines += [f"  tag: {t}" for t in tags]
    hint = next_step_hint(project, message, use_draft)
    if hint:
        lines.append(f"  {hint}")
    return "\n".join(lines)


REFLECTED_TYPES = ("gate", "respond", "decide")


def next_step_hint(project: Project, message: str, from_draft: bool) -> Optional[str]:
    """커밋 뒤 에이전트와 관련해 사람이 할 일 (설계 문서 §18.2 9). 할 일이 없으면 None."""
    if from_draft:  # 에이전트가 초안을 만들고 멈춰 기다리는 경우
        return "에이전트가 기다리고 있으면 '커밋했어'라고 알리세요. 새 세션에서는 자동으로 확인합니다."
    ctype = project.header_type(message)
    if ctype in REFLECTED_TYPES or (ctype == "plan" and "Approve" in project.trailers(message)):
        return "다음 세션 시작 때 에이전트가 자동으로 반영합니다. 열린 세션에서 바로 이어 가려면 알리세요."
    if ctype == "spec":
        return "규칙 문서가 바뀌었습니다. 열린 에이전트 세션이 있으면 새로 시작하세요."
    return None


# ---------------------------------------------------------------- 메시지 준비


def _from_draft(project: Project, allow_empty: bool) -> str:
    """§18.5."""
    if not allow_empty and not project.staged_paths():
        raise Fail(EXIT_TARGET, "✗ 초안은 있는데 stage된 변경이 없습니다 (.lg/pending/COMMIT_MSG).")
    message = project.draft_path.read_text(encoding="utf-8")
    if project.trailers(message).get("Actor") != "human":
        raise Fail(EXIT_USAGE, "✗ 초안이 사람 커밋용이 아닙니다 (Actor: human 이 없습니다).")
    return message


def _compose(project: Project, allow_empty: bool) -> str:
    """§18.4 작성 모드."""
    hook = project.hook
    if not allow_empty and not project.staged_paths():
        changed = project.changed_paths()
        if not changed:
            raise Fail(EXIT_TARGET, "✗ 커밋할 변경이 없습니다.")
        chosen = prompts.checkbox("커밋할 파일 (스페이스로 선택, 엔터로 확정)", changed)
        if not chosen:
            raise Fail(EXIT_TARGET, "✗ 고른 파일이 없습니다.")
        project.git("add", "-A", "--", *chosen)

    ctype = prompts.select("타입", project.human_types())
    trailers: list[tuple[str, str]] = []
    if ctype in hook["TASK_REQUIRED"]:
        task = _ask_task(project)
        scope: Optional[str] = task
        trailers.append(("Task", task))
    else:
        approve = _ask_approve(project) if ctype == "plan" else []
        if approve:
            trailers.append(("Approve", ", ".join(approve)))
        if len(approve) == 1:
            scope = approve[0]
        else:
            scope = prompts.text(
                "scope (선택, 빈 입력이면 생략)",
                lambda v: "공백과 괄호는 쓸 수 없습니다" if any(c in v.strip() for c in " ()") else None,
            ) or None

    if ctype == "gate":
        trailers.append(("Verdict", prompts.select("Verdict", ["approve", "revise", "redirect"])))
    if ctype in hook["SOURCE_REQUIRED"]:
        trailers.append(("Source", prompts.select("Source", ["document", "conversation"])))
    if ctype == "gate":
        nxt = prompts.text(
            "Next (다음 task ID 또는 none, 빈 입력이면 생략)",
            lambda v: None if not v.strip() or v.strip() == "none" or hook["TASK_ID_RE"].match(v.strip())
            else "M<n>-T<n> 또는 none",
        )
        if nxt:
            trailers.append(("Next", nxt))
        mv = prompts.select("Milestone-Verdict (마일스톤 마지막 task일 때)", [NONE, "go", "nogo", "conditional"])
        if mv != NONE:
            trailers.append(("Milestone-Verdict", mv))
    if ctype == "decide":
        trailers.append(("Decisions", prompts.text(
            "Decisions (결정 ID, 쉼표로 구분)",
            lambda v: None if v.strip() and all(hook["DECISION_ID_RE"].match(x.strip()) for x in v.split(","))
            else "D<n>.<n> 형식, 쉼표로 구분",
        )))

    prefix = len(f"{ctype}({scope}): " if scope else f"{ctype}: ")
    summary = prompts.text(
        "요약 (무엇을 했는지 한 줄)",
        lambda v: "요약을 입력하세요" if not v.strip()
        else f"헤더가 {hook['MAX_HEADER']}자를 넘습니다" if prefix + len(v.strip()) > hook["MAX_HEADER"]
        else None,
    )
    return build_message(ctype, summary, scope, None, trailers)


def _ask_approve(project: Project) -> list[str]:
    """plan 커밋의 Approve: 승인할 task (여러 개, 없으면 빈 목록)."""
    ids = project.task_ids()
    if ids:
        return prompts.checkbox("Approve (승인할 task, 스페이스로 선택, 없으면 그냥 엔터)", ids)
    pattern = project.hook["TASK_ID_RE"]
    raw = prompts.text(
        "Approve (승인할 task ID, 쉼표로 구분, 빈 입력이면 생략)",
        lambda v: None if not v.strip() or all(pattern.match(x.strip()) for x in v.split(","))
        else "M<n>-T<n> 형식, 쉼표로 구분",
    )
    return [x.strip() for x in raw.split(",") if x.strip()]


def _ask_task(project: Project) -> str:
    ids = project.task_ids()
    if ids:
        return prompts.select("Task", ids)
    return prompts.text("Task (M<n>-T<n>)", lambda v: None if project.hook["TASK_ID_RE"].match(v.strip()) else "M<n>-T<n> 형식")


# ---------------------------------------------------------------- 확인, 커밋, tag


def _gate_check(project: Project, message: str) -> tuple[list[str], int]:
    """§23.6: gate 커밋이면 그 Task로 lg verify를 돌린 요약과 위반 수. 막지 않는다."""
    if project.header_type(message) != "gate":
        return [], 0
    task = project.trailers(message).get("Task", "")
    if not project.hook["TASK_ID_RE"].match(task):
        return [], 0
    return verify_module.summary_for_commit(project, task)


def _confirm(project: Project, message: str) -> str:
    """§18.2 5: stage 요약과 메시지를 보여 주고 커밋 / 편집 / 취소. gate면 lg verify 요약도 (§23.6)."""
    checked_for, check, violations = None, [], 0
    while True:
        if checked_for != message:
            check, violations = _gate_check(project, message)
            checked_for = message
        typer.echo("\n" + project.git("diff", "--cached", "--stat").rstrip())
        if check:
            typer.echo("\n" + "\n".join(check))
        typer.echo("\n" + "\n".join(f"  │ {l}" for l in message.rstrip("\n").split("\n")) + "\n")
        errors = project.check_message(message)
        if errors:
            typer.echo("✗ 커밋 규약에 맞지 않습니다:\n" + "\n".join(f"  - {e}" for e in errors), err=True)
        commit_label = f"{COMMIT} (위반 {violations}건 있음)" if violations else COMMIT
        choice = prompts.select("어떻게 할까요?", ([] if errors else [commit_label]) + [EDIT, CANCEL])
        if choice == commit_label:
            return message
        if choice == CANCEL:
            raise Fail(EXIT_ABORT, "취소했습니다. stage된 변경과 초안은 그대로 두었습니다.")
        edited = _edit(project, message)
        if edited is not None:
            message = edited.rstrip("\n") + "\n"


def _edit(project: Project, message: str) -> Optional[str]:
    """Git과 같은 편집기(`git var GIT_EDITOR`: core.editor, GIT_EDITOR, VISUAL, EDITOR 순)로 고친다.
    편집기를 실행하지 못하면 None."""
    editor = project.git("var", "GIT_EDITOR").strip()
    fd, path = tempfile.mkstemp(prefix="lg-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(message)
        try:  # Git처럼 편집기 문자열을 셸로 실행한다 (인자가 붙은 "code --wait" 등)
            code = subprocess.call(["sh", "-c", f'{editor} "$@"', editor, path])
        except OSError as e:
            code = None
            typer.echo(f"✗ 편집기를 실행하지 못했습니다 ({editor}): {e}", err=True)
        if code != 0:
            if code is not None:
                typer.echo(f"✗ 편집기가 오류로 끝났습니다 ({editor}, 코드 {code}).", err=True)
            return None
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    finally:
        os.unlink(path)


def _commit(project: Project, message: str, allow_empty: bool) -> str:
    fd, path = tempfile.mkstemp(prefix="lg-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(message)
        args = ["commit", "-q", "-F", path] + (["--allow-empty"] if allow_empty else [])
        result = gitops.run(args, cwd=project.root)
    finally:
        os.unlink(path)
    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        raise Fail(EXIT_GIT, "✗ 커밋하지 못했습니다:\n" + "\n".join(f"  | {l}" for l in output.splitlines()))
    return project.git("rev-parse", "--short", "HEAD").strip()


def _tag(project: Project, message: str) -> list[str]:
    """§18.2 8: gate 승인이면 gate/<Task>, Milestone-Verdict가 있으면 milestone/<M>-<verdict>."""
    if project.header_type(message) != "gate":
        return []
    trailers = project.trailers(message)
    task = trailers.get("Task", "")
    tags = []
    if trailers.get("Verdict") == "approve":
        tags.append(f"gate/{task}")
    if trailers.get("Milestone-Verdict"):
        tags.append(f"milestone/{task.split('-')[0]}-{trailers['Milestone-Verdict']}")
    for tag in tags:
        result = gitops.run(["tag", tag], cwd=project.root)
        if result.returncode != 0:
            raise Fail(EXIT_GIT, f"✗ 커밋은 했지만 tag {tag} 를 만들지 못했습니다: {(result.stderr or result.stdout).strip()}")
    return tags
