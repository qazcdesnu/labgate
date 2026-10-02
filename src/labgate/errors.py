"""종료 코드와 명령 공통 오류 (설계 문서 §5.2, §18.6, §19.3)."""
from __future__ import annotations

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_TARGET, EXIT_GIT, EXIT_ABORT = 0, 1, 2, 3, 4, 130


class Fail(Exception):
    """정해진 종료 코드와 메시지로 명령을 끝낸다."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
