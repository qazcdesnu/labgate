"""생성 파일의 분류와 정규화·해시 (설계 문서 §22.3, §22.4).

분류는 경로 규칙 하나로 정한다. 생성 계획(`plan.py`), `lg upgrade`, 해시표를 만드는 스크립트가
모두 이 모듈을 쓴다. 지난 버전의 파일도 같은 규칙으로 분류할 수 있도록 경로만 본다.
"""
from __future__ import annotations

import hashlib
import re

MANAGED = "managed"        # 관리 문서: 손대지 않았으면 교체, 고쳤으면 갱신 실패
EDITABLE = "editable"      # 사람이 채우는 관리 문서: 고쳤으면 내용 유지
GITIGNORE = "gitignore"    # 관리 구역만 갱신
RESEARCH = "research"      # 연구 문서: frontmatter spec_version만 갱신
RECORD = "record"          # 초기화·갱신 기록 (.lg/project.yaml, .lg/identities.json)
OTHER = "other"            # .gitkeep 등: 무시

_MANAGED_FILES = {
    "AGENTS.md", "CLAUDE.md",
    "specs/conventions.md", "specs/workflow.md", "specs/git-commit.md",
    "specs/doc-types/task-card.spec.md", "specs/doc-types/review.spec.md",
    # ideation의 완성된 규칙 문서 (§26, §27): 사람이 채우는 틀이 아니다
    "specs/doc-types/idea.spec.md", "specs/doc-types/criteria.spec.md",
    "specs/doc-types/brief.spec.md", "specs/doc-types/anchor.spec.md",
}
_MANAGED_DIRS = (".claude/", "scripts/", ".lg/hooks/", "specs/procedures/", "specs/templates/")


def classify(path: str) -> str:
    if path == ".gitignore":
        return GITIGNORE
    if path.endswith(".gitkeep"):
        return OTHER
    if path in (".lg/project.yaml", ".lg/identities.json"):
        return RECORD
    if path in _MANAGED_FILES or path.startswith(_MANAGED_DIRS):
        return MANAGED
    if path == "specs/README.md" or (path.startswith("specs/doc-types/") and path.endswith(".spec.md")):
        return EDITABLE
    if path.endswith(".md"):
        return RESEARCH
    return OTHER


# ---------------------------------------------------------------- 정규화 (§22.4)

_AGENTS_PROJECT_LINES = (
    (re.compile(r"^- 이름: .*$", re.M), "- 이름: <name>"),
    (re.compile(r"^- 연구 질문: .*$", re.M), "- 연구 질문: <research_question>"),
    (re.compile(r"^- 제안 핵심 질문: .*$", re.M), "- 제안 핵심 질문: <research_question>"),  # kind: proposal
    (re.compile(r"^- 탐색 주제: .*$", re.M), "- 탐색 주제: <research_question>"),  # kind: ideation
    (re.compile(r"^- 에이전트 신원: .*$", re.M), "- 에이전트 신원: <agent>"),
)
_UPDATED_LINE = re.compile(r"^updated: .*\n", re.M)


def normalize(path: str, text: str) -> str:
    """프로젝트마다 달라지는 부분을 자리표시로 바꾼다."""
    if path == "AGENTS.md":
        for pattern, placeholder in _AGENTS_PROJECT_LINES:
            text = pattern.sub(placeholder, text, count=1)
    elif path == "specs/README.md":
        text = _UPDATED_LINE.sub("", text, count=1)
    return text


def carry_project_lines(path: str, current: str, new: str) -> str:
    """새 버전으로 교체할 때 지금 파일의 프로젝트 정보 줄(정규화되는 부분)을 그대로 옮긴다.
    사람이 프로젝트 이름 등을 고쳤어도 교체가 그 수정을 지우지 않게 한다."""
    if path != "AGENTS.md":
        return new
    for pattern, _ in _AGENTS_PROJECT_LINES:
        found = pattern.search(current)
        if found:
            new = pattern.sub(lambda _m: found.group(0), new, count=1)
    return new


def digest(path: str, text: str) -> str:
    return "sha256:" + hashlib.sha256(normalize(path, text).encode("utf-8")).hexdigest()


def variant(claude_code: bool, kind: str = "research") -> str:
    """해시표의 변형 이름. 연구는 spec_version 2부터 쓰던 이름 그대로, 다른 종류는 앞에 종류를 붙인다 (§25)."""
    base = "claude_code" if claude_code else "no_claude_code"
    return base if kind == "research" else f"{kind}_{base}"


# ---------------------------------------------------------------- .gitignore 줄 (§22.6)

BEGIN = "# labgate:begin"
END = "# labgate:end"


def gitignore_lines(text: str) -> list[str]:
    """빈 줄과 구역 표시를 뺀 줄 (주석 포함, 앞뒤 공백 제거)."""
    return [l.strip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith((BEGIN, END))]


def is_rule(line: str) -> bool:
    return not line.startswith("#")


# FILEMAP.md에서 프로젝트마다 다른 줄 (마일스톤 표의 행, 날짜)
_FILEMAP_VARIABLE = re.compile(r"^(\| `M\d+` \||updated: |spec_version: )")


def filemap_lines(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.strip() and not _FILEMAP_VARIABLE.match(l)]


def build_table(files_by_variant: dict[str, dict[str, str]], spec_version: int, labgate_version: str) -> dict:
    """해시표: {variant: {path: content}} → JSON으로 쓸 dict."""
    files: dict[str, dict[str, str]] = {}
    gitignore: list[str] = []
    filemap: list[str] = []
    for var, contents in sorted(files_by_variant.items()):
        for path, text in sorted(contents.items()):
            kind = classify(path)
            if kind in (MANAGED, EDITABLE):
                files.setdefault(path, {})[var] = digest(path, text)
            elif kind == GITIGNORE and not gitignore:
                gitignore = gitignore_lines(text)
            elif path == "FILEMAP.md" and var == "claude_code":
                filemap = filemap_lines(text)
    return {
        "spec_version": spec_version,
        "labgate_version": labgate_version,
        "files": files,
        "gitignore": gitignore,
        "filemap": filemap,
    }
