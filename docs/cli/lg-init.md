# lg init

연구 또는 제안서 프로젝트의 작업 공간을 한 번에 만든다: 폴더 구조, 문서 사양, 에이전트 규칙, 커밋 규약 검사 hook, 사람 신원의 초기 커밋.

- 누가: 사람
- 언제: 프로젝트마다 한 번
- 전제: `git` (`--no-git`이면 불필요). 대상이 이미 Git 저장소 안이면 안 된다. 대화형 모드는 터미널에서만.

## 형식

```
lg init [PATH] [--config FILE] [--kind research|proposal] [--import DIR] [--force] [--dry-run] [--no-git] [--yes]
```

## 인자와 옵션

| 이름 | 값 | 기본값 | 설명 |
|---|---|---|---|
| `PATH` | 경로 | 생략하면 묻는다 | 만들 프로젝트 폴더. 없으면 만든다(상위 폴더 포함). `--config`를 쓰면 필수 |
| `--config` | 파일 | 없음 (대화형) | 설정 파일(YAML)로 모든 입력을 받는다. 질문하지 않는다. 형식은 아래 [설정 파일](#설정-파일) |
| `--kind` | `research` 또는 `proposal` | `research` (설정 파일의 `project.kind`) | 프로젝트 종류. 대화형이면 생략할 때 처음에 묻는다. 설정 파일이 다른 종류를 정했으면 오류 |
| `--import` | 폴더 | 없음 | 이미 가진 자료 폴더. 내용을 `notes/` 아래로 복사하고(같은 이름은 건너뜀, `.git*` 제외) stage해 둔다. init 커밋에는 넣지 않고, 첫 task 승인 커밋에 함께 들어간다. 프로젝트 폴더 안의 폴더나 빈 폴더는 안 된다 |
| `--force` | — | 꺼짐 | 비어 있지 않은 폴더에도 만든다. **기존 파일은 덮어쓰지 않는다.** 만들 파일과 같은 경로의 파일이 하나라도 있으면 실패한다. 원래 있던 파일은 초기 커밋에 넣지 않고 목록으로 알린다(정한 자리로 옮겨 커밋하거나 `.gitignore`에) |
| `--dry-run` | — | 꺼짐 | 만들 파일 트리와 개수만 출력하고 아무것도 쓰지 않는다. 폴더·Git 검사 실패는 오류 대신 경고로 출력한다 |
| `--no-git` | — | 꺼짐 | Git 초기화, hook 경로 설정, 초기 커밋을 하지 않는다 |
| `--yes`, `-y` | — | 꺼짐 | 대화형 모드의 마지막 확인을 건너뛴다 |

## 동작

1. 대상 경로를 정한다 (`PATH` 또는 첫 질문).
2. 다른 입력을 받기 **전에** 대상 폴더와 Git을 검사한다. 질문에 다 답한 뒤 실패하지 않도록 하기 위해서다.
3. 설정 파일을 읽거나 질문한다. 검증 오류는 모두 모아 한 번에 출력한다.
4. 만들 파일을 메모리에 모두 준비한 뒤 쓴다. 쓰는 도중 실패하면 만든 것을 지운다.
5. Git을 초기화한다: 기본 브랜치 `main`, 저장소 로컬 `user.name`·`user.email`을 첫 번째 사람으로, `core.hooksPath`를 `.lg/hooks`로, 그리고 사람 신원의 `init` 커밋. 이 커밋도 hook 검사를 통과한다.
6. 다음 단계를 안내한다.

자세한 사양: 설계 문서 §5, §6, §10.

## 대화형 질문

`--config` 없이 터미널에서 실행하면 차례로 묻는다. 답할 때마다 검증하고, 틀리면 이유를 보여 주고 다시 묻는다.

| 질문 | 기본값 |
|---|---|
| 프로젝트 경로 | `PATH`를 주면 묻지 않는다 |
| 프로젝트 이름 | — |
| slug | 경로의 마지막 이름에서 만든 값 |
| 한 줄 요약, 핵심 연구 질문 | — |
| 사람 이름, 이메일 | `git config --global user.name`, `user.email` |
| 사람을 더 추가할까요? | 아니요 |
| 에이전트 이름, 이메일 | `research-agent`, `agent@<slug>.local` |
| Claude Code를 사용합니까? | 예 |
| 마일스톤 제목 | 빈 입력이면 끝. 최소 1개, 최대 20개 |
| 이대로 만들까요? | 예 (`--yes`면 묻지 않음) |

## 설정 파일

```yaml
schema_version: 1
project:
  name: "SSM State as Latent Reasoning Memory"   # 1–100자
  slug: ssm-latent-reasoning                     # 영문 소문자·숫자·하이픈, 40자 이하
  summary: "한 줄 요약"                           # 1–200자
  research_question: "핵심 연구 질문"             # 1–500자. 제안서면 제안의 핵심 질문
  kind: research                                 # research(기본) 또는 proposal
people:
  humans:                                        # 1명 이상. 첫 번째 사람이 초기 커밋 작성자
    - name: "홍길동"
      email: "gildong@example.com"
  agent:                                         # 생략 가능
    name: "research-agent"
    email: "agent@ssm-latent-reasoning.local"
agent_tools:
  claude_code: true                              # 기본 true
milestones:                                      # 1–20개. ID(M0, M1 …)는 순서대로 붙는다
  - title: "문헌 검토와 연구 질문 확정"
  - title: "기준선 재현"
```

- 모든 문자열은 한 줄이어야 한다. 이메일은 소문자로 바뀌고, 사람끼리 겹치거나 에이전트 이메일이 사람과 같으면 안 된다.
- `milestones`에 `id`를 적으면 순서와 맞는지 검사한다.
- `kind: proposal`(제안서)이면 용어와 원고 폴더만 다르다: 연구 질문 → 제안 핵심 질문, 가설 → 제안 전략과 가정, 공통 실험 원칙 → 공통 작업 원칙, 문헌 → 자료, 마일스톤 판정의 뜻(go = 다음 단계로, 마지막이면 제출), `paper/` 대신 `deliverables/`. 규칙, 절차, 사양, 커밋 규약, `lg` 명령은 같다.
- 만든 프로젝트의 `.lg/project.yaml`에는 이 내용과 함께 만든 labgate 버전, spec_version, 날짜가 기록된다.

## 읽고 쓰는 것

- 쓰는 것: 프로젝트 폴더 아래 파일 전부. 개수는 Claude Code를 쓰면 `60 + 6N`, 쓰지 않으면 `52 + 6N`이다(N = 마일스톤 수).
- Git: `.git/` 생성, 저장소 로컬 설정 3개(`user.name`, `user.email`, `core.hooksPath`), 커밋 1개.
- 읽는 것: 설정 파일, (대화형이면) `git config --global user.name`, `user.email`.

## 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 성공 (`--dry-run` 포함) |
| 1 | 예기치 못한 오류 |
| 2 | 사용법·설정 검증 오류. 대화형인데 터미널이 아님 |
| 3 | 대상 폴더 문제: 폴더가 아님, 비어 있지 않음(`--force` 없이), 파일 충돌 |
| 4 | Git 오류: Git 없음, 이미 Git 저장소 안, 초기화·커밋 실패. 실패해도 만든 파일은 남기고 수동 복구 명령을 출력한다 |
| 130 | 사용자가 중단(Ctrl-C, Ctrl-D)하거나 확인에서 거부 |

## 예

```bash
# 설정 파일로 만들기
lg init ~/research/my-study --config my-study.yaml

# 무엇이 만들어지는지 먼저 보기
lg init ~/research/my-study --config my-study.yaml --dry-run

# 대화형으로 만들기
lg init

# 이미 자료가 있는 폴더에 만들기 (기존 파일은 그대로, 초기 커밋에 포함)
lg init ./existing-folder --config my-study.yaml --force
```

## 관련 절차

만든 뒤에는 첫 task(M0-T0)를 사람이 승인하고([lg commit](lg-commit.md)의 `--allow-empty`), 에이전트 세션을 시작한다(`specs/procedures/session-start.md`).
