"""긴 출력을 pager로 보여 준다 (`lg answer`, `lg commit`의 자세히 보기).

색·굵게 코드는 pager가 해석할 때만 보낸다. 해석하지 못하는 pager에 보내면 `ESC[1m` 같은 글자가
그대로 보인다(실사용: `PAGER`·`LESS`가 비어 있어 pydoc이 옵션 없는 less를 썼다).
"""
from __future__ import annotations

import os
import pydoc
import shutil
from typing import Optional


def _chosen() -> Optional[str]:
    return os.environ.get("MANPAGER") or os.environ.get("PAGER")


def keeps_color() -> bool:
    """pydoc이 고를 pager가 less인가 (사람이 정하지 않았으면 pydoc은 less를 쓴다)."""
    chosen = _chosen()
    if chosen is None:
        return shutil.which("less") is not None
    program = os.path.basename(chosen.split()[0]) if chosen.split() else ""
    return program == "less"


def page(colored: str, plain: str) -> None:
    """less면 `-R`을 더해 색을 그대로, 다른 pager면 색 없는 글을 보낸다."""
    if not keeps_color():
        pydoc.pager(plain)
        return
    before = os.environ.get("LESS")
    flags = before or ""
    if "R" not in flags and "r" not in flags:  # 예: LESS=-FRX 면 이미 있다
        os.environ["LESS"] = (flags + " -R").strip()
    try:
        pydoc.pager(colored)
    finally:
        if before is None:
            os.environ.pop("LESS", None)
        else:
            os.environ["LESS"] = before
