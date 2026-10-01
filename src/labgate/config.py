"""설정 모델, 검증, YAML 로드·저장 (설계 문서 §6)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated, Any, Literal, Optional

import yaml
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+$")
MAX_MILESTONES = 20
DEFAULT_AGENT_NAME = "research-agent"


class ConfigError(Exception):
    """설정 검증 실패. `errors`는 `<필드 경로>: <이유>` 형식의 문자열 목록이다."""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


# ---------------------------------------------------------------- 필드 타입


def _no_newline(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("줄바꿈을 넣을 수 없습니다")
    return value


def _strip(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _lower(value: Any) -> Any:
    return value.strip().lower() if isinstance(value, str) else value


def _slug(value: str) -> str:
    if not SLUG_RE.match(value):
        raise ValueError(
            "소문자·숫자로 시작하고 소문자·숫자·하이픈만 쓰는 40자 이하여야 합니다 (예: cap-partition)"
        )
    return value


def _email(value: str) -> str:
    if not EMAIL_RE.match(value):
        raise ValueError("이메일 형식이 아닙니다 (예: name@example.com)")
    return value


def single_line(min_len: int, max_len: int) -> Any:
    return Annotated[
        str,
        BeforeValidator(_strip),
        Field(min_length=min_len, max_length=max_len),
        AfterValidator(_no_newline),
    ]


ProjectName = single_line(1, 100)
Summary = single_line(1, 200)
ResearchQuestion = single_line(1, 500)
PersonName = single_line(1, 60)
MilestoneTitle = single_line(1, 80)
Slug = Annotated[str, BeforeValidator(_strip), AfterValidator(_slug)]
Email = Annotated[str, BeforeValidator(_lower), AfterValidator(_email)]


# ---------------------------------------------------------------- 모델


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Project(_Model):
    name: ProjectName
    slug: Slug
    summary: Summary
    research_question: ResearchQuestion


class Person(_Model):
    name: PersonName
    email: Email


class People(_Model):
    humans: list[Person] = Field(min_length=1)
    agent: Optional[Person] = None  # 생략 시 Config가 기본값을 채운다


class AgentTools(_Model):
    claude_code: bool = True


class Milestone(_Model):
    id: Optional[str] = None  # 생략 시 순서대로 M0, M1, …
    title: MilestoneTitle


class Generated(_Model):
    labgate_version: str
    spec_version: int
    created: str


class Config(_Model):
    schema_version: Literal[1]
    project: Project
    people: People
    agent_tools: AgentTools = Field(default_factory=AgentTools)
    milestones: list[Milestone] = Field(min_length=1, max_length=MAX_MILESTONES)
    generated: Optional[Generated] = None  # .lg/project.yaml에만 있다

    @model_validator(mode="after")
    def _normalize(self) -> "Config":
        errors = _cross_errors(self.model_dump())
        if errors:
            raise ValueError("\n".join(errors))
        for i, m in enumerate(self.milestones):
            m.id = f"M{i}"
        if self.people.agent is None:
            self.people.agent = Person(
                name=DEFAULT_AGENT_NAME, email=default_agent_email(self.project.slug)
            )
        return self

    @property
    def humans(self) -> list[Person]:
        return self.people.humans

    @property
    def agent(self) -> Person:
        assert self.people.agent is not None
        return self.people.agent


def _cross_errors(data: dict[str, Any]) -> list[str]:
    """여러 필드에 걸친 규칙(마일스톤 ID 순서, 이메일 중복).

    필드 검증이 실패해도 함께 보고하기 위해 검증 전의 원본 dict에도 쓸 수 있게 작성한다.
    """
    errors: list[str] = []

    milestones = data.get("milestones")
    if isinstance(milestones, list):
        for i, m in enumerate(milestones):
            mid = m.get("id") if isinstance(m, dict) else None
            if mid is not None and mid != f"M{i}":
                errors.append(
                    f"milestones.{i}.id: 순서상 'M{i}'여야 합니다 (입력값: {mid!r}). "
                    "id를 지우면 자동으로 부여됩니다"
                )

    people = data.get("people")
    if not isinstance(people, dict):
        return errors
    seen: dict[str, int] = {}
    humans = people.get("humans")
    for i, h in enumerate(humans if isinstance(humans, list) else []):
        email = _lower(h.get("email")) if isinstance(h, dict) else None
        if not isinstance(email, str) or not email:
            continue
        if email in seen:
            errors.append(
                f"people.humans.{i}.email: people.humans.{seen[email]}과 이메일이 같습니다 ({email})"
            )
        else:
            seen[email] = i

    agent = people.get("agent")
    if isinstance(agent, dict):
        email, path = _lower(agent.get("email")), "people.agent.email"
    else:
        project = data.get("project")
        slug = project.get("slug") if isinstance(project, dict) else None
        email = default_agent_email(slug) if isinstance(slug, str) else None
        path = "people.agent.email (기본값)"
    if isinstance(email, str) and email in seen:
        errors.append(f"{path}: 사람의 이메일과 같을 수 없습니다 ({email})")
    return errors


# ---------------------------------------------------------------- 도우미


def default_agent_email(slug: str) -> str:
    return f"agent@{slug}.local"


def suggest_slug(path: str | Path) -> Optional[str]:
    """경로의 마지막 이름으로 slug 기본값을 만든다. 규칙에 맞지 않으면 None (§6.3 #3)."""
    name = Path(path).expanduser().resolve().name.lower()
    slug = re.sub(r"[^a-z0-9-]", "-", name)
    return slug if SLUG_RE.match(slug) else None


def check_value(field_type: Any, value: Any) -> tuple[Any, Optional[str]]:
    """대화형 입력 하나를 검증한다. (정규화된 값, 오류 메시지 또는 None)."""
    try:
        return TypeAdapter(field_type).validate_python(value), None
    except ValidationError as e:
        return value, _message(e.errors()[0])


# ---------------------------------------------------------------- 검증·입출력


_MESSAGES = {
    "missing": "필수 항목입니다",
    "extra_forbidden": "알 수 없는 항목입니다 (오타인지 확인하세요)",
    "string_type": "문자열이어야 합니다",
    "bool_parsing": "true 또는 false여야 합니다",
    "bool_type": "true 또는 false여야 합니다",
    "list_type": "목록이어야 합니다",
    "model_type": "키: 값 형식의 항목이어야 합니다",
    "model_attributes_type": "키: 값 형식의 항목이어야 합니다",
    "dict_type": "키: 값 형식의 항목이어야 합니다",
    "literal_error": "허용되는 값: {expected}",
}


def _message(err: dict[str, Any]) -> str:
    kind = err["type"]
    ctx = err.get("ctx", {})
    is_str = isinstance(err.get("input"), str)
    unit = "자" if is_str else "개"
    if kind in ("string_too_short", "too_short"):
        if is_str and ctx.get("min_length") == 1:
            return "비어 있을 수 없습니다"
        return f"{ctx['min_length']}{unit} 이상이어야 합니다"
    if kind in ("string_too_long", "too_long"):
        return f"{ctx['max_length']}{unit} 이하여야 합니다 (현재 {len(err['input'])}{unit})"
    if kind == "value_error":
        return str(ctx.get("error", err["msg"]))
    if kind in _MESSAGES:
        return _MESSAGES[kind].format(**ctx)
    return err["msg"]


def _format_errors(exc: ValidationError) -> list[str]:
    out: list[str] = []
    for err in exc.errors():
        path = ".".join(str(p) for p in err["loc"])
        msg = _message(err)
        if not path:  # model_validator: 메시지 안에 경로가 이미 있다
            out.extend(msg.splitlines())
            continue
        shown = err.get("input")
        if err["type"] != "missing" and isinstance(shown, (str, int, bool)):
            if isinstance(shown, str) and len(shown) > 40:
                shown = shown[:40] + "…"
            msg += f" (입력값: {shown!r})"
        out.append(f"{path}: {msg}")
    return out


def parse_config(data: Any) -> Config:
    if not isinstance(data, dict):
        raise ConfigError(["(최상위): 키: 값 형식의 YAML 문서여야 합니다"])
    try:
        return Config.model_validate(data)
    except ValidationError as e:
        errors = _format_errors(e)
        # 필드 오류가 있으면 교차 검사(model_validator)가 실행되지 않으므로 원본으로 따로 한다
        errors += [x for x in _cross_errors(data) if x not in errors]
        raise ConfigError(errors) from None


def load_config(path: str | Path) -> Config:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        raise ConfigError([f"{path}: 설정 파일을 읽지 못했습니다 ({e.strerror})"]) from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigError([f"{path}: YAML 형식 오류\n{e}"]) from None
    return parse_config(data)


def dump_project_yaml(config: Config, labgate_version: str, spec_version: int, created: str) -> str:
    """`.lg/project.yaml` 내용 (§6.1 + generated)."""
    data = {
        "schema_version": config.schema_version,
        "project": config.project.model_dump(),
        "people": {
            "humans": [h.model_dump() for h in config.humans],
            "agent": config.agent.model_dump(),
        },
        "agent_tools": config.agent_tools.model_dump(),
        "milestones": [m.model_dump() for m in config.milestones],
        "generated": {
            "labgate_version": labgate_version,
            "spec_version": spec_version,
            "created": created,
        },
    }
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)
