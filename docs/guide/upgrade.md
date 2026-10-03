# labgate 업데이트하기

- 언제: 새 버전이 나왔을 때, 프로젝트가 요구하는 기능이 설치된 `lg`에 없을 때
- 결과: 새 `lg`. 필요하면 프로젝트의 규칙 문서도 갱신

## 버전 두 가지

| 무엇 | 어디서 보나 | 바뀌는 때 |
|---|---|---|
| labgate 버전 (`lg`) | `lg --version` | 설치·업데이트할 때 |
| 프로젝트의 spec_version | `.lg/project.yaml`의 `spec_version`, 생성된 `README.md` 맨 아래 | `lg init`으로 만들 때 정해진다. 자동으로 바뀌지 않는다 |

| 프로젝트 spec_version | 만든 버전 | `lg commit`, `lg draft` |
|---|---|---|
| 1 | labgate 0.1.x | 쓸 수 없다. `git commit`으로 커밋한다 |
| 2 | labgate 0.2.x | 쓸 수 있다 (사람 커밋 반영 도구 없음) |
| 3 | labgate 0.3.x | 쓸 수 있다. 규칙 우선순위, 특별 규칙, `scripts/apply-human-commits` |

## 순서

### `lg` 업데이트 (어느 터미널이든)

```bash
pipx install --force git+https://github.com/qazcdesnu/labgate.git@v0.3.0
lg --version
```

버전 목록과 바뀐 점은 [Releases](https://github.com/qazcdesnu/labgate/releases)에 있다. 개발 중인 기능을 미리 쓰려면 `@dev`(설치한 시점의 `dev`로 고정된다).

`lg`를 업데이트해도 이미 만든 프로젝트의 파일(규칙 문서, 스크립트, hook)은 바뀌지 않는다.

### 이전 버전으로 만든 프로젝트

자동 갱신 명령(`lg upgrade`)은 아직 없다. 두 가지 중 고른다.

1. **그대로 쓴다.** 프로젝트는 만든 버전의 규칙대로 계속 동작한다. spec_version 1 프로젝트는 `git commit`으로 커밋한다.
2. **규칙 문서를 수동으로 갱신한다.** 같은 설정으로 새 버전의 프로젝트를 임시 폴더에 만들고, 바뀐 파일을 옮겨 `spec` 커밋으로 확정한다.
   ```bash
   lg init /tmp/fresh --config <원래 설정 파일> --no-git
   diff -r /tmp/fresh/specs specs; diff /tmp/fresh/AGENTS.md AGENTS.md   # 무엇이 바뀌었는지
   ```
   옮길 대상은 규칙과 도구다(실행 권한을 지키도록 `cp -p`로 `/tmp/fresh`에서 복사한다): `AGENTS.md`, `CLAUDE.md`, `.claude/`, `specs/`(사양·절차), `scripts/`, `.lg/hooks/`, 그리고 `.lg/project.yaml`의 `spec_version`. 연구 내용(`plan/`, `decisions/`, `references/`, `results/` 등)은 옮기지 않는다. 버전마다 필요한 작업은 릴리즈 노트에 적는다.

   **연구 문서의 `spec_version`도 같은 커밋에서 올린다.** 문서 frontmatter의 `spec_version`은 그 문서가 따르는 사양 버전이다. 연구 문서는 내용은 그대로 두고 이 값만 바꾼다. 에이전트는 이 값을 바꾸지 않으므로 사람이 일괄로 한다.
   ```bash
   git grep -l '^spec_version: 2$' -- '*.md' | xargs sed -i 's/^spec_version: 2$/spec_version: 3/'
   sed -i 's/^  spec_version: 2$/  spec_version: 3/' .lg/project.yaml
   git grep -n '^spec_version: 2$' -- '*.md'        # 아무것도 안 나와야 함
   ```
   초기화 기록(`.lg/project.yaml`의 `labgate_version`·`created`, 생성된 `README.md` 맨 아래 줄)은 그대로 둔다.

   spec_version 2 → 3에서 바뀌는 파일: `AGENTS.md`, `specs/workflow.md`, `specs/git-commit.md`, `specs/procedures/*.md`, 사양 문서들의 `spec_version`, `scripts/session-check`, 새 `scripts/apply-human-commits`, `.lg/hooks/commit-msg`(`Applies` 검사). 갱신하기 전의 사람 커밋은 이미 반영된 상태면 도구가 건너뛰고 `Applies`만 남기므로 그대로 둬도 된다.

## 확인

```bash
lg --version
grep spec_version .lg/project.yaml
lg commit --help        # 프로젝트 안에서 실행해도 아무것도 바꾸지 않는다
```

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `labgate 0.1로 만든 프로젝트입니다 (spec_version 1)` | 위 "이전 버전으로 만든 프로젝트" |
| `이 labgate가 모르는 spec_version` | 프로젝트가 설치된 `lg`보다 새 버전으로 만들어졌다. `lg`를 업데이트한다 |
| 업데이트했는데 버전이 그대로 | `which lg`로 다른 설치(예: 가상환경)가 먼저 잡히는지 확인한다 |
