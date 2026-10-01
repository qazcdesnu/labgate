"""Typer 앱 (설계 문서 §5). `init`은 이후 단계에서 구현한다."""
from __future__ import annotations

from typing import Optional

import typer

from . import __version__

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"labgate {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version, is_eager=True, help="버전을 출력한다."
    ),
) -> None:
    """사람이 승인 게이트마다 판정하는 연구 프로젝트 작업 공간 도구."""


@app.command()
def init() -> None:
    """연구 프로젝트 작업 공간을 만든다."""
    typer.echo("lg init은 아직 구현되지 않았습니다.", err=True)
    raise typer.Exit(1)
