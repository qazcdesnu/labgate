# lg answer

열린 게이트 요청이나 에스컬레이션을 터미널에 보여 주고 판정을 한 번 묻는다. 그 답으로 요청서의 `## 응답`, frontmatter, 사람 커밋(`gate` 또는 `respond`, 필요하면 `plan`·`decide`)과 tag를 **한 번에** 만든다.

- 누가: 사람만. 표준 입력과 출력이 모두 터미널일 때만 동작한다(에이전트는 실행할 수 없고, Claude Code deny도 있다). 그래서 응답은 사람이 썼다는 것을 도구가 보장한다(G5).
- 언제: 에이전트가 게이트 요청이나 에스컬레이션을 내고 멈췄을 때 (`lg status`가 `→ lg answer <ID>`로 안내한다)
- 전제: labgate 0.2 이상으로 만든 프로젝트. 반영 미리보기는 spec_version 5 이상

## 형식

```
lg answer [REVIEW_ID] [--no-tag]
lg answer <결정 ID>          # 예: lg answer D0.1 (게이트와 별개로 결정 확정)
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `REVIEW_ID` | review ID (예: `M0-T0_gate-01`) 또는 결정 ID (예: `D0.1`) | 없음 | 응답할 요청, 또는 확정할 결정. 생략하면 열린 요청이 하나면 그것, 여럿이면 목록에서 고른다 |
| `--no-tag` | — | 꺼짐 | gate 승인이어도 tag를 만들지 않는다 |

## 동작

1. **확인.** 다음 중 하나라도 걸리면 아무것도 바꾸지 않고 멈춘다.
   - 사람 커밋 대기 상태다(`.lg/pending/COMMIT_MSG`): 대화로 판정해 에이전트가 초안을 만들었다면 `lg commit`으로 확정한다.
   - 그 요청서에 커밋되지 않은 변경이 있다: 응답을 직접 쓰고 있는 것이므로 `lg commit`한다. `lg answer`는 사람이 쓴 것을 덮어쓰지 않는다.
   - 요청서 말고 stage된 변경이 있다.
   - 요청서가 `open`이 아니다.
   - `reviews/closed/`에 같은 ID가 있다: 남은 사본이므로 지우라고 안내한다(고를 목록에서도 뺀다).
2. **보여 주기.** 요청서의 에이전트 섹션(`## 응답` 위)을 렌더링한다. 게이트면 `lg verify --task <Task>` 요약과 완료 기준 체크 수를 붙인다. 화면보다 길면 pager(`MANPAGER`, `PAGER`, 없으면 `less`)로 연다.
3. **묻기.**
   - 게이트:
     1. 판정(approve / revise / redirect)
     2. approve면 다음 task: 같은 마일스톤의 draft 카드에서 여러 개 고를 수 있다. 요청서의 `proposed_next`를 미리 골라 둔다.
     3. 마일스톤 판정: 그 task가 마일스톤의 마지막일 때만 묻는다(다음 task를 고르지 않았고, 닫히지 않은 다른 task가 없을 때).
     4. 확정할 결정: 요청서가 확정을 요청한 결정(frontmatter `decisions`)만 제목과 함께 나오고 미리 골라져 있다. 요청이 없으면 묻지 않는다. 고른 결정마다 확정 내용 한 줄. 그 밖의 결정은 `lg answer <D-ID>`로 따로 확정한다
     5. 코멘트: revise·redirect면 필수다.
   - 에스컬레이션: 선택지(요청서 `## 선택지`의 항목, 또는 직접 입력), 확정할 결정, 코멘트, 커밋 요약.
4. **미리보기.** 이 판정이 반영되면 생길 상태 변화를 보여 준다. 예: 카드 `in-review → closed`, 다음 카드 `draft → approved`, T0 승인이면 마일스톤 `planned → active`, review 이동, tag.
   - 프로젝트의 `scripts/apply-human-commits --preview`가 계산하므로 실제 반영과 같다.
   - 반영할 수 없는 판정이면 여기서 멈춘다. 예: 카드가 `in-review`가 아님.
   - spec_version 4 이하에서는 미리보기 대신 커밋할 trailer만 보여 준다.
5. **확인.** 응답 원문과 커밋 메시지를 보여 주고 고른다: 커밋 / 편집기로 응답 수정 / 취소.
   - 고친 응답은 다시 검사한다(하위 섹션이 모두 있는가, 게이트 판정이 고른 것과 같은가). 판정을 바꾸려면 취소하고 다시 한다.
   - 취소하면 아무것도 바뀌지 않는다.
6. **쓰기와 커밋.**
   - 요청서를 쓴다: `## 응답`의 하위 섹션(판정, 코멘트, 확정 결정, 다음 task 승인)과 frontmatter(`status: answered`, `answered`, `verdict`, `source: document`, `updated`).
   - 요청서만 stage해서 커밋한다.

| 판정 | 커밋 |
|---|---|
| 게이트 | `gate(<Task>): <판정>[, next <Next>]` + `Task`, `Verdict`, `Source: document`, `Next`(approve일 때, 고른 것이 없으면 `none`), `Milestone-Verdict`, `Decisions`, `Review` |
| 다음 task를 둘 이상 골랐을 때 | 이어서 빈 커밋 `plan: approve <나머지>` + `Approve`. 첫째(요청서가 제안한 것이 있으면 그것)는 gate의 `Next`가 된다 |
| 에스컬레이션 | `respond(<Task>): <요약>` + `Task`, `Source: document`, `Review` |
| 에스컬레이션에서 결정을 골랐을 때 | 이어서 빈 커밋 `decide…: confirm` + `Decisions`, `Source: document` |

- 게이트 승인이면 `gate/<Task>`, 마일스톤 판정이면 `milestone/<M>-<판정>` tag를 만든다(`lg commit`과 같다).
- 커밋 뒤의 안내도 `lg commit`과 같다: 다음 세션 시작 때 에이전트가 자동으로 반영한다.
- 두 번째 커밋이 실패하면 첫 커밋은 그대로 두고 코드 4로 끝내며, 남은 커밋 메시지를 보여 준다.

## 결정 확정 (`lg answer D0.1`)

게이트 판정과 별개로 결정 하나를 확정한다.

1. **확인.** 결정 문서(`decisions/D0.1_*.md`)가 하나이고 `proposed`나 `discussing`이어야 한다. 사람 커밋 대기 상태, 결정 문서에 커밋되지 않은 변경, stage된 변경이 있으면 멈춘다.
2. **보여 주기.** 결정 문서를 터미널에 보여 준다.
3. **묻기.** 확정 내용 한 줄(필수), 근거·코멘트(선택), 커밋 요약(기본값 `confirm <확정 내용>`).
4. **미리보기.** 결정 `→ confirmed`와 결정 목록의 변화를 보여 준다.
5. **커밋.** 커밋 / 취소. 빈 커밋 `decide(D0.1): <요약>`을 만든다. 본문은 `확정: <내용>`, trailer는 `Decisions: D0.1`, `Source: document`.

결정 문서는 고치지 않는다. 결정 문서의 양식은 프로젝트가 채우는 사양이기 때문이다. 확정 내용은 커밋 본문에 남고, 상태는 다음 세션에 에이전트가 반영한다.

자세한 사양: 설계 문서 §24.4.

## 읽고 쓰는 것

- 읽는 것: `reviews/open/`의 요청서, 카드·결정·마일스톤의 frontmatter, `.lg/identities.json`, `.lg/hooks/commit-msg`, 프로젝트의 `scripts/apply-human-commits --preview`
- 쓰는 것: 그 요청서, 사람 신원 커밋, tag, `.lg/pending/HUMAN_FILES` 정리

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 커밋함 |
| 1 | 예기치 못한 오류 |
| 2 | 터미널이 아님, 등록되지 않은 사람 신원, labgate 프로젝트가 아님, 요청서 말고 stage된 변경, 요청서 형식 오류 |
| 3 | 응답할 요청 없음, 없는 ID, 없는 결정·확정할 수 없는 결정 상태, 닫힌 review의 사본, 사람 커밋 대기 상태, 요청서에 커밋되지 않은 변경, 요청서가 open이 아님, 반영할 수 없는 판정 |
| 4 | Git 오류 (hook 거부 포함) |
| 130 | 취소, 중단(Ctrl-C) |

## 예

```
$ lg answer
… 요청서 …
✓ lg verify --task M0-T0: 위반 없음
  완료 기준: 7/7 체크
? M0-T0 판정  approve
? 다음 task 승인  ◉ M0-T1  ◉ M0-T2  ◉ M0-T3  ◉ M0-T4  ○ M0-T5
? 확정할 결정
? 코멘트 (선택, 빈 입력이면 없음)  D1.1은 결정으로 유지

이 판정이 반영되면 (다음 세션에서 에이전트가):
  plan/milestones/M0/tasks/M0-T0.md: status in-review → closed
  plan/milestones/M0/tasks/M0-T1.md: status draft → approved
  plan/milestones/M0/milestone.md: status planned → active
  reviews/open/M0-T0_gate-01.md → reviews/closed/M0-T0_gate-01.md (status closed)
  plan/milestones/M0/tasks/M0-T2.md: status draft → approved
  …
  tag: gate/M0-T0
? 어떻게 할까요?  커밋 (2개)
✓ 커밋했습니다: 3f2a1c9 gate(M0-T0): approve, next M0-T1
✓ 커밋했습니다: 8b0d4e2 plan: approve M0-T2, M0-T3, M0-T4
  tag: gate/M0-T0
  다음 세션 시작 때 에이전트가 자동으로 반영합니다. 열린 세션에서 바로 이어 가려면 알리세요.
```

## 관련

- 할 일 찾기: [lg status](lg-status.md)
- [게이트 판정하기](../guide/judge-gate.md), [에스컬레이션에 답하기](../guide/respond-escalation.md)
- 요청서를 직접 쓰거나 대화로 판정하는 방법: [lg commit](lg-commit.md), 절차 gate-conversation
