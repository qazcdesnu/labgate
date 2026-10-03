# 잘못된 것을 바로잡기

- 언제: 커밋을 잘못했을 때, 초안이 틀렸을 때, 에이전트가 멈추거나 규칙을 어겼을 때
- 결과: 이력을 지우지 않고 바로잡는다. 이 프로젝트에서 이력 재작성(rebase, amend, force push)은 사람도 하지 않는다

## 순서

### 잘못된 커밋 되돌리기 (터미널 A)

```bash
git revert <해시>
```

`Revert "…"`로 시작하는 커밋은 hook이 검사하지 않으므로 그대로 통과한다. 되돌린 이유를 본문에 남긴다(`git revert` 편집기에서). 에이전트의 커밋이든 사람의 커밋이든 되돌리는 것은 사람이 한다.

### 사람 커밋의 초안 버리기 (터미널 A)

`lg commit`에서 "취소"를 고르면 초안과 stage는 그대로 남는다. 아예 버리려면:

```bash
git restore --staged <초안에 stage된 경로>    # 또는 git diff --cached --name-only 로 확인한 경로 전부
rm .lg/pending/COMMIT_MSG
```

그 뒤 에이전트에게 알린다. 초안이 있는 동안(사람 커밋 대기 상태) 에이전트는 커밋하지 않기 때문이다.

### 초안의 일부만 고치기

`lg commit`의 확인 단계에서 "편집기로 수정"을 고른다. 고친 메시지는 규약을 다시 검사한다. stage된 파일을 바꾸려면 취소한 뒤 `git add`/`git restore --staged`로 조정하고 `lg commit --pending`.

### 에이전트가 멈췄을 때

| 에이전트가 말한 것 | 할 일 |
|---|---|
| 카드가 `approved`가 아니다 | 승인했다면 승인 커밋을 알려 준다 ([approve-task.md](approve-task.md)). 아직이면 승인한다 |
| 사람 커밋 대기 상태다 | 터미널 A에서 `lg commit` |
| 커밋되지 않은 사람의 변경이 있다 | [edit-yourself.md](edit-yourself.md) |
| 범위·예산을 넘는다, 결정이 필요하다 | 에스컬레이션이다 ([respond-escalation.md](respond-escalation.md)) |
| 규칙끼리 부딪친다 | 어느 쪽을 따를지 알려 주고, 반복될 문제면 규칙 문서를 고친다(`spec` 커밋, [change-plan.md](change-plan.md)) |

### 에이전트가 규칙을 어겼을 때

예: 사람의 변경이 에이전트 커밋에 들어갔다, 에이전트가 사람 전용 상태를 바꿨다. `lg verify`(게이트 커밋 때 `lg commit`이 자동으로 보여 준다)가 찾는 위반이 여기에 해당한다.

1. 해당 커밋을 `git revert`한다.
2. 사람의 변경이었다면 다시 사람 신원으로 커밋한다(`lg commit`).
3. 원인을 에이전트에게 알리고, 같은 일이 반복되면 규칙 문서를 고치거나 labgate에 이슈를 남긴다.

### 긴급할 때 hook 우회

```bash
git commit --no-verify …
```

사람만, 긴급할 때만 쓴다. 다음 커밋 본문에 우회한 이유를 남긴다. 에이전트는 쓸 수 없다(`scripts/agent-commit`이 거부한다).

## 확인

```bash
git log --format='%h %an | %s' -5
git status --short
ls .lg/pending/
```

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `git revert`가 충돌 | 뒤에 같은 부분을 고친 커밋이 있다. 충돌을 풀고 `git revert --continue` |
| 이력을 고치고 싶다(오타 등) | 고치지 않는다. 새 커밋으로 바로잡는다 |
