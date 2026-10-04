---
id: review
type: spec
spec_version: 6
status: complete
---
# Review 문서 사양 (게이트 요청 · 에스컬레이션)

## 1. 목적

에이전트가 사람의 판단을 요청하고, 사람이 응답을 남기는 비동기 창구다. `kind`로 두 종류를 구분한다.

- `gate`: task 완료 후 판정 요청
- `escalation`: task 진행 중 막혔을 때 판단 요청

## 2. 위치와 파일명

- 대기 중: `reviews/open/<Task>_gate-<NN>.md`, `reviews/open/<Task>_esc-<NN>.md`
- 처리 후: `reviews/closed/` 로 이동 (파일명 유지)

## 3. Frontmatter

| 필드 | 필수 | 값 |
|---|---|---|
| `id` | ✓ | 파일명에서 `.md`를 뺀 것 |
| `type` | ✓ | `review` |
| `spec_version` | ✓ | `6` |
| `kind` | ✓ | `gate` \| `escalation` |
| `task` | ✓ | Task ID |
| `status` | ✓ | `open` \| `answered` \| `closed` |
| `requested` | ✓ | 요청일 |
| `answered` | ✓ | 응답일 또는 `null` |
| `verdict` | ✓ | `gate`: `approve` \| `revise` \| `redirect` \| `null`. `escalation`: 항상 `null` |
| `source` | ✓ | `document` \| `conversation` \| `null` |
| `decisions` | ✓ | 이 요청에서 확정이 필요한 결정 ID 목록 |
| `proposed_next` | gate만 | 제안하는 다음 Task ID 또는 `null` |
| `updated` | ✓ | 날짜 |

## 4. 본문 구조

### 4.1 `kind: gate`

| 섹션 | 작성자 | 내용 |
|---|---|---|
| `# <id>` | 에이전트 | |
| `## 요약` | 에이전트 | 무엇을 했고 무엇을 알게 되었는지 3–5문장 |
| `## 완료 기준 점검` | 에이전트 | 표: 기준 / 충족 여부(✓, ✗, 부분) / 근거(경로·실행 ID) |
| `## 예상과 달랐던 점` | 에이전트 | 없으면 "없음" |
| `## 확정이 필요한 결정` | 에이전트 | 결정 ID별 추천안과 근거 |
| `## 다음 task 제안` | 에이전트 | 계획대로인지, 수정안이 있는지, 다음 task의 자원 요청 |
| `## 응답` | 사람 | 아래 하위 섹션 |

### 4.2 `kind: escalation`

| 섹션 | 작성자 | 내용 |
|---|---|---|
| `# <id>` | 에이전트 | |
| `## 상황` | 에이전트 | 무엇이 막혔는지, 어떤 규칙(workflow §7.1)에 해당하는지 |
| `## 선택지` | 에이전트 | 선택지별 내용과 영향(시간, 자원, 결과 해석) |
| `## 추천` | 에이전트 | 추천안과 이유 |
| `## 응답` | 사람 | 아래 하위 섹션 |

### 4.3 `## 응답` (공통)

```
## 응답

### 판정
<gate: approve | revise | redirect. escalation: 선택한 선택지>

### 코멘트
<자유>

### 확정 결정
<결정 ID와 확정 내용, 없으면 "없음">

### 다음 task 승인
<gate만: 승인하는 Task ID 또는 "없음">
```

응답 섹션은 요청 시 하위 제목만 두고 비워 둔다.

## 5. 작성·수정 권한

| 부분 | 에이전트 | 사람 |
|---|---|---|
| `## 응답` 위의 모든 섹션 | 작성 (제출 후 수정 금지) | 읽기 |
| `## 응답` | 대화 경로에서 사람 발언 그대로 기록만 (procedures/gate-conversation.md) | 작성 |
| `verdict`, `source`, `answered`, `status: answered` | 대화 경로에서만 기록 | 작성 |
| `status: closed`, 폴더 이동 | 사람 커밋 이후 수행 | 가능 |

## 6. 생성·갱신 시점

- 생성: 게이트 요청(procedures/task-gate.md), 에스컬레이션(procedures/escalate.md).
- 응답: 사람의 `gate` / `respond` 커밋과 같은 커밋.
- 종료: 다음 세션에서 에이전트가 `closed/`로 이동(procedures/gate-apply.md).

## 7. 검증 규칙

- `id`가 파일명과 같고, 파일명의 Task·종류가 `task`, `kind`와 일치한다.
- `open/`에 있으면 `status`가 `open` 또는 `answered`, `closed/`에 있으면 `closed`.
- `status`가 `answered` 이상이면 `answered`, `source`가 채워져 있고, `gate`는 `verdict`도 채워져 있다.
- `closed`인 gate review에 대응하는 사람의 `gate` 커밋이 존재한다 (`Review:` trailer 또는 `Task:`와 날짜로 대응).
- `## 완료 기준 점검` 표의 항목 수가 task 카드의 완료 기준 수와 같다.
