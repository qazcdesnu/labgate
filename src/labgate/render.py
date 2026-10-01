"""Jinja2 환경, 렌더링 컨텍스트, 필터 (설계 문서 §9)."""
from __future__ import annotations

import json
from dataclasses import asdict
from functools import lru_cache
from importlib.resources import files
from typing import Any, Optional

import jinja2

from . import SPEC_VERSION, __version__
from .config import Config
from .stubs import Stub

RESIDUE = ("{{", "{%")


class RenderError(Exception):
    """템플릿 렌더링 실패 (종료 코드 1)."""


def yq(value: Any) -> str:
    """문자열을 YAML frontmatter에 안전하게 넣는다. JSON 문자열은 유효한 YAML 문자열이다."""
    return json.dumps(value, ensure_ascii=False)


@lru_cache(maxsize=1)
def environment() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.PackageLoader("labgate", "templates/jinja"),
        undefined=jinja2.StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["yq"] = yq
    return env


def base_context(config: Config, today: str) -> dict[str, Any]:
    """모든 템플릿에 공통으로 넘기는 컨텍스트 (§9 표)."""
    return {
        "project": config.project.model_dump(),
        "humans": [h.model_dump() for h in config.humans],
        "agent": config.agent.model_dump(),
        "milestones": [
            {"id": m.id, "index": i, "title": m.title} for i, m in enumerate(config.milestones)
        ],
        "claude_code": config.agent_tools.claude_code,
        "today": today,
        "labgate_version": __version__,
        "spec_version": SPEC_VERSION,
    }


def milestone_context(base: dict[str, Any], index: int) -> dict[str, Any]:
    """마일스톤별 템플릿(A.10, A.11, A.14)용: `m`과 `prev`(직전 마일스톤 또는 None)를 더한다."""
    milestones = base["milestones"]
    prev: Optional[dict[str, Any]] = milestones[index - 1] if index > 0 else None
    return {**base, "m": milestones[index], "prev": prev}


def stub_context(base: dict[str, Any], stub: Stub) -> dict[str, Any]:
    """stub 사양 템플릿(B.7)용: `stub`을 더한다."""
    return {**base, "stub": asdict(stub)}


def render(template: str, context: dict[str, Any]) -> str:
    """`templates/jinja/` 기준 경로의 템플릿을 렌더링한다. 실패하면 RenderError.

    잔여 문법 검사는 검사용 컨텍스트(`probe_context`)로 렌더링한 결과에만 한다 (§9).
    """
    text = _render(template, context)
    check_residue(template, _render(template, probe_context(context)))
    return text


def _render(template: str, context: dict[str, Any]) -> str:
    try:
        return environment().get_template(template).render(context)
    except jinja2.TemplateNotFound as e:
        raise RenderError(f"{template}: 템플릿이 없습니다 ({e.name})") from e
    except jinja2.TemplateSyntaxError as e:
        raise RenderError(f"{template}:{e.lineno}: 템플릿 문법 오류: {e.message}") from e
    except jinja2.UndefinedError as e:
        raise RenderError(f"{template}: 정의되지 않은 변수: {e.message}") from e


def probe_context(value: Any) -> Any:
    """모든 문자열을 "x"로 바꾼 같은 구조의 값. 사용자 입력의 `{{`가 검사에 걸리지 않게 한다."""
    if isinstance(value, str):
        return "x"
    if isinstance(value, dict):
        return {k: probe_context(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [probe_context(v) for v in value]
    return value


def check_residue(name: str, text: str) -> None:
    """렌더링 결과에 템플릿 문법이 남아 있으면 RenderError (템플릿 실수 감지)."""
    for n, line in enumerate(text.splitlines(), 1):
        for token in RESIDUE:
            if token in line:
                raise RenderError(
                    f"{name}: {n}행에 템플릿 문법 '{token}'이 남아 있습니다 (템플릿 오류)"
                )


def read_static(path: str) -> str:
    """`templates/static/` 기준 경로의 파일을 그대로 읽는다."""
    resource = files("labgate").joinpath("templates", "static", *path.split("/"))
    try:
        return resource.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise RenderError(f"{path}: 정적 템플릿이 없습니다") from e
