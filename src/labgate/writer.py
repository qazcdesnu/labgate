"""대상 폴더 검사, 충돌 검사, 파일 쓰기와 롤백 (설계 문서 §5.3, §8.3)."""
from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path, PurePosixPath
from typing import Iterable

from .plan import PlannedFile


class TargetError(Exception):
    """대상 폴더 문제 (종료 코드 3)."""


def check_target(target: Path, force: bool) -> bool:
    """§5.3 2단계. 대상이 이미 존재하면 True. 쓸 수 없는 상태면 TargetError."""
    if not os.path.lexists(target):
        return False
    if not target.is_dir():
        raise TargetError(f"대상이 폴더가 아닙니다: {target}\n  다른 경로를 지정하세요.")
    if not force and any(target.iterdir()):
        raise TargetError(
            f"대상 폴더가 비어 있지 않습니다: {target}\n"
            "  빈 폴더나 새 경로를 지정하거나, 기존 파일을 유지한 채 추가하려면 --force 를 쓰세요."
        )
    return True


def find_conflicts(target: Path, plan: Iterable[PlannedFile]) -> list[PurePosixPath]:
    """생성할 파일 자리에 이미 무언가 있거나, 만들 폴더 자리에 파일이 있는 경로 (§5.3 5단계)."""
    conflicts: set[PurePosixPath] = set()
    for f in plan:
        if os.path.lexists(target / f.path):
            conflicts.add(f.path)
        for parent in list(f.path.parents)[:-1]:  # 마지막은 '.'
            p = target / parent
            if os.path.lexists(p) and not p.is_dir():
                conflicts.add(parent)
    return sorted(conflicts, key=lambda p: p.parts)


def write_plan(target: Path, plan: list[PlannedFile]) -> None:
    """§8.3. 실패하거나 중단(Ctrl-C)되면 이번에 만든 것만 지우고 예외를 다시 올린다."""
    if os.path.lexists(target):
        _write_into_existing(target, plan)
    else:
        _write_new(target, plan)


def _write_file(path: Path, f: PlannedFile) -> None:
    with open(path, "x", encoding="utf-8", newline="\n") as fh:  # 'x': 기존 파일은 절대 덮어쓰지 않는다
        fh.write(f.content)
    os.chmod(path, f.mode)


def _write_new(target: Path, plan: list[PlannedFile]) -> None:
    """임시 폴더에 모두 쓴 뒤 이름을 바꾼다. 중간 실패 시 임시 폴더와 새로 만든 상위 폴더를 지운다."""
    created_parents: list[Path] = []
    for parent in reversed(target.parents):
        if not os.path.lexists(parent):
            parent.mkdir()
            created_parents.append(parent)
    tmp = target.parent / f".{target.name}.lg-tmp-{secrets.token_hex(4)}"
    try:
        tmp.mkdir()
        for f in plan:
            path = tmp / f.path
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_file(path, f)
        os.rename(tmp, target)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        for parent in reversed(created_parents):
            _rmdir_quietly(parent)
        raise


def _write_into_existing(target: Path, plan: list[PlannedFile]) -> None:
    """직접 쓰고, 새로 만든 파일·폴더를 기록해 두었다가 실패 시 역순으로 지운다."""
    created: list[Path] = []
    try:
        for f in plan:
            path = target / f.path
            for d in reversed(path.parents):
                if d != target and target in d.parents and not os.path.lexists(d):
                    d.mkdir()
                    created.append(d)
            _write_file(path, f)
            created.append(path)
    except BaseException:
        for p in reversed(created):
            if p.is_dir() and not p.is_symlink():
                _rmdir_quietly(p)
            else:
                p.unlink(missing_ok=True)
        raise


def _rmdir_quietly(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        pass
