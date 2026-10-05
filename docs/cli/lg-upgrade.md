# lg upgrade

이전 spec_version으로 만든 프로젝트를 현재 labgate의 spec_version으로 올린다: 관리 문서(규칙·절차·도구) 교체, 모든 문서의 `spec_version` 갱신, `.gitignore` 관리 구역, 갱신 기록. **커밋하지 않는다.**

- 누가: 사람. 에이전트는 실행하지 않는다(규칙 파일 수정 금지, `.claude/settings.json`이 막는다).
- 언제: labgate를 새 마이너 버전으로 업데이트한 뒤, 프로젝트의 규칙도 새 버전으로 올릴 때
- 전제: labgate 프로젝트 안. 작업 트리가 깨끗하고, 사람 커밋 대기(`.lg/pending/COMMIT_MSG`)나 반영 커밋 대기(`.lg/pending/APPLY_MSG`)가 없다. 반영이 이미 커밋됐는데 기록만 남았으면(다음 세션 전) `scripts/apply-human-commits --tidy`로 정리하고 진행한다. 출발 spec_version이 릴리즈된 버전이다(dev 버전으로 만든 프로젝트는 지원하지 않음).

## 형식

```
lg upgrade [--dry-run] [--diff] [--force]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `--dry-run` | — | 꺼짐 | 바꿀 것만 보여 주고 아무것도 쓰지 않는다 |
| `--diff` | — | 꺼짐 | 릴리즈된 버전과 다른 문서마다 지금 파일 → 새 버전의 차이(unified diff)를 보여 준다. 아무것도 쓰지 않는다 |
| `--force` | — | 꺼짐 | 릴리즈된 버전과 다른 관리 문서도 새 버전으로 덮어쓴다. 원래 내용은 `.lg/pending/upgrade/<경로>`에 남고, 목록이 갱신 기록의 `forced`에 들어간다 |

## 동작

**사람이 항상 우선이다.** 사람의 수정을 발견하면 지우지 않고 알린다.

| 파일 | 그 버전 그대로 | 릴리즈된 그 버전과 다름 |
|---|---|---|
| 관리 문서: `AGENTS.md`, `CLAUDE.md`, `.claude/`, `specs/`의 완성 사양·절차·양식, `scripts/`, `.lg/hooks/` | 새 버전으로 교체 | **갱신 실패** (아무것도 바꾸지 않음). `--force`면 덮어씀 |
| 사람이 채우는 관리 문서: stub 사양 11종, `specs/README.md` | 새 버전으로 교체 | 내용 유지, `spec_version`만 갱신 (`--force`로도 덮어쓰지 않음) |
| `.gitignore` | `# labgate:begin` ~ `# labgate:end` 구역만 새 버전으로 | 사람이 지운 labgate 줄은 다시 넣지 않고, 사람이 더한 줄은 구역 밖에 둔다 |
| 연구 문서 (`plan/`, `decisions/`, `references/`, `STATUS.md`, `FILEMAP.md`, …) | frontmatter `spec_version`만 갱신 | 같음 |

- "그 버전 그대로"인지는 labgate에 들어 있는 버전별 해시표로 판별한다. 도구는 **릴리즈된 파일과 다르다**는 것만 알 수 있고, 누가 왜 바꿨는지는 모른다(사람이 고쳤을 수도, 릴리즈 전 버전을 복사했을 수도 있다). 다른 문서 옆에는 지금 파일 → 새 버전의 줄 수를 보여 주고, `--diff`로 차이를 볼 수 있다. `AGENTS.md`의 프로젝트 정보 줄(이름, 연구 질문, 에이전트 신원)은 비교에서 빼고, 교체할 때도 지금 줄을 그대로 옮긴다.
- 문서의 `spec_version`은 정확히 `spec_version: <정수>` 한 줄이어야 바꾼다. 형식이 다르면 그대로 두고 알린다. 현재보다 큰 값이 있으면 오류다.
- labgate가 만드는 `FILEMAP.md`의 구조(폴더 표 등)가 바뀌었으면 반영할 줄을 알려 준다.
- 실행 권한은 생성 규칙대로 맞춘다.

자세한 사양: 설계 문서 §22.

## 읽고 쓰는 것

- 읽는 것: `.lg/project.yaml`(설정과 버전), Git이 추적하는 파일
- 쓰는 것: 관리 문서, 문서의 `spec_version` 줄, `.gitignore`, `.lg/project.yaml`(`generated.spec_version`, `upgrades`), `--force`면 `.lg/pending/upgrade/`

`.lg/project.yaml`에 남는 갱신 기록:

```yaml
upgrades:
- from: 3
  to: 4
  labgate_version: 0.4.0
  date: '2026-10-04'
  forced:
  - specs/conventions.md
```

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 갱신함, 이미 최신, `--dry-run` |
| 1 | 예기치 못한 오류 |
| 2 | labgate 프로젝트가 아님, 올릴 수 없는 spec_version, 해시표 없음(dev 버전으로 만든 프로젝트), 작업 트리가 깨끗하지 않음, 대기 상태, 현재보다 큰 문서 spec_version |
| 3 | 릴리즈된 버전과 다른 관리 문서가 있음. 아무것도 바꾸지 않았다 (`--diff`로 보고 `--force`로 해결) |
| 4 | Git 오류 |
| 130 | 중단(Ctrl-C) |

## 예

```bash
lg upgrade --dry-run       # 무엇이 바뀌는지 먼저
lg upgrade                 # 갱신 (릴리즈된 버전과 다른 관리 문서가 있으면 멈춤)
lg upgrade --diff          # 다른 문서의 차이 보기
lg upgrade --force         # 다른 관리 문서도 덮어씀
git diff                   # 확인
git add -A && lg commit    # 타입 spec 으로 확정
```

## 관련 작업

- [labgate 업데이트하기](../guide/upgrade.md)
