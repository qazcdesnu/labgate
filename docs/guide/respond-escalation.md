# 에스컬레이션에 답하기

- 언제: 에이전트가 범위 밖 작업, 확정되지 않은 결정, 예산 초과, 잘못된 완료 기준, 규칙 충돌 때문에 멈추고 질문했을 때. 요청서는 `reviews/open/<Task>_esc-NN.md`, 카드는 `blocked`
- 결과: 사람 신원의 `respond` 커밋. 에이전트가 반영하고 작업으로 돌아간다

## 순서

요청서의 `## 상황`, `## 선택지`, `## 추천`을 읽고 고른다. 답하는 방법은 게이트 판정과 같다.

### 방법 1: 문서로 (터미널 A)

1. 요청서의 `## 응답`에 고른 선택지와 조건(예: 추가 예산)을 쓴다. frontmatter: `status: answered`, `answered: <날짜>`, `source: document` (`verdict`는 `null` 그대로).
2. 커밋한다.
   ```bash
   git add reviews/open/M1-T2_esc-01.md
   lg commit
   ```
   질문: 타입 `respond` → Task → Source `document` → 요약(예: `choose option 2, +20 GPU h`) → 커밋.

### 방법 2: 대화로 (터미널 B → A)

1. 터미널 B에서 답한다. 예: "2번으로 가자. GPU 20시간 추가."
2. 에이전트가 응답을 문서에 옮기고 `lg draft --type respond …`로 초안을 만든 뒤 멈춘다.
3. 터미널 A에서 `lg commit`으로 확정하고, 터미널 B에 알린다.

예산이나 범위를 넓히는 답이면, task 카드의 "범위"나 "자원 예산"도 같은 커밋에서 고치는 것이 좋다. 카드에 적힌 범위가 에이전트에게 가장 우선하는 기준이다.

## 확인

```bash
git log -1 --format='%an | %s%n%(trailers:only,unfold)'   # 나 | respond(M1-T2): … / Task, Source
```

다음 세션에서 에이전트가 요청서를 닫고 카드를 `in-progress`로 돌려 `task(<Task>): resume after response <해시>`를 커밋한다.

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| 에이전트가 응답 뒤에도 멈춰 있음 | 커밋했다고 알리거나 `/session-start`로 새로 시작한다 |
| 선택지에 원하는 답이 없음 | 응답에 새 방향을 쓰면 된다. 계획이 크게 바뀌면 `plan` 커밋도 한다 ([change-plan.md](change-plan.md)) |

## 에이전트는 무엇을 하나

- 질문 제출: `specs/procedures/escalate.md`
- 대화 응답의 반영과 초안: `specs/procedures/gate-conversation.md`
- 커밋 뒤 정리: `specs/procedures/gate-apply.md`
