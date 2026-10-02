# lg draft

사람 커밋의 초안을 준비한다: 변경을 stage하고 메시지를 `.lg/pending/COMMIT_MSG`에 쓴다. **커밋하지 않는다.** 확정은 사람이 [lg commit](lg-commit.md)으로 한다.

- 누가: 주로 에이전트. 사람도 쓸 수 있다.
- 언제: 사람의 변경을 사람 신원으로 커밋할 수 있게 준비할 때(절차 `commit-prep`), 사람이 대화로 내린 판정·결정·응답을 커밋 초안으로 만들 때(절차 `gate-conversation`).
- 전제: labgate 0.2 이상으로 만든 프로젝트(spec_version 2) 안. 터미널이나 신원은 확인하지 않는다(커밋하지 않으므로).

## 형식

```
lg draft --type TYPE --summary TEXT [--scope SCOPE] [--body TEXT] [--trailer KEY=VALUE ...] [PATH ...]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `PATH` | 경로, 여러 개 | `.lg/pending/HUMAN_FILES`의 경로 | stage할 경로. 현재 폴더 기준. 폴더를 주면 그 아래 변경 전부 |
| `--type` | 타입 | 필수 | 사람이 쓸 수 있는 타입: `gate`, `decide`, `plan`, `spec`, `respond`, `exp`, `run`, `result`, `ref`, `log`, `chore` |
| `--summary` | 문자열 | 필수 | 헤더의 요약 한 줄 |
| `--scope` | 문자열 | `Task` trailer의 값 | 헤더의 scope |
| `--body` | 문자열 | 없음 | 본문(무엇을 왜) |
| `--trailer` | `KEY=VALUE` | 없음 | trailer. 여러 번 쓴다. `Actor`는 지정할 수 없다(항상 `Actor: human`) |

**경로를 생략하면** 세션 시작 때 `scripts/session-check`가 기록한 사람의 변경(`.lg/pending/HUMAN_FILES`) 중 아직 커밋되지 않은 경로만 stage한다. 커밋되지 않은 모든 변경을 stage하는 형태는 없다. 세션 도중에 쓰면 에이전트의 변경까지 사람 커밋에 섞이기 때문이다.

## 동작

1. 프로젝트를 확인한다 (`lg commit`과 같다).
2. 초안이 이미 있으면(사람 커밋 대기 상태) 멈춘다.
3. 메시지를 만들고 검사한다: 사람이 쓸 수 있는 타입인지, 그리고 프로젝트 hook의 커밋 규약(필수 trailer, 형식, 헤더 길이). 오류는 모두 모아 출력한다. **여기까지는 아무것도 바꾸지 않는다.**
4. 대상 경로 밖에 이미 stage된 변경이 있으면 멈춘다. 에이전트의 변경이 사람 커밋에 섞이지 않게 하기 위해서다.
5. 대상 경로를 stage한다(`git add -A -- <경로>`, 삭제 포함).
6. `.lg/pending/COMMIT_MSG`에 메시지를 쓴다. 이제 사람 커밋 대기 상태다.

자세한 사양: 설계 문서 §19.

## 읽고 쓰는 것

- 읽는 것: `.lg/project.yaml`, `.lg/hooks/commit-msg`, `.lg/pending/HUMAN_FILES`
- 쓰는 것: stage, `.lg/pending/COMMIT_MSG`

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 초안을 준비함 |
| 1 | 예기치 못한 오류 |
| 2 | 커밋 규약에 맞지 않음, 경로를 생략했는데 `HUMAN_FILES`가 없음, 대상 밖에 stage된 변경이 있음, 저장소 밖의 경로, labgate 프로젝트가 아님, 지원하지 않는 spec_version |
| 3 | 이미 사람 커밋 대기 상태, `HUMAN_FILES`의 경로에 남은 변경이 없음, stage된 변경이 없음 |
| 4 | Git 오류 (없는 경로를 stage하려는 경우 등) |
| 130 | 중단(Ctrl-C) |

## 예

```bash
# 세션 시작 때 감지된 사람의 변경으로 초안 (경로 생략)
lg draft --type exp --summary "fix data loader padding" --body "사람이 직접 수정"

# 사람이 세션 도중 알려 준 파일만
lg draft --type result --summary "add ablation table" --trailer Task=M1-T2 results/M1/M1-T2_result.md

# 대화로 내린 게이트 판정
lg draft --type gate --summary "approve, next M1-T1" \
  --trailer Task=M1-T0 --trailer Verdict=approve --trailer Source=conversation \
  --trailer Next=M1-T1 reviews/open/M1-T0_gate-01.md plan/milestones/M1

# 대화로 내린 결정 확정
lg draft --type decide --summary "use Mamba-2 as default core" \
  --trailer Decisions=D0.2 --trailer Source=conversation decisions/D0.2_ssm-core.md
```

`Task` trailer가 있으면 scope는 자동으로 그 Task가 된다(`result(M1-T2): …`).

## 관련 절차

- `specs/procedures/commit-prep.md`: 사람의 변경 커밋 준비
- `specs/procedures/gate-conversation.md`: 대화 경로의 판정·결정·응답
- 확정: [lg commit](lg-commit.md)
