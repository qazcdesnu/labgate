# 게이트 판정하기

- 언제: 에이전트가 task를 끝내고 게이트 요청서(`reviews/open/<Task>_gate-NN.md`)를 냈을 때. `STATUS.md`의 "사람 판단 대기"에 올라온다
- 결과: 사람 신원의 `gate` 커밋(`Verdict`, `Source`, 필요하면 `Next`, `Milestone-Verdict`). 승인이면 tag `gate/<Task>`

## 판정의 종류

| Verdict | 뜻 | 카드 | 다음 |
|---|---|---|---|
| `approve` | 받아들인다 | `closed` | `Next:`의 task가 승인된다. `Next: none`이면 다음 지시를 기다린다 |
| `revise` | 같은 task를 고쳐서 다시 | `revise` | 에이전트가 같은 task를 재개하고, 다음 요청서는 `gate-02`처럼 번호가 오른다 |
| `redirect` | 이 방향은 접는다 | `redirected` | 사람이 `plan` 커밋으로 대체 계획을 낼 때까지 기다린다 |

마일스톤의 마지막 task라면 `Milestone-Verdict`(`go`, `nogo`, `conditional`)도 함께 정한다. tag `milestone/<M>-<verdict>`가 생긴다.

## 순서

판정은 두 방법 중 편한 쪽으로 한다. 결과(사람 신원의 `gate` 커밋)는 같다.

### 방법 1: 문서로 (터미널 A)

1. 요청서를 읽는다: 요약, 완료 기준 점검, 예상과 달랐던 점, 확정이 필요한 결정, 다음 task 제안.
2. 요청서의 `## 응답`을 쓴다(판정, 코멘트, 확정 결정, 다음 task 승인). frontmatter를 채운다:
   ```yaml
   status: answered
   answered: 2026-10-05
   verdict: approve          # approve | revise | redirect
   source: document
   ```
3. 필요하면 같은 커밋에서 다음 task 카드의 `status`를 `approved`로, 확정하는 결정 문서의 `status`를 `confirmed`로 바꾼다. 바꾸지 않아도 에이전트가 커밋을 보고 반영한다.
4. stage하고 커밋한다.
   ```bash
   git add reviews/open/M0-T0_gate-01.md     # 함께 바꾼 카드·결정 문서도
   lg commit
   ```
   질문: 타입 `gate` → Task `M0-T0` → Verdict → Source `document` → Next(예: `M0-T1`, 없으면 빈 입력) → Milestone-Verdict(마지막 task가 아니면 `(없음)`) → 요약(예: `approve, next M0-T1`) → 커밋.
5. 커밋하기 전 확인 화면에 **`lg verify` 결과**가 나온다. `✓ … 위반 없음`이면 그대로 커밋한다. `✗ … 위반 N건`이면 `lg verify --task <Task>`로 자세히 보고 정한다: 의도된 것(예: 카드 범위가 허용한 규칙 파일 수정)이면 커밋, 아니면 취소하고 에이전트에게 바로잡게 한다([mistakes.md](mistakes.md)). 점검표(완료 기준 체크 수, 근거 경로)도 판정에 참고한다.

### 방법 2: 대화로 (터미널 B → A)

1. 터미널 B에서 에이전트에게 판정을 말한다. 예:
   > M0-T0 승인. 다음은 M0-T1. D0.2는 Mamba-2로 확정.
2. 에이전트가 발언을 요청서의 `## 응답`에 그대로 옮기고, 바뀐 파일을 stage하고, `lg draft`로 커밋 초안을 만든 뒤 멈춘다(사람 커밋 대기 상태).
3. 터미널 A에서 확정한다.
   ```bash
   git diff --cached        # 에이전트가 무엇을 바꿨는지
   lg commit                # 초안이 있으면 초안 모드: 메시지 확인 → 커밋 (고칠 것이 있으면 편집기로 수정)
   ```
4. 터미널 B에 "커밋했어"라고 알린다.

판정이 모호하면 에이전트가 초안을 만들기 전에 되묻는다. 판정·다음 task·확정할 결정을 한 번에 분명히 말하는 것이 좋다.

## 확인

```bash
git log -1 --format='%an | %s%n%(trailers:only,unfold)'   # 나 | gate(M0-T0): … / Verdict, Source, Next …
git tag --points-at HEAD                                   # 승인이면 gate/M0-T0
```

다음 세션에서(또는 커밋했다고 알리면) 에이전트가 `scripts/apply-human-commits`로 반영한다. 요청서가 `reviews/closed/`로 옮겨지고, 카드가 `closed`, 다음 카드가 `approved`가 되며, 반영 커밋에 `Applies: <판정 커밋>`이 남는다. 대화로 판정한 경우도 같다.

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `'gate' 커밋에는 Source trailer가 필요합니다` 등 | `git commit`으로 직접 쓸 때 trailer를 빠뜨렸다. `lg commit`은 필요한 것을 모두 묻는다 |
| `scope(…)가 Task(…)와 같아야 합니다` | 헤더 `gate(<Task>)`의 Task와 `Task:` trailer가 다르다 |
| 초안 내용이 내가 말한 것과 다름 | `lg commit`의 확인 단계에서 "편집기로 수정"을 고르거나, "취소" 후 에이전트에게 고쳐 달라고 한다 |
| tag가 필요 없음 | `lg commit --no-tag` |

## 에이전트는 무엇을 하나

- 요청서 작성: `specs/procedures/task-gate.md`
- 대화 판정의 반영과 초안: `specs/procedures/gate-conversation.md`
- 커밋 뒤 정리(요청서 닫기, 상태 반영, `log(<Task>): apply gate <해시>` 커밋): `specs/procedures/gate-apply.md`
