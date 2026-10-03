# 계획·사양을 바꾸고 결정을 확정하기

- 언제: 연구 질문·로드맵·마일스톤을 바꿀 때, 문서 사양이나 에이전트 규칙을 바꿀 때, 결정 문서를 확정할 때
- 결과: 사람 신원의 `plan`, `spec`, `decide` 커밋

이 문서들은 사람만 확정한다. 에이전트는 바꾸고 싶은 것이 있으면 `notes/`에 제안을 쓰고 `propose` 커밋을 남긴다. 사람은 제안을 읽고 받아들일지 정한다.

| 바꾸는 것 | 파일 | 커밋 타입 |
|---|---|---|
| 연구 질문, 가설, 마일스톤 목록 | `plan/roadmap.md` | `plan` |
| 마일스톤의 목표, task 목록, Go/No-go 기준 (`active` 이후) | `plan/milestones/<M>/milestone.md` | `plan` |
| task 승인 | (task 카드) | `plan` + `Approve` ([approve-task.md](approve-task.md)) |
| 문서 사양, 절차, 에이전트 규칙 | `specs/`, `AGENTS.md`, `CLAUDE.md`, `.claude/` | `spec` |
| 결정 확정 | `decisions/<D-ID>_<slug>.md` | `decide` + `Decisions`, `Source` |

마일스톤이 `planned`인 동안(그 마일스톤의 T0 진행 중)에는 에이전트가 목표·기준의 초안을 직접 쓸 수 있다. T0의 게이트를 승인하면 `active`가 되고, 그 뒤로는 사람만 바꾼다.

## 순서

### 계획·사양 변경 (터미널 A)

1. 에이전트의 제안(`notes/`, `propose` 커밋)이 있으면 읽는다: `git log --grep '^propose' --oneline`.
2. 파일을 고친다.
3. 커밋한다.
   ```bash
   lg commit
   ```
   질문: 파일 선택 → 타입 `plan` 또는 `spec` → (`plan`이면 Approve는 고르지 않음) → scope(예: `M1`, 빈 입력이면 생략) → 요약 → 커밋. 본문에 바꾼 이유를 쓰려면 확인 단계에서 "편집기로 수정".
4. 터미널 B에 알린다. 에이전트는 다음 작업부터 바뀐 계획·사양을 따른다.

### 결정 확정

결정은 보통 게이트 판정 때 함께 확정한다(요청서의 "확정이 필요한 결정"). 따로 확정할 때:

1. 결정 문서의 `status`를 `confirmed`로 바꾸고 근거를 적는다.
2. `lg commit` → 타입 `decide` → scope(예: `D0.2`, 빈 입력이면 생략) → Source `document` → Decisions(예: `D0.2`) → 요약 → 커밋. 헤더는 `decide(D0.2): …`가 된다.

대화로 정했다면 에이전트에게 말하면 된다. 에이전트가 `lg draft --type decide …`로 초안을 만들고, `lg commit`으로 확정한다.

## 확인

```bash
git log -1 --format='%an | %s%n%(trailers:only,unfold)'
```

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `decide 커밋에는 Decisions trailer가 필요합니다` | `git commit`으로 직접 쓸 때 빠뜨렸다. `lg commit`은 묻는다 |
| `Decisions 형식이 잘못되었습니다` | `D<n>.<n>` 형식, 쉼표로 구분 (예: `D0.2, D1.1`) |
| 에이전트가 바뀐 규칙을 모르는 것 같음 | `/session-start`로 새로 시작한다. 규칙 문서는 세션 시작 때 읽는다 |

## 에이전트는 무엇을 하나

- 변경 제안: `notes/`에 쓰고 `propose` 커밋 (규칙: 생성된 `AGENTS.md`)
- 결정 확정의 반영: `scripts/apply-human-commits`가 결정 문서를 `confirmed`로, 결정 목록의 상태와 확정 커밋 칸을 바꾼다(절차 `gate-apply`). spec_version 2 프로젝트에서는 확정할 때 결정 문서의 `status`를 직접 `confirmed`로 바꿔 함께 커밋하면 확실하다.
