# labgate 업데이트하기

- 언제: 새 버전이 나왔을 때, 프로젝트가 요구하는 기능이 설치된 `lg`에 없을 때
- 결과: 새 `lg`. 필요하면 프로젝트의 규칙 문서도 갱신

## 버전 두 가지

| 무엇 | 어디서 보나 | 바뀌는 때 |
|---|---|---|
| labgate 버전 (`lg`) | `lg --version` | 설치·업데이트할 때 |
| 프로젝트의 spec_version | `.lg/project.yaml`의 `spec_version`, 생성된 `README.md` 맨 아래 | `lg init`으로 만들 때 정해진다. 자동으로 바뀌지 않는다 |

| 프로젝트 spec_version | 만든 버전 | `lg commit`, `lg draft`, `lg status`, `lg answer` (`lg upgrade`로 5까지 올릴 수 있다) |
|---|---|---|
| 1 | labgate 0.1.x | 쓸 수 없다. `git commit`으로 커밋한다 |
| 2 | labgate 0.2.x | 쓸 수 있다 (사람 커밋 반영 도구 없음) |
| 3 | labgate 0.3.x | 쓸 수 있다. 규칙 우선순위, 특별 규칙, `scripts/apply-human-commits` |
| 4 | labgate 0.4.x | 쓸 수 있다. `lg upgrade`, `.gitignore` 관리 구역 |
| 5 | labgate 0.5.x | 쓸 수 있다. `lg answer`의 반영 미리보기(`apply-human-commits --preview`), 게이트 요청 전 카드 체크와 `lg verify`, 에이전트 보고의 `lg answer` 안내 |

## 순서

### `lg` 업데이트 (어느 터미널이든)

```bash
pipx install --force git+https://github.com/qazcdesnu/labgate.git@v0.5.0
lg --version
```

버전 목록과 바뀐 점은 [Releases](https://github.com/qazcdesnu/labgate/releases)에 있다. 개발 중인 기능을 미리 쓰려면 `@dev`(설치한 시점의 `dev`로 고정된다).

`lg`를 업데이트해도 이미 만든 프로젝트의 파일(규칙 문서, 스크립트, hook)은 바뀌지 않는다.

### 이전 버전으로 만든 프로젝트: `lg upgrade` (터미널 A)

프로젝트 폴더에서 에이전트 세션을 모두 종료한 뒤 실행한다. 세션이 열려 있으면 에이전트가 읽은 규칙과 파일이 달라진다.

1. 무엇이 바뀌는지 본다.
   ```bash
   lg upgrade --dry-run
   ```
2. 갱신한다.
   ```bash
   lg upgrade
   ```
   - 릴리즈된 버전과 다른 관리 문서(규칙·절차·도구)가 있으면 **아무것도 바꾸지 않고** 멈춘다(코드 3). 도구는 누가 왜 바꿨는지 모르므로, `lg upgrade --diff`로 차이를 보고 정한다.
     - 의도한 수정이 아니면 `lg upgrade --force`.
     - 의도한 수정이면 `--force`로 갱신한 뒤, `.lg/pending/upgrade/<경로>`에 남은 원래 내용을 보고 다시 합친다.
   - 사람이 채운 stub 사양, `.gitignore`에 더한 줄, 지운 labgate 줄은 그대로 두고 알려 준다.
3. 확인하고 커밋한다.
   ```bash
   git diff
   git add -A
   lg commit          # 타입 spec, 요약 예: upgrade to spec_version 5
   ```
4. 에이전트 세션을 새로 연다.

마음에 들지 않으면 커밋하기 전에 `git restore .`로 되돌릴 수 있다(`lg upgrade`는 커밋하지 않는다). 무엇을 어떻게 바꾸는지는 [lg upgrade](../cli/lg-upgrade.md).

### `lg` 없이 수동으로 갱신할 때

같은 설정으로 새 버전의 프로젝트를 임시 폴더에 만들고(`lg init /tmp/fresh --config <설정 파일> --no-git`), 관리 문서를 `cp -p`로 옮기고, 모든 문서의 `spec_version`을 올린 뒤 `spec` 커밋으로 확정한다. `lg upgrade`가 하는 일을 손으로 하는 것이라, 사람이 고친 문서를 덮어쓰지 않도록 직접 확인해야 한다.

```bash
git grep -l '^spec_version: 2$' -- '*.md' | xargs sed -i 's/^spec_version: 2$/spec_version: 3/'   # 숫자는 버전에 맞게
```

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
