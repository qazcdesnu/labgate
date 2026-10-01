# 구현 진행

[labgate-design.md](labgate-design.md)(무엇을 만드는가)를 구현하는 순서와 진행 상황이다. 단계를 마칠 때마다 상태와 커밋을 갱신한다.

## 완료 조건 (모든 단계 공통)

- `scripts/test-matrix.sh` 통과: Python 3.10–3.13 × 의존성 최신·최소(`pyproject.toml` 하한) = 8개 조합
- GitHub Actions(`.github/workflows/test.yml`) 통과: 위 조합 × Linux·macOS

## 단계

| 단계 | 내용 | 설계 문서 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | 패키지 뼈대(`pyproject.toml`, `--version`), `config.py`와 테스트 | §4, §6, §8.2 | ✅ 완료 | `05684ca`, `25936a1` |
| 2 | 부록 A·B·C 원문을 템플릿 파일로 옮기기, `render.py`, `stubs.py`와 테스트 | §8.1, §9, 부록 A·B·C | ✅ 완료 | `c1208bf` |
| 3 | `plan.py`와 테스트 (경로 집합, 파일 권한, frontmatter 파싱, 파일 수) | §7, §8.4, §14.1 | ✅ 완료 | `261d42b` |
| 4 | commit-msg hook 단위 테스트 (§14.1 표의 사례 전체) | §11, 부록 C | 다음 | |
| 5 | `writer.py`, `gitops.py`, `prompts.py`, `cli.py`의 `init` 명령, 통합 테스트 | §5, §8.3, §10, §14.2 | | |
| 6 | 수용 기준 점검 (마일스톤 1개·20개, `git status` 깨끗함, M0-T0 승인 커밋이 hook 통과) | §14.3 | | |

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
