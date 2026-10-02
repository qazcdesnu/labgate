"""생성된 프로젝트 찾기, spec_version 확인, hook 규칙 읽기 (설계 문서 §18.3).

`lg commit`, `lg draft`가 쓴다. 커밋 규칙은 프로젝트의 `.lg/hooks/commit-msg`가 원본이므로
여기서 따로 정의하지 않고 그 파일을 모듈로 읽는다.
"""
from __future__ import annotations

import json
import os
import re
import runpy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from . import SPEC_VERSION, gitops
from .errors import EXIT_USAGE, Fail
from .gitops import GitError

# hook에서 가져오는 이름. hook과 lg 사이의 계약이다 (§11).
HOOK_NAMES = (
    "HUMAN_TYPES", "AGENT_TYPES", "COMMON_TYPES", "TASK_REQUIRED", "SOURCE_REQUIRED",
    "MAX_HEADER", "HEADER_RE", "TASK_ID_RE", "DECISION_ID_RE", "parse", "check",
)

# 사람이 쓸 수 있는 타입을 보여 줄 순서 (git-commit.md §3 표 순서)
TYPE_ORDER = ("gate", "decide", "plan", "spec", "respond", "exp", "run", "result", "ref", "log", "chore")


@dataclass
class Project:
    root: Path
    identities: dict[str, Any]
    hook: dict[str, Any]

    @property
    def pending(self) -> Path:
        return self.root / ".lg" / "pending"

    @property
    def draft_path(self) -> Path:
        return self.pending / "COMMIT_MSG"

    @property
    def human_files_path(self) -> Path:
        return self.pending / "HUMAN_FILES"

    def human_emails(self) -> set[str]:
        return {h["email"].lower() for h in self.identities.get("humans", [])}

    def human_types(self) -> list[str]:
        """사람 커밋에 쓸 수 있는 타입: 사람 전용 ∪ 공통 − {init}."""
        allowed = (set(self.hook["HUMAN_TYPES"]) | set(self.hook["COMMON_TYPES"])) - {"init"}
        rank = {t: i for i, t in enumerate(TYPE_ORDER)}
        return sorted(allowed, key=lambda t: (rank.get(t, len(rank)), t))

    def check_message(self, text: str) -> list[str]:
        """hook의 검사를 신원 검사 없이 돌린다."""
        return list(self.hook["check"](text, check_author=False))

    def trailers(self, text: str) -> dict[str, str]:
        return self.hook["parse"](text)[1]

    def header_type(self, text: str) -> Optional[str]:
        header = self.hook["parse"](text)[0]
        m = self.hook["HEADER_RE"].match(header or "")
        return m.group("type") if m else None

    def task_ids(self) -> list[str]:
        """`plan/milestones/*/tasks/*.md` 중 Task ID 형식인 파일 이름."""
        ids = {
            p.stem for p in self.root.glob("plan/milestones/*/tasks/*.md")
            if self.hook["TASK_ID_RE"].match(p.stem)
        }
        return sorted(ids, key=lambda t: [int(n) for n in re.findall(r"\d+", t)])

    # ---------------------------------------------------------------- git

    def git(self, *args: str) -> str:
        result = gitops.run(list(args), cwd=self.root)
        if result.returncode != 0:
            output = (result.stderr or result.stdout).strip()
            raise GitError(f"git {' '.join(args)} 이(가) 실패했습니다:\n" + "\n".join(f"  | {l}" for l in output.splitlines()))
        return result.stdout

    def staged_paths(self) -> list[str]:
        return [p for p in self.git("diff", "--cached", "--name-only", "-z").split("\0") if p]

    def changed_paths(self) -> list[str]:
        """커밋되지 않은 변경의 경로 (scripts/session-check와 같은 규칙, §17.2)."""
        entries = self.git("status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0")
        paths: set[str] = set()
        i = 0
        while i < len(entries):
            entry = entries[i]
            i += 1
            if not entry:
                continue
            status, path = entry[:2], entry[3:]
            paths.add(path)
            if "R" in status or "C" in status:
                if "R" in status:
                    paths.add(entries[i])
                i += 1
        return sorted(paths)

    def refresh_human_files(self) -> None:
        """HUMAN_FILES에서 이미 커밋된 경로를 뺀다. 남는 것이 없으면 지운다 (§18.2 7)."""
        if not self.human_files_path.exists():
            return
        listed = [l for l in self.human_files_path.read_text(encoding="utf-8").splitlines() if l]
        changed = set(self.changed_paths())
        remaining = [p for p in listed if p in changed]
        if remaining:
            self.human_files_path.write_text("".join(p + "\n" for p in remaining), encoding="utf-8")
        else:
            self.human_files_path.unlink()

    def relative(self, path: str, cwd: Path) -> str:
        """명령줄 경로(현재 폴더 기준)를 저장소 루트 기준 경로로."""
        full = os.path.abspath(cwd / path)
        rel = os.path.relpath(full, self.root)
        if rel == ".." or rel.startswith(".." + os.sep):
            raise Fail(EXIT_USAGE, f"✗ 저장소 밖의 경로입니다: {path}")
        return Path(rel).as_posix()


def build_message(ctype: str, summary: str, scope: Optional[str], body: Optional[str],
                  trailers: list[tuple[str, str]]) -> str:
    """사람 커밋 메시지. trailer 블록은 `Actor: human`으로 시작하는 마지막 한 문단이다."""
    header = f"{ctype}({scope}): {summary}" if scope else f"{ctype}: {summary}"
    parts = [header.strip()]
    if body and body.strip():
        parts.append(body.strip())
    parts.append("\n".join(["Actor: human", *(f"{k}: {v}" for k, v in trailers)]))
    return "\n\n".join(parts) + "\n"


def find_project(cwd: Optional[Path] = None) -> Project:
    """§18.3 1–5. 실패하면 Fail(2)."""
    cwd = cwd or Path.cwd()
    try:
        result = gitops.run(["rev-parse", "--show-toplevel"], cwd=cwd)
    except OSError:
        raise Fail(EXIT_USAGE, "✗ git 을 실행할 수 없습니다.") from None
    if result.returncode != 0:
        raise Fail(EXIT_USAGE, "✗ Git 저장소가 아닙니다. labgate 프로젝트 폴더 안에서 실행하세요.")
    root = Path(result.stdout.strip())

    project_yaml = root / ".lg" / "project.yaml"
    if not project_yaml.is_file():
        raise Fail(EXIT_USAGE, f"✗ labgate 프로젝트가 아닙니다 ({root} 에 .lg/project.yaml 이 없습니다).")
    try:
        version = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))["generated"]["spec_version"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as e:
        raise Fail(EXIT_USAGE, f"✗ .lg/project.yaml 을 읽지 못했습니다: {e}") from None
    if version != SPEC_VERSION:
        if version == 1:
            raise Fail(EXIT_USAGE, (
                "✗ labgate 0.1로 만든 프로젝트입니다 (spec_version 1).\n"
                "  lg commit, lg draft는 spec_version 2 프로젝트만 지원합니다. git commit 을 직접 쓰세요."
            ))
        raise Fail(EXIT_USAGE, (
            f"✗ 이 labgate가 모르는 spec_version 입니다: {version} (지원: {SPEC_VERSION}).\n"
            "  labgate를 업데이트하세요."
        ))

    try:
        identities = json.loads((root / ".lg" / "identities.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Fail(EXIT_USAGE, f"✗ .lg/identities.json 을 읽지 못했습니다: {e}") from None

    hook_path = root / ".lg" / "hooks" / "commit-msg"
    try:
        hook = runpy.run_path(str(hook_path), run_name="labgate_hook")
    except (OSError, SyntaxError) as e:
        raise Fail(EXIT_USAGE, f"✗ {hook_path} 를 읽지 못했습니다: {e}") from None
    missing = [n for n in HOOK_NAMES if n not in hook]
    if missing:
        raise Fail(EXIT_USAGE, f"✗ commit-msg hook이 spec_version {SPEC_VERSION} 형식이 아닙니다 (없음: {', '.join(missing)}).")
    return Project(root, identities, hook)
