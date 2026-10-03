"""`lg verify`: 에이전트의 작업이 규칙을 지켰는지 커밋 이력과 문서로 사후에 확인한다 (설계 문서 §23).

읽기만 한다. 검사 기준은 그 프로젝트의 파일(commit-msg hook, identities, specs/)에서 읽는다.
V2–V4의 판정은 표준 라이브러리만 쓰는 함수로 짠다(다음 마이너 버전에서 hook으로 옮길 수 있게).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from . import gitops
from .errors import EXIT_USAGE, Fail
from .gitops import GitError
from .project import Project, find_project

PROTECTED = ("specs/", "AGENTS.md", "CLAUDE.md", ".claude/", ".lg/")
PASSTHROUGH = ("Revert ", "fixup! ", "squash! ", "amend! ")
VERDICT_STATE = {"approve": "closed", "revise": "revise", "redirect": "redirected"}
SEP = "\x1e"


# ---------------------------------------------------------------- 결과


@dataclass
class Finding:
    rule: str      # V1 … V5
    commit: str    # 짧은 해시 또는 ""
    header: str
    detail: str


@dataclass
class Report:
    scope: str
    commits: int
    findings: list[Finding] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)

    def by_rule(self, rule: str) -> list[Finding]:
        return [f for f in self.findings if f.rule == rule]


RULES = (
    ("V1", "신원과 타입 (P2, P3, P4)"),
    ("V2", "사람 몫의 상태 전이 (G4)"),
    ("V3", "review 응답 (G5)"),
    ("V4", "규칙 파일 (G7)"),
    ("V5", "문서 형식"),
)


# ---------------------------------------------------------------- Git


@dataclass
class Commit:
    sha: str
    parents: list[str]
    email: str
    body: str

    @property
    def short(self) -> str:
        return self.sha[:7]

    @property
    def header(self) -> str:
        return self.body.strip().split("\n", 1)[0] if self.body.strip() else ""


def _git(root: Path, *args: str, check: bool = True) -> str:
    result = gitops.run(list(args), cwd=root)
    if check and result.returncode != 0:
        raise GitError(f"git {' '.join(args)} 실패: {(result.stderr or result.stdout).strip()}")
    return result.stdout if result.returncode == 0 else ""


def _commits(root: Path, rev_range: Optional[str]) -> list[Commit]:
    args = ["log", "--reverse", f"--format=%H%x00%P%x00%ae%x00%B{SEP}"]
    if rev_range:
        args.append(rev_range)
    out = _git(root, *args, check=False)
    commits = []
    for record in out.split(SEP):
        record = record.lstrip("\n")
        if record:
            sha, parents, email, body = record.split("\x00", 3)
            commits.append(Commit(sha, parents.split(), email.strip().lower(), body))
    return commits


def _changes(root: Path, commit: Commit) -> list[tuple[str, Optional[str], Optional[str]]]:
    """(상태, 이전 경로, 새 경로). 이름 바꾸기를 따라간다."""
    args = ["diff-tree", "--no-commit-id", "-r", "-M", "--name-status", "-z"]
    if not commit.parents:
        args.append("--root")
    out = _git(root, *args, commit.sha, check=False).split("\0")
    result, i = [], 0
    while i < len(out) and out[i]:
        status = out[i]
        if status[0] in "RC":
            result.append((status[0], out[i + 1], out[i + 2]))
            i += 3
        else:
            path = out[i + 1]
            result.append((status[0], None if status[0] == "A" else path, None if status[0] == "D" else path))
            i += 2
    return result


def _show(root: Path, rev: str, path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    result = gitops.run(["show", f"{rev}:{path}"], cwd=root)
    return result.stdout if result.returncode == 0 else None


# ---------------------------------------------------------------- 표준 라이브러리만 쓰는 판정 (V2–V4)


def frontmatter_fields(text: Optional[str]) -> dict[str, str]:
    """frontmatter의 최상위 `key: value` 줄 (값은 따옴표를 뗀 문자열)."""
    if not text or not text.startswith("---\n") or "\n---\n" not in text[3:]:
        return {}
    block = text[4:text.index("\n---\n", 3)]
    fields = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):[ \t]*(.*)$", line)
        if m:
            fields[m.group(1)] = m.group(2).strip().strip('"\'')
    return fields


def section(text: Optional[str], heading: str) -> str:
    """`## heading` 아래부터 다음 `## ` 전까지 (없으면 빈 문자열)."""
    if not text:
        return ""
    m = re.search(rf"^## {re.escape(heading)}[ \t]*$", text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    n = re.search(r"^## ", rest, re.M)
    return (rest[:n.start()] if n else rest).strip()


def human_transition(doc_type: str, before: Optional[str], after: Optional[str]) -> bool:
    """G4: 사람 몫의 상태 전이인가."""
    if before is None or after is None or before == after:
        return False
    if doc_type == "task-card":
        return before == "draft" or (before == "in-review" and after in ("closed", "revise", "redirected"))
    if doc_type == "decision":
        return after == "confirmed"
    if doc_type == "milestone":
        return (before, after) in (("planned", "active"), ("active", "closed"))
    return False


def justifies(doc_type: str, doc_id: str, after: str, ctype: str, trailers: dict[str, str]) -> bool:
    """사람 커밋(타입, trailer)이 그 문서의 그 전이를 정하는가."""
    items = lambda key: [v.strip() for v in trailers.get(key, "").split(",") if v.strip()]  # noqa: E731
    task = trailers.get("Task", "")
    if doc_type == "task-card":
        if ctype == "plan" and doc_id in items("Approve"):
            return True
        if ctype == "gate" and trailers.get("Next") == doc_id:
            return True
        if ctype == "gate" and task == doc_id and VERDICT_STATE.get(trailers.get("Verdict", "")) == after:
            return True
        return ctype == "respond" and task == doc_id
    if doc_type == "decision":
        return ctype in ("decide", "gate") and doc_id in items("Decisions")
    if doc_type == "milestone":
        in_milestone = task.split("-")[0] == doc_id
        if after == "active":
            return ctype == "gate" and in_milestone and task.endswith("-T0") and trailers.get("Verdict") == "approve"
        return ctype == "gate" and in_milestone and bool(trailers.get("Milestone-Verdict"))
    return False


def doc_identity(path: str, fields: dict[str, str]) -> tuple[str, str]:
    """(유형, ID). 유형은 frontmatter `type`, ID는 `id`, 없으면 파일 이름에서."""
    doc_type = fields.get("type", "")
    doc_id = fields.get("id") or Path(path).stem
    if doc_type == "decision" and "_" in doc_id:
        doc_id = doc_id.split("_", 1)[0]
    if doc_type == "milestone" and not re.match(r"^M\d+$", doc_id):
        doc_id = Path(path).parent.name
    return doc_type, doc_id


def protected(path: Optional[str]) -> bool:
    return bool(path) and (path in PROTECTED or path.startswith(tuple(p for p in PROTECTED if p.endswith("/"))))


# ---------------------------------------------------------------- 프로젝트 규칙 읽기 (§23.3)


def _table_rows(text: str) -> list[list[str]]:
    rows = [l for l in text.splitlines() if l.startswith("|")]
    return [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows[2:]]


def project_rules(root: Path) -> dict:
    """conventions의 type·상태값 표, 완성 사양의 필수 필드."""
    conv = (root / "specs" / "conventions.md").read_text(encoding="utf-8")
    types: set[str] = set()
    start = conv.find("`type` 값:")
    if start != -1:
        for row in _table_rows(conv[start:start + 2000].split("\n\n- ")[0]):
            types.update(re.findall(r"`([a-z-]+)`", row[1] if len(row) > 1 else ""))
    statuses: dict[str, set[str]] = {}
    for row in _table_rows(section(conv, "5. 상태값")):
        if len(row) > 1:
            statuses[row[0].strip("`")] = set(re.findall(r"`([a-z-]+)`", row[1]))
    required: dict[str, list[str]] = {}
    for doc_type in ("task-card", "review"):
        spec = root / "specs" / "doc-types" / f"{doc_type}.spec.md"
        if spec.is_file():
            names = []
            for row in _table_rows(section(spec.read_text(encoding="utf-8"), "3. Frontmatter")):
                if len(row) > 1 and row[1] == "✓":
                    names += [n.split(".")[0] for n in re.findall(r"`([\w.]+)`", row[0])]
            required[doc_type] = sorted(set(names))
    return {"types": types, "statuses": statuses, "required": required}


# ---------------------------------------------------------------- 검사


def _range(root: Path, task: Optional[str], since: Optional[str], everything: bool) -> tuple[Optional[str], str]:
    if everything or task:
        return None, "처음부터" if everything else f"task {task}"
    if since:
        if gitops.run(["rev-parse", "--verify", "-q", f"{since}^{{commit}}"], cwd=root).returncode != 0:
            raise Fail(EXIT_USAGE, f"✗ 커밋을 찾을 수 없습니다: {since}")
        return f"{since}..HEAD", f"{since} 이후"
    tag = gitops.run(["describe", "--tags", "--match", "gate/*", "--abbrev=0", "HEAD"], cwd=root)
    if tag.returncode == 0 and tag.stdout.strip():
        name = tag.stdout.strip()
        return f"{name}..HEAD", f"마지막 게이트 {name} 이후"
    return None, "처음부터 (게이트 tag 없음)"


def _relevant(project: Project, commit: Commit, task: str, changes) -> bool:
    """그 task에 관련된 커밋: Task trailer·scope, Approve·Next, 그 task 카드 파일을 바꾼 커밋."""
    trailers = project.trailers(commit.body)
    scope_match = re.match(r"^[a-z]+\(([^()]+)\):", commit.header)
    if trailers.get("Task") == task or (scope_match and scope_match.group(1) == task):
        return True
    if task in [v.strip() for v in (trailers.get("Approve", "") + "," + trailers.get("Next", "")).split(",")]:
        return True
    if project.header_type(commit.body) in ("init", "spec"):  # 카드를 만들거나 버전만 올린 커밋은 task의 작업이 아니다
        return False
    return any(p and Path(p).stem == task and "/tasks/" in p for _, a, b in changes for p in (a, b))


def run_verify(task: Optional[str] = None, since: Optional[str] = None, everything: bool = False,
               cwd: Optional[Path] = None, project: Optional[Project] = None) -> Report:
    project = project or find_project(cwd)
    root = project.root
    if task and not project.hook["TASK_ID_RE"].match(task):
        raise Fail(EXIT_USAGE, f"✗ Task ID 형식이 아닙니다: {task}")
    rev_range, scope = _range(root, task, since, everything)
    commits = _commits(root, rev_range)
    humans = project.human_emails()
    agent = project.identities.get("agent", {}).get("email", "").lower()
    by_sha = {c.sha: c for c in _commits(root, None)}

    changes = {c.sha: _changes(root, c) for c in commits}
    if task:  # 관련 커밋과, 그것을 Applies·Refs로 가리키는 반영 커밋
        related = [c for c in commits if _relevant(project, c, task, changes[c.sha])]
        shas = [c.sha for c in related]
        commits = [c for c in commits if c in related
                   or any(sha.startswith(h) for h in _applies(project, c) for sha in shas)]
    report = Report(scope, len(commits))

    for c in commits:
        role = "agent" if c.email == agent else "human" if c.email in humans else None
        _check_identity(project, c, role, report)
        if role != "agent" or len(c.parents) > 1:
            continue
        _check_states(project, c, changes[c.sha], by_sha, humans, report)
        _check_response(project, c, changes[c.sha], report)
        _check_protected(project, c, changes[c.sha], report)
    _check_documents(project, report)
    if task:
        _checklist(project, task, commits, changes, report)
    return report


def _applies(project: Project, commit: Commit) -> list[str]:
    trailers = project.trailers(commit.body)
    return [h.strip().lower() for key in ("Applies", "Refs") for h in trailers.get(key, "").split(",") if h.strip()]


def _check_identity(project: Project, c: Commit, role: Optional[str], report: Report) -> None:
    if c.header.startswith(PASSTHROUGH):
        return
    if len(c.parents) > 1 or c.header.startswith("Merge "):
        if role == "agent":
            report.findings.append(Finding("V1", c.short, c.header, "에이전트 신원의 병합 커밋"))
        return
    if role is None:
        report.findings.append(Finding("V1", c.short, c.header, f"등록되지 않은 작성자 <{c.email}>"))
        return
    for error in project.check_message(c.body):
        report.findings.append(Finding("V1", c.short, c.header, error))
    actor = project.trailers(c.body).get("Actor")
    if actor in ("human", "agent") and actor != role:
        report.findings.append(Finding("V1", c.short, c.header, f"작성자 신원({role})과 Actor({actor})가 다름"))


def _check_states(project: Project, c: Commit, changes, by_sha, humans: set[str], report: Report) -> None:
    evidence = []
    for h in _applies(project, c):
        found = next((x for sha, x in by_sha.items() if sha.startswith(h)), None)
        if found and found.email in humans:
            evidence.append(found)
    for status, old, new in changes:
        path = new or old
        if not path.endswith(".md") or status == "A" or new is None:
            continue
        before_fields = frontmatter_fields(_show(project.root, c.parents[0], old) if c.parents else None)
        after_fields = frontmatter_fields(_show(project.root, c.sha, new))
        doc_type, doc_id = doc_identity(path, after_fields or before_fields)
        before, after = before_fields.get("status"), after_fields.get("status")
        if not human_transition(doc_type, before, after):
            continue
        if any(justifies(doc_type, doc_id, after, project.header_type(e.body) or "", project.trailers(e.body))
               for e in evidence):
            continue
        basis = ", ".join(e.sha[:7] for e in evidence) or "근거(Applies) 없음"
        report.findings.append(Finding("V2", c.short, c.header,
                                       f"{path}: status {before} → {after}, {basis}"))


def _check_response(project: Project, c: Commit, changes, report: Report) -> None:
    for status, old, new in changes:
        path = new or old
        if not path.startswith("reviews/") or status == "A" or old is None or new is None:
            continue
        before = section(_show(project.root, c.parents[0], old) if c.parents else None, "응답")
        after = section(_show(project.root, c.sha, new), "응답")
        if before != after:
            report.findings.append(Finding("V3", c.short, c.header, f"{path}: ## 응답 이 바뀜"))


def _check_protected(project: Project, c: Commit, changes, report: Report) -> None:
    touched = sorted({p for _, a, b in changes for p in (a, b) if protected(p)})
    if not touched:
        return
    trailers = project.trailers(c.body)
    task = trailers.get("Task") or ""
    scope_text = ""
    if task:
        card = next(iter(project.root.glob(f"plan/milestones/*/tasks/{task}.md")), None)
        if card:
            scope = section(card.read_text(encoding="utf-8"), "범위")
            m = re.search(r"### 포함\s*\n(.*?)(?=\n### |\Z)", scope, re.S)
            scope_text = (m.group(1).strip() if m else "").replace("\n", " / ")[:200]
    detail = ", ".join(touched[:5]) + (" …" if len(touched) > 5 else "")
    if scope_text:
        detail += f"  [카드 {task} 범위 › 포함: {scope_text}]"
    report.findings.append(Finding("V4", c.short, c.header, detail))


def _check_documents(project: Project, report: Report) -> None:
    root = project.root
    try:
        rules = project_rules(root)
    except OSError as e:
        report.notices.append(f"V5: 규칙 문서를 읽지 못해 문서 형식 검사를 건너뜀 ({e})")
        return
    spec_version = _spec_version(root)
    outdated = 0
    for path in _git(root, "ls-files", "-z", "--", "*.md").split("\0"):
        if not path or path.startswith("specs/templates/"):
            continue
        text = (root / path).read_text(encoding="utf-8") if (root / path).is_file() else ""
        if not text.startswith("---\n"):
            continue
        if "\n---\n" not in text[3:]:
            report.findings.append(Finding("V5", "", "", f"{path}: frontmatter가 닫히지 않음"))
            continue
        try:
            data = yaml.safe_load(text[4:text.index("\n---\n", 3)]) or {}
        except yaml.YAMLError:
            report.findings.append(Finding("V5", "", "", f"{path}: frontmatter를 YAML로 읽을 수 없음"))
            continue
        if not isinstance(data, dict):
            continue
        version_line = re.search(r"^spec_version:(.*)$", text[:text.index("\n---\n", 3)], re.M)
        if version_line:
            m = re.match(r"^ (\d+)$", version_line.group(1))
            if not m:
                report.findings.append(Finding("V5", "", "", f"{path}: spec_version 형식이 아님 ({version_line.group(0).strip()})"))
            elif int(m.group(1)) > spec_version:
                report.findings.append(Finding("V5", "", "", f"{path}: spec_version {m.group(1)} > 프로젝트 {spec_version}"))
            elif int(m.group(1)) < spec_version:
                outdated += 1
        doc_type = data.get("type")
        if rules["types"] and doc_type not in rules["types"]:
            report.findings.append(Finding("V5", "", "", f"{path}: 알 수 없는 type ({doc_type})"))
            continue
        allowed = rules["statuses"].get(doc_type)
        if allowed and "status" in data and data["status"] not in allowed:
            report.findings.append(Finding("V5", "", "", f"{path}: {doc_type} 상태값이 아님 ({data['status']})"))
        for name in rules["required"].get(doc_type, []):
            if name not in data:
                report.findings.append(Finding("V5", "", "", f"{path}: 필수 필드 없음 ({name})"))
        if doc_type in rules["required"] and str(data.get("id")) != Path(path).stem:
            report.findings.append(Finding("V5", "", "", f"{path}: id({data.get('id')})가 파일 이름과 다름"))
    if outdated:
        report.notices.append(f"V5: 갱신 전 문서 {outdated}개 (spec_version < {spec_version}, lg upgrade 참고)")


def _spec_version(root: Path) -> int:
    data = yaml.safe_load((root / ".lg" / "project.yaml").read_text(encoding="utf-8"))
    return int(data["generated"]["spec_version"])


def _evidence_path(token: str) -> Optional[str]:
    """요청서 근거 칸의 토큰 중 경로로 볼 것. 섹션 인용(`## …`), 공백이 든 문구, URL,
    확장자 없는 ID(`D1.1`)는 경로가 아니다. `#앵커`와 `:줄 번호`는 뗀다."""
    token = token.strip()
    if not token or token.startswith("#") or " " in token or "://" in token:
        return None
    path = re.sub(r"(#.*|:\d+(-\d+)?)$", "", token)
    if "/" in path or re.search(r"\.[A-Za-z]\w*$", path):
        return path
    return None


def _exists(root: Path, path: str) -> bool:
    """경로가 있는지. 디렉터리 없이 파일 이름만 쓴 것(`M0-T5.md`)은 저장소 어디에든 있으면 있다."""
    if (root / path).exists():
        return True
    if "/" not in path:
        return any(p for p in root.rglob(path) if ".git" not in p.relative_to(root).parts)
    return False


def _checklist(project: Project, task: str, commits, changes, report: Report) -> None:
    root = project.root
    card = next(iter(root.glob(f"plan/milestones/*/tasks/{task}.md")), None)
    if card:
        items = re.findall(r"^- \[([ xX])\]", section(card.read_text(encoding="utf-8"), "완료 기준"), re.M)
        done = sum(1 for i in items if i.lower() == "x")
        report.checklist.append(f"완료 기준: {done}/{len(items)} 체크")
    else:
        report.checklist.append(f"task 카드를 찾지 못함: {task}")
    reviews = sorted(root.glob(f"reviews/*/{task}_gate-*.md"), key=lambda p: p.name)
    if reviews:
        latest = reviews[-1]
        table = section(latest.read_text(encoding="utf-8"), "완료 기준 점검")
        missing = []
        for row in _table_rows(table):
            for token in re.findall(r"`([^`]+)`|([\w./-]+/[\w./-]+)", row[2] if len(row) > 2 else ""):
                path = _evidence_path(token[0] or token[1])
                if path and not _exists(root, path):
                    missing.append(path)
        rel = latest.relative_to(root).as_posix()
        report.checklist.append(f"게이트 요청서 {rel}: 근거 경로 " + ("모두 있음" if not missing else "없음 → " + ", ".join(missing)))
    files = sorted({p for c in commits for _, a, b in changes.get(c.sha, []) for p in (a, b) if p})
    report.checklist.append(f"바뀐 파일 {len(files)}개" + (": " + ", ".join(files[:10]) + (" …" if len(files) > 10 else "") if files else ""))


# ---------------------------------------------------------------- 출력


def render(report: Report) -> str:
    lines = [f"lg verify: {report.scope}, 커밋 {report.commits}개", ""]
    for rule, title in RULES:
        found = report.by_rule(rule)
        if not found:
            lines.append(f"✓ {rule} {title}")
            continue
        lines.append(f"✗ {rule} {title}  {len(found)}건")
        for f in found:
            where = f"{f.commit} {f.header}" if f.commit else ""
            lines.append(f"    {where}".rstrip())
            lines.append(f"      {f.detail}" if where else f"    {f.detail}")
    if report.notices:
        lines += ["", *[f"! {n}" for n in report.notices]]
    if report.checklist:
        lines += ["", "점검표 (판정하지 않음)", *[f"  - {c}" for c in report.checklist]]
    total = len(report.findings)
    lines += ["", f"위반 {total}건." if total else "위반 없음."]
    return "\n".join(lines)


def summary_for_commit(project: Project, task: str) -> tuple[list[str], int]:
    """`lg commit`의 gate 확인 단계에 보여 줄 (요약, 위반 수) (§23.6). 실패해도 예외를 내지 않는다."""
    try:
        report = run_verify(task=task, project=project)
    except Exception as e:  # noqa: BLE001 - 검사는 판정을 돕는 정보일 뿐 커밋의 조건이 아니다
        return [f"! lg verify --task {task}: 검사하지 못했습니다 ({type(e).__name__}: {e})"], 0
    lines = []
    if not report.findings:
        lines.append(f"✓ lg verify --task {task}: 위반 없음")
    else:
        lines.append(f"✗ lg verify --task {task}: 위반 {len(report.findings)}건")
        for f in report.findings[:5]:
            lines.append(f"    {f.rule} {f.commit} {f.detail}".rstrip())
        if len(report.findings) > 5:
            lines.append(f"    … 외 {len(report.findings) - 5}건")
        lines.append(f"    자세히: lg verify --task {task}")
    lines += [f"  {c}" for c in report.checklist[:2]]
    return lines, len(report.findings)
