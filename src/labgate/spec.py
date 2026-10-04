"""`lg spec adopt`: 에이전트가 `notes/`에 쓴 사양 초안을 stub 사양에 합쳐 확정한다 (설계 문서 §24.8).

초안은 사양의 번호 붙은 절(`## 3. Frontmatter` …)만 쓴다. stub의 frontmatter와 나머지 절은 그대로 두고,
초안에 있는 절만 바꾼다. 사람의 `spec` 커밋 하나로 확정한다(규칙 문서는 사람만 고친다, G7).
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer

from . import commit as commit_module
from . import prompts
from .errors import EXIT_ABORT, EXIT_TARGET, EXIT_USAGE, Fail
from .project import Project, build_message, find_project
from .stubs import STUBS

SECTION_RE = re.compile(r"^## (\d+)\. .*$", re.M)
ANY_SECTION_RE = re.compile(r"^## .*$", re.M)
STUB_NOTE = "> 이 사양은 아직 공통 구조만 있다."
TODO = "> TODO"
INDEX = "specs/README.md"
COMMIT, CANCEL = "커밋", "취소"


@dataclass
class Adoption:
    draft: str          # 저장소 기준 경로
    name: str           # stub 이름 (catalog …)
    target: str         # specs/doc-types/<name>.spec.md
    before: str
    after: str
    replaced: list[int]


def run_adopt(drafts: list[str], name: Optional[str], cwd: Optional[Path] = None) -> str:
    project = find_project(cwd)
    commit_module.require_human_terminal(project, "lg spec adopt", "에이전트는 사양 초안을 notes/ 에 쓰고 사람에게 확정을 요청합니다.")
    if name and len(drafts) != 1:
        raise Fail(EXIT_USAGE, "✗ --name 은 초안 하나에만 쓸 수 있습니다.")
    cwd = cwd or Path.cwd()
    adoptions = [_plan(project, project.relative(d, cwd), name) for d in drafts]
    names = [a.name for a in adoptions]
    if len(set(names)) != len(names):
        raise Fail(EXIT_USAGE, "✗ 같은 사양에 초안이 둘 이상입니다: " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
    index_before, index_after = _index(project, names)
    _check_ready(project, [a.target for a in adoptions] + [INDEX])

    for a in adoptions:
        typer.echo(_diff(a.target, a.before, a.after))
        typer.echo(f"  ({a.draft} → §{', §'.join(map(str, a.replaced))})\n")
    if index_after != index_before:
        typer.echo(_diff(INDEX, index_before, index_after))
    message = _message(project, adoptions)
    typer.echo("\n" + "\n".join(f"  ┊ {l}" for l in message.rstrip("\n").split("\n")) + "\n")
    if prompts.select("어떻게 할까요?", [COMMIT, CANCEL]) != COMMIT:
        raise Fail(EXIT_ABORT, "취소했습니다. 아무것도 바꾸지 않았습니다.")

    for a in adoptions:
        _write(project.root / a.target, a.after)
    if index_after != index_before:
        _write(project.root / INDEX, index_after)
    paths = [a.target for a in adoptions] + ([INDEX] if index_after != index_before else [])
    project.git("add", "--", *paths)
    sha = commit_module._commit(project, message, allow_empty=False)
    project.refresh_human_files()
    lines = [f"✓ 커밋했습니다: {sha} {message.split(chr(10), 1)[0]}",
             f"  초안은 그대로 두었습니다 ({', '.join(a.draft for a in adoptions)}). 필요 없으면 지우세요.",
             "  " + commit_module.next_step_hint(project, message, from_draft=False)]
    return "\n".join(lines)


# ---------------------------------------------------------------- 합치기


def _plan(project: Project, draft: str, name: Optional[str]) -> Adoption:
    path = project.root / draft
    if not path.is_file():
        raise Fail(EXIT_USAGE, f"✗ 초안이 없습니다: {draft}")
    text = path.read_text(encoding="utf-8")
    name = name or _name_of(draft, text)
    known = {s.name for s in STUBS}
    if name not in known:
        raise Fail(EXIT_USAGE, f"✗ {draft}: stub 사양 이름이 아닙니다 ({name}). --name 으로 지정하세요.\n"
                   f"  stub 사양: {', '.join(sorted(known))}")
    target = f"specs/doc-types/{name}.spec.md"
    if not (project.root / target).is_file():
        raise Fail(EXIT_USAGE, f"✗ {target} 가 없습니다.")
    before = (project.root / target).read_text(encoding="utf-8")
    after, replaced = merge(before, text, draft)
    return Adoption(draft, name, target, before, after, replaced)


def _name_of(draft: str, text: str) -> str:
    """초안 frontmatter의 id, 없으면 파일 이름(`catalog.md`, `catalog.spec.md`)."""
    m = re.match(r"^---\n(?:.*\n)*?id:\s*(\S+)\s*\n(?:.*\n)*?---\n", text)
    if m:
        return m.group(1).strip("\"'")
    stem = Path(draft).name
    for suffix in (".spec.md", ".md"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def sections(text: str) -> tuple[str, list[tuple[int, str, str]]]:
    """(첫 `## N.` 앞부분, [(번호, 제목 줄, 본문)])."""
    found = list(SECTION_RE.finditer(text))
    if not found:
        return text, []
    head = text[:found[0].start()]
    out = []
    for i, m in enumerate(found):
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append((int(m.group(1)), m.group(0), text[m.end():end]))
    return head, out


def merge(stub: str, draft: str, draft_name: str = "초안") -> tuple[str, list[int]]:
    """stub에 초안의 번호 붙은 절을 넣는다. 초안에 없는 절은 stub 그대로. 결과에 TODO가 남으면 오류."""
    body = draft[draft.index("\n---\n", 3) + 5:] if draft.startswith("---\n") and "\n---\n" in draft[3:] else draft
    unnumbered = [m.group(0) for m in ANY_SECTION_RE.finditer(body) if not SECTION_RE.match(m.group(0))]
    if unnumbered:
        raise Fail(EXIT_USAGE, f"✗ {draft_name}: 번호 없는 절은 옮길 곳을 알 수 없습니다: {', '.join(unnumbered)}\n"
                   "  사양의 절 번호(## 3. Frontmatter …)로 쓰세요.")
    _, new = sections(body)
    if not new:
        raise Fail(EXIT_USAGE, f"✗ {draft_name}: 사양의 번호 붙은 절(## 3. Frontmatter …)이 없습니다.")
    replacement = {n: b for n, _, b in new}
    head, old = sections(stub)
    numbers = {n for n, _, _ in old}
    extra = sorted(set(replacement) - numbers)
    if extra:
        raise Fail(EXIT_USAGE, f"✗ {draft_name}: 사양에 없는 절입니다: " + ", ".join(f"§{n}" for n in extra))

    head = re.sub(r"^(# .+?) \(stub\)$", r"\1", head, count=1, flags=re.M)
    head = "\n".join(l for l in head.split("\n") if not l.startswith(STUB_NOTE))
    head = re.sub(r"\n{3,}", "\n\n", head)
    head = re.sub(r"^status: *stub$", "status: complete", head, count=1, flags=re.M)
    parts = [head.rstrip("\n") + "\n"]
    for n, heading, b in old:
        text = replacement.get(n, b)
        parts.append(f"\n{heading}\n\n{text.strip()}\n")
    result = "".join(parts)
    todo = [n for n, _, b in old if n not in replacement and b.strip() == TODO]
    if todo:
        raise Fail(EXIT_USAGE, f"✗ {draft_name}: 합친 뒤에도 비어 있는(TODO) 절이 있습니다: "
                   + ", ".join(f"§{n}" for n in todo) + "\n  초안에 그 절을 채운 뒤 다시 하세요.")
    return result, sorted(replacement)


def _index(project: Project, names: list[str]) -> tuple[str, str]:
    """specs/README.md 표에서 그 사양 행의 상태 칸 stub → complete."""
    path = project.root / INDEX
    if not path.is_file():
        return "", ""
    before = path.read_text(encoding="utf-8")
    after = before
    for name in names:
        after = re.sub(rf"^(\| {re.escape(name)} \|.*\| )stub( \|)$", r"\1complete\2", after, count=1, flags=re.M)
    return before, after


def _check_ready(project: Project, paths: list[str]) -> None:
    if project.draft_path.exists():
        raise Fail(EXIT_TARGET, "✗ 사람 커밋 대기 상태입니다 (.lg/pending/COMMIT_MSG). 먼저 lg commit 으로 확정하세요.")
    changed = set(project.changed_paths())
    dirty = [p for p in paths if p in changed]
    if dirty:
        raise Fail(EXIT_TARGET, "✗ 커밋되지 않은 변경이 있습니다. 사람이 쓴 것을 덮어쓰지 않습니다:\n"
                   + "\n".join(f"  {p}" for p in dirty))
    staged = project.staged_paths()
    if staged:
        raise Fail(EXIT_USAGE, "✗ stage된 변경이 있습니다. 사양 커밋에 섞이지 않게 먼저 정리하세요:\n"
                   + "\n".join(f"  {p}" for p in staged))


def _message(project: Project, adoptions: list[Adoption]) -> str:
    names = [a.name for a in adoptions]
    summary = f"adopt {', '.join(names)} spec" + ("s" if len(names) > 1 else "")
    if len(f"spec: {summary}") > project.hook["MAX_HEADER"]:
        summary = f"adopt {len(names)} doc-type specs"
    body = "초안: " + ", ".join(a.draft for a in adoptions)
    return build_message("spec", summary, None, body, [])


def _diff(path: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                        f"{path} (지금)", f"{path} (확정)"))


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
