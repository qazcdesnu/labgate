# 구현 진행

[labgate-design.md](labgate-design.md)(무엇을 만드는가)를 구현하는 순서와 진행 상황이다. 단계를 마칠 때마다 상태와 커밋을 갱신한다.

**현재 상태: v1(`lg init`) 구현 완료. §14.3 수용 기준을 모두 충족한다.**

## 완료 조건 (모든 단계 공통)

- `scripts/test-matrix.sh` 통과: Python 3.10–3.14 × 의존성 최신·최소(`pyproject.toml` 하한) = 10개 조합
- 생성되는 hook은 Python 3.9에서도 통과 (`test-matrix.sh` 전체 실행에 포함)
- GitHub Actions(`.github/workflows/test.yml`) 통과: 위 조합 × Linux·macOS, hook × Python 3.9

## 단계

| 단계 | 내용 | 설계 문서 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | 패키지 뼈대(`pyproject.toml`, `--version`), `config.py`와 테스트 | §4, §6, §8.2 | ✅ 완료 | `05684ca`, `25936a1` |
| 2 | 부록 A·B·C 원문을 템플릿 파일로 옮기기, `render.py`, `stubs.py`와 테스트 | §8.1, §9, 부록 A·B·C | ✅ 완료 | `c1208bf` |
| 3 | `plan.py`와 테스트 (경로 집합, 파일 권한, frontmatter 파싱, 파일 수) | §7, §8.4, §14.1 | ✅ 완료 | `261d42b` |
| 4 | commit-msg hook 단위 테스트 (§14.1 표의 사례 전체) | §11, 부록 C | ✅ 완료 | `6b3a881` |
| 5 | `writer.py`, `gitops.py`, `prompts.py`, `cli.py`의 `init` 명령, 통합 테스트 | §5, §8.3, §10, §14.2 | ✅ 완료 | `b55d142` |
| 6 | 수용 기준 점검 (마일스톤 1개·20개, `git status` 깨끗함, M0-T0 승인 커밋이 hook 통과) | §14.3 | ✅ 완료 | `a154ddd` |

## 단계별 메모

### 1단계

- 설계 문서에 없어서 정한 것: 설정 문자열 앞뒤 공백 제거, 알 수 없는 키는 오류, `.lg/project.yaml`에 마일스톤 `id`도 기록.
- 최소 의존성 조합 테스트에서 실제 오류가 나와 하한을 올림: `typer>=0.15.4`, `pyyaml>=6.0.2`, `pydantic>=2.8` (설계 문서 §4에 이유 기록).

### 2단계

- 템플릿 원문의 원본은 설계 문서다. `scripts/sync-templates.py`가 부록의 `~~~~` 블록을 `src/labgate/templates/`로 옮기고, `--check`로 차이를 검사한다 (`tests/test_templates.py`가 매번 실행). **템플릿을 고칠 때는 설계 문서를 고치고 스크립트를 실행한다.**
- 템플릿 경로: Jinja는 `jinja/<출력 경로>.j2`, 마일스톤별 T0 카드는 `jinja/plan/milestones/tasks/T0.md.j2`, stub은 `jinja/specs/doc-types/_stub.spec.md.j2`. 점으로 시작하는 경로는 `dot-` 접두어 (§8.1).
- `stubs.py`의 표와 `specs/README.md`의 stub 목록이 설계 문서 B.7과 일치하는지 테스트한다.
- wheel에 템플릿이 모두 들어가는지 테스트하려고 dev 의존성에 `hatchling>=1.24`를 추가했다.
- ~~미결: 사용자 입력의 `{{`, `{%`를 잔여 문법 검사가 템플릿 실수로 오인~~ → 해결 (`ee0f354`, 설계 문서 1.3 §9). 문자열을 모두 `"x"`로 바꾼 검사용 컨텍스트로 한 번 더 렌더링해 그 결과만 검사한다. LaTeX·BibTeX 입력이 그대로 출력된다. **템플릿 제어문은 문자열 비교로 분기하지 않는다**(이 방식의 전제).

### 3단계

- `build_plan(config, today)`는 경로 순으로 정렬한 `PlannedFile` 목록을 돌려준다. 정적·Jinja 파일 표는 `plan.py` 상단 상수(`STATIC_FILES`, `SINGLE_TEMPLATES`, `MILESTONE_TEMPLATES`, `GITKEEP_*`)에 있다.
- 테스트의 기대 경로는 `plan.py`와 별도로 §7.1 트리를 보고 적었다. 템플릿 폴더의 모든 파일이 표에서 쓰이는지도 검사한다(템플릿을 추가하고 표에 빠뜨리면 실패).
- 파일 수: N=1 → 55, N=3 → 67, N=20 → 169 (Claude Code 사용), N=3 미사용 → 60.

### 4단계

- `tests/test_hook.py`: 생성될 hook과 `agent-commit`을 임시 저장소에 설치하고 실제 `git commit`으로 검사한다. 사용자 전역 Git 설정은 테스트마다 차단한다(`GIT_CONFIG_GLOBAL`, `HOME`).
- §14.1 표 15개 사례 + §11의 나머지 규칙 20개 + `--author` 인식, identities 손상, agent-commit 신원·옵션 차단 (총 52개). agent-commit은 §14.2의 통합 테스트 일부를 앞당겨 다룬 것이다.
- hook의 `#!/usr/bin/env python3`는 PATH를 따르므로, 테스트는 PATH 맨 앞에 테스트 중인 Python(또는 `HOOK_PYTHON`)을 둔다. 덕분에 매트릭스가 hook도 3.10–3.14에서 검증하고, 별도로 3.9에서도 돌린다.
- 확인된 hook 동작: `Approve: M0-T0,`처럼 끝에 빈 항목이 있으면 무시하고 통과한다.

### 5단계

- 구현하며 정한 동작은 설계 문서 1.4에 반영했다: `--force` 시 기존 파일도 `init` 커밋에 포함, EOF도 중단(130), 대화형은 터미널 필요(아니면 2), Git 초기화 중 중단 안내, dry-run 트리 형식(실행 파일 `*`), `--no-git`·Claude Code 미사용 시 안내 문구, `-y`.
- 쓰기는 `open(..., "x")`로 해서 충돌 검사를 지나쳐도 기존 파일을 덮어쓰지 않는다.
- 초기 커밋은 `GIT_AUTHOR_*`, `GIT_COMMITTER_*`와 함께 `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`도 지운 환경에서 실행한다(다른 Git hook 안에서 `lg`를 실행해도 대상 저장소가 바뀌지 않도록).
- 사용자 전역 설정은 존중한다. 예: `commit.gpgsign=true`이면 초기 커밋도 서명을 시도한다(실패하면 코드 4와 수동 명령 안내).
- 테스트:
  - 대화형은 prompt_toolkit 파이프 입력으로 실제 questionary를 구동한다(`tests/test_init.py`의 `keys`). 키를 다 보낸 뒤 입력을 닫으므로, 입력이 모자라면 멈추지 않고 EOF(코드 130)로 실패한다.
  - 테스트 격리 장치가 `GIT_*`를 지우므로, 사용자 환경 변수 누출은 별도 테스트로 재현한다.
- 알려진 경고: 최소 의존성 조합(questionary 2.0.0 → prompt_toolkit ≤ 3.0.36)에서 Python 3.12+이면 prompt_toolkit 내부의 `DeprecationWarning`(이벤트 루프)이 1건 난다. 동작에는 영향 없음.
- 개발용 `.venv`는 uv 기본값이라 Python 3.14다(지원 범위 밖이지만 통과).

### 6단계

`tests/test_acceptance.py`는 설치된 `lg` 실행 파일을 별도 프로세스로 실행한다(사람이 쓰는 그대로). 수용 기준과 확인하는 테스트:

| §14.3 수용 기준 | 확인 |
|---|---|
| §14.1, §14.2 테스트 모두 통과 | §14.1: `test_config.py`, `test_render.py`, `test_templates.py`, `test_plan.py`, `test_writer.py`, `test_hook.py`. §14.2: `test_init.py` (6항목 각각 `test_init_with_config`, `test_agent_commit_in_generated_project`(2·3), `test_dry_run_writes_nothing`, `test_no_git`, `test_inside_existing_repo`) |
| 마일스톤 1개, 20개 설정 모두에서 생성 성공 | `test_acceptance[1·20 × Claude Code 사용·미사용]` |
| 생성된 Markdown에 렌더링되지 않은 템플릿 문법 없음 (사용자 입력의 `{{`·`{%`는 그대로, 생성 성공) | `test_acceptance`, `test_user_braces_are_kept_and_generation_succeeds` |
| 생성 직후 `git status` 깨끗함 | `test_acceptance` (`--ignored` 포함) |
| §5.4 안내대로 M0-T0 승인 커밋을 실행하면 hook 통과 | `test_acceptance` (`lg` 출력에서 명령을 그대로 꺼내 실행), `test_approve_together_with_card_status` |

- 결함 주입 확인: 안내문의 승인 커밋 타입을 `plan` → `gate`로 바꾸면 5개 테스트가 실패한다.
- 배포 확인(수동): wheel을 빌드해 새 가상환경에 설치(`pipx install .`과 같은 형태)하고 `lg init`을 실행 → 성공, 실행 권한 유지, 작업 트리 깨끗함.
- 최종: 로컬 매트릭스 8개 조합 각 227개 통과, hook × Python 3.9 52개 통과.

### 3.14 지원 추가

- 지원 범위를 3.10–3.14로 넓혔다 (설계 문서 1.5 §4). 3.14에서는 하한 버전의 pyyaml(6.0.2)·pydantic(2.8)에 wheel이 없어 소스 빌드가 실패하므로, 환경 마커로 3.14에서만 하한을 올렸다: `pyyaml>=6.0.3`, `pydantic>=2.12`.
- 알려진 경고: 3.14 최소 의존성 조합에서 prompt_toolkit 3.0.36의 `asyncio.get_event_loop_policy` 사용 중단 경고(Python 3.16 제거 예정)가 반복된다. 동작에는 영향 없음.

## 남은 결정·후속 작업

- **[사용 시나리오 점검에서 발견]** ([docs/scenarios/codi.md](docs/scenarios/codi.md) §6–7)
  1. ~~충돌: Claude Code의 공동 작성자 trailer가 별도 문단으로 붙으면 hook이 커밋을 거부한다 → 생성 `.claude/settings.json`에 `"attribution": {"commit": "", "pr": "", "sessionUrl": false}` (빈 문자열이 문서상 끄는 방법. `attribution: false`는 v2.1.281 미만에서 설정 파일 전체를 건너뛰게 하므로 쓰지 않음), `git-commit.md`에 "trailer는 마지막 한 문단에".~~ → **해소** (설계 문서 1.6)
  2. ~~충돌: 워크트리 브랜치·병합이 선형 이력 규칙을 깨고 병합 커밋은 hook을 통과한다 → `.gitignore`에 `.claude/worktrees/`, AGENTS.md에 워크트리 정책, `git merge` deny 검토.~~ → **해소** (설계 문서 1.6: 워크트리는 실험 격리용, 병합·cherry-pick 금지. hook이 에이전트 병합 커밋 거부, deny에 `git merge`·`git cherry-pick`, `.gitignore`에 `.claude/worktrees/`)
  3. 긴장: 자동 메모리가 저장소 밖에 연구 판단을 남길 수 있다 → 사용 지침 또는 `autoMemoryEnabled: false`.
  4. 공백: `--no-verify` → Claude Code PreToolUse hook 검토.
  5. 운영: 탐색 구간 task 크기 지침.
- Claude Code 슬래시 커맨드는 `.claude/commands/`(지원되지만 구식)로 생성한다. `.claude/skills/`로 옮길지는 v1 이후 검토.
- §15 향후 확장(`lg gate`, `lg status`, `lg validate`, `lg upgrade`, `lg doctor`).
