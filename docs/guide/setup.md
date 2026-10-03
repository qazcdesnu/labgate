# 설치하고 프로젝트 만들기

- 언제: labgate를 처음 쓸 때, 새 연구를 시작할 때, 다른 컴퓨터에서 프로젝트를 클론했을 때
- 결과: `lg` 명령, 초기 커밋이 있는 프로젝트, 터미널 두 개

## 순서

### 1. labgate 설치 (한 번)

Python 3.10 이상과 [pipx](https://pipx.pypa.io)가 필요하다.

```bash
pipx install git+https://github.com/qazcdesnu/labgate.git@v0.4.0
lg --version
```

### 2. 프로젝트 만들기 (연구마다 한 번, 터미널 A)

설정 파일을 쓰는 쪽을 권한다. 나중에 같은 설정으로 다시 만들거나 남에게 보여 주기 쉽다.

```bash
lg init ~/research/my-study --config my-study.yaml --dry-run   # 먼저 무엇이 생기는지 확인
lg init ~/research/my-study --config my-study.yaml
```

설정 파일 형식은 [lg init](../cli/lg-init.md#설정-파일)에 있다. 연구 질문이 아직 잠정적이어도 괜찮다. 첫 마일스톤을 "문헌 검토와 연구 질문 확정"으로 두고, 확정되면 `plan` 커밋으로 고친다.

기존 자료(아이디어 메모, 문헌 정리)는 `notes/`에 넣는다. 넣은 자료는 첫 task 승인 커밋에 함께 넣으면 된다([approve-task.md](approve-task.md)).

### 3. 터미널 두 개 열기

| 터미널 | 여는 법 | 하는 일 |
|---|---|---|
| A (사람) | `cd ~/research/my-study` | `lg commit`, `git log`, 문서 확인 |
| B (에이전트) | `cd ~/research/my-study && claude` | 에이전트에게 작업 지시 |

Claude Code는 **반드시 프로젝트 폴더에서** 연다. 그래야 그 프로젝트의 `CLAUDE.md`(규칙), `.claude/settings.json`(차단 규칙, 세션 시작 hook), 슬래시 명령이 적용된다. 다른 폴더에서 연 세션에는 적용되지 않는다.

### 4. 다른 컴퓨터에서 클론했을 때

hook 경로와 사람 신원은 저장소 로컬 설정이라 클론하면 사라진다. 프로젝트 폴더에서 다시 설정한다.

```bash
git config core.hooksPath .lg/hooks
git config user.name "<이름>"
git config user.email "<.lg/identities.json에 등록된 이메일>"
```

## 확인

```bash
lg --version                                   # labgate 0.4.0
git log --format='%an <%ae> | %s'              # init 커밋, 작성자가 나
git config core.hooksPath                      # .lg/hooks
grep spec_version .lg/project.yaml             # 4
```

## 잘 안 될 때

| 증상 | 원인과 해결 |
|---|---|
| `lg: command not found` | `pipx ensurepath` 후 새 터미널을 연다 |
| `대상이 이미 Git 저장소 안에 있습니다` | 상위 폴더가 Git 저장소다. 저장소 밖 경로를 쓰거나 `--no-git` |
| `이미 있는 파일과 겹칩니다` | `--force`여도 기존 파일은 덮어쓰지 않는다. 겹치는 파일을 옮긴다 |
| 커밋할 때 `등록되지 않은 작성자입니다` | 4번(클론 후 설정)을 하지 않았다. `user.email`을 등록된 이메일로 |
| `lg commit`이 `spec_version 1`이라며 거부 | labgate 0.1로 만든 프로젝트다. [upgrade.md](upgrade.md) |
| 설치된 `lg`가 예전 버전 | `pipx install --force …@v0.4.0` ([upgrade.md](upgrade.md)) |

## 에이전트는 무엇을 하나

아직 없다. 프로젝트를 만든 직후에는 첫 task(M0-T0)가 `draft`이므로, 에이전트는 사람이 승인할 때까지 작업하지 않는다. 다음: [approve-task.md](approve-task.md).
