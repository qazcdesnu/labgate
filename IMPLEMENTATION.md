# 구현 진행

[labgate-design.md](labgate-design.md)(무엇을 만드는가)를 구현하는 순서와 진행 상황이다. 단계를 마칠 때마다 상태와 커밋을 갱신한다.

## 완료 조건 (모든 단계 공통)

- `scripts/test-matrix.sh` 통과: Python 3.10–3.13 × 의존성 최신·최소(`pyproject.toml` 하한) = 8개 조합
- GitHub Actions(`.github/workflows/test.yml`) 통과: 위 조합 × Linux·macOS

## 단계

| 단계 | 내용 | 설계 문서 | 상태 | 커밋 |
|---|---|---|---|---|
| 1 | 패키지 뼈대(`pyproject.toml`, `--version`), `config.py`와 테스트 | §4, §6, §8.2 | ✅ 완료 | `05684ca`, `25936a1` |
| 2 | 부록 A·B·C 원문을 템플릿 파일로 옮기기, `render.py`, `stubs.py`와 테스트 | §8.1, §9, 부록 A·B·C | 진행 중 | |
| 3 | `plan.py`와 테스트 (경로 집합, 파일 권한, frontmatter 파싱, 파일 수) | §7, §8.4, §14.1 | | |
| 4 | commit-msg hook 단위 테스트 (§14.1 표의 사례 전체) | §11, 부록 C | | |
| 5 | `writer.py`, `gitops.py`, `prompts.py`, `cli.py`의 `init` 명령, 통합 테스트 | §5, §8.3, §10, §14.2 | | |
| 6 | 수용 기준 점검 (마일스톤 1개·20개, `git status` 깨끗함, M0-T0 승인 커밋이 hook 통과) | §14.3 | | |

## 단계별 메모

### 1단계

- 설계 문서에 없어서 정한 것: 설정 문자열 앞뒤 공백 제거, 알 수 없는 키는 오류, `.lg/project.yaml`에 마일스톤 `id`도 기록.
- 최소 의존성 조합 테스트에서 실제 오류가 나와 하한을 올림: `typer>=0.15.4`, `pyyaml>=6.0.2`, `pydantic>=2.8` (설계 문서 §4에 이유 기록).
