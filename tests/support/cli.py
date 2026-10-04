"""`lg`를 같은 프로세스에서 실행하기 (CliRunner)와 대화형 키 입력."""
import contextlib
import os

from typer.testing import CliRunner

from labgate.cli import app

ENTER, DOWN, SPACE, CLEAR, CTRL_C = "\r", "\x1b[B", " ", "\x15", "\x03"


def lg(*args, cwd=None):
    """`lg <args>`. cwd가 있으면 그 폴더에서 실행하고 돌아온다. 예외는 숨기지 않는다."""
    with (in_dir(cwd) if cwd else contextlib.nullcontext()):
        return CliRunner().invoke(app, [str(a) for a in args], catch_exceptions=False)


@contextlib.contextmanager
def in_dir(path):
    before = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(before)
