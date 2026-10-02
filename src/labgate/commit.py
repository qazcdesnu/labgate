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
from .project import Project, build_message, find_project

COMMIT, EDIT, CANCEL = "커밋", "편집기로 수정", "취소"
NONE = "(없음)"


def is_tty() -> bool:
    """§18.2 2: 표준 입력과 출력이 모두 터미널인가. 에이전트의 셸은 터미널이 아니다."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def run_commit(pending: Optional[bool], no_tag: bool, cwd: Optional[Path] = None) -> str:
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

    message = _from_draft(project) if use_draft else _compose(project)
    message = _confirm(project, message)
    sha = _commit(project, message)

    if use_draft:
        project.draft_path.unlink()
    project.refresh_human_files()
    tags = [] if no_tag else _tag(project, message)

    lines = [f"✓ 커밋했습니다: {sha} {message.split(chr(10), 1)[0]}"]
    lines += [f"  tag: {t}" for t in tags]
    lines.append("  에이전트에게 커밋했다고 알리세요.")
    return "\n".join(lines)


# ---------------------------------------------------------------- 메시지 준비


def _from_draft(project: Project) -> str:
    """§18.5."""
    if not project.staged_paths():
        raise Fail(EXIT_TARGET, "✗ 초안은 있는데 stage된 변경이 없습니다 (.lg/pending/COMMIT_MSG).")
    message = project.draft_path.read_text(encoding="utf-8")
    if project.trailers(message).get("Actor") != "human":
        raise Fail(EXIT_USAGE, "✗ 초안이 사람 커밋용이 아닙니다 (Actor: human 이 없습니다).")
    return message


def _compose(project: Project) -> str:
    """§18.4 작성 모드."""
    hook = project.hook
    if not project.staged_paths():
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


def _ask_task(project: Project) -> str:
    ids = project.task_ids()
    if ids:
        return prompts.select("Task", ids)
    return prompts.text("Task (M<n>-T<n>)", lambda v: None if project.hook["TASK_ID_RE"].match(v.strip()) else "M<n>-T<n> 형식")


# ---------------------------------------------------------------- 확인, 커밋, tag


def _confirm(project: Project, message: str) -> str:
    """§18.2 5: stage 요약과 메시지를 보여 주고 커밋 / 편집 / 취소."""
    while True:
        typer.echo("\n" + project.git("diff", "--cached", "--stat").rstrip())
        typer.echo("\n" + "\n".join(f"  │ {l}" for l in message.rstrip("\n").split("\n")) + "\n")
        errors = project.check_message(message)
        if errors:
            typer.echo("✗ 커밋 규약에 맞지 않습니다:\n" + "\n".join(f"  - {e}" for e in errors), err=True)
        choice = prompts.select("어떻게 할까요?", ([] if errors else [COMMIT]) + [EDIT, CANCEL])
        if choice == COMMIT:
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


def _commit(project: Project, message: str) -> str:
    fd, path = tempfile.mkstemp(prefix="lg-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(message)
        result = gitops.run(["commit", "-q", "-F", path], cwd=project.root)
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
