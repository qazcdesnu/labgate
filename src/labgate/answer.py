"""`lg answer`: 열린 review를 보여 주고 판정을 물어, `## 응답`과 사람 커밋을 함께 만든다 (설계 문서 §24.4).

사람만 쓴다(터미널 검사). 확인하기 전에는 아무것도 쓰지 않는다.
"""
from __future__ import annotations

import datetime
import io
import pydoc
import re
import shutil
import sys
from dataclasses import dataclass, field
from typing import Optional

import typer
from rich.console import Console
from rich.markdown import Markdown

from . import commit as commit_module
from . import preview as preview_module
from . import prompts, state
from . import verify as verify_module
from .errors import EXIT_ABORT, EXIT_GIT, EXIT_TARGET, EXIT_USAGE, Fail
from .project import Project, build_message, find_project
from .state import Doc

VERDICTS = ("approve", "revise", "redirect")
MILESTONE_VERDICTS = ("go", "nogo", "conditional")
NO_MILESTONE_VERDICT = "하지 않음"
OWN_CHOICE = "직접 입력"
COMMIT, EDIT, CANCEL = "커밋", "편집기로 응답 수정", "취소"
DONE_TASK = ("closed", "redirected")
OPEN_DECISION = ("proposed", "discussing")
SUBSECTIONS = ("판정", "코멘트", "확정 결정", "다음 task 승인")


@dataclass
class Answer:
    """사람이 고른 것. 응답 문서와 커밋 메시지는 여기서 만든다."""
    review: Doc
    kind: str                       # gate | escalation
    task: str
    verdict: str = ""               # gate: approve|revise|redirect, escalation: 고른 선택지
    next_tasks: list[str] = field(default_factory=list)
    milestone_verdict: Optional[str] = None
    decisions: dict[str, str] = field(default_factory=dict)   # ID → 확정 내용
    comment: str = ""
    summary: str = ""               # escalation 커밋 헤더의 요약


def run_answer(review_id: Optional[str], no_tag: bool, cwd=None) -> str:
    project = find_project(cwd)
    commit_module.require_human_terminal(project, "lg answer", "에이전트는 응답을 쓰지 않습니다 (G5).")
    if review_id and project.hook["DECISION_ID_RE"].match(review_id):
        return _answer_decision(project, review_id)
    review = _choose(project, review_id)
    _check_ready(project, review)

    typer.echo(_show(project, review))
    ans = _ask(project, review)
    response = response_text(ans)
    messages = build_messages(project, ans)
    for m in messages:
        errors = project.check_message(m)
        if errors:  # 도구가 만든 메시지가 규약에 어긋나면 labgate 버그다
            raise Fail(EXIT_USAGE, "✗ 만든 커밋 메시지가 규약에 맞지 않습니다:\n" + "\n".join(f"  - {e}" for e in errors))
    typer.echo(_preview(project, messages))
    response = _confirm(project, ans, response, messages)

    _write(project, ans, response)
    project.git("add", "--", ans.review.rel)
    shas = [commit_module._commit(project, messages[0], allow_empty=False)]
    tags = [] if no_tag else commit_module._tag(project, messages[0])
    for m in messages[1:]:
        try:
            shas.append(commit_module._commit(project, m, allow_empty=True))
        except Fail as e:
            raise Fail(EXIT_GIT, f"{e}\n  응답 커밋({shas[0]})은 했습니다. 남은 커밋은 lg commit --allow-empty 로 하세요:\n"
                       + "\n".join(f"  │ {l}" for l in m.rstrip().split("\n"))) from None
    project.refresh_human_files()

    lines = [f"✓ 커밋했습니다: {sha} {m.split(chr(10), 1)[0]}" for sha, m in zip(shas, messages)]
    lines += [f"  tag: {t}" for t in tags]
    lines.append("  " + commit_module.next_step_hint(project, messages[0], from_draft=False))
    return "\n".join(lines)


# ---------------------------------------------------------------- 고르기, 전제


def _choose(project: Project, review_id: Optional[str]) -> Doc:
    reviews = state.open_reviews(project)
    if review_id:
        found = [r for r in reviews if r.id == review_id]
        if not found:
            raise Fail(EXIT_TARGET, f"✗ reviews/open/ 에 {review_id} 가 없습니다." + _listing(reviews))
        return found[0]
    closed = state.closed_review_ids(project)
    waiting = [r for r in reviews if r.status == "open" and r.id not in closed]
    if not waiting:
        raise Fail(EXIT_TARGET, "✗ 응답을 기다리는 review가 없습니다 (reviews/open/).")
    if len(waiting) == 1:
        return waiting[0]
    labels = {f"{r.id}  ({r.fields.get('kind', '')}, {r.fields.get('requested', '')})": r for r in waiting}
    return labels[prompts.select("응답할 review", list(labels))]


def _listing(reviews: list[Doc]) -> str:
    return ("\n  열린 review: " + ", ".join(r.id for r in reviews)) if reviews else ""


def _check_ready(project: Project, review: Doc) -> None:
    """§24.4.1. 사람이 이미 손댄 것은 덮어쓰지 않는다."""
    if review.id in state.closed_review_ids(project):
        raise Fail(EXIT_TARGET, (
            f"✗ {review.id} 는 이미 닫혔습니다 (reviews/closed/). reviews/open/ 의 것은 남은 사본입니다.\n"
            f"  내용을 확인하고 지우세요: rm {review.rel}"
        ))
    if project.draft_path.exists():
        raise Fail(EXIT_TARGET, (
            "✗ 사람 커밋 대기 상태입니다 (.lg/pending/COMMIT_MSG).\n"
            "  대화로 판정해 에이전트가 초안을 만들었다면 lg commit 으로 확정하세요."
        ))
    if review.status != "open":
        hint = "응답이 이미 있습니다. lg commit 으로 커밋하세요." if review.status == "answered" else ""
        raise Fail(EXIT_TARGET, f"✗ {review.id} 의 status가 {review.status} 입니다. {hint}".rstrip())
    if review.rel in project.changed_paths():
        raise Fail(EXIT_TARGET, (
            f"✗ {review.rel} 에 커밋되지 않은 변경이 있습니다. 응답을 직접 쓰고 있다면 그대로 lg commit 하세요.\n"
            "  lg answer 는 사람이 쓴 내용을 덮어쓰지 않습니다."
        ))
    others = [p for p in project.staged_paths() if p != review.rel]
    if others:
        raise Fail(EXIT_USAGE, "✗ stage된 다른 변경이 있습니다. 응답 커밋에 섞이지 않게 먼저 정리하세요:\n"
                   + "\n".join(f"  {p}" for p in others))
    kind = review.fields.get("kind")
    if kind not in ("gate", "escalation"):
        raise Fail(EXIT_USAGE, f"✗ {review.id} 의 kind를 알 수 없습니다: {kind}")
    if not project.hook["TASK_ID_RE"].match(review.fields.get("task", "")):
        raise Fail(EXIT_USAGE, f"✗ {review.id} 의 task 형식이 잘못되었습니다: {review.fields.get('task')}")


# ---------------------------------------------------------------- 보여 주기


def _render(markdown: str) -> str:
    """frontmatter를 떼고 터미널용으로 렌더링한다 (터미널이 아니면 색 없이)."""
    if markdown.startswith("---\n") and "\n---\n" in markdown[3:]:
        markdown = markdown.split("\n---\n", 1)[1]
    width = min(shutil.get_terminal_size((100, 40)).columns, 100)
    buffer = io.StringIO()
    Console(file=buffer, width=width, force_terminal=sys.stdout.isatty(), highlight=False).print(Markdown(markdown))
    return "\n".join(l.rstrip() for l in buffer.getvalue().rstrip().split("\n"))


def _show(project: Project, review: Doc) -> str:
    """응답 위의 에이전트 섹션을 렌더링한다. gate면 lg verify 요약을 붙인다."""
    body = re.split(r"^## 응답[ \t]*$", review.text, maxsplit=1, flags=re.M)[0]
    text = _render(body)
    if review.fields.get("kind") == "gate":
        lines, _ = verify_module.summary_for_commit(project, review.fields["task"])
        text += "\n\n" + "\n".join(lines)
    if sys.stdout.isatty() and text.count("\n") > shutil.get_terminal_size((100, 40)).lines - 4:
        pydoc.pager(text + "\n")  # MANPAGER, PAGER, 없으면 less
        return f"({review.rel} 를 보여 주었습니다)"
    return text + "\n"


# ---------------------------------------------------------------- 묻기 (§24.4.3, §24.4.4)


def _ask(project: Project, review: Doc) -> Answer:
    task = review.fields["task"]
    ans = Answer(review, review.fields["kind"], task)
    if ans.kind == "gate":
        ans.verdict = prompts.select(f"{task} 판정", list(VERDICTS))
        if ans.verdict == "approve":
            ans.next_tasks = _ask_next(project, review)
            if _milestone_ends(project, task, ans.next_tasks):
                mv = prompts.select(f"{state.milestone_of(task)} 마일스톤 판정도 함께 할까요?",
                                    [NO_MILESTONE_VERDICT, *MILESTONE_VERDICTS])
                ans.milestone_verdict = None if mv == NO_MILESTONE_VERDICT else mv
    else:
        ans.verdict = _ask_option(review)
    ans.decisions = _ask_decisions(project, review)
    need = ans.kind == "gate" and ans.verdict in ("revise", "redirect")
    ans.comment = prompts.text(
        "코멘트" + (" (무엇을 고치거나 바꿀지, 필수)" if need else " (선택, 빈 입력이면 없음)"),
        lambda v: "revise·redirect에는 코멘트가 필요합니다" if need and not v.strip() else None,
    )
    if ans.kind == "escalation":
        prefix = len(f"respond({task}): ")
        limit = project.hook["MAX_HEADER"] - prefix
        ans.summary = prompts.text(
            "커밋 요약 (한 줄)",
            lambda v: "요약을 입력하세요" if not v.strip() else f"{limit}자를 넘습니다" if len(v.strip()) > limit else None,
            default=ans.verdict[:min(40, limit)],
        )
    return ans


def _ask_next(project: Project, review: Doc) -> list[str]:
    """같은 마일스톤의 draft 카드에서 여러 개. 요청서의 proposed_next를 미리 골라 둔다."""
    task = review.fields["task"]
    drafts = [c.id for c in state.cards(project, state.milestone_of(task)) if c.status == "draft" and c.id != task]
    if not drafts:
        return []
    proposed = review.fields.get("proposed_next", "")
    labels = {f"{c}  {state.card_title(project, c)}".rstrip(): c for c in drafts}
    checked = {l for l, c in labels.items() if c == proposed}
    chosen = prompts.checkbox("다음 task 승인 (스페이스로 선택, 없으면 그냥 엔터)", list(labels), checked)
    ids = [labels[l] for l in chosen]
    if proposed in ids:  # 요청서가 제안한 것을 Next로
        ids.remove(proposed)
        ids.insert(0, proposed)
    return ids


def _milestone_ends(project: Project, task: str, next_tasks: list[str]) -> bool:
    """이 task가 그 마일스톤의 마지막이다: 다음 task를 고르지 않았고, 닫히지 않은 다른 task가 없다."""
    rest = [c for c in state.cards(project, state.milestone_of(task)) if c.id != task and c.status not in DONE_TASK]
    return not rest and not next_tasks


def _ask_option(review: Doc) -> str:
    options = parse_options(verify_module.section(review.text, "선택지"))
    if options:
        choice = prompts.select("선택", options + [OWN_CHOICE])
        if choice != OWN_CHOICE:
            return choice
    return prompts.text("선택한 내용", lambda v: "입력하세요" if not v.strip() else None)


def parse_options(section: str) -> list[str]:
    """`## 선택지`의 항목: `### 제목`이 있으면 제목들, 없으면 맨 바깥 목록 항목의 첫 줄."""
    headings = [m.group(1).strip() for m in re.finditer(r"^###\s+(.+)$", section, re.M)]
    if headings:
        return [_plain(h) for h in headings]
    items = [m.group(1).strip() for m in re.finditer(r"^(?:[-*]|\d+[.)])\s+(.+)$", section, re.M)]
    return [_plain(i) for i in items]


def _plain(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    return text.strip()[:120]


def _ask_decisions(project: Project, review: Doc) -> dict[str, str]:
    """요청서가 확정을 요청한 결정(frontmatter `decisions`)만 묻는다. 요청이 없으면 묻지 않는다
    (실사용: 제안된 결정 7개가 ID만으로 나와 무엇을 묻는지 알 수 없었다). 다른 결정은 `lg answer <D-ID>`."""
    asked = state.frontmatter_list(review.text, "decisions")
    docs = {d.id: d for d in state.decisions(project)}
    open_ids = [d for d in asked if d in docs and docs[d].status in OPEN_DECISION]
    if not open_ids:
        if asked:
            typer.echo(f"요청서가 확정을 요청한 결정({', '.join(asked)})은 이미 확정됐거나 문서가 없습니다.")
        return {}
    typer.echo("\n요청서가 이 판정과 함께 확정하기를 요청한 결정입니다. 고른 결정은 proposed → confirmed가 되고,"
               "\n고르지 않으면 지금 상태로 남습니다(나중에 lg answer <D-ID>로 확정할 수 있다).")
    labels = {f"{d}  {docs[d].fields.get('title', '')} ({docs[d].status})".replace("  (", " ("): d for d in open_ids}
    chosen = prompts.checkbox("확정할 결정 (스페이스로 선택, 없으면 그냥 엔터)", list(labels), set(labels))
    return {labels[l]: prompts.text(f"{labels[l]} 확정 내용 (한 줄)", lambda v: "입력하세요" if not v.strip() else None)
            for l in chosen}


# ---------------------------------------------------------------- 응답과 메시지


def response_text(ans: Answer) -> str:
    """`## 응답` 절 전체 (review.spec §4.3의 하위 섹션 순서)."""
    verdict = ans.verdict + (f"\n마일스톤 {state.milestone_of(ans.task)}: {ans.milestone_verdict}" if ans.milestone_verdict else "")
    decided = "\n".join(f"- {d}: {text}" for d, text in ans.decisions.items()) or "없음"
    nxt = ", ".join(ans.next_tasks) if ans.kind == "gate" and ans.next_tasks else "없음"
    parts = {"판정": verdict, "코멘트": ans.comment or "없음", "확정 결정": decided, "다음 task 승인": nxt}
    return "## 응답\n\n" + "\n\n".join(f"### {k}\n{parts[k]}" for k in SUBSECTIONS) + "\n"


def check_response(ans: Answer, response: str) -> list[str]:
    """편집기로 고친 응답의 검사: 하위 섹션이 모두 있고 판정이 비어 있지 않으며, gate 판정은 고른 것과 같다."""
    errors = []
    found = {m.group(1).strip(): m.end() for m in re.finditer(r"^### (.+)$", response, re.M)}
    missing = [s for s in SUBSECTIONS if s not in found]
    if missing:
        errors.append("하위 섹션이 없습니다: " + ", ".join(missing))
    if not response.lstrip().startswith("## 응답"):
        errors.append("첫 줄은 '## 응답'이어야 합니다")
    if "판정" in found:
        first = next((l.strip() for l in response[found["판정"]:].splitlines() if l.strip()), "")
        if not first or first.startswith("### "):
            errors.append("판정이 비어 있습니다")
        elif ans.kind == "gate" and first != ans.verdict:
            errors.append(f"판정({first})이 고른 판정({ans.verdict})과 다릅니다. 판정을 바꾸려면 취소하고 다시 하세요")
    return errors


def build_messages(project: Project, ans: Answer) -> list[str]:
    """첫째가 응답 커밋(gate 또는 respond). 다음 task가 여럿이면 plan, escalation에서 결정을 골랐으면 decide가 잇는다."""
    review_id = ans.review.id
    max_header = project.hook["MAX_HEADER"]
    decisions = list(ans.decisions)
    if ans.kind == "gate":
        trailers = [("Task", ans.task), ("Verdict", ans.verdict), ("Source", "document")]
        summary = ans.verdict
        if ans.verdict == "approve":
            nxt = ans.next_tasks[0] if ans.next_tasks else "none"
            trailers.append(("Next", nxt))
            if nxt != "none" and len(f"gate({ans.task}): {summary}, next {nxt}") <= max_header:
                summary += f", next {nxt}"
        if ans.milestone_verdict:
            trailers.append(("Milestone-Verdict", ans.milestone_verdict))
        if decisions:
            trailers.append(("Decisions", ", ".join(decisions)))
        trailers.append(("Review", review_id))
        messages = [build_message("gate", summary, ans.task, None, trailers)]
        rest = ans.next_tasks[1:]
        if rest:
            summary = f"approve {', '.join(rest)}"
            if len(f"plan: {summary}") > max_header:
                summary = f"approve {len(rest)} tasks after {ans.task} gate"
            messages.append(build_message("plan", summary, None, None, [("Approve", ", ".join(rest))]))
        return messages
    messages = [build_message("respond", ans.summary, ans.task, None,
                              [("Task", ans.task), ("Source", "document"), ("Review", review_id)])]
    if decisions:
        scope = decisions[0] if len(decisions) == 1 else None
        summary = "confirm" if scope else f"confirm {', '.join(decisions)}"
        if len(f"decide: {summary}") > max_header:
            summary = f"confirm {len(decisions)} decisions"
        messages.append(build_message("decide", summary, scope, f"{review_id} 응답에서 확정.",
                                      [("Decisions", ", ".join(decisions)), ("Source", "document")]))
    return messages


# ---------------------------------------------------------------- 미리보기, 확인, 쓰기


def _preview(project: Project, messages: list[str]) -> str:
    """§24.5.4: 반영할 수 없는 판정이면 아무것도 쓰기 전에 멈춘다."""
    lines, error = preview_module.preview(project, messages)
    if error:
        raise Fail(EXIT_TARGET, error + "\n  아무것도 바꾸지 않았습니다. 카드 상태를 확인하세요 (lg status).")
    return ("\n" + "\n".join(lines) + "\n") if lines else ""


def _confirm(project: Project, ans: Answer, response: str, messages: list[str]) -> str:
    while True:
        typer.echo("\n" + "\n".join(f"  │ {l}" for l in response.rstrip("\n").split("\n")))
        for m in messages:
            typer.echo("\n" + "\n".join(f"  ┊ {l}" for l in m.rstrip("\n").split("\n")))
        errors = check_response(ans, response)
        if errors:
            typer.echo("✗ 응답을 고쳐야 합니다:\n" + "\n".join(f"  - {e}" for e in errors), err=True)
        label = COMMIT if len(messages) == 1 else f"{COMMIT} ({len(messages)}개)"
        choice = prompts.select("어떻게 할까요?", ([] if errors else [label]) + [EDIT, CANCEL])
        if choice == label:
            return response
        if choice == CANCEL:
            raise Fail(EXIT_ABORT, "취소했습니다. 아무것도 바꾸지 않았습니다.")
        edited = commit_module._edit(project, response)
        if edited is not None:
            response = edited.rstrip("\n") + "\n"


def _write(project: Project, ans: Answer, response: str) -> None:
    """`## 응답` 절을 바꾸고 frontmatter의 사람 몫 필드를 채운다 (review.spec §5)."""
    text = ans.review.text
    m = re.search(r"^## 응답[ \t]*$", text, re.M)
    text = (text[:m.start()] if m else text.rstrip("\n") + "\n\n") + response
    today = datetime.date.today().isoformat()
    fields = {"status": "answered", "answered": today, "source": "document", "updated": today}
    if ans.kind == "gate":
        fields["verdict"] = ans.verdict
    for key, value in fields.items():
        text = _set_field(text, key, value)
    path = project.root / ans.review.rel
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _set_field(text: str, key: str, value: str) -> str:
    end = text.index("\n---\n", 3)
    head, n = re.subn(rf"^{key}:.*$", f"{key}: {value}", text[:end], count=1, flags=re.M)
    if not n:
        head = head + f"\n{key}: {value}"
    return head + text[end:]


# ---------------------------------------------------------------- 결정 확정 (§24.4.5)


def _answer_decision(project: Project, decision_id: str) -> str:
    """게이트와 별개로 결정 하나를 확정한다. 결정 문서는 고치지 않고(양식은 프로젝트의 stub 사양),
    확정 내용은 `decide` 커밋 본문에 남긴다. 상태는 다음 세션에 반영 도구가 바꾼다."""
    found = [d for d in state.decisions(project) if d.id == decision_id]
    if len(found) != 1:
        open_ids = [d.id for d in state.decisions(project) if d.status in OPEN_DECISION]
        raise Fail(EXIT_TARGET, f"✗ 결정 {decision_id} 를 하나로 찾지 못했습니다 (decisions/{decision_id}_*.md)."
                   + (f"\n  확정할 수 있는 결정: {', '.join(open_ids)}" if open_ids else ""))
    doc = found[0]
    if doc.status not in OPEN_DECISION:
        raise Fail(EXIT_TARGET, f"✗ {decision_id} 의 status가 {doc.status} 입니다 (확정할 수 있는 것: proposed, discussing).")
    if project.draft_path.exists():
        raise Fail(EXIT_TARGET, "✗ 사람 커밋 대기 상태입니다 (.lg/pending/COMMIT_MSG). 먼저 lg commit 으로 확정하세요.")
    if doc.rel in project.changed_paths():
        raise Fail(EXIT_TARGET, f"✗ {doc.rel} 에 커밋되지 않은 변경이 있습니다. 직접 고치고 있다면 lg commit (타입 decide) 하세요.")
    staged = project.staged_paths()
    if staged:
        raise Fail(EXIT_USAGE, "✗ stage된 변경이 있습니다. 결정 커밋에 섞이지 않게 먼저 정리하세요:\n"
                   + "\n".join(f"  {p}" for p in staged))

    typer.echo(_render(doc.text) + "\n")
    content = prompts.text(f"{decision_id} 확정 내용 (한 줄)", lambda v: "입력하세요" if not v.strip() else None)
    comment = prompts.text("근거·코멘트 (선택, 빈 입력이면 없음)")
    limit = project.hook["MAX_HEADER"] - len(f"decide({decision_id}): ")
    summary = prompts.text(
        "커밋 요약 (한 줄)",
        lambda v: "요약을 입력하세요" if not v.strip() else f"{limit}자를 넘습니다" if len(v.strip()) > limit else None,
        default=f"confirm {content}"[:limit],
    )
    body = f"확정: {content}" + (f"\n\n{comment}" if comment else "")
    message = build_message("decide", summary, decision_id, body,
                            [("Decisions", decision_id), ("Source", "document")])
    errors = project.check_message(message)
    if errors:
        raise Fail(EXIT_USAGE, "✗ 만든 커밋 메시지가 규약에 맞지 않습니다:\n" + "\n".join(f"  - {e}" for e in errors))
    typer.echo(_preview(project, [message]))
    typer.echo("\n".join(f"  ┊ {l}" for l in message.rstrip("\n").split("\n")))
    if prompts.select("어떻게 할까요?", [COMMIT, CANCEL]) != COMMIT:
        raise Fail(EXIT_ABORT, "취소했습니다. 아무것도 바꾸지 않았습니다.")
    sha = commit_module._commit(project, message, allow_empty=True)
    return "\n".join([f"✓ 커밋했습니다: {sha} {message.split(chr(10), 1)[0]}",
                      "  " + commit_module.next_step_hint(project, message, from_draft=False)])
