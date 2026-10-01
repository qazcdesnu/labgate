"""대상 폴더 검사, 충돌 검사, 쓰기와 롤백 (설계 문서 §5.3, §8.3, §14.1 `writer`)."""
import stat
from pathlib import PurePosixPath

import pytest

import labgate.writer as writer
from labgate.plan import PlannedFile
from labgate.writer import TargetError, check_target, find_conflicts, write_plan

PLAN = [
    PlannedFile(PurePosixPath("README.md"), "hello\n"),
    PlannedFile(PurePosixPath("a/b/c.md"), "c\n"),
    PlannedFile(PurePosixPath("a/.gitkeep"), ""),
    PlannedFile(PurePosixPath("scripts/run"), "#!/bin/sh\n", 0o755),
]


def tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def fail_on(monkeypatch, n, exc=OSError("디스크 가득 참")):
    """n번째 파일을 쓸 때 예외를 낸다."""
    real = writer._write_file
    calls = {"n": 0}

    def fake(path, f):
        calls["n"] += 1
        if calls["n"] == n:
            raise exc
        real(path, f)

    monkeypatch.setattr(writer, "_write_file", fake)


# ---------------------------------------------------------------- check_target


def test_target_missing(tmp_path):
    assert check_target(tmp_path / "new", force=False) is False


def test_target_empty_dir(tmp_path):
    assert check_target(tmp_path, force=False) is True


def test_target_not_empty_needs_force(tmp_path):
    (tmp_path / "x").write_text("x")
    with pytest.raises(TargetError, match="--force"):
        check_target(tmp_path, force=False)
    assert check_target(tmp_path, force=True) is True


def test_target_is_file(tmp_path):
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(TargetError, match="폴더가 아닙니다"):
        check_target(f, force=True)


# ---------------------------------------------------------------- find_conflicts


def test_no_conflicts_when_only_directories_exist(tmp_path):
    (tmp_path / "a/b").mkdir(parents=True)
    assert find_conflicts(tmp_path, PLAN) == []


def test_conflicts(tmp_path):
    (tmp_path / "README.md").write_text("mine")
    (tmp_path / "scripts").write_text("파일이 폴더 자리에")
    (tmp_path / "a/b/c.md").mkdir(parents=True)  # 폴더가 파일 자리에
    assert [str(p) for p in find_conflicts(tmp_path, PLAN)] == ["README.md", "a/b/c.md", "scripts"]


# ---------------------------------------------------------------- 새 대상


def test_new_target_written_with_modes(tmp_path):
    target = tmp_path / "proj"
    write_plan(target, PLAN)
    assert tree(target) == ["README.md", "a", "a/.gitkeep", "a/b", "a/b/c.md", "scripts", "scripts/run"]
    assert (target / "README.md").read_bytes() == b"hello\n"
    assert mode(target / "README.md") == 0o644 and mode(target / "scripts/run") == 0o755
    assert [p.name for p in tmp_path.iterdir()] == ["proj"]  # 임시 폴더가 남지 않음


def test_new_target_is_atomic(tmp_path, monkeypatch):
    """쓰는 동안 대상 경로는 존재하지 않는다 (임시 폴더에 쓰고 마지막에 이름을 바꾼다)."""
    target = tmp_path / "proj"
    real = writer._write_file
    seen = []

    def spy(path, f):
        seen.append(target.exists())
        real(path, f)

    monkeypatch.setattr(writer, "_write_file", spy)
    write_plan(target, PLAN)
    assert seen == [False] * len(PLAN) and target.is_dir()


def test_new_target_creates_parents(tmp_path):
    target = tmp_path / "x/y/proj"
    write_plan(target, PLAN)
    assert (target / "README.md").exists()


@pytest.mark.parametrize("exc", [OSError("디스크 가득 참"), KeyboardInterrupt()])
def test_new_target_rollback(tmp_path, monkeypatch, exc):
    target = tmp_path / "x/y/proj"
    fail_on(monkeypatch, 3, exc)
    with pytest.raises(type(exc)):
        write_plan(target, PLAN)
    assert list(tmp_path.iterdir()) == []  # 임시 폴더와 새로 만든 상위 폴더까지 정리


def test_new_target_rollback_keeps_existing_parents(tmp_path, monkeypatch):
    (tmp_path / "x").mkdir()
    (tmp_path / "x/keep").write_text("k")
    fail_on(monkeypatch, 2)
    with pytest.raises(OSError):
        write_plan(tmp_path / "x/y/proj", PLAN)
    assert tree(tmp_path) == ["x", "x/keep"]


# ---------------------------------------------------------------- 기존 대상


def test_existing_target_keeps_other_files(tmp_path):
    (tmp_path / "mine.txt").write_text("mine")
    (tmp_path / "a").mkdir()
    write_plan(tmp_path, PLAN)
    assert (tmp_path / "mine.txt").read_text() == "mine"
    assert (tmp_path / "a/b/c.md").read_text() == "c\n"


@pytest.mark.parametrize("exc", [OSError("디스크 가득 참"), KeyboardInterrupt()])
def test_existing_target_rollback(tmp_path, monkeypatch, exc):
    (tmp_path / "mine.txt").write_text("mine")
    (tmp_path / "a").mkdir()
    (tmp_path / "a/old.md").write_text("old")
    fail_on(monkeypatch, 4, exc)
    with pytest.raises(type(exc)):
        write_plan(tmp_path, PLAN)
    assert tree(tmp_path) == ["a", "a/old.md", "mine.txt"]  # 원래 있던 것만 남는다


def test_existing_file_is_never_overwritten(tmp_path):
    """충돌 검사를 건너뛰어도 쓰기는 기존 파일을 덮어쓰지 않고 롤백한다."""
    (tmp_path / "a/b").mkdir(parents=True)
    (tmp_path / "a/b/c.md").write_text("mine")
    with pytest.raises(FileExistsError):
        write_plan(tmp_path, PLAN)
    assert (tmp_path / "a/b/c.md").read_text() == "mine"
    assert tree(tmp_path) == ["a", "a/b", "a/b/c.md"]


def test_written_files_use_lf(tmp_path):
    write_plan(tmp_path / "p", [PlannedFile(PurePosixPath("x.md"), "a\nb\n")])
    assert (tmp_path / "p/x.md").read_bytes() == b"a\nb\n"
