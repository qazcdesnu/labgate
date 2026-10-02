---
id: gate-conversation
type: procedure
spec_version: 2
---
# 대화 경로 판정

- 시작 조건: 사람이 게이트 판정, 결정 확정, 에스컬레이션 응답을 대화로 전했을 때.
- 푸는 일반 규칙: 6번 — review 문서의 `## 응답` 작성, 사람이 말한 범위의 카드·결정 상태 변경(사람 커밋에 들어갈 변경으로만), `lg draft`가 `.lg/pending/`에 초안을 쓰는 것.
- 끝나는 상태: 사람 커밋 대기 상태 (변경이 stage되고 초안이 있다).

## 단계

1. 이번 세션에 자기가 바꾼 파일이 있으면 먼저 `scripts/agent-commit`으로 커밋한다(경로 지정).
2. 사람의 발언을 그대로 반영해 review 문서의 `## 응답`을 쓰고 frontmatter `verdict`, `source: conversation`, `status: answered`, `answered`를 채운다. 사람이 말하지 않은 내용을 더하지 않는다.
3. 사람이 말한 범위에서 카드·결정 상태를 바꾼다 ([workflow.md](../workflow.md) §6.4).
4. 바꾼 파일 경로를 붙여 초안을 만든다.
   - 게이트: `lg draft --type gate --summary "<verdict>, next <Next>" --trailer Task=<Task> --trailer Verdict=<verdict> --trailer Source=conversation [--trailer Next=<Task|none>] [--trailer Milestone-Verdict=<go|nogo|conditional>] <경로…>`
   - 결정 확정: `lg draft --type decide --summary "<요약>" --trailer Decisions=<D-ID,…> --trailer Source=conversation <경로…>`
   - 에스컬레이션 응답: `lg draft --type respond --summary "<요약>" --trailer Task=<Task> --trailer Source=conversation <경로…>`
5. 사람에게 `git diff --cached` 확인과 터미널에서 `lg commit` 실행을 요청하고 멈춘다. 내용이 다르면 사람이 `lg commit`의 편집 단계에서 고친다. 게이트 승인이면 `lg commit`이 tag를 만든다.
6. 사람이 커밋했다고 알리면 절차 [gate-apply](gate-apply.md).

## 멈추는 경우

- 판정이 모호하면(verdict나 다음 task가 분명하지 않으면) 초안을 만들기 전에 묻는다.
- `lg`가 설치되어 있지 않으면 4단계 대신 바꾼 파일을 경로로 stage하고, 같은 내용의 메시지를 `.lg/pending/COMMIT_MSG`에 직접 쓴다(`Actor: human` 포함). 사람에게 `git commit -F .lg/pending/COMMIT_MSG && rm .lg/pending/COMMIT_MSG` 실행과, 승인이면 `git tag gate/<Task>`를 요청한다.
