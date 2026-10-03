# lg verify

에이전트의 작업이 규칙을 지켰는지 커밋 이력과 문서로 사후에 확인한다. **읽기만 한다.**

- 누가: 사람, 에이전트 모두 (읽기만 하므로 막지 않는다)
- 언제: 게이트를 판정하기 전(`lg commit`이 `gate` 커밋에서 자동으로 요약을 보여 준다), 에이전트가 게이트 요청을 내기 전, 다른 컴퓨터에서 작업한 뒤
- 전제: labgate 0.2 이상으로 만든 프로젝트(spec_version 2 이상) 안

## 형식

```
lg verify [--task TASK | --since REV | --all]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `--task` | Task ID | 없음 | 그 task에 관련된 커밋만 검사하고 점검표를 붙인다 |
| `--since` | 커밋 | 없음 | 그 커밋 이후만 검사한다 |
| `--all` | — | 꺼짐 | 처음부터 검사한다 |

아무것도 주지 않으면 마지막 게이트 tag(`gate/*`) 이후를 검사한다. tag가 없으면 처음부터다. 세 옵션은 하나만 쓴다.

`--task`의 관련 커밋: `Task` trailer나 scope가 그 Task인 커밋, `Approve`·`Next`에 그 Task가 있는 커밋, 그 task 카드를 바꾼 커밋(`init`, `spec` 커밋 제외), 그 커밋들을 `Applies`·`Refs`로 가리키는 반영 커밋.

## 검사

| | 무엇을 | 위반 |
|---|---|---|
| V1 | 신원과 타입 (P2, P3, P4) | 등록되지 않은 작성자, 커밋 규약 위반(hook과 같은 검사), 작성자 신원과 `Actor`가 다름, 에이전트 신원의 병합. hook을 우회했거나 hook이 없던 컴퓨터에서 만든 커밋도 잡는다 |
| V2 | 사람 몫의 상태 전이 (G4) | 에이전트 커밋이 task `draft →`, `in-review → closed/revise/redirected`, 결정 `→ confirmed`, 마일스톤 `planned → active`, `active → closed`를 했는데, `Applies`(또는 v0.2 방식의 `Refs`)가 가리키는 사람 커밋이 그 전이를 정하지 않음 |
| V3 | review 응답 (G5) | 에이전트 커밋이 `reviews/` 문서의 `## 응답`을 바꿈 (이름 바꾸기는 따라가서 비교) |
| V4 | 규칙 파일 (G7) | 에이전트 커밋이 `specs/`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.lg/`를 바꿈. 카드의 "범위 › 포함"이 허용했을 수 있으므로 그 원문을 함께 보여 준다 (판정은 사람이) |
| V5 | 문서 형식 (지금 상태) | frontmatter를 읽을 수 없음, `spec_version` 형식·값, 모르는 `type`, 상태값 어휘 밖, 완성 사양(`task-card`, `review`)의 필수 필드 없음, `id`와 파일 이름이 다름 |

- 검사 기준은 그 프로젝트의 파일에서 읽는다: `.lg/hooks/commit-msg`(커밋 규약), `.lg/identities.json`, `specs/conventions.md`(type·상태값 표), `specs/doc-types/task-card.spec.md`·`review.spec.md`(필수 필드). 그래서 그 프로젝트를 만든 버전의 규칙으로 검사한다.
- `specs/templates/`의 양식 문서는 V5에서 뺀다.
- 갱신 전 문서(문서 spec_version < 프로젝트)는 위반이 아니라 알림이다.
- 반영 누락(P1)은 검사하지 않는다. 세션 시작 때 `scripts/session-check`가 알린다.

**`--task`의 점검표 (판정하지 않음):** 카드 `## 완료 기준`의 체크 수, 가장 최근 게이트 요청서의 "완료 기준 점검" 표에 적힌 근거 경로 중 저장소에 없는 것, 범위의 커밋이 바꾼 파일. 충족 여부는 사람이 게이트에서 판정한다.

자세한 사양: 설계 문서 §23.

## 읽고 쓰는 것

- 읽는 것: 커밋 이력, Git이 추적하는 `.md`, 위의 규칙 파일
- 쓰는 것: 없음

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 위반 없음 (알림은 있을 수 있음) |
| 1 | 예기치 못한 오류 |
| 2 | labgate 프로젝트가 아님, 지원하지 않는 spec_version, 옵션 오류(둘 이상, 없는 커밋, Task 형식) |
| 3 | 위반 있음 |
| 4 | Git 오류 |
| 130 | 중단(Ctrl-C) |

## 예

```bash
lg verify                       # 마지막 게이트 이후
lg verify --task M1-T2          # 그 task의 커밋 + 점검표 (게이트 판정 전에)
lg verify --all                 # 처음부터 (다른 컴퓨터에서 작업한 뒤 등)
```

```
lg verify: task M1-T2, 커밋 6개

✓ V1 신원과 타입 (P2, P3, P4)
✗ V2 사람 몫의 상태 전이 (G4)  1건
    3f2a1c9 task(M1-T2): start
      plan/milestones/M1/tasks/M1-T2.md: status draft → in-progress, 근거(Applies) 없음
✓ V3 review 응답 (G5)
✓ V4 규칙 파일 (G7)
✓ V5 문서 형식

점검표 (판정하지 않음)
  - 완료 기준: 5/5 체크
  - 게이트 요청서 reviews/open/M1-T2_gate-01.md: 근거 경로 모두 있음
  - 바뀐 파일 9개: …

위반 1건.
```

## 관련

- `lg commit`이 `gate` 커밋을 확인할 때 같은 검사를 `--task`로 돌려 요약을 보여 준다 ([lg commit](lg-commit.md)). 막지는 않는다.
- 위반을 찾았을 때: [잘못된 것을 바로잡기](../guide/mistakes.md)
