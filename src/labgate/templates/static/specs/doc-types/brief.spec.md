---
id: brief
type: spec
spec_version: 8
status: complete
---
# 방향 확정 문서 사양

## 1. 목적

ideation에서 고른 방향을 실행 프로젝트로 넘긴다. 사람이 읽고 판정하는 문서이면서, `lg init --from`이 frontmatter를 읽는다.

## 2. 위치와 파일명

`brief.md` (ideation 프로젝트 루트에 하나).

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | `brief` |
| `type` | ✓ | `brief` |
| `spec_version` | ✓ | `8` |
| `status` | ✓ | `draft` \| `confirmed` |
| `kind` | ✓ | 넘길 실행 프로젝트의 종류: `research` \| `proposal` |
| `question` | ✓ | 확정 질문 (실행 프로젝트의 `research_question`) |
| `summary` | ✓ | 한 줄 요약 |
| `selected` | ✓ | 고른 후보 ID 목록 |
| `dropped` | ✓ | 버린 후보 ID 목록 |
| `milestones` | ✓ | 실행 프로젝트의 마일스톤 제목 목록 (1개 이상) |
| `references` | ✓ | 넘길 참고문헌 ID 목록 |
| `decision` | ✓ | 방향을 정한 결정 ID |
| `criteria_commit` | ✓ | 평가에 쓴 기준을 잠근 커밋 |
| `baseline` | ✓ | 기준선 논문의 참고문헌 ID (`plan/baseline.md`의 `reference`). 실행 프로젝트로 넘어가 첫 task가 그 재현이 된다 |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

`## 질문과 가설`, `## 왜 이 방향인가`(고른 후보와 `lg ideas` 비교표, 순위와 다르게 골랐으면 그 이유), `## 버린 후보와 이유`, `## 첫 마일스톤에서 할 일`, `## 남은 위험과 열린 질문`.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| 내용 | 작성 (마지막 마일스톤의 task) | 수정 |
| `status: draft → confirmed` | 하지 않는다. 마지막 마일스톤 게이트의 `Milestone-Verdict: go`를 반영 도구가 반영한다 | 결정 |

## 6. 생성·갱신 시점

생성: `lg init --kind ideation`(빈 양식). 작성: 마지막 마일스톤. 확정: 그 게이트.

## 7. 검증 규칙

- `confirmed`이면 `question`, `summary`, `milestones`가 비어 있지 않다.
- `selected`, `dropped`의 ID가 `ideas/`에 있다. `references`의 ID가 `references/catalog.md`에 있다.
