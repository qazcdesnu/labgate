# lg status

사람이 할 일, 에이전트 몫, 진행 상황을 프로젝트의 파일과 커밋 이력에서 모아 보여 준다. **읽기만 한다.**

- 누가: 사람, 에이전트 모두 (읽기만 하므로 막지 않는다)
- 언제: 터미널 A에서 지금 무엇을 판단해야 하는지 볼 때, 에이전트 세션이 끝난 뒤, 다른 컴퓨터에서 이어서 일할 때
- 전제: labgate 0.2 이상으로 만든 프로젝트(spec_version 2 이상) 안

## 형식

```
lg status [--json]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `--json` | — | 꺼짐 | 같은 내용을 JSON으로 출력한다 (다른 도구가 읽을 때) |

## 보여 주는 것

| 묶음 | 항목 | 출처 | 안내 |
|---|---|---|---|
| 사람이 할 일 | 열린 게이트 요청·에스컬레이션 (`status: open`) | `reviews/open/*.md`의 frontmatter | `lg answer <ID>` |
| | 요청서에 응답을 쓰는 중 (커밋되지 않은 변경이 있음) | `git status` | `lg commit` |
| | 사람 커밋 대기 (초안) | `.lg/pending/COMMIT_MSG` | `lg commit` |
| | 커밋되지 않은 내 변경 | `.lg/pending/HUMAN_FILES` (세션 시작 때 `session-check`가 기록) | `lg commit` |
| 에이전트 몫 | 반영되지 않은 사람 커밋 | 프로젝트의 `scripts/apply-human-commits --check` | 다음 세션에서 자동 |
| | 반영했지만 커밋 전 | `scripts/apply-human-commits --tidy` | 다음 세션에서 자동 |
| 진행 | 현재 마일스톤(active인 첫 마일스톤, 없으면 planned인 첫 마일스톤)과 그 task의 상태별 목록, proposed·discussing 결정 | frontmatter | — |

- `STATUS.md`는 읽지 않는다. `STATUS.md`는 에이전트가 쓰는 서술이고, `lg status`는 사실만 모은다.
- `HUMAN_FILES`가 없으면 커밋되지 않은 변경의 수만 "진행"에 적는다. 누구의 변경인지는 세션 시작 때 `session-check`가 기록한다.
- 사람이 할 일이 없고 에이전트 몫만 있으면 "에이전트 세션을 시작하면 이어서 진행합니다"로 끝난다.
- spec_version 2 프로젝트에는 `scripts/apply-human-commits`가 없어 에이전트 몫은 알 수 없다고 적는다.

자세한 사양: 설계 문서 §24.3.

## 읽고 쓰는 것

- 읽는 것: 계획·결정·review 문서의 frontmatter, `.lg/pending/`, `git status`, 프로젝트의 `scripts/apply-human-commits`(`--check`, `--tidy`)
- 쓰는 것: 없음

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 출력함 |
| 1 | 예기치 못한 오류 |
| 2 | labgate 프로젝트가 아님, 지원하지 않는 spec_version |
| 4 | Git 오류 |
| 130 | 중단(Ctrl-C) |

## 예

```
$ lg status
ssm-latent-reasoning · spec_version 5 · M0 (planned)

사람이 할 일 1건
  [gate]   M0-T0_gate-01  M0-T0 착수 계획 · 10-03 요청  → lg answer M0-T0_gate-01

에이전트 몫: 없음

진행
  in-review   M0-T0
  draft       M0-T1 … M0-T5 (5)
  결정        proposed·discussing 5 (D0.1 D1.1 D2.1 D2.2 D3.1)
```

## 관련

- 열린 요청에 응답하기: [lg answer](lg-answer.md)
- [에이전트와 하루 작업하기](../guide/daily-loop.md)
