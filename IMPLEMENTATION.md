# 구현 메모

[labgate-design.md](labgate-design.md)(무엇을 만드는가)를 구현·유지보수할 때 알아야 할 것을 모은다.

**현재 상태:** v1(`lg init`) 구현 완료. §14.3 수용 기준을 모두 충족한다. 구현 단계별 경과는 `git log`로 본다.

## 완료 조건 (모든 변경 공통)

- `scripts/test-matrix.sh` 통과: Python 3.10–3.14 × 의존성 최신·최소(`pyproject.toml` 하한) = 10개 조합, 그리고 생성되는 hook × Python 3.9
- GitHub Actions(`.github/workflows/test.yml`) 통과: 위 조합 × Linux·macOS

## 템플릿

- 템플릿 원문의 원본은 설계 문서다. `scripts/sync-templates.py`가 부록의 `~~~~` 블록을 `src/labgate/templates/`로 옮기고, `--check`로 차이를 검사한다(`tests/test_templates.py`가 매번 실행). **템플릿을 고칠 때는 설계 문서를 고치고 스크립트를 실행한다.**
- 템플릿 경로: Jinja는 `jinja/<출력 경로>.j2`, 마일스톤별 T0 카드는 `jinja/plan/milestones/tasks/T0.md.j2`, stub은 `jinja/specs/doc-types/_stub.spec.md.j2`. 점으로 시작하는 경로는 `dot-` 접두어(§8.1).
- **템플릿 제어문은 문자열 비교로 분기하지 않는다.** 잔여 문법 검사는 문자열을 모두 `"x"`로 바꾼 검사용 컨텍스트로 렌더링해서 하므로(§9), 문자열로 분기하면 검사가 실제 출력과 달라진다.
- 생성 파일 표는 `plan.py` 상단 상수(`STATIC_FILES`, `SINGLE_TEMPLATES`, `MILESTONE_TEMPLATES`, `GITKEEP_*`)에 있다. 템플릿을 추가하고 표에 빠뜨리면 테스트가 실패한다.

## 구현 결정 (설계 문서에 없는 세부)

- 설정: 문자열 앞뒤 공백 제거, 알 수 없는 키는 오류, `.lg/project.yaml`에 마일스톤 `id`도 기록.
- 쓰기는 `open(..., "x")`로 해서 충돌 검사를 지나쳐도 기존 파일을 덮어쓰지 않는다.
- 초기 커밋은 `GIT_AUTHOR_*`, `GIT_COMMITTER_*`와 함께 `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`도 지운 환경에서 실행한다(다른 Git hook 안에서 `lg`를 실행해도 대상 저장소가 바뀌지 않도록).
- 사용자 전역 Git 설정은 존중한다. 예: `commit.gpgsign=true`이면 초기 커밋도 서명을 시도한다(실패하면 코드 4와 수동 명령 안내).
- hook 동작 참고: `Approve: M0-T0,`처럼 목록 끝에 빈 항목이 있으면 무시하고 통과한다.
- dev 의존성의 `hatchling`은 wheel에 템플릿이 모두 들어가는지 검사하는 테스트용이다.

## 테스트

- `tests/test_hook.py`: 생성될 hook과 `agent-commit`을 임시 저장소에 설치하고 실제 `git commit`으로 검사한다. hook의 `#!/usr/bin/env python3`는 PATH를 따르므로, 테스트는 PATH 맨 앞에 테스트 중인 Python(또는 환경 변수 `HOOK_PYTHON`)을 둔다. 그래서 매트릭스가 hook도 각 버전에서 검증한다.
- 사용자 전역 Git 설정과 `GIT_*` 변수는 테스트마다 차단한다(`tests/conftest.py`의 `isolated_git_env`). 그래서 사용자 환경 변수 누출은 별도 테스트로 재현한다.
- 대화형은 prompt_toolkit 파이프 입력으로 실제 questionary를 구동한다(`tests/test_init.py`의 `keys`). 키를 다 보낸 뒤 입력을 닫으므로, 입력이 모자라면 멈추지 않고 EOF(코드 130)로 실패한다.
- `tests/test_acceptance.py`는 설치된 `lg` 실행 파일을 별도 프로세스로 실행한다(사람이 쓰는 그대로).

§14.3 수용 기준과 확인하는 테스트:

| 수용 기준 | 확인 |
|---|---|
| §14.1, §14.2 테스트 모두 통과 | §14.1: `test_config.py`, `test_render.py`, `test_templates.py`, `test_plan.py`, `test_writer.py`, `test_hook.py`. §14.2: `test_init.py` (`test_init_with_config`, `test_agent_commit_in_generated_project`, `test_dry_run_writes_nothing`, `test_no_git`, `test_inside_existing_repo`) |
| 마일스톤 1개, 20개 설정 모두에서 생성 성공 | `test_acceptance[1·20 × Claude Code 사용·미사용]` |
| 생성된 Markdown에 렌더링되지 않은 템플릿 문법 없음 (사용자 입력의 `{{`·`{%`는 그대로) | `test_acceptance`, `test_user_braces_are_kept_and_generation_succeeds` |
| 생성 직후 `git status` 깨끗함 | `test_acceptance` (`--ignored` 포함) |
| §5.4 안내대로 M0-T0 승인 커밋을 실행하면 hook 통과 | `test_acceptance`, `test_approve_together_with_card_status` |

## 알려진 경고

- 최소 의존성 조합(questionary 2.0.0 → prompt_toolkit 3.0.36)에서 Python 3.12 이상이면 prompt_toolkit 내부의 asyncio 사용 중단 경고가 난다(3.14에서는 반복). 해당 함수는 Python 3.16에서 제거 예정이며, 지금은 동작에 영향이 없다.

## 남은 과제

- 자동 메모리 사용 지침 (또는 `autoMemoryEnabled: false`): Claude Code가 연구 판단을 저장소 밖에 남길 수 있다 ([docs/scenarios/codi.md](docs/scenarios/codi.md) §6.4).
- `--no-verify` 차단용 Claude Code PreToolUse hook 검토 (같은 문서 §6.5).
- 탐색 구간의 task 크기 지침(넓은 범위 + 예산)을 `workflow.md`에 추가 검토 (같은 문서 §4.2).
- Claude Code 슬래시 커맨드를 `.claude/commands/`(지원되지만 구식)에서 `.claude/skills/`로 옮길지 검토.
- §15 향후 확장: `lg gate`, `lg status`, `lg validate`, `lg upgrade`, `lg doctor`.
