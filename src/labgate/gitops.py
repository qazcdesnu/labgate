"""Git 명령 래퍼 (설계 문서 §5.3 3단계, §10)."""
from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import Config

# 사용자 환경의 이 변수들이 초기 커밋의 신원·대상 저장소를 바꾸지 못하게 한다 (§10.1 5)
_STRIPPED_ENV_PREFIXES = ("GIT_AUTHOR_", "GIT_COMMITTER_")
_STRIPPED_ENV = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"}


class GitError(Exception):
    """Git 관련 오류 (종료 코드 4)."""


def _env() -> dict[str, str]:
    return {
        k: v for k, v in os.environ.items()
        if not k.startswith(_STRIPPED_ENV_PREFIXES) and k not in _STRIPPED_ENV
    }


def _run(args: list[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, env=_env(), capture_output=True, text=True)


def run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """lg commit·lg draft용 git 실행. 사용자 환경의 GIT_AUTHOR_* 등은 지운다 (작성자 = 저장소 설정)."""
    return _run(args, cwd=cwd)


def check_available() -> None:
    try:
        ok = _run(["--version"]).returncode == 0
    except OSError:
        ok = False
    if not ok:
        raise GitError(
            "git 을 실행할 수 없습니다.\n  Git을 설치하거나, Git 없이 파일만 만들려면 --no-git 을 쓰세요."
        )


def inside_work_tree(path: Path) -> Optional[Path]:
    """path(또는 존재하는 가장 가까운 상위 폴더)가 Git 작업 트리 안이면 그 저장소 루트."""
    probe = path
    while not probe.is_dir():
        probe = probe.parent
    result = _run(["rev-parse", "--is-inside-work-tree", "--show-toplevel"], cwd=probe)
    lines = result.stdout.split()
    if result.returncode == 0 and lines and lines[0] == "true":
        return Path(lines[1]) if len(lines) > 1 else probe
    return None


def global_identity() -> tuple[str, str]:
    """대화형 기본값용 `git config --global user.name/email` (없으면 빈 문자열)."""
    def get(key: str) -> str:
        try:
            r = _run(["config", "--global", key])
        except OSError:
            return ""
        return r.stdout.strip() if r.returncode == 0 else ""
    return get("user.name"), get("user.email")


def init_message(config: Config) -> str:
    return f"init: initialize research project\n\n{config.project.name}\n\nActor: human\n"


@dataclass(frozen=True)
class Step:
    name: str
    args: list[str]


def init_repo(target: Path, config: Config) -> str:
    """§10.1: 저장소 초기화와 사람 신원의 초기 커밋. 초기 커밋의 짧은 해시를 돌려준다."""
    human = config.humans[0]
    fd, msg_path = tempfile.mkstemp(prefix="lg-init-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(init_message(config))
        steps = [
            Step("저장소 초기화", ["init", "-q"]),
            Step("기본 브랜치를 main으로", ["symbolic-ref", "HEAD", "refs/heads/main"]),
            Step("사람 이름 설정", ["config", "user.name", human.name]),
            Step("사람 이메일 설정", ["config", "user.email", human.email]),
            Step("hook 경로 설정", ["config", "core.hooksPath", ".lg/hooks"]),
            Step("파일 추가", ["add", "-A"]),
            Step("초기 커밋 (hook 검사 포함)", ["commit", "-q", "-F", msg_path]),
        ]
        for i, step in enumerate(steps):
            result = _run(step.args, cwd=target)
            if result.returncode != 0:
                raise GitError(_failure(target, step, result, steps[i:]))
        return _run(["rev-parse", "--short", "HEAD"], cwd=target).stdout.strip()
    finally:
        os.unlink(msg_path)


def _failure(target: Path, step: Step, result: subprocess.CompletedProcess, remaining: list[Step]) -> str:
    """§10.2: 실패한 단계, 명령, stderr, 남은 수동 명령."""
    def show(s: Step) -> str:
        if s.args[:1] == ["commit"]:  # 임시 메시지 파일은 이미 지워지므로 -m 형태로 안내
            return 'git commit -m "init: initialize research project" -m "Actor: human"'
        return shlex.join(["git", *s.args])

    output = (result.stderr or result.stdout).strip()
    lines = [
        f"Git 초기화 중 '{step.name}' 단계가 실패했습니다.",
        f"  명령: {show(step)}",
        *(f"  | {l}" for l in output.splitlines()),
        "",
        "생성된 파일은 그대로 두었습니다. 원인을 해결한 뒤 프로젝트 폴더에서 다음을 실행하세요:",
        f"  cd {shlex.quote(str(target))}",
        *(f"  {show(s)}" for s in remaining),
    ]
    return "\n".join(lines)
