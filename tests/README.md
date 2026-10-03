# 테스트 설명서

labgate의 테스트를 **무엇을 실행하는가**에 따라 다섯 계층으로 나눈다. 계층은 폴더이고, 폴더 이름이 그대로 pytest marker가 된다(`tests/conftest.py`가 붙인다).

이 문서는 세 가지 질문에 답한다.

- 새 테스트를 어디에 둘 것인가
- 이미 있는 테스트와 겹치는가
- 기능이 바뀌면 어떤 테스트를 지울 것인가

## 1. 계층

| 계층 | 폴더 | 실행하는 것 | 필요한 것 | 테스트 수 (대략) | 시간 |
|---|---|---|---|---|---|
| unit | `unit/` | `labgate` 패키지의 순수 함수 | 없음 (`tmp_path` 정도) | 120 | 1초 미만 |
| contract | `contract/` | 서로 맞아야 하는 두 원본을 비교: 설계 문서 ↔ 템플릿, 명령 설명서 ↔ CLI, 해시표 ↔ 릴리즈 tag, 렌더링 결과 ↔ 규약 | 저장소 파일 (해시표 검사는 Git tag) | 80 | 2초 |
| tools | `tools/` | **생성된 프로젝트에 들어가는 도구**: `.lg/hooks/commit-msg`, `scripts/agent-commit`, `scripts/session-check`, `scripts/apply-human-commits` | Git, 실제 저장소 | 95 | 8초 |
| commands | `commands/` | `lg` 명령(`init`, `draft`, `commit`, `upgrade`, `verify`)을 같은 프로세스에서 (CliRunner) | Git, `lg init`으로 만든 프로젝트 | 105 | 12초 |
| e2e | `e2e/` | 설치된 `lg` 실행 파일을 별도 프로세스로 (사람이 쓰는 그대로) | Git, 설치된 `lg` | 8 | 2초 |

- 아래 계층일수록 빠르고, 실패했을 때 원인을 좁히기 쉽다.
- Git이 필요한 세 계층(tools, commands, e2e)은 Git이 없으면 건너뛴다. 파일마다 `pytestmark`를 쓰지 않는다.

### tools 계층과 Python 3.9

생성되는 hook과 스크립트는 연구 프로젝트의 `python3`로 돌기 때문에 **Python ≥ 3.9**를 지원한다(설계 문서 §4). `lg` 자체는 3.10 이상이다.

- **도구를 실행하는 방식:** 테스트의 Git 환경(`support.env.isolated_git_env`)은 `python3`를 환경 변수 `HOOK_PYTHON`(없으면 테스트 중인 Python)으로 바꿔 PATH 맨 앞에 둔다.
- **3.9 검사:** CI와 `scripts/test-matrix.sh`는 `HOOK_PYTHON=<3.9> pytest tests/tools`로 tools 계층만 3.9로 다시 돌린다.
- **그래서:** hook이나 생성 스크립트의 동작을 검사하는 테스트는 **반드시 `tools/`에 둔다.** 다른 폴더에 두면 3.9 검사에서 빠진다.

commands 계층도 커밋할 때 hook을 거치고, `approve_and_start`처럼 반영 스크립트를 돌리기도 한다. 하지만 그것은 명령을 검사하기 위한 준비 과정이지, 도구 자체를 검사하는 것이 아니다.

## 2. 어디에 둘까

위에서부터 처음 "예"가 나오는 곳에 둔다.

1. **설치된 `lg`를 별도 프로세스로 돌려야만 확인되는가?** (entry point, 수용 기준 §14.3) → `e2e/`
2. **생성되는 hook·스크립트의 동작인가?** → `tools/`
3. **`lg` 명령의 동작인가?** (출력, 종료 코드, 만든 커밋·파일) → `commands/`
4. **두 원본이 서로 맞는지 보는가?** (설계 문서, 명령 설명서, 해시표, 릴리즈 tag, 생성 규약) → `contract/`
5. **나머지:** 함수 하나의 입력과 출력 → `unit/`

`lg` 명령 안에서 쓰는 판정 함수는 함수 자체를 `unit/`에서 검사한다. 예: `verify.human_transition`, `verify._evidence_path`. `commands/`에서는 그 함수가 명령에 연결되어 있는지만 본다.

## 3. 파일

| 파일 | 대상 | 설계 문서 |
|---|---|---|
| `unit/test_config.py` | 설정 파일 검사, 기본값, `.lg/project.yaml` 쓰기 | §6, §14.1 |
| `unit/test_render.py` | 템플릿 렌더링, 잔여 문법 검사 | §9 |
| `unit/test_plan.py` | 생성 계획: 경로, 파일 수, 권한, 줄 끝 | §7, §8.4 |
| `unit/test_writer.py` | 대상 폴더 검사, 쓰기와 롤백 | §5.3, §8.3 |
| `unit/test_kinds.py` | 생성 파일 분류의 정규화 (`lg upgrade` 비교 기준) | §22.3 |
| `unit/test_verify_rules.py` | `lg verify`의 전이·근거 판정, 근거 경로 판별 | §23 |
| `contract/test_templates.py` | 템플릿 = 설계 문서 부록, 렌더링 결과 규약, 절차 문서 링크·특별 규칙, verify 규칙 = AGENTS.md, wheel 내용 | 부록 A–C, §16, §23.3 |
| `contract/test_docs.py` | `docs/cli/`의 옵션 표·종료 코드 = CLI, `docs/guide/` 링크 | — |
| `contract/test_releases.py` | 해시표 = 릴리즈 tag의 템플릿, 릴리즈된 spec_version 동결, 모든 생성 파일 분류 | §22.2.2, §22.4 |
| `tools/test_hook.py` | commit-msg hook 규칙 전부, `agent-commit` 옵션 차단 | §11, §12, 부록 C, §14.1 |
| `tools/test_session_check.py` | 사람의 변경 기록, 초안·반영 대기 알림, `--tidy` 연동 | §17.2 |
| `tools/test_apply.py` | 사람 커밋(plan, gate, respond, decide)의 반영 | §21 |
| `commands/test_project.py` | 명령 공통의 프로젝트 확인: 위치, spec_version, hook 계약 | §18.3 |
| `commands/test_init.py` | `lg init` (설정 파일, 대화형, 오류와 롤백) | §5, §6.3, §10, §14.2 |
| `commands/test_draft.py` | `lg draft` | §19 |
| `commands/test_commit.py` | `lg commit` (초안·작성 모드, tag, gate의 verify 요약, 다음 할 일 안내) | §18, §23.5 |
| `commands/test_upgrade.py` | `lg upgrade` (옛 tag로 만든 프로젝트를 올리기) | §22 |
| `commands/test_verify.py` | `lg verify` (V1–V5, 범위, 옛 프로젝트) | §23 |
| `e2e/test_acceptance.py` | §14.3 수용 기준, entry point, 워크트리 | §14.3 |

각 파일 첫 줄 docstring에 대상과 설계 문서 절을 적는다. 설계 문서의 절이 바뀌면 이 표와 docstring을 함께 고친다.

## 4. 공용 도구

같은 도우미를 파일마다 다시 만들지 않는다. 필요한 것이 없으면 `support/`에 더한다.

### `tests/conftest.py` (fixture)

| fixture | 내용 |
|---|---|
| `config` | 렌더링이 까다로운 값(따옴표, 콜론, 한글)을 담은 파싱된 설정 |
| `git_sandbox` | 격리된 Git 환경을 `os.environ`에 적용하고 그 dict를 돌려준다 (CliRunner로 `lg`를 돌릴 때 필수) |
| `project` | 기본 설정으로 `lg init`한 `Project` (`git_sandbox` 포함) |
| `old_sources` | 릴리즈 tag별 labgate 소스 (session 범위, `support.releases.make_old`에 넘긴다) |
| `tty` | 터미널에서 실행하는 것으로 둔다 (`lg init` 대화형, `lg commit`) |
| `keys` | 가짜 키 입력 (`tty` 포함). `keys("abc\r", ENTER)`로 모두 넣고 입력을 닫는다. 모자라면 EOF로 끝나 코드 130 |

### `tests/support/` (모듈)

| 모듈 | 내용 |
|---|---|
| `env` | `ROOT`, `SRC`, `STATIC_DIR`, `JINJA_DIR`, `isolated_git_env(tmp_path)` |
| `configs` | `BASE`/`make_config()`(까다로운 값, unit·contract용), `project_config()`(실제 프로젝트용: 사람 `H <h@x.com>`, 마일스톤 M0·M1), `HUMAN`, `PROJECT_NAME`, `write_config()` |
| `cli` | `lg(*args, cwd=None)`(CliRunner, 예외를 숨기지 않음), `in_dir()`, 키 상수 `ENTER`, `DOWN`, `SPACE`, `CLEAR`, `CTRL_C` |
| `project` | `Project`, `init_project()` |
| `markdown` | `frontmatter()`, `section()`, `table_column()` |
| `releases` | `TAGS`(spec_version → 그 버전을 처음 릴리즈한 tag), `has_tag()`, `make_old()`, `current_files()` |

`support`는 `pyproject.toml`의 `pythonpath = ["tests"]`로 import한다. `--import-mode=importlib`이므로 테스트 파일 이름이 폴더끼리 겹쳐도 된다. 다만 **테스트 파일끼리 import하지 않는다.** 둘 이상이 쓰는 것은 `support/`로 옮긴다.

### `Project`

`lg init`으로 만든 실제 프로젝트를 다룬다. 모든 명령이 격리된 Git 환경에서 돈다.

| 메서드 | 하는 일 |
|---|---|
| `project / "경로"` | 경로 (`project.root / "경로"`와 같음) |
| `read`, `write(rel, text="x\n")` | 파일 읽기·쓰기 (`write`는 폴더를 만든다) |
| `status(rel)`, `set_status(rel, value)` | frontmatter `status` 읽기·바꾸기 |
| `yaml()`, `agent_email` | `.lg/project.yaml`, 에이전트 이메일 (`agent@<slug>.local`을 하드코딩하지 않는다) |
| `run`, `git`, `lg`, `script(name, *args)` | 명령 실행. `git`은 stdout 문자열, `lg`는 프로젝트 폴더에서 CliRunner, `script`는 `python3 scripts/<name>` |
| `human(message, *paths, all=False, no_verify=False)` | 사람 신원 커밋. 지정한 경로만 stage (`all=True`면 전부) |
| `agent(message, *paths, no_verify=False)` | `scripts/agent-commit`으로 에이전트 커밋. `no_verify`면 hook을 우회한 커밋을 git으로 직접 |
| `last_commit()`, `trailers()` | `"작성자 이메일\|헤더"`, 마지막 커밋의 trailer |
| `session_check()`, `apply(*args)`, `commit_apply(result)` | 생성 스크립트 실행, 반영 결과의 커밋 명령 실행 |
| `approve_and_start(task="M0-T0")` | 정상 흐름: 승인 → 반영 → 착수 |

### 설정 고르기

- **생성 내용을 검사할 때 (unit, contract):** `make_config()`. 이름에 따옴표·콜론·한글이 있어 렌더링 오류가 드러난다.
- **실제 프로젝트로 동작을 볼 때 (tools, commands):** `project` fixture나 `init_project(tmp_path, env, project_config(...))`.
- **파일 고유의 설정:** `commands/test_init.py`처럼 출력 내용(커밋 본문 등)을 실제 이름으로 확인해야 할 때만 쓴다. 그 이유를 설정 옆 주석에 적는다.

## 5. 겹침을 피하는 규칙

1. **한 동작은 그 동작을 가진 가장 낮은 계층에서 한 번 검사한다.**
   - 예: hook 규칙은 `tools/test_hook.py`의 규칙 표에서만 검사한다. `lg draft`가 hook과 같은 규칙으로 거부하는 것은 `commands/`에서 "같은 원본(프로젝트의 hook)을 쓴다"는 연결만 확인한다.
2. **위 계층은 연결을 확인한다.**
   - 예: e2e의 수용 기준은 설치된 `lg`로 만든 결과가 규약을 지키는지 본다. 규약의 세부 사례는 contract에 있다.
   - 설계 문서가 계층별 사례를 따로 요구하면(§14.2의 "생성된 프로젝트에서 agent-commit") 그 요구가 우선이다. docstring에 절 번호를 적어 두면 지울 때 알 수 있다.
3. **어떤 테스트의 검사가 다른 테스트에 모두 들어 있으면 작은 쪽을 지운다.**
   - 예: `settings.json` 전체를 보는 검사가 있으면, `attribution` 한 칸만 보는 검사는 지운다.
4. **같은 setup에서 단언만 다른 테스트는 하나로 합친다.**
5. **모양만 같은 "다른 진입점" 검사는 겹침이 아니다.**
   - 예: hook이 미등록 작성자를 거부하는 것과, `lg verify`가 hook을 우회한 커밋에서 미등록 작성자를 찾는 것은 서로 다른 검사다.

## 6. 테스트를 더할 때

1. 2절의 순서로 계층을 고른다.
2. 대상 파일을 3절 표에서 찾는다. 새 명령이나 새 생성 도구면 새 파일을 만들고 표에 더한다.
3. fixture와 `support`를 쓴다. `lg()`, `git()`, 설정 dict, 키 입력 fixture를 파일 안에 다시 만들지 않는다.
4. docstring에 설계 문서 절이나 이유를 쓴다. 특히 다음 두 경우는 반드시 쓴다.
   - "v0.2 방식"처럼 **호환성 때문에 남긴 테스트**
   - 실사용에서 드러난 문제를 막는 테스트
5. 문구를 검사할 때는 출력 전체가 아니라 핵심 구절만 본다. 문구를 다듬을 때 테스트가 함께 깨지지 않게 하기 위해서다.

## 7. 테스트를 지울 때 (obsolete)

이런 경우에 지운다.

- **기능이나 문구를 없앴다:** 그 기능을 검사하는 테스트를 지운다. 설계 문서 절 번호로 찾는다(`grep -rn "§18.2" tests`).
- **지원 범위를 줄였다:** `SUPPORTED_SPEC_VERSIONS`(`src/labgate/project.py`)에서 버전을 뺐다면, docstring에 "v0.2 방식"·"spec_version 2"가 있는 호환성 테스트와 `support.releases.TAGS`의 그 버전을 함께 정리한다.
- **5절의 겹침이 생겼다.**

**지우지 않는 것:** 지금은 건너뛰지만 상황이 바뀌면 다시 의미가 생기는 테스트다.

- 예: `contract/test_releases.py::test_current_templates_frozen_if_released`는 현재 spec_version이 아직 릴리즈 전이면 건너뛴다. 다음 spec_version을 개발하는 동안 실제로 건너뛰고, 릴리즈 뒤에는 동결을 지킨다.

지운 수는 커밋 메시지에 적는다. 테스트 수가 줄어든 이유를 리뷰에서 바로 알 수 있다.

## 8. 실행

```bash
.venv/bin/pytest                         # 전체
.venv/bin/pytest -m unit                 # 계층 하나 (빠른 확인)
.venv/bin/pytest -m "not commands and not e2e"
.venv/bin/pytest tests/tools             # 폴더로도 된다
HOOK_PYTHON="$(uv python find 3.9)" .venv/bin/pytest tests/tools   # 생성 도구를 Python 3.9로
scripts/test-matrix.sh                   # Python 3.10–3.14 × 최신·최소 의존성, 그리고 tools × 3.9
```

- **CI** (`.github/workflows/test.yml`): 위 조합을 Linux와 macOS에서 돈다. 주 작업은 `fetch-depth: 0`으로 tag를 받는다. 옛 프로젝트를 tag의 labgate로 만들어야 하기 때문이다.
- **e2e:** 설치된 `lg`(테스트를 돌리는 Python 옆의 실행 파일)를 쓴다. `pip install -e .` 없이 돌리면 실패한다.

## 9. 릴리즈할 때

새 spec_version을 처음 릴리즈하면 다음 세 가지를 한다.

1. 해시표를 만든다: `scripts/hash-templates.py WORKTREE <spec_version>` (루트 README "개발").
2. tag를 만든 뒤 `support/releases.py`의 `TAGS`에 `{<spec_version>: "<tag>"}`를 더한다.
   - 그러면 다음 테스트들이 그 버전을 자동으로 포함한다: `contract/test_releases.py`(해시표 = tag), `commands/test_verify.py`(옛 프로젝트 검사), 다음 spec_version 개발 중의 `commands/test_upgrade.py`(그 버전에서 올리기).
3. 3절 표의 설계 문서 절 번호가 바뀌었으면 고친다.

## 10. 알려진 한계

- **tag가 없으면 건너뜀:** tag가 필요한 테스트는 얕은 클론이나 소스 배포판에서 조용히 건너뛴다. CI 주 작업은 tag를 받으므로 거기서는 항상 돈다.
- **같은 프로세스 실행:** commands 계층은 `lg`를 CliRunner로 같은 프로세스에서 돌린다. 터미널 감지(`tty` fixture)와 키 입력(`keys`)은 흉내 낸 것이고, 실제 터미널 동작은 e2e와 실사용으로만 확인된다.
