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

결정은 보통 게이트 판정 때 함께 확정한다(`lg answer`의 "확정할 결정"). 따로 확정할 때는 터미널에서:

```bash
lg answer D0.2
```

결정 문서가 터미널에 나온다. 확정 내용 한 줄과 근거를 쓰고 커밋한다. `decide(D0.2): …` 커밋의 본문에 `확정: <내용>`이 남고, 다음 세션에 에이전트가 결정 문서를 `confirmed`로 반영한다.

`lg`가 없거나 결정 문서에 직접 쓰고 싶으면, 결정 문서를 고친 뒤 `lg commit`으로 커밋한다. 질문 순서: 타입 `decide` → scope(예: `D0.2`) → Source `document` → Decisions(예: `D0.2`) → 요약.

### 사양 초안 확정 (stub 사양 보완)

에이전트는 stub 사양을 보완할 때 `notes/`에 초안을 쓴다(예: `notes/spec-drafts/catalog.md`, 그 사양의 `## 3. Frontmatter` 같은 번호 붙은 절만). 확정은 사람이 한다.

1. 초안을 읽는다. 초안 묶음에 "확정 전에 판단이 필요한 점"이 있으면 먼저 정해 초안에 반영한다. 직접 고쳐도 되고, 에이전트에게 고치게 해도 된다.
2. 합쳐서 커밋한다.
   ```bash
   lg spec adopt notes/spec-drafts/catalog.md notes/spec-drafts/decision.md   # 여러 개 한 번에
   ```
   파일마다 바뀌는 차이가 나온다. stub에 초안의 절이 들어가고 `status: complete`가 된다. 확인하고 커밋하면 `spec: adopt … specs` 커밋 하나가 생긴다.
3. 열린 에이전트 세션이 있으면 새로 시작한다(규칙 문서는 세션 시작 때 읽는다).

초안에 비어 있는 절(TODO)이 남거나, 번호 없는 절이 있으면 `lg spec adopt`가 멈추고 이유를 알려 준다.

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
