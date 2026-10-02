"""`lg draft`: 사람 커밋의 초안을 준비한다. 커밋하지 않는다 (설계 문서 §19)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .errors import EXIT_TARGET, EXIT_USAGE, Fail
from .project import Project, build_message, find_project


def parse_trailers(items: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """`KEY=VALUE` 목록 → (trailer 목록, 오류)."""
    trailers, errors = [], []
    for item in items:
        key, sep, value = item.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or not value:
            errors.append(f"--trailer 는 KEY=VALUE 형식입니다: {item}")
        elif key == "Actor":
            errors.append("Actor trailer는 지정할 수 없습니다 (항상 Actor: human).")
        else:
            trailers.append((key, value))
    return trailers, errors


def _covered(path: str, targets: list[str]) -> bool:
    return any(path == t or path.startswith(t.rstrip("/") + "/") for t in targets)


def run_draft(ctype: str, summary: str, scope: Optional[str], body: Optional[str],
              trailer_args: list[str], paths: list[str], cwd: Optional[Path] = None) -> str:
    """§19.2. 성공하면 출력할 안내를 돌려준다."""
    cwd = cwd or Path.cwd()
    project = find_project(cwd)

    # 2. 사람 커밋 대기 상태
    if project.draft_path.exists():
        raise Fail(EXIT_TARGET, (
            "✗ 사람 커밋 대기 상태입니다 (.lg/pending/COMMIT_MSG 가 있습니다).\n"
            "  사람이 lg commit 으로 확정한 뒤 다시 실행하세요."
        ))

    # 3. 메시지 검사 (아무것도 바꾸기 전에)
    trailers, errors = parse_trailers(trailer_args)
    allowed = project.human_types()
    if ctype not in allowed:
        errors.append(f"사람 커밋에 쓸 수 없는 타입입니다: {ctype} (가능: {', '.join(allowed)})")
    if not scope:
        scope = dict(trailers).get("Task")
    message = build_message(ctype, summary, scope, body, trailers)
    if not errors:
        errors = project.check_message(message)
    if errors:
        raise Fail(EXIT_USAGE, "✗ 초안이 커밋 규약(specs/git-commit.md)에 맞지 않습니다:\n" + "\n".join(f"  - {e}" for e in errors))

    # 대상 경로
    if paths:
        targets = [project.relative(p, cwd) for p in paths]
    else:
        if not project.human_files_path.exists():
            raise Fail(EXIT_USAGE, (
                "✗ 경로를 지정하세요. .lg/pending/HUMAN_FILES 가 없습니다\n"
                "  (scripts/session-check 가 세션 시작 때 사람의 변경을 기록합니다)."
            ))
        listed = [l for l in project.human_files_path.read_text(encoding="utf-8").splitlines() if l]
        changed = set(project.changed_paths())
        targets = [p for p in listed if p in changed]
        if not targets:
            raise Fail(EXIT_TARGET, "✗ .lg/pending/HUMAN_FILES 의 경로에 남은 변경이 없습니다.")

    # 4. 대상 밖에 이미 stage된 변경
    others = [p for p in project.staged_paths() if not _covered(p, targets)]
    if others:
        listing = "\n".join(f"    {p}" for p in others)
        raise Fail(EXIT_USAGE, (
            f"✗ stage된 다른 변경이 있습니다:\n{listing}\n"
            "  사람 커밋에 섞이지 않도록 먼저 커밋하거나 unstage(git restore --staged <경로>)하세요."
        ))

    # 5. stage
    project.git("add", "-A", "--", *targets)
    staged = project.staged_paths()
    if not staged:
        raise Fail(EXIT_TARGET, "✗ stage된 변경이 없습니다 (지정한 경로에 변경이 없습니다).")

    # 6. 초안
    project.pending.mkdir(parents=True, exist_ok=True)
    project.draft_path.write_text(message, encoding="utf-8", newline="\n")

    header = message.split("\n", 1)[0]
    return (
        f"✓ 초안을 준비했습니다: {header}\n"
        f"  stage된 파일 {len(staged)}개, 초안 .lg/pending/COMMIT_MSG\n"
        "  사람이 터미널에서 lg commit 을 실행해 확인하고 확정합니다."
    )
