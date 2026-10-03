"""저장소 경로와 격리된 Git 환경."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "labgate"
STATIC_DIR = SRC / "templates" / "static"
JINJA_DIR = SRC / "templates" / "jinja"


def isolated_git_env(tmp_path):
    """사용자 Git 설정과 GIT_* 변수를 차단한 환경. hook과 생성 스크립트의 `python3`는 테스트 중인 Python
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
