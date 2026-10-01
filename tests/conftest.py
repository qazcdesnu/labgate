import copy
import os
import sys
from pathlib import Path

import pytest

from labgate.config import parse_config

ROOT = Path(__file__).resolve().parent.parent

BASE = {
    "schema_version": 1,
    "project": {
        "name": "Capacity-Driven: \"Adaptive\" 분할",  # 따옴표·콜론·한글
        "slug": "cap-partition",
        "summary": "Fenwick 분할을 적응 분할로 대체하는 연구",
        "research_question": "같은 state 예산에서 recall이 개선되는가?",
    },
    "people": {"humans": [{"name": "홍길동", "email": "gildong@example.com"}]},
    "milestones": [
        {"title": "기반 구축: 재현"},
        {"title": "디텍터 신호 \"유효성\" 검증"},
        {"title": "Split-only 적응 분할"},
    ],
}


def make_config(milestones=3, claude_code=True):
    data = copy.deepcopy(BASE)
    data["agent_tools"] = {"claude_code": claude_code}
    data["milestones"] = [
        BASE["milestones"][i] if i < 3 else {"title": f"마일스톤 {i}"} for i in range(milestones)
    ]
    return parse_config(data)


@pytest.fixture
def config():
    return make_config()


def isolated_git_env(tmp_path):
    """사용자 Git 설정과 GIT_* 변수를 차단한 환경. hook의 `python3`는 테스트 중인 Python
    (환경 변수 HOOK_PYTHON이 있으면 그것)으로 실행되게 PATH 맨 앞에 둔다."""
    bindir = tmp_path / "_bin"
    bindir.mkdir(exist_ok=True)
    link = bindir / "python3"
    if not link.exists():
        link.symlink_to(Path(os.environ.get("HOOK_PYTHON", sys.executable)))
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        PATH=f"{bindir}{os.pathsep}{env.get('PATH', '')}",
        HOME=str(tmp_path),  # 사용자 전역 설정(commit.gpgsign 등) 차단
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        LC_ALL="C.UTF-8",
    )
    return env


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
