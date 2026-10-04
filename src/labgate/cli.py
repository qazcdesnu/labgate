"""Typer 앱: `lg init` (설계 문서 §5), `lg commit` (§18), `lg draft` (§19), `lg upgrade` (§22), `lg verify` (§23),
`lg status`, `lg answer` (§24)."""
from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Callable, List, Optional

import typer
import yaml

from . import __version__, gitops, prompts
from . import commit as commit_module  # 명령 함수 commit, draft와 이름이 겹치지 않게
from . import answer as answer_module
from . import draft as draft_module
from . import ideas as ideas_module
from . import origin as origin_module
from . import spec as spec_module
from . import status as status_module
from . import upgrade as upgrade_module
from . import verify as verify_module
from .config import KINDS, Config, ConfigError, load_config, parse_config
from .errors import EXIT_ABORT, EXIT_ERROR, EXIT_GIT, EXIT_OK, EXIT_TARGET, EXIT_USAGE, Fail
from .gitops import GitError
from .plan import EXECUTABLE, PlannedFile, build_plan
from .render import RenderError
from .writer import TargetError, check_target, find_conflicts, write_plan

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"labgate {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version, is_eager=True, help="버전을 출력한다."
    ),
) -> None:
    """사람이 승인 게이트마다 판정하는 연구 프로젝트 작업 공간 도구."""


@app.command()
def init(
    path: Optional[Path] = typer.Argument(None, help="생성할 프로젝트 폴더. 생략하면 묻는다.", show_default=False),
    config_file: Optional[Path] = typer.Option(
        None, "--config", help="설정 파일(YAML)로 모든 입력을 받는다. PATH 필수.", show_default=False
    ),
    force: bool = typer.Option(False, "--force", help="비어 있지 않은 폴더에도 만든다. 기존 파일은 덮어쓰지 않는다."),
    dry_run: bool = typer.Option(False, "--dry-run", help="만들 파일 트리와 개수만 출력한다."),
    no_git: bool = typer.Option(False, "--no-git", help="Git 초기화와 초기 커밋을 하지 않는다."),
    yes: bool = typer.Option(False, "--yes", "-y", help="대화형 모드의 마지막 확인을 건너뛴다."),
    kind: Optional[str] = typer.Option(
        None, "--kind", help="프로젝트 종류: research(연구, 기본), ideation(아이디어 탐색), proposal(제안서).",
        show_default=False,
    ),
    import_dir: Optional[Path] = typer.Option(
        None, "--import", help="이미 가진 자료 폴더. 내용을 notes/로 복사하고 stage해 둔다 (첫 승인 커밋에 함께).",
        show_default=False,
    ),
    from_dir: Optional[Path] = typer.Option(
        None, "--from", help="확정한 방향을 가져올 ideation 프로젝트. 질문·요약·마일스톤·근거 문헌을 넘겨받는다.",
        show_default=False,
    ),
) -> None:
    """연구·제안서 프로젝트 작업 공간을 만든다."""
    _guard(
        lambda: _init(path, config_file, force, dry_run, no_git, yes, kind, import_dir, from_dir),
        interrupted="\n중단했습니다. 아무것도 만들지 않았습니다.",  # 쓰기 중 중단은 writer가 이미 롤백했다
    )


@app.command()
def commit(
    pending: Optional[bool] = typer.Option(
        None, "--pending/--no-pending",
        help="초안(.lg/pending/COMMIT_MSG) 모드를 강제하거나 끈다. 생략하면 초안이 있을 때 초안 모드.",
        show_default=False,
    ),
    no_tag: bool = typer.Option(False, "--no-tag", help="gate 승인이어도 tag를 만들지 않는다."),
    allow_empty: bool = typer.Option(
        False, "--allow-empty", help="바뀐 파일 없이 커밋한다 (예: 첫 task 승인 plan 커밋)."
    ),
) -> None:
    """사람 신원으로 커밋한다. 사람이 터미널에서 직접 실행한다."""
    _guard(lambda: _echo(commit_module.run_commit(pending, no_tag, allow_empty)), interrupted="\n중단했습니다.")


@app.command()
def draft(
    ctype: str = typer.Option(..., "--type", help="커밋 타입 (사람이 쓸 수 있는 타입).", show_default=False),
    summary: str = typer.Option(..., "--summary", help="헤더의 요약 한 줄.", show_default=False),
    scope: Optional[str] = typer.Option(None, "--scope", help="scope. 생략하면 Task trailer를 쓴다.", show_default=False),
    body: Optional[str] = typer.Option(None, "--body", help="본문 (무엇을 왜).", show_default=False),
    trailer: Optional[List[str]] = typer.Option(None, "--trailer", help="KEY=VALUE. 여러 번 쓸 수 있다.", show_default=False),
    paths: Optional[List[str]] = typer.Argument(
        None, help="stage할 경로. 생략하면 .lg/pending/HUMAN_FILES의 경로.", show_default=False
    ),
) -> None:
    """사람 커밋의 초안을 준비한다 (stage와 .lg/pending/COMMIT_MSG). 커밋하지 않는다."""
    _guard(
        lambda: _echo(draft_module.run_draft(ctype, summary, scope, body, trailer or [], paths or [])),
        interrupted="\n중단했습니다.",
    )


@app.command()
def upgrade(
    dry_run: bool = typer.Option(False, "--dry-run", help="바꿀 것만 보여 주고 아무것도 쓰지 않는다."),
    force: bool = typer.Option(False, "--force", help="그 버전과 다른 관리 문서도 새 버전으로 덮어쓴다 (원래 내용은 .lg/pending/upgrade/)."),
    diff: bool = typer.Option(False, "--diff", help="그 버전과 다른 문서마다 지금 파일 → 새 버전의 차이를 보여 준다. 아무것도 쓰지 않는다."),
) -> None:
    """프로젝트를 현재 spec_version으로 올린다. 커밋하지 않는다. 사람이 실행한다."""
    _guard(lambda: _echo(upgrade_module.run_upgrade(dry_run, force, diff=diff)), interrupted="\n중단했습니다.")


@app.command()
def verify(
    task: Optional[str] = typer.Option(None, "--task", help="그 task에 관련된 커밋만 검사하고 점검표를 붙인다.", show_default=False),
    since: Optional[str] = typer.Option(None, "--since", help="그 커밋 이후만 검사한다.", show_default=False),
    everything: bool = typer.Option(False, "--all", help="처음부터 검사한다."),
) -> None:
    """에이전트의 작업이 규칙을 지켰는지 커밋 이력과 문서로 확인한다. 읽기만 한다."""
    def run() -> int:
        if sum(bool(x) for x in (task, since, everything)) > 1:
            raise Fail(EXIT_USAGE, "✗ --task, --since, --all 중 하나만 쓰세요.")
        report = verify_module.run_verify(task=task, since=since, everything=everything)
        typer.echo(verify_module.render(report))
        return EXIT_TARGET if report.findings else EXIT_OK
    _guard(run, interrupted="\n중단했습니다.")


@app.command()
def status(
    as_json: bool = typer.Option(False, "--json", help="같은 내용을 JSON으로 출력한다."),
) -> None:
    """사람이 할 일, 에이전트 몫, 진행 상황을 보여 준다. 읽기만 한다."""
    _guard(lambda: _echo(status_module.run_status(as_json)), interrupted="\n중단했습니다.")


@app.command()
def answer(
    review_id: Optional[str] = typer.Argument(
        None, help="응답할 review ID, 또는 확정할 결정 ID(D0.1). 생략하면 열린 review에서 고른다.", show_default=False
    ),
    no_tag: bool = typer.Option(False, "--no-tag", help="gate 승인이어도 tag를 만들지 않는다."),
) -> None:
    """열린 review에 응답하거나 결정을 확정한다. 응답 문서와 사람 커밋을 함께 만든다. 사람이 터미널에서 직접 실행한다."""
    _guard(lambda: _echo(answer_module.run_answer(review_id, no_tag)), interrupted="\n중단했습니다. 아무것도 바꾸지 않았습니다.")


@app.command()
def ideas(
    as_json: bool = typer.Option(False, "--json", help="같은 내용을 JSON으로 출력한다."),
) -> None:
    """ideation 후보를 잠근 평가 기준으로 비교한다: 점수, 가중 평균, 순위, 결격. 읽기만 한다."""
    _guard(lambda: _echo(ideas_module.run_ideas(as_json)), interrupted="\n중단했습니다.")


spec_app = typer.Typer(no_args_is_help=True, help="사양 문서를 다룬다. 사람이 터미널에서 직접 실행한다.")
app.add_typer(spec_app, name="spec")


@spec_app.command("adopt")
def spec_adopt(
    drafts: List[str] = typer.Argument(..., help="사양 초안 파일 (notes/ 의 번호 붙은 절). 여러 개 쓸 수 있다.", show_default=False),
    name: Optional[str] = typer.Option(None, "--name", help="합칠 stub 사양 이름. 생략하면 초안의 id 또는 파일 이름.", show_default=False),
) -> None:
    """사양 초안을 stub 사양에 합쳐 spec 커밋으로 확정한다."""
    _guard(lambda: _echo(spec_module.run_adopt(drafts, name)), interrupted="\n중단했습니다. 아무것도 바꾸지 않았습니다.")


def _echo(message: str) -> int:
    typer.echo(message)
    return EXIT_OK


def _guard(run: Callable[[], int], interrupted: str) -> None:
    """명령 공통 오류 처리: 예외를 종료 코드와 한 줄 메시지로 바꾼다 (§5.2, §13)."""
    try:
        code = run()
    except Fail as e:
        _err(str(e))
        code = e.code
    except ConfigError as e:
        _err("✗ 설정이 올바르지 않습니다:\n" + "\n".join(f"  - {x}" for x in e.errors))
        code = EXIT_USAGE
    except TargetError as e:
        _err(f"✗ {e}")
        code = EXIT_TARGET
    except GitError as e:
        _err(f"✗ {e}")
        code = EXIT_GIT
    except RenderError as e:
        _err(f"✗ 템플릿 렌더링 오류 (labgate 버그입니다): {e}")
        code = EXIT_ERROR
    except KeyboardInterrupt:
        _err(interrupted)
        code = EXIT_ABORT
    except Exception as e:  # noqa: BLE001 - §13: 예기치 못한 오류는 한 줄로, traceback은 LG_DEBUG=1일 때만
        if os.environ.get("LG_DEBUG") == "1":
            traceback.print_exc()
        _err(f"✗ 예기치 못한 오류: {type(e).__name__}: {e}\n  자세한 내용은 LG_DEBUG=1 로 다시 실행하세요.")
        code = EXIT_ERROR
    raise typer.Exit(code)


def _err(message: str) -> None:
    typer.echo(message, err=True)


def _init(path: Optional[Path], config_file: Optional[Path], force: bool,
          dry_run: bool, no_git: bool, yes: bool, kind: Optional[str] = None,
          import_dir: Optional[Path] = None, from_dir: Optional[Path] = None) -> int:
    interactive = config_file is None
    if kind is not None and kind not in KINDS:
        raise Fail(EXIT_USAGE, f"✗ --kind 는 {', '.join(KINDS)} 중 하나입니다: {kind}")
    if from_dir and kind == "ideation":
        raise Fail(EXIT_USAGE, "✗ --from 은 ideation에서 확정한 방향으로 연구·제안서 프로젝트를 만듭니다 (--kind ideation 과 함께 쓰지 않음).")
    ideation = origin_module.read_source(from_dir) if from_dir else None

    # 1. 경로 확정
    if path is None:
        if not interactive:
            raise Fail(EXIT_USAGE, "✗ --config 를 쓸 때는 PATH 가 필요합니다.\n  예: lg init ./my-project --config project.yaml")
        _require_tty()
        path = prompts.ask_path()
    target = Path(os.path.abspath(path.expanduser()))
    source = _check_import(import_dir, target) if import_dir else None

    # 2–3. 대상 폴더와 Git 사전 검사 (나머지 입력 전에)
    exists = _check_target(target, force, dry_run)
    if not no_git:
        _check_git(target, dry_run)

    # 4. 입력 수집과 검증
    if ideation:  # §26.8: 질문·요약·마일스톤은 brief에서, 이름과 slug만 새로
        if interactive:
            _require_tty()
            name, slug = prompts.ask_name_slug(target)
            data = origin_module.config_data(ideation, None, kind, name, slug)
        else:
            data = origin_module.config_data(ideation, _raw_config(config_file), kind, None, None)
        config = parse_config(data)
    elif interactive:
        _require_tty()
        config = prompts.ask_config(target, kind)
    else:
        config = load_config(config_file)
        if kind and kind != config.project.kind:
            if config.project.kind != "research":  # 설정 파일이 다른 종류를 정했다
                raise Fail(EXIT_USAGE, f"✗ --kind {kind} 와 설정 파일의 project.kind ({config.project.kind})가 다릅니다.")
            config = config.model_copy(update={"project": config.project.model_copy(update={"kind": kind})})

    # 5. 생성 계획
    plan = build_plan(config, date.today().isoformat())
    if exists:
        conflicts = find_conflicts(target, plan)
        if conflicts:
            listing = "\n".join(f"  {c}" for c in conflicts)
            message = f"이미 있는 파일과 겹칩니다 ({len(conflicts)}개). 기존 파일은 덮어쓰지 않습니다:\n{listing}"
            if not dry_run:
                raise TargetError(message + "\n  겹치는 파일을 옮기거나 다른 경로를 지정하세요.")
            _warn(message)

    # 6. dry-run
    if dry_run:
        typer.echo(f"{target}/ (dry-run: 아무것도 쓰지 않습니다)")
        typer.echo(format_tree(plan))
        typer.echo(f"\n파일 {len(plan)}개")
        return EXIT_OK

    # 7. 확인
    if interactive and not yes:
        typer.echo("\n" + prompts.summarize(target, config, git=not no_git) + "\n")
        if not prompts.confirm_create():
            raise Fail(EXIT_ABORT, "만들지 않았습니다.")

    # 8. 파일 쓰기
    write_plan(target, plan)

    # 9. Git: 생성한 파일만 커밋한다 (§25.4)
    try:
        commit = None if no_git else gitops.init_repo(target, config, [str(f.path) for f in plan])
    except KeyboardInterrupt:
        raise Fail(EXIT_ABORT, f"\nGit 초기화 중에 중단했습니다. 생성된 파일은 그대로 두었습니다: {target}") from None
    leftover = _untracked(target) if commit and exists else []

    # 10. 자료 가져오기 (§25.5, §26.8): notes/·references/로 복사하고 stage만 한다
    imported = _import(source, target, stage=bool(commit)) if source else []
    if ideation:
        carried = origin_module.carry(ideation, target)
        if commit and carried:
            gitops.run(["add", "--", *carried], cwd=target)
        imported += carried

    # 11. 안내
    typer.echo(success_message(target, config, len(plan), commit, imported, leftover))
    return EXIT_OK


def _raw_config(path: Path) -> dict:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ConfigError([f"{path}: 설정 파일을 읽지 못했습니다 ({e})"]) from None
    if not isinstance(data, dict):
        raise ConfigError(["(최상위): 키: 값 형식의 YAML 문서여야 합니다"])
    return data


def _check_import(import_dir: Path, target: Path) -> Path:
    source = Path(os.path.abspath(import_dir.expanduser()))
    if not source.is_dir():
        raise Fail(EXIT_USAGE, f"✗ --import 폴더가 없습니다: {source}")
    if source == target or target in source.parents:
        raise Fail(EXIT_USAGE, "✗ --import 폴더가 프로젝트 폴더 안에 있습니다. 프로젝트 밖의 자료 폴더를 지정하세요.")
    if not any(source.iterdir()):
        raise Fail(EXIT_USAGE, f"✗ --import 폴더가 비어 있습니다: {source}")
    return source


def _import(source: Path, target: Path, stage: bool) -> list[str]:
    """자료 폴더의 내용을 notes/ 아래로 복사한다(같은 이름이 있으면 건너뜀). 복사한 경로 목록 (프로젝트 기준)."""
    notes = target / "notes"
    copied: list[str] = []
    for path in sorted(source.rglob("*")):
        if path.is_dir() or any(part.startswith(".git") for part in path.relative_to(source).parts):
            continue
        dest = notes / path.relative_to(source)
        if dest.exists():
            _warn(f"이미 있어서 가져오지 않았습니다: {dest.relative_to(target)}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        copied.append(dest.relative_to(target).as_posix())
    if stage and copied:
        gitops.run(["add", "--", *copied], cwd=target)
    return copied


def _untracked(target: Path) -> list[str]:
    """init 커밋에 넣지 않은, 폴더에 원래 있던 파일·폴더."""
    result = gitops.run(["status", "--porcelain", "--untracked-files=normal"], cwd=target)
    return [l[3:] for l in result.stdout.splitlines() if l.startswith("?? ")]


def _require_tty() -> None:
    if not sys.stdin.isatty():
        raise Fail(EXIT_USAGE, "✗ 대화형 입력에는 터미널이 필요합니다.\n  --config 로 설정 파일을 지정하세요.")


def _warn(message: str) -> None:
    _err("! " + message.replace("\n", "\n  "))


def _check_target(target: Path, force: bool, dry_run: bool) -> bool:
    try:
        return check_target(target, force)
    except TargetError as e:
        if not dry_run:
            raise
        _warn(str(e))
        return target.is_dir()


def _check_git(target: Path, dry_run: bool) -> None:
    try:
        gitops.check_available()
        repo = gitops.inside_work_tree(target)
        if repo is not None:
            raise GitError(
                f"대상이 이미 Git 저장소 안에 있습니다 (저장소: {repo}).\n"
                "  저장소 밖의 경로를 지정하거나, 그 저장소 안에 파일만 만들려면 --no-git 을 쓰세요."
            )
    except GitError as e:
        if not dry_run:
            raise
        _warn(str(e))


def format_tree(plan: list[PlannedFile]) -> str:
    """§7.1 모양의 트리. 실행 파일에는 `*`를 붙인다."""
    tree: dict = {}
    modes: dict[PurePosixPath, int] = {}
    for f in plan:
        node = tree
        for part in f.path.parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[f.path.parts[-1]] = None
        modes[f.path] = f.mode

    lines: list[str] = []

    def walk(node: dict, prefix: str, base: PurePosixPath) -> None:
        names = sorted(node, key=lambda n: (n.endswith("/"), n))  # 파일 먼저, 그다음 폴더
        for i, name in enumerate(names):
            last = i == len(names) - 1
            path = base / name.rstrip("/")
            mark = " *" if modes.get(path) == EXECUTABLE else ""
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}{mark}")
            if node[name] is not None:
                walk(node[name], prefix + ("    " if last else "│   "), path)

    walk(tree, "", PurePosixPath())
    return "\n".join(lines)


def success_message(target: Path, config: Config, count: int, commit: Optional[str],
                    imported: Optional[list[str]] = None, leftover: Optional[list[str]] = None) -> str:
    """§5.4."""
    first = f"{config.milestones[0].id}-T0"
    lines = [f"✓ {prompts.KIND_LABELS[config.project.kind]} 프로젝트를 만들었습니다: {target}"]
    if commit:
        lines.append(f"  파일 {count}개, 초기 커밋 {commit} (init)")
    else:
        lines.append(f"  파일 {count}개 (Git 초기화 안 함: --no-git)")
    if leftover:
        shown = ", ".join(leftover[:5]) + (f" 외 {len(leftover) - 5}개" if len(leftover) > 5 else "")
        lines.append(f"  폴더에 원래 있던 {len(leftover)}개는 커밋하지 않았습니다: {shown}")
        lines.append("    notes/ 등 정한 자리로 옮겨 커밋하거나, 필요 없으면 .gitignore 에 넣으세요.")
    if imported:
        lines += ["", "다음 단계:", f"  1. 가져온 자료 {len(imported)}개가 notes/ 에 있습니다"
                  + (" (stage됨, 첫 승인 커밋에 함께 들어갑니다)." if commit else ".")]
    elif config.project.kind == "ideation":
        lines += ["", "다음 단계:", "  1. notes/ 에 아이디어 메모를 넣고, plan/criteria.md 의 '가진 자원'을 채우세요"
                  f" (평가 기준은 {first} 게이트에서 확정·잠금)."]
    else:
        lines += ["", "다음 단계:", "  1. notes/ 에 기존 계획 자료를 넣으세요."]
    if commit:
        lines += [
            f"  2. STATUS.md 를 확인하고, {first} 을 승인하세요:",
            f'       git commit --allow-empty -m "plan({first}): approve initial task" -m "Actor: human',
            f'     Approve: {first}"',
            f"     ({first} 카드의 status 를 approved 로 바꿔 함께 커밋해도 됩니다)",
            f"     또는 터미널에서 lg commit --allow-empty (타입 plan, Approve {first})",
        ]
    else:
        lines += [
            "  2. Git을 쓰려면 프로젝트 폴더에서 다음을 실행한 뒤, STATUS.md 를 확인하고",
            f"     {first} 을 승인하세요 (plan 커밋, specs/git-commit.md §5):",
            "       git init && git symbolic-ref HEAD refs/heads/main",
            "       git config core.hooksPath .lg/hooks",
            '       git config user.name "<이름>" && git config user.email "<.lg/identities.json의 이메일>"',
        ]
    if config.agent_tools.claude_code:
        lines.append("  3. 에이전트 세션을 시작하세요 (Claude Code: /session-start)")
    else:
        lines.append("  3. 에이전트 세션을 시작하세요 (AGENTS.md 의 \"세션 시작 절차\")")
    return "\n".join(lines)
