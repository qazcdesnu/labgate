"""모든 계층이 쓰는 fixture와 계층 표시. 계층 설명은 tests/README.md."""
import os
import shutil

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

import labgate.cli as cli
import labgate.commit as commit_module
import labgate.prompts as prompts

from support.configs import make_config
from support.env import isolated_git_env
from support.project import init_project
from support.releases import extract_sources

LAYERS = ("unit", "contract", "tools", "commands", "e2e")
NEEDS_GIT = {"tools", "commands", "e2e"}


def pytest_collection_modifyitems(config, items):
    """폴더 이름을 계층 marker로 붙인다 (`pytest -m unit`). Git이 필요한 계층은 git이 없으면 건너뛴다."""
    no_git = shutil.which("git") is None
    for item in items:
        layer = item.path.parent.name
        if layer in LAYERS:
            item.add_marker(getattr(pytest.mark, layer))
            if no_git and layer in NEEDS_GIT:
                item.add_marker(pytest.mark.skip(reason="git 없음"))


# ---------------------------------------------------------------- 설정, 환경


@pytest.fixture
def config():
    """렌더링이 까다로운 값을 담은 파싱된 설정 (support.configs.BASE)."""
    return make_config()


@pytest.fixture
def git_sandbox(tmp_path, monkeypatch):
    """isolated_git_env를 현재 프로세스(os.environ)에도 적용한다 (CliRunner로 lg를 돌릴 때)."""
    env = isolated_git_env(tmp_path)
    for k in list(os.environ):
        if k.startswith("GIT_"):
            monkeypatch.delenv(k)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return env


@pytest.fixture
def project(tmp_path, git_sandbox):
    """기본 설정(support.configs.project_config)으로 `lg init`한 프로젝트."""
    return init_project(tmp_path, git_sandbox)


@pytest.fixture(scope="session")
def old_sources(tmp_path_factory):
    """릴리즈 tag별 labgate 소스 (support.releases.make_old에 넘긴다)."""
    return extract_sources(tmp_path_factory)


# ---------------------------------------------------------------- 대화형


@pytest.fixture
def tty(monkeypatch):
    """터미널에서 실행하는 것으로 둔다 (`lg init` 대화형, `lg commit`)."""
    monkeypatch.setattr(cli, "_require_tty", lambda: None)
    monkeypatch.setattr(commit_module, "is_tty", lambda: True)


@pytest.fixture
def keys(monkeypatch, tty):
    """가짜 터미널 입력. keys("abc\\r", ...) 로 입력할 키를 모두 넣고 입력을 닫는다.
    입력이 모자라면 기다리지 않고 EOF로 끝난다 (중단, 코드 130)."""
    with create_pipe_input() as pipe:
        monkeypatch.setattr(prompts, "IO", {"input": pipe, "output": DummyOutput()})

        def send(*parts):
            pipe.send_text("".join(parts))
            pipe.pipe.close_write()

        yield send
