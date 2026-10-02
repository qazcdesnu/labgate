# 명령 설명서

labgate가 제공하는 명령과, 생성된 프로젝트에 들어 있는 스크립트의 설명서다. 무엇을 할지에서 출발하려면 사용자 작업 설명서(`docs/guide/`, 작성 예정)를 본다. 구현 사양은 [설계 문서](../../labgate-design.md)에 있다.

## 한눈에 보기

| 명령 | 누가 | 언제 | 바꾸는 것 | 설명서 |
|---|---|---|---|---|
| `lg init [PATH]` | 사람 | 프로젝트마다 한 번 | 파일 생성, Git 초기화, 사람 신원의 `init` 커밋 | [lg-init.md](lg-init.md) |
| `lg commit` | 사람 (터미널에서만) | 사람의 모든 커밋: task 승인, 게이트 판정, 결정, 직접 고친 것 | stage(작성 모드에서 고른 파일), 사람 신원 커밋, tag, `.lg/pending/` 정리 | [lg-commit.md](lg-commit.md) |
| `lg draft` | 에이전트 (사람도 가능) | 사람 커밋의 초안을 준비할 때 | stage, `.lg/pending/COMMIT_MSG` | [lg-draft.md](lg-draft.md) |
| `lg --version` | 누구나 | 설치된 버전 확인 | — | 아래 |
| `scripts/agent-commit` | 에이전트 | 에이전트의 모든 커밋 | 에이전트 신원 커밋 | [project-scripts.md](project-scripts.md#scriptsagent-commit) |
| `scripts/session-check` | 에이전트 (Claude Code는 hook이 자동 실행) | 세션 시작 | `.lg/pending/HUMAN_FILES` | [project-scripts.md](project-scripts.md#scriptssession-check) |
| `.lg/hooks/commit-msg` | Git이 자동 실행 | 모든 커밋 | — (검사만) | [project-scripts.md](project-scripts.md#lghookscommit-msg) |

`lg`는 labgate를 설치하면 생기는 명령이고, `scripts/`와 `.lg/hooks/`는 `lg init`이 프로젝트 안에 만드는 파일이다. 프로젝트 안의 스크립트는 Python 표준 라이브러리만 쓰므로 `lg` 없이도 동작한다.

## 사람과 에이전트의 경계

- 사람 신원의 커밋은 사람만 만든다. 그래서 `lg commit`은 표준 입력과 출력이 모두 터미널일 때만 커밋한다. 에이전트의 셸은 터미널이 아니므로, 에이전트는 `lg draft`로 초안까지만 준비하고 사람이 `lg commit`으로 확정한다.
- 에이전트의 커밋은 `scripts/agent-commit`으로만 한다. 이 스크립트는 작성자를 항상 에이전트 신원으로 고정한다.
- 어느 쪽 커밋이든 `.lg/hooks/commit-msg`가 커밋 규약과 작성자 신원을 검사한다. `lg` 없이 `git commit`으로 커밋해도 hook을 통과하면 유효하다.

## 공통 종료 코드

모든 `lg` 명령이 같은 체계를 쓴다. 명령마다 실제로 쓰는 코드는 각 설명서에 있다.

| 코드 | 의미 |
|---|---|
| 0 | 성공 |
| 1 | 예기치 못한 오류. `LG_DEBUG=1`로 다시 실행하면 traceback을 출력한다 |
| 2 | 사용법·설정·환경 오류 |
| 3 | 대상 문제 (폴더 충돌, 커밋할 것 없음, 사람 커밋 대기 상태) |
| 4 | Git 오류 (hook 거부 포함) |
| 130 | 사용자가 중단하거나 취소 |

## `lg --version`

```
lg --version
```

설치된 labgate 버전을 `labgate <버전>` 형식으로 출력한다. 생성된 프로젝트의 `README.md` 맨 아래에는 그 프로젝트를 만든 labgate 버전과 spec_version이 적혀 있다.
