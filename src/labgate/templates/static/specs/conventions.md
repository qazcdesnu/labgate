---
id: conventions
type: spec
spec_version: 2
status: complete
---
# 공통 규칙

## 1. ID 체계

| 대상 | 형식 | 예 | 비고 |
|---|---|---|---|
| 마일스톤 | `M<n>` | `M1` | 0부터 |
| Task | `M<n>-T<n>` | `M1-T2` | 마일스톤마다 T0부터 |
| 결정 | `D<n>.<n>` | `D1.3` | 앞 숫자 = 마일스톤 번호, 뒤 숫자 = 그 마일스톤 안의 순번(1부터) |
| 참고문헌 | `<1저자 성><연도>-<키워드>` | `guo2025-loglinear` | 소문자 ASCII, 키워드는 하이픈 연결 영문 1–3단어. 충돌 시 연도 뒤에 `b`, `c` (`guo2025b-…`) |
| 실행 | `<Task>_run-<NNN>` | `M1-T2_run-003` | task 안에서 001부터 |
| Review | `<Task>_gate-<NN>`, `<Task>_esc-<NN>` | `M1-T2_gate-01` | task 안에서 종류별 01부터 |
| 작업 일지 | `YYYY-MM-DD_s<NN>` | `2026-10-03_s02` | 그날 세션 순번 |

ID는 한 번 부여하면 바꾸지 않는다. 폐기된 대상의 ID는 재사용하지 않는다.

## 2. 파일과 폴더 이름

- 위 ID를 파일명에 그대로 쓴다. 추가 설명이 필요하면 `<ID>_<slug>` 형식으로 붙인다.
- `slug`는 소문자 ASCII와 하이픈만 쓴다 (`^[a-z0-9]+(-[a-z0-9]+)*$`).
- 위치는 [FILEMAP.md](../FILEMAP.md)와 각 사양 §2를 따른다.

## 3. 날짜와 시간

- 날짜: `YYYY-MM-DD` (로컬 날짜).
- 시각이 필요하면 ISO 8601 (`2026-10-03T14:05:00+09:00`).

## 4. Frontmatter

Markdown 문서는 YAML frontmatter로 시작한다. 다음은 예외다(frontmatter 없음):

- 루트 `README.md`: 사람용 입구
- `AGENTS.md`, 그리고 있다면 `CLAUDE.md`와 `.claude/` 아래 파일: 에이전트 도구가 그대로 읽는 지침
- `notes/`, `paper/` 아래 파일: 형식 자유

`specs/templates/`의 양식은 frontmatter를 갖지만 값이 `<...>` 자리 표시이므로 검증 대상이 아니다.

공통 필드:

| 필드 | 필수 | 설명 |
|---|---|---|
| `id` | ✓ | 문서 ID |
| `type` | ✓ | 문서 유형. 아래 표 참고 |
| `spec_version` | ✓ | 따르는 사양 버전 (현재 2) |
| `status` | 유형별 | §5의 상태값 |
| `created` | 유형별 | 생성일 |
| `updated` | ✓ (사양 문서 제외) | 마지막 수정일. 사양 문서(`type: spec`)의 변경 시점은 `spec` 커밋 이력으로 본다 |

`type` 값:

| 구분 | `type` |
|---|---|
| 사양이 있는 문서 | `specs/doc-types/`의 사양 이름과 같다: `task-card`, `review`, `roadmap`, `milestone`, `task-map`, `catalog`, `decision`, `experiment-readme`, `run-record`, `task-result`, `milestone-report`, `worklog`, `status` |
| 사양 문서 자신 | `spec` |
| 절차 문서 (`specs/procedures/`) | `procedure` |
| 목록·안내 문서 (사양 없음) | `filemap` (`FILEMAP.md`), `spec-index` (`specs/README.md`), `decision-index` (`decisions/index.md`) |

- 값이 없으면 `null`. 목록이 비면 `[]`.
- 사람이 입력한 문자열은 큰따옴표로 감싼다.
- 다른 문서를 가리키는 필드에는 경로가 아니라 ID를 쓴다.

## 5. 상태값

| 유형 | 상태값 |
|---|---|
| task-card | `draft`, `approved`, `in-progress`, `blocked`, `in-review`, `revise`, `closed`, `redirected` |
| milestone | `planned`, `active`, `closed` |
| decision | `proposed`, `discussing`, `confirmed`, `superseded` |
| review | `open`, `answered`, `closed` |
| roadmap | `draft`, `active` |
| spec | `stub`, `complete` |

전이 규칙은 [workflow.md](workflow.md) §3.

## 6. 링크와 참조

- 문서 본문에서 다른 문서를 언급할 때는 ID를 백틱으로 쓴다: `M1-T2`, `D1.3`, `guo2025-loglinear`.
- 처음 언급하거나 바로 열어 봐야 하는 경우에는 상대 경로 Markdown 링크를 함께 쓴다.
- 커밋을 가리킬 때는 짧은 해시 7자리.

## 7. 언어와 문체

- 본문: 한국어. 식별자, frontmatter 키, 상태값, 커밋 타입, 코드: 영어.
- 사실과 추측을 구분한다. 추측에는 "추정", "가설", "미확인"을 붙인다.
- 수치에는 출처(실행 ID, 참고문헌 ID)를 붙인다.

## 8. Stub 사양의 문서를 쓸 때

해당 사양이 `stub`이면 이 문서의 규칙을 지키고, 초기화 때 생성된 같은 유형의 문서가 있으면 그 구조를 따른다. 새로 구조를 정했다면 작업 일지에 적어 둔다(사양 보완 근거가 된다).
