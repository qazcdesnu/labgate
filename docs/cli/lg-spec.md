# lg spec

사양 문서를 다룬다. 지금은 `adopt` 하나다: 에이전트가 `notes/`에 쓴 사양 초안을 stub 사양에 합치고, 사람의 `spec` 커밋으로 확정한다.

- 누가: 사람만. 표준 입력과 출력이 모두 터미널일 때만 동작한다. 규칙 문서는 사람만 고치므로(G7) 에이전트는 실행할 수 없다(Claude Code deny).
- 언제: 에이전트가 stub 사양의 보완 초안을 제안했을 때 (예: `notes/spec-drafts/catalog.md`)
- 전제: labgate 0.2 이상으로 만든 프로젝트. 초안은 사양의 번호 붙은 절(`## 3. Frontmatter` …)로 쓰여 있다

## 형식

```
lg spec adopt DRAFT... [--name NAME]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `DRAFT` | 초안 파일 경로 (여러 개) | 없음 (필수) | 합칠 초안. 현재 폴더 기준 |
| `--name` | stub 사양 이름 (예: `catalog`) | 초안 frontmatter의 `id`, 없으면 파일 이름(`catalog.md`, `catalog.spec.md`) | 합칠 사양. 초안이 하나일 때만 쓴다 |

## 동작

1. **확인.** 다음 중 하나라도 걸리면 아무것도 바꾸지 않고 멈춘다.
   - 초안의 이름이 stub 사양 11종 중 하나가 아니다.
   - 초안에 번호 없는 절(`## 메모`)이 있다: 옮길 곳을 알 수 없다.
   - 초안에 사양에 없는 번호의 절이 있다.
   - 합친 뒤에도 비어 있는(`> TODO`) 절이 남는다: 초안에 그 절을 채운 뒤 다시 한다.
   - 사람 커밋 대기 상태다.
   - 대상 사양이나 `specs/README.md`에 커밋되지 않은 변경이 있다.
   - 다른 stage된 변경이 있다.
2. **합치기.**
   - 대상 `specs/doc-types/<이름>.spec.md`의 절 가운데 초안에 있는 번호의 절만 초안 내용으로 바꾼다. 나머지 절(보통 §1 목적, §2 위치)과 frontmatter는 그대로 둔다.
   - `status: stub` → `complete`로 바꾸고, 제목의 `(stub)`과 stub 안내 문단을 지운다.
   - `specs/README.md` 사양 표에서 그 행의 상태도 `complete`로 바꾼다.
   - 이미 `complete`인 사양에도 쓸 수 있다(개정).
3. **보여 주기.** 파일마다 지금 → 확정의 차이(unified diff)와 커밋 메시지를 보여 주고 고른다: 커밋 / 취소.
4. **커밋.** 대상 사양들과 `specs/README.md`만 stage해서 커밋한다.
   - 메시지: `spec: adopt <이름…> spec(s)`. 72자를 넘으면 `spec: adopt <n> doc-type specs`.
   - 본문: `초안: <경로…>`, trailer: `Actor: human`.
   - 초안 파일은 지우지 않는다.

확정 전에 정할 것이 초안에 적혀 있으면(예: `notes/spec-drafts/README.md`의 "확정 전에 판단이 필요한 점") 먼저 초안을 고치거나 에이전트에게 고치게 한 뒤 실행한다.

자세한 사양: 설계 문서 §24.8.

## 읽고 쓰는 것

- 읽는 것: 초안, `specs/doc-types/`, `specs/README.md`, `.lg/identities.json`, `.lg/hooks/commit-msg`
- 쓰는 것: 대상 사양, `specs/README.md`, 사람 신원의 `spec` 커밋

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 커밋함 |
| 1 | 예기치 못한 오류 |
| 2 | 터미널이 아님, 등록되지 않은 사람 신원, labgate 프로젝트가 아님, 초안 없음·이름 모름·번호 없는 절·없는 절·TODO가 남음, `--name`을 여러 초안에 씀, stage된 다른 변경 |
| 3 | 사람 커밋 대기 상태, 대상에 커밋되지 않은 변경 |
| 4 | Git 오류 (hook 거부 포함) |
| 130 | 취소, 중단(Ctrl-C) |

## 예

```bash
lg spec adopt notes/spec-drafts/catalog.md notes/spec-drafts/decision.md
lg spec adopt notes/spec-drafts/*.md          # README.md처럼 사양이 아닌 파일은 빼고
lg spec adopt notes/catalog-v2.md --name catalog
```

## 관련

- 에이전트가 초안을 쓰는 규칙: 생성된 `specs/conventions.md` §8
- [로드맵·마일스톤·사양을 바꾼다](../guide/change-plan.md)
