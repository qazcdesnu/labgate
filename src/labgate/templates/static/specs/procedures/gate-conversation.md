---
id: gate-conversation
type: procedure
spec_version: 6
---
# 대화 경로 판정

- 시작 조건: 사람이 게이트 판정, 결정 확정, 에스컬레이션 응답을 대화로 전했을 때.
- 끝나는 상태: 사람 커밋 대기 상태 (review 문서가 stage되고 초안이 있다).

## 특별 규칙

이 절차를 수행하는 동안 아래가 일반 규칙보다 우선한다. 불변 원칙은 그대로다.

| 대신하는 일반 규칙 | 이 절차에서는 |
|---|---|
| G5 (review의 `## 응답`을 쓰지 않는다) | 사람의 발언을 그대로 `## 응답`에 옮기고 frontmatter `verdict`, `source: conversation`, `status: answered`, `answered`를 채운다. 사람이 말하지 않은 내용을 더하지 않는다 |

## 단계

1. 이번 세션에 자기가 바꾼 파일이 있으면 먼저 `scripts/agent-commit`으로 커밋한다(경로 지정).
2. review 문서의 `## 응답`을 쓴다(특별 규칙). 카드·결정·마일스톤의 상태는 바꾸지 않는다. 사람이 커밋한 뒤 절차 [gate-apply](gate-apply.md)가 반영한다.
3. review 문서 경로를 붙여 초안을 만든다. 사람이 말한 판정을 trailer로 옮긴다.
   - 게이트: `lg draft --type gate --summary "<verdict>, next <Next>" --trailer Task=<Task> --trailer Verdict=<verdict> --trailer Source=conversation [--trailer Next=<Task|none>] [--trailer Milestone-Verdict=<go|nogo|conditional>] [--trailer Decisions=<D-ID,…>] <review 경로>`
   - 결정 확정: `lg draft --type decide --summary "<요약>" --trailer Decisions=<D-ID,…> --trailer Source=conversation <review 경로 또는 결정 문서 경로>`
   - 에스컬레이션 응답: `lg draft --type respond --summary "<요약>" --trailer Task=<Task> --trailer Source=conversation <review 경로>`
4. 사람에게 터미널에서 `lg commit` 실행을 요청하고 멈춘다. 확인 화면이 옮겨 적은 응답, 반영 미리보기, 메시지를 보여 준다. 내용이 다르면 사람이 `lg commit`의 편집 단계에서 고친다. 게이트 승인이면 `lg commit`이 tag를 만든다.
5. 사람이 커밋했다고 알리면 절차 [gate-apply](gate-apply.md).

## 멈추는 경우

- 판정이 모호하면(verdict, 다음 task, 확정할 결정이 분명하지 않으면) 초안을 만들기 전에 묻는다.
- `lg`가 설치되어 있지 않으면 3단계 대신 review 문서를 경로로 stage하고, 같은 내용의 메시지를 `.lg/pending/COMMIT_MSG`에 직접 쓴다(`Actor: human` 포함). 사람에게 `git commit -F .lg/pending/COMMIT_MSG && rm .lg/pending/COMMIT_MSG` 실행과, 승인이면 `git tag gate/<Task>`를 요청한다.
