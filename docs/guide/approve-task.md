# task 승인하기

- 언제: 프로젝트를 만든 직후 첫 task(M0-T0)를 시작하게 할 때. 그 밖에 게이트를 거치지 않고 task를 승인할 때
- 결과: 사람 신원의 `plan` 커밋 + `Approve: <Task>`. 에이전트가 그 task를 착수할 수 있다

다음 task는 보통 따로 승인하지 않는다. 앞 task의 게이트 판정에서 `Next: <Task>`로 함께 승인한다([judge-gate.md](judge-gate.md)).

## 순서

### 첫 task 승인 (터미널 A)

1. `STATUS.md`와 첫 task 카드(`plan/milestones/M0/tasks/M0-T0.md`)의 범위와 완료 기준을 읽는다. 고칠 것이 있으면 카드를 고친다.
2. `notes/`에 넣은 자료나 카드 수정이 있으면 stage한다. 없으면 건너뛴다.
   ```bash
   git add notes/ plan/milestones/M0/tasks/M0-T0.md
   ```
3. 커밋한다.
   ```bash
   lg commit --allow-empty
   ```
   - stage한 것이 있으면 `--allow-empty` 없이 `lg commit`도 된다.
   - 질문: 타입 `plan` → Approve에서 `M0-T0`을 스페이스로 고르고 엔터 → 요약(예: `approve initial task`) → 커밋.
   - 결과 헤더는 `plan(M0-T0): approve initial task`, trailer는 `Actor: human`, `Approve: M0-T0`.

`lg`가 없는 환경에서는 같은 내용을 `git commit`으로 쓴다.

```bash
git commit --allow-empty -m "plan(M0-T0): approve initial task" -m "Actor: human
Approve: M0-T0"
```

### 착수시키기 (터미널 B)

```
/session-start
/task-start M0-T0
```

### 여러 task를 한 번에 승인

`lg commit`의 Approve에서 여러 개를 고른다. 이때 scope는 따로 묻는다(빈 입력이면 생략). trailer는 `Approve: M1-T1, M1-T2`처럼 된다.

## 확인

```bash
git log -1 --format='%an | %s%n%(trailers:only,unfold)'   # 나 | plan(M0-T0): … / Actor: human / Approve: M0-T0
```

에이전트가 착수한 뒤에는:

```bash
grep -m1 '^status:' plan/milestones/M0/tasks/M0-T0.md   # in-progress
git log -1 --format='%an | %s%n%(trailers:only,unfold)'  # research-agent | task(M0-T0): start … / Refs: <승인 커밋>
```

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `lg commit`이 "커밋할 변경이 없습니다" | stage한 것이 없다. `--allow-empty`를 붙인다 |
| `plan`을 골랐는데 Approve를 묻지 않음 | labgate 0.2.0이다. 0.2.1로 업데이트한다 ([upgrade.md](upgrade.md)) |
| 에이전트가 "카드가 draft라 작업할 수 없다"며 멈춤 | 아래 참고 |

## 에이전트는 무엇을 하나

에이전트는 승인 커밋을 보고 카드 상태를 `draft → approved`로 반영한 뒤, `task-start`에서 `in-progress`로 바꾸고 `task(<Task>): start` 커밋을 남긴다. 실사용에서는 승인 커밋의 해시를 `Refs:` trailer와 카드 진행 메모에 남겼다.

**v0.2 기준 주의:** 이 반영은 에이전트 절차에 명시되어 있지 않고 원칙("사실의 원본은 커밋, 상태 필드는 에이전트가 반영")에 기대고 있다. 에이전트가 반영하지 않고 멈추면 이렇게 알린다.

> M0-T0은 `<승인 커밋 해시>`의 plan 커밋(Approve: M0-T0)으로 승인됐어. 커밋이 우선이니 카드 status를 반영하고 /task-start M0-T0 진행해.

v0.3에서 이 반영을 도구(`apply-human-commits`)로 만든다. 또는 승인 커밋에서 카드의 `status`를 직접 `approved`로 바꿔 함께 커밋하면 이 문제가 생기지 않는다.
