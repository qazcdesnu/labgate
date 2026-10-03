---
id: git-commit
type: spec
spec_version: 4
status: complete
---
# 커밋 규약

이 규약은 `.lg/hooks/commit-msg`가 검사한다.

## 1. 신원

| 주체 | 커밋 방법 | 작성자 |
|---|---|---|
| 사람 | 터미널에서 `lg commit`, 또는 `git commit` (저장소 로컬 설정) | `.lg/identities.json`의 `humans` 중 하나 |
| 에이전트 | `scripts/agent-commit` | `.lg/identities.json`의 `agent` |

작성자 이메일이 둘 중 어디에도 없으면 커밋이 거부된다.

에이전트가 사람 커밋을 준비할 때는 `lg draft`로 stage와 초안(`.lg/pending/COMMIT_MSG`)까지만 하고, 확정은 사람이 `lg commit`으로 한다 ([procedures/commit-prep.md](procedures/commit-prep.md)).

## 2. 메시지 형식

```
<type>(<scope>): <요약>

<본문 (선택)>

Actor: human | agent
<기타 trailer>
```

- 헤더는 72자 이하. 요약은 무엇을 했는지 한 문장.
- 본문은 왜 했는지, 무엇이 달라졌는지.
- 마지막 문단은 trailer 블록(`Key: value` 줄만). **trailer는 이 한 문단에 모두 쓴다.** `Co-Authored-By` 같은 다른 trailer를 넣으려면 같은 문단에 넣는다. trailer 뒤에 빈 줄을 두고 다른 문단을 붙이면 hook이 trailer를 찾지 못한다.
- scope: task 관련 타입은 Task ID와 같아야 한다. 그 밖에는 선택(결정 ID, 마일스톤 ID 등).

## 3. 타입

| 분류 | 타입 | 용도 |
|---|---|---|
| 사람 전용 | `gate` | task 게이트 판정 |
| | `decide` | 결정 확정 |
| | `plan` | 로드맵·마일스톤 변경, 첫 task 승인 |
| | `spec` | 사양·규칙 문서 변경 확정 |
| | `respond` | 에스컬레이션 응답 |
| 에이전트 전용 | `task` | task 상태 전이, 카드 갱신 |
| | `propose` | 결정·계획·사양 변경 제안 |
| | `review` | 게이트 요청, 에스컬레이션 제출 |
| 공통 | `exp` | 실험 코드 |
| | `run` | 실행 기록 |
| | `result` | 결과 문서, 그림, 표 |
| | `ref` | 참고문헌 추가, 매핑 문서 |
| | `log` | 작업 일지, STATUS, 사람 커밋 반영 |
| | `init` | 초기화 |
| | `chore` | 위에 속하지 않는 잡무 |

사람 전용 타입은 판정·확정을, 에이전트 전용 타입은 에이전트가 사람에게 요청하는 흐름을 나타낸다. 공통 타입은 작업 내용을 나타내며, 누가 했는지는 작성자 신원과 `Actor`로 구분한다.

## 4. Trailer

| Key | 필수 | 값 |
|---|---|---|
| `Actor` | 항상 | `human` \| `agent` (타입 분류·작성자와 일치) |
| `Task` | `gate`, `respond`, `task`, `run`, `result`, `review` | `M<n>-T<n>` |
| `Verdict` | `gate` | `approve` \| `revise` \| `redirect` |
| `Source` | `gate`, `decide`, `respond` | `document` \| `conversation` |
| `Decisions` | `decide` (그 외 선택) | `D<n>.<n>` 쉼표 목록 |
| `Next` | 선택 (`gate`) | `M<n>-T<n>` 또는 `none` |
| `Milestone-Verdict` | 선택 (`gate`) | `go` \| `nogo` \| `conditional` |
| `Approve` | 선택 (`plan`) | `M<n>-T<n>` 쉼표 목록 |
| `Applies` | 선택 (반영 커밋) | 이 커밋이 상태 필드에 반영한 사람 커밋의 해시(7–40자) 쉼표 목록. `scripts/apply-human-commits`가 쓴다 |
| `Refs` | 선택 | 관련 ID 목록 |
| `Review` | 선택 | review 문서 ID |

## 5. 예시

에이전트 착수:

```
task(M1-T2): start signal validation

Actor: agent
Task: M1-T2
```

에이전트 게이트 요청:

```
review(M1-T2): request gate

완료 기준 5개 중 5개 충족. D1.3 확정 필요.

Actor: agent
Task: M1-T2
Review: M1-T2_gate-01
Decisions: D1.3
```

사람 게이트 판정:

```
gate(M1-T2): approve, next M1-T3

신호 검증 결과 수용. PR 기준 채택.

Actor: human
Task: M1-T2
Verdict: approve
Source: conversation
Next: M1-T3
Decisions: D1.3
```

사람 결정 확정:

```
decide(D1.3): confirm participation ratio as primary signal

Actor: human
Decisions: D1.3
Source: document
```

사람이 직접 고친 실험 코드:

```
exp(M1-T2): fix off-by-one in window mask

Actor: human
Task: M1-T2
```

사람 커밋의 반영 (에이전트):

```
log(M0-T0): apply plan 70ea21b

Actor: agent
Applies: 70ea21b
```

첫 task 승인:

```
plan(M0-T0): approve initial task

Actor: human
Approve: M0-T0
```

## 6. Tag

| 시점 | tag | 만드는 사람 |
|---|---|---|
| task 게이트 `approve` | `gate/<Task>` | 사람 (`lg commit`이 자동) |
| 마일스톤 판정 | `milestone/<M>-<go\|nogo\|conditional>` | 사람 (`lg commit`이 자동) |

tag는 해당 `gate` 커밋에 붙인다.

## 7. 금지

- 에이전트: `git commit`·`lg commit` 실행, `--no-verify`, `--author`, `-a`, 사람 전용 타입, tag, 이력 재작성, 브랜치 병합과 cherry-pick (워크트리는 실험 격리용, AGENTS.md). 일괄 stage(`git add -A`, `git add .`, `git add -u`)와 사람의 미커밋 변경을 커밋에 넣는 것 ([workflow.md](workflow.md) §4.1).
- 사람: 이력 재작성 (실수는 `git revert`).
- `--no-verify`는 사람이 긴급할 때만 쓰고, 다음 커밋 본문에 이유를 남긴다.
