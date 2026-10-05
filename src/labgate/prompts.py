"""대화형 입력 (설계 문서 §6.3). 질문마다 바로 검증하고, 틀리면 이유를 보여 주고 다시 묻는다."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import questionary
import typer

from .config import (
    DEFAULT_AGENT_NAME,
    IDEATION_MILESTONES,
    MAX_MILESTONES,
    Config,
    Email,
    MilestoneTitle,
    PersonName,
    ProjectName,
    ResearchQuestion,
    Slug,
    Summary,
    check_value,
    default_agent_email,
    parse_config,
    suggest_slug,
)
from .gitops import global_identity

# 테스트에서 questionary의 입출력(input=, output=)을 바꿔 끼우는 자리
IO: dict[str, Any] = {}


def _answer(question: questionary.Question) -> Any:
    try:
        answer = question.ask()
    except EOFError:  # 입력이 닫힘 (Ctrl-D, 파이프 끝): 중단으로 처리
        raise KeyboardInterrupt from None
    if answer is None:  # Ctrl-C: questionary는 예외 대신 None을 돌려준다
        raise KeyboardInterrupt
    return answer


def _text(
    message: str,
    field_type: Any,
    default: str = "",
    extra: Optional[Callable[[Any], Optional[str]]] = None,
) -> Any:
    """한 필드를 묻고 정규화된 값을 돌려준다. `extra`는 다른 답과의 관계 검사 (오류 문구 또는 None)."""
    def validate(raw: str) -> Any:
        value, error = check_value(field_type, raw)
        return error or (extra(value) if extra else None) or True

    raw = _answer(questionary.text(message, default=default, validate=validate, **IO))
    return check_value(field_type, raw)[0]


def _confirm(message: str, default: bool) -> bool:
    return bool(_answer(questionary.confirm(message, default=default, **IO)))


def ask_path() -> Path:
    raw = _answer(questionary.text(
        "프로젝트 경로", validate=lambda v: bool(v.strip()) or "경로를 입력하세요", **IO
    ))
    return Path(raw.strip()).expanduser()


KIND_CHOICES = {"연구 (research)": "research", "아이디어 탐색 (ideation)": "ideation", "제안서 (proposal)": "proposal"}


KIND_LABELS = {"research": "연구", "ideation": "아이디어 탐색", "proposal": "제안서"}
QUESTION_LABELS = {"research": "연구 질문", "ideation": "탐색 주제", "proposal": "제안 핵심 질문"}


def ask_config(target: Path, kind: Optional[str] = None) -> Config:
    """§6.3 질문 2–12. 종류(§25)는 `--kind`가 없을 때 처음에 묻는다."""
    if kind is None:
        kind = KIND_CHOICES[select("프로젝트 종류", list(KIND_CHOICES))]
    name = _text("프로젝트 이름", ProjectName)
    slug = _text("slug (영문 소문자·숫자·하이픈)", Slug, default=suggest_slug(target) or "")
    summary = _text("한 줄 요약", Summary)
    label = {"proposal": "제안 핵심 질문", "ideation": "탐색 주제 (질문이 아니어도 된다)"}.get(kind, "핵심 연구 질문")
    question = _text(label, ResearchQuestion)

    git_name, git_email = global_identity()
    humans: list[dict[str, str]] = []
    while True:
        first = not humans
        h_name = _text("사람 이름", PersonName, default=git_name if first else "")
        h_email = _text(
            "사람 이메일", Email, default=git_email if first else "",
            extra=lambda v: "이미 입력한 사람의 이메일입니다" if v in {h["email"] for h in humans} else None,
        )
        humans.append({"name": h_name, "email": h_email})
        if not _confirm("사람을 더 추가할까요?", default=False):
            break

    human_emails = {h["email"] for h in humans}
    agent_name = _text("에이전트 이름", PersonName, default=DEFAULT_AGENT_NAME)
    agent_email = _text(
        "에이전트 이메일", Email, default=default_agent_email(slug),
        extra=lambda v: "사람의 이메일과 같을 수 없습니다" if v in human_emails else None,
    )
    claude_code = _confirm("Claude Code를 사용합니까?", default=True)

    milestones: list[dict[str, str]] = []
    optional = kind == "ideation"  # 생략하면 기본 두 개 (§26)
    if optional:
        typer.echo("마일스톤을 생략하면 기본 두 개를 씁니다: " + ", ".join(IDEATION_MILESTONES))
    while len(milestones) < MAX_MILESTONES:
        n = len(milestones)
        title = _answer(questionary.text(
            f"M{n} 제목 (빈 입력이면 종료)",
            validate=lambda v, n=n: _milestone_error(v, n, optional) or True,
            **IO,
        )).strip()
        if not title:
            break
        milestones.append({"title": check_value(MilestoneTitle, title)[0]})
    else:
        typer.echo(f"마일스톤은 최대 {MAX_MILESTONES}개입니다. 입력을 마칩니다.")

    return parse_config({
        "schema_version": 1,
        "project": {"name": name, "slug": slug, "summary": summary, "research_question": question, "kind": kind},
        "people": {"humans": humans, "agent": {"name": agent_name, "email": agent_email}},
        "agent_tools": {"claude_code": claude_code},
        "milestones": milestones,
    })


def ask_name_slug(target: Path) -> tuple[str, str]:
    """`lg init --from`: 이름과 slug만 묻는다. 나머지는 ideation의 brief에서 온다."""
    name = _text("프로젝트 이름", ProjectName)
    slug = _text("slug (영문 소문자·숫자·하이픈)", Slug, default=suggest_slug(target) or "")
    return name, slug


def _milestone_error(raw: str, n: int, optional: bool = False) -> Optional[str]:
    if not raw.strip():
        return "마일스톤이 최소 1개 필요합니다" if n == 0 and not optional else None
    return check_value(MilestoneTitle, raw)[1]


def summarize(target: Path, config: Config, git: bool) -> str:
    lines = [
        f"경로: {target}",
        f"프로젝트: {config.project.name} ({config.project.slug})",
        f"요약: {config.project.summary}",
        f"종류: {KIND_LABELS[config.project.kind]}",
        f"{QUESTION_LABELS[config.project.kind]}: {config.project.research_question}",
        "사람: " + ", ".join(f"{h.name} <{h.email}>" for h in config.humans),
        f"에이전트: {config.agent.name} <{config.agent.email}>",
        f"Claude Code: {'사용' if config.agent_tools.claude_code else '사용 안 함'}",
        "마일스톤: " + ", ".join(f"{m.id} {m.title}" for m in config.milestones),
        f"Git: {'초기화하고 사람 신원으로 init 커밋' if git else '초기화하지 않음 (--no-git)'}",
    ]
    return "\n".join(lines)


def confirm_create() -> bool:
    return _confirm("이대로 만들까요?", default=True)


# ---------------------------------------------------------------- lg commit (§18.4)


def select(message: str, choices: list[str]) -> str:
    return _answer(questionary.select(message, choices=choices, **IO))


def checkbox(message: str, choices: list[str], checked: Optional[set[str]] = None) -> list[str]:
    """여러 개 고르기. `checked`의 항목은 미리 골라 둔다."""
    items = [questionary.Choice(c, checked=c in (checked or set())) for c in choices]
    return list(_answer(questionary.checkbox(message, choices=items, **IO)))


def text(message: str, validate: Optional[Callable[[str], Optional[str]]] = None, default: str = "") -> str:
    """한 줄 입력. `validate`는 오류 문구 또는 None을 돌려준다."""
    def check(raw: str) -> Any:
        return (validate(raw) if validate else None) or True

    return _answer(questionary.text(message, default=default, validate=check, **IO)).strip()
