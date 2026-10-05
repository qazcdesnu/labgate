---
id: baseline
type: spec
spec_version: 8
status: complete
---
# 기준선 연구 사양

## 1. 목적

후보들이 성능을 비교할 **기준선 연구 하나**를 후보 평가 전에 정하고 잠근다. 기준선이 없으면 후보마다 비교 대상·과제·설정이 달라 후보끼리 비교할 수 없다.

## 2. 위치와 파일명

`plan/baseline.md` (ideation 프로젝트에 하나).

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | `baseline` |
| `type` | ✓ | `baseline` |
| `spec_version` | ✓ | `8` |
| `status` | ✓ | `draft` \| `locked` |
| `locked_commit` | ✓ | 잠근 사람 커밋의 해시 또는 `null` |
| `reference` | ✓ | 기준선 논문의 참고문헌 ID (잠글 때는 비어 있으면 안 된다) |
| `task` | ✓ | 과제·벤치마크 |
| `metric` | ✓ | 지표 |
| `reported` | ✓ | 보고 수치와 표 번호 |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

`## 선정한 기준선`(논문, 과제, 지표와 수치, 설정, 공개 코드, 재현 비용), `## 선정 규칙`(최신성, 비교 대상으로 쓰이나, 재현 가능성, 하나만), `## 후보 기준선 비교`(표), `## 선정 이유`.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| 후보 기준선 비교, 추천, 선정 이유 초안 | 작성 (잠기기 전) | 수정 |
| 선정(frontmatter `reference` 등) | 추천을 채운다 (잠기기 전) | 결정 |
| `status: draft → locked`, `locked_commit` | 하지 않는다. 첫 마일스톤의 `Milestone-Verdict: go`를 반영 도구가 반영한다 | 결정 |
| 잠근 뒤 | 고치지 않는다 (G7) | `plan` 커밋으로만. 바꾸면 모든 후보를 다시 쓰고 평가한다 |

## 6. 생성·갱신 시점

생성: `lg init --kind ideation`. 작성: 첫 마일스톤의 지형 조사. 잠금: 첫 마일스톤의 마지막 게이트(go).

## 7. 검증 규칙

- 잠글 때 `reference`, `task`, `metric`, `reported`가 비어 있지 않고 `reference`가 `references/catalog.md`에 있다.
- 후보의 평가는 기준선이 잠긴 뒤에만 있고, 평가 표 머리의 기준선 버전이 지금 버전과 같다.
