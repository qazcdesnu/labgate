"""`lg upgrade`: 프로젝트를 현재 spec_version으로 올린다. 커밋하지 않는다 (설계 문서 §22).

사람이 항상 우선이다. 사람의 수정을 발견하면 지우지 않고 알린다. 관리 문서를 사람이 고쳤으면
갱신을 멈추고, `--force`일 때만 덮어쓴다(원래 내용은 .lg/pending/upgrade/에 남긴다).
"""
from __future__ import annotations

import difflib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from importlib.resources import files as package_files
from pathlib import Path
from typing import Optional

import yaml

from . import SPEC_VERSION, __version__, gitops
from .config import ConfigError, parse_config
from .errors import EXIT_TARGET, EXIT_USAGE, Fail
from .gitops import GitError
from .kinds import (BEGIN, EDITABLE, END, GITIGNORE, MANAGED, RESEARCH, carry_project_lines, classify, digest,
                    filemap_lines, gitignore_lines, is_rule, normalize, variant)
from .plan import build_plan

# n → n+1에서 기본 갱신(관리 문서 교체, 문서 spec_version 갱신, .gitignore 관리 구역) 외에 할 일 (§22.6).
# 기본 갱신으로 충분한 단계도 등록해, 등록되지 않은 단계(출발할 수 없는 버전)를 구분한다.
MIGRATIONS: dict[int, tuple] = {2: (), 3: (), 4: (), 5: ()}

SPEC_LINE = re.compile(r"^spec_version:(.*)$", re.M)
EXACT_VALUE = re.compile(r"^ (\d+)$")
MAX_SHOWN = 20


def load_hashes(spec_version: int) -> Optional[dict]:
    resource = package_files("labgate") / "hashes" / f"{spec_version}.json"
    if not resource.is_file():
        return None
    return json.loads(resource.read_text(encoding="utf-8"))


@dataclass
class UpgradePlan:
    root: Path
    source: int
    writes: dict[str, str] = field(default_factory=dict)    # 경로 → 새 내용
    modes: dict[str, int] = field(default_factory=dict)     # 경로 → 권한
    deletes: list[str] = field(default_factory=list)
    replaced: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)            # 사람이 채운 관리 문서
    failed: list[str] = field(default_factory=list)          # 그 버전의 해시와 다른 관리 문서
    compare: dict[str, tuple[str, str]] = field(default_factory=dict)  # 경로 → (지금, 새 버전): 다른 문서의 비교용
    forced: list[str] = field(default_factory=list)
    bumped: dict[int, list[str]] = field(default_factory=dict)
    notices: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- 계획


def run_upgrade(dry_run: bool, force: bool, cwd: Optional[Path] = None, diff: bool = False) -> str:
    root, data = _project(cwd or Path.cwd())
    source = data["generated"]["spec_version"]
    if source == SPEC_VERSION:
        return f"이미 spec_version {SPEC_VERSION}입니다. 갱신할 것이 없습니다."
    if not isinstance(source, int) or source > SPEC_VERSION:
        raise Fail(EXIT_USAGE, f"✗ 이 labgate(spec_version {SPEC_VERSION})보다 새 프로젝트입니다 (spec_version {source}). labgate를 업데이트하세요.")
    if any(n not in MIGRATIONS for n in range(source, SPEC_VERSION)):
        raise Fail(EXIT_USAGE, f"✗ spec_version {source}에서는 올릴 수 없습니다 (지원: {', '.join(map(str, sorted(MIGRATIONS)))}).")
    hashes = load_hashes(source)
    if hashes is None:
        raise Fail(EXIT_USAGE, (
            f"✗ spec_version {source}의 해시표가 없습니다. 릴리즈되지 않은 dev 버전으로 만든 프로젝트는 지원하지 않습니다."
        ))
    _check_clean(root)

    try:
        config = parse_config({k: v for k, v in data.items() if k not in ("generated", "upgrades")})
    except ConfigError as e:
        raise Fail(EXIT_USAGE, "✗ .lg/project.yaml 의 설정을 읽지 못했습니다:\n" + "\n".join(f"  - {x}" for x in e.errors))
    new = {str(f.path): f for f in build_plan(config, str(data["generated"]["created"]))}
    var = variant(config.agent_tools.claude_code, config.project.kind)
    tracked = set(p for p in _git(root, "ls-files", "-z").split("\0") if p)

    plan = UpgradePlan(root, source)
    _plan_managed(plan, hashes, new, var, force)
    _plan_gitignore(plan, hashes, new)
    _plan_versions(plan, tracked)
    _plan_filemap(plan, hashes, new)
    if plan.errors:
        raise Fail(EXIT_USAGE, "✗ 갱신할 수 없습니다:\n" + "\n".join(f"  - {e}" for e in plan.errors))

    if diff:
        return _diffs(plan)
    report = _report(plan, dry_run)
    if dry_run:
        return report + "\n\n(--dry-run: 아무것도 바꾸지 않았습니다)"
    if plan.failed and not force:
        raise Fail(EXIT_TARGET, report + (
            f"\n\n✗ 릴리즈된 spec_version {plan.source}의 파일과 다른 관리 문서가 있어 갱신하지 않았습니다. "
            "아무것도 바꾸지 않았습니다.\n"
            "  누가 왜 바꿨는지는 도구가 알 수 없습니다. 먼저 차이를 보세요: lg upgrade --diff\n"
            "  의도한 수정이 아니면: lg upgrade --force\n"
            "  의도한 수정이면: --force로 갱신한 뒤 .lg/pending/upgrade/ 에 남는 원래 내용을 보고 다시 합치세요."
        ))
    _record(plan, data)
    _write(plan)
    return report + (
        "\n\n✓ 갱신했습니다. 커밋하지 않았습니다.\n"
        "  다음: git diff 로 확인하고, 터미널에서 git add -A && lg commit (타입 spec)"
    )


def _project(cwd: Path) -> tuple[Path, dict]:
    try:
        result = gitops.run(["rev-parse", "--show-toplevel"], cwd=cwd)
    except OSError:
        raise Fail(EXIT_USAGE, "✗ git 을 실행할 수 없습니다.") from None
    if result.returncode != 0:
        raise Fail(EXIT_USAGE, "✗ Git 저장소가 아닙니다. labgate 프로젝트 폴더 안에서 실행하세요.")
    root = Path(result.stdout.strip())
    path = root / ".lg" / "project.yaml"
    if not path.is_file():
        raise Fail(EXIT_USAGE, f"✗ labgate 프로젝트가 아닙니다 ({root} 에 .lg/project.yaml 이 없습니다).")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["generated"]["spec_version"], data["generated"]["created"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as e:
        raise Fail(EXIT_USAGE, f"✗ .lg/project.yaml 을 읽지 못했습니다: {e}") from None
    return root, data


def _git(root: Path, *args: str) -> str:
    result = gitops.run(list(args), cwd=root)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} 실패: {(result.stderr or result.stdout).strip()}")
    return result.stdout


def _check_clean(root: Path) -> None:
    if _git(root, "status", "--porcelain").strip():
        raise Fail(EXIT_USAGE, "✗ 작업 트리가 깨끗하지 않습니다. 먼저 커밋하거나 정리하세요 (git status).")
    for name in ("COMMIT_MSG", "APPLY_MSG"):
        if (root / ".lg" / "pending" / name).exists():
            raise Fail(EXIT_USAGE, f"✗ .lg/pending/{name} 이 있습니다. 대기 중인 커밋을 먼저 끝내세요.")


def _read(root: Path, path: str) -> Optional[str]:
    full = root / path
    return full.read_text(encoding="utf-8") if full.is_file() else None


def _plan_managed(plan: UpgradePlan, hashes: dict, new: dict, var: str, force: bool) -> None:
    old = {p: d[var] for p, d in hashes["files"].items() if var in d}
    paths = set(old) | {p for p in new if classify(p) in (MANAGED, EDITABLE)}
    for path in sorted(paths):
        kind = classify(path)
        current = _read(plan.root, path)
        target = new[path].content if path in new else None
        if current is None:
            if target is None:
                continue
            if path not in old:
                plan.writes[path], plan.modes[path] = target, new[path].mode
                plan.added.append(path)
            elif kind == MANAGED:
                plan.failed.append(path)  # 지워진 관리 문서
                plan.compare[path] = ("", target)
                if force:
                    plan.writes[path], plan.modes[path] = target, new[path].mode
                    plan.forced.append(path)
            else:
                plan.notices.append(f"사람이 지운 문서를 다시 만들지 않았습니다: {path}")
            continue
        if target is not None and normalize(path, current) == normalize(path, target):
            continue  # 이미 새 버전
        pristine = path in old and digest(path, current) == old[path]
        if pristine or (kind == MANAGED and force):
            if not pristine:
                plan.failed.append(path)
                plan.forced.append(path)
                plan.compare[path] = (current, target or "")
            if target is None:
                plan.deletes.append(path)
            else:
                plan.writes[path] = carry_project_lines(path, current, target)
                plan.modes[path] = new[path].mode
                plan.replaced.append(path)
        elif kind == MANAGED:
            plan.failed.append(path)
            plan.compare[path] = (current, target or "")
        else:  # 사람이 채운 것으로 본다: 내용 유지 (spec_version은 _plan_versions가 올린다)
            plan.kept.append(path)
            plan.compare[path] = (current, target or "")


def _plan_gitignore(plan: UpgradePlan, hashes: dict, new: dict) -> None:
    current = _read(plan.root, ".gitignore")
    if current is None:
        plan.notices.append("사람이 지운 .gitignore 를 다시 만들지 않았습니다.")
        return
    lines = current.split("\n")
    if any(l.strip().startswith(BEGIN) for l in lines) and any(l.strip().startswith(END) for l in lines):
        b = next(i for i, l in enumerate(lines) if l.strip().startswith(BEGIN))
        e = next(i for i, l in enumerate(lines) if l.strip().startswith(END))
        before, block, after = lines[:b], lines[b + 1:e], lines[e + 1:]
        legacy = False
    else:
        before, block, after = [], lines, []
        legacy = True
    old = set(hashes["gitignore"])
    present = set(gitignore_lines("\n".join(block)))
    removed = {l for l in old if is_rule(l) and l not in present}
    human = [l.strip() for l in block if l.strip() and l.strip() not in old]

    template = new[".gitignore"].content.split("\n")
    tb = next(i for i, l in enumerate(template) if l.strip().startswith(BEGIN))
    te = next(i for i, l in enumerate(template) if l.strip().startswith(END))
    new_block = [l for l in template[tb:te + 1] if l.strip() not in removed]
    result = before + new_block
    if human:
        result += [""] + human
    result += after if after else [""]
    text = "\n".join(result).rstrip("\n") + "\n"
    if text == current:
        return
    plan.writes[".gitignore"] = text
    plan.replaced.append(".gitignore")
    if removed:
        plan.notices.append(".gitignore: 사람이 지운 labgate 줄은 다시 넣지 않았습니다: " + ", ".join(sorted(removed)))
    if human:
        where = "관리 구역 아래에 남겼습니다" if legacy else "관리 구역 밖(아래)으로 옮겼습니다"
        plan.notices.append(f".gitignore: labgate가 만들지 않은 줄 {len(human)}개를 {where}: " + ", ".join(human[:5])
                            + (" …" if len(human) > 5 else ""))


def _plan_versions(plan: UpgradePlan, tracked: set[str]) -> None:
    """연구 문서와 사람이 채운 관리 문서의 frontmatter spec_version을 올린다."""
    candidates = sorted(p for p in tracked if classify(p) == RESEARCH) + plan.kept
    for path in candidates:
        text = _read(plan.root, path)
        if text is None or not text.startswith("---\n") or "\n---\n" not in text[3:]:
            continue
        end = text.index("\n---\n", 3)
        m = SPEC_LINE.search(text, 0, end)
        if not m:
            continue
        exact = EXACT_VALUE.match(m.group(1))
        if not exact:
            plan.notices.append(f"spec_version 형식이 아니라 그대로 두었습니다: {path} ({m.group(0).strip()})")
            continue
        value = int(exact.group(1))
        if value > SPEC_VERSION:
            plan.errors.append(f"{path}: spec_version {value}는 이 labgate({SPEC_VERSION})보다 새 버전입니다")
        elif value < SPEC_VERSION:
            plan.writes[path] = text[:m.start()] + f"spec_version: {SPEC_VERSION}" + text[m.end():]
            plan.bumped.setdefault(value, []).append(path)


def _plan_filemap(plan: UpgradePlan, hashes: dict, new: dict) -> None:
    if _read(plan.root, "FILEMAP.md") is None or "FILEMAP.md" not in new:
        return
    old = hashes.get("filemap", [])
    now = filemap_lines(new["FILEMAP.md"].content)
    added = [l for l in now if l not in old]
    removed = [l for l in old if l not in now]
    if added or removed:
        lines = [f"    + {l}" for l in added] + [f"    - {l}" for l in removed]
        plan.notices.append("FILEMAP.md: labgate의 구조가 바뀌었습니다. 필요하면 반영하세요:\n" + "\n".join(lines))


# ---------------------------------------------------------------- 쓰기


def _record(plan: UpgradePlan, data: dict) -> None:
    data["generated"]["spec_version"] = SPEC_VERSION
    data.setdefault("upgrades", []).append({
        "from": plan.source, "to": SPEC_VERSION, "labgate_version": __version__,
        "date": date.today().isoformat(), "forced": plan.forced,
    })
    plan.writes[".lg/project.yaml"] = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=1000)


def _write(plan: UpgradePlan) -> None:
    keep = plan.root / ".lg" / "pending" / "upgrade"
    for path in plan.forced:
        original = _read(plan.root, path)
        if original is not None:
            dst = keep / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(original, encoding="utf-8")
    for path in plan.deletes:
        (plan.root / path).unlink()
    for path, text in plan.writes.items():
        full = plan.root / path
        full.parent.mkdir(parents=True, exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        if path in plan.modes:
            os.chmod(full, plan.modes[path])


def _counts(plan: UpgradePlan, path: str) -> str:
    """다른 문서 옆에 붙일 줄 수: 지금 파일 → 새 버전."""
    if path not in plan.compare:
        return ""
    current, target = plan.compare[path]
    added = removed = 0
    for line in difflib.unified_diff(current.splitlines(), target.splitlines(), lineterm="", n=0):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return f"  (지금 → 새 버전: +{added} −{removed}줄)"


def _diffs(plan: UpgradePlan) -> str:
    """--diff: 그 버전과 다른 문서마다 지금 파일 → 새 버전의 차이. 아무것도 쓰지 않는다."""
    if not plan.compare:
        return f"릴리즈된 spec_version {plan.source}과 다른 문서가 없습니다."
    out = [f"릴리즈된 spec_version {plan.source}과 다른 문서: 지금 파일(-) → --force가 쓸 새 버전(+)",
           "새 버전으로 바뀌는 줄(버전 갱신)과 이 프로젝트에서 바뀐 줄이 함께 보입니다.", ""]
    for path, (current, target) in sorted(plan.compare.items()):
        out += difflib.unified_diff(current.splitlines(), target.splitlines(),
                                    fromfile=f"{path} (지금)", tofile=f"{path} (새 버전)", lineterm="")
        out.append("")
    return "\n".join(out).rstrip() + "\n\n(--diff: 아무것도 바꾸지 않았습니다)"


def _report(plan: UpgradePlan, dry_run: bool) -> str:
    def section(title: str, items: list[str]) -> list[str]:
        if not items:
            return []
        shown = [f"    {p}{_counts(plan, p)}" for p in items[:MAX_SHOWN]]
        if len(items) > MAX_SHOWN:
            shown.append(f"    … 외 {len(items) - MAX_SHOWN}개")
        return [f"  {title} ({len(items)})", *shown]

    lines = [f"spec_version {plan.source} → {SPEC_VERSION}" + (" (미리 보기)" if dry_run else "")]
    lines += section("교체", plan.replaced)
    lines += section("추가", plan.added)
    lines += section("삭제", plan.deletes)
    lines += section(f"릴리즈된 spec_version {plan.source}과 다른 문서(사람이 채운 것으로 봄): 내용 유지, spec_version만 갱신", plan.kept)
    lines += section(f"릴리즈된 spec_version {plan.source}과 다른 관리 문서"
                     + (" → --force로 덮어씀" if plan.forced else " → 갱신 실패"), plan.failed)
    for value, paths in sorted(plan.bumped.items()):
        lines += section(f"spec_version {value} → {SPEC_VERSION}", paths)
    if plan.notices:
        lines.append("  알림")
        lines += [f"    {n}" for n in plan.notices]
    return "\n".join(lines)
