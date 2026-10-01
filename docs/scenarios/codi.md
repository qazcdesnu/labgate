# 사용 시나리오: Coconut을 읽고 CODI를 시작하는 연구자

> 이 문서는 labgate를 실제 연구 흐름에 대입해 보는 **가상의 시나리오**다. 목적은 두 가지다.
>
> 1. labgate의 개발 목적과 의도(사람이 task 경계에서 판정하고 에이전트가 그 사이를 수행하는 연구)를 구체적인 연구로 점검한다.
> 2. 신규 사용자가 "내 연구에서는 labgate를 어떻게 쓰게 될까"를 그려 볼 수 있게 한다.
>
> **사실과 가정의 구분**
>
> - 두 논문의 내용(방법, 수치)은 공개된 논문에서 확인한 것이다 (출처는 [맨 끝](#출처)).
> - 연구자 A, 연구 과정, 기간, 재현 수치, 판정 내용은 **모두 가정**이다. CODI 저자들이 실제로 어떻게 연구했는지는 알 수 없으며, 이 문서는 그것을 묘사하지 않는다. "전통 방식"은 에이전트 없이 혼자 또는 소규모로 진행하는 흔한 연구 방식을 가정한 것이다.
> - Claude Code의 동작은 공식 문서(code.claude.com/docs)와 직접 실험으로 확인했다 (2026-10-01, labgate 0.1.0).

---

## 0. 요약

| 질문 | 결론 |
|---|---|
| 무엇이 달라지는가 | 아이디어와 작업 사이의 **판단**이 문서와 커밋으로 남는다. 착상 → 재현 → 탐색 → 본 실험 → 논문의 모든 수치가 실행 ID와 결정 ID로 거슬러 올라간다. 연구자는 코드·실행·정리 대신 **판정**에 시간을 쓴다. |
| 시너지 | Claude Code는 실행력(코드, 장시간 실행, 문헌 정리, 문서 작성)을, labgate는 그 실행의 경계(승인된 범위, 예산, 사람 전용 결정, 기록 형식)를 제공한다. 서로의 약점(에이전트의 범위 이탈 / 문서 작성 부담)을 메운다. |
| 충돌 | **실제 충돌 2건 확인** (Claude Code의 커밋 공동 작성자 trailer, 워크트리 브랜치·병합). 둘 다 생성 파일 설정으로 해소 가능하며 [§6](#6-충돌-점검)에 조치안을 적었다. 나머지는 보완 또는 가외성(중복 안전장치)이다. |
| 설계 점검 | 목적(추적성, 사람의 판정권, 세션 연속성)은 시나리오 전 구간에서 성립한다. 비용은 게이트 대기와 문서 읽기 부담이며, 탐색이 빠른 구간에서는 task를 넓게 잡아야 한다 ([§4.2](#42-비용과-한계)). |

---

## 1. 출발점: 두 논문

### 1.1 연구자 A가 읽은 논문: Coconut

**Training Large Language Models to Reason in a Continuous Latent Space** (Hao et al., Meta FAIR·UC San Diego, arXiv 2412.06769, 2024-12, COLM 2025)

- **아이디어:** 언어 모델의 마지막 은닉 상태(continuous thought)를 언어 토큰으로 바꾸지 않고 **다음 입력 임베딩으로 바로 넣는다**. `<bot>`/`<eot>` 토큰으로 잠재 추론 구간을 표시한다.
- **학습:** 다단계 커리큘럼. 단계 k에서 앞의 k개 언어 추론 단계를 k×c개의 continuous thought로 바꾼다. GSM8k에서는 c=2, GPT-2 기반.
- **결과 (논문 표 1):** GSM8k 정확도 Coconut 34.1% / CoT 42.9% / iCoT 30.0% / No-CoT 16.5%. 생성 토큰은 Coconut 8.2개, CoT 25.0개. 계획이 많이 필요한 ProsQA에서는 Coconut 97.0% / CoT 77.5%.
- **저자가 밝힌 한계:** continuous thought를 순차적으로 계산해야 해서 학습 병렬화가 어렵다. 커리큘럼 없이는 학습이 되지 않았다. GSM8k에서 CoT와의 격차가 남는다.

### 1.2 연구자 A의 착상 (= CODI가 도달한 설계)

연구자 A는 Coconut의 한계를 보고 다음과 같은 질문을 떠올린다.

> 커리큘럼으로 언어 단계를 하나씩 지우는 대신, **같은 모델이 언어 CoT를 풀 때의 내부 상태를 정답으로 삼아** 잠재 추론을 한 번에 가르칠 수 없을까?

이 시나리오는 연구자 A가 이 질문에서 출발해 CODI 논문의 설계에 이르는 과정을 따라간다. 도착점인 CODI는 다음과 같다.

**CODI: Compressing Chain-of-Thought into Continuous Space via Self-Distillation** (Shen, Yan, Zhang, Hu, Du, He, King's College London·Alan Turing Institute, arXiv 2502.21074, 2025-02)

- **자기 증류:** 한 모델이 교사(언어 CoT를 cross-entropy로 학습)와 학생(continuous thought를 자기회귀로 만든 뒤 답을 학습)을 동시에 맡는다.
- **정렬 지점:** "The answer is:"의 **콜론(`:`) 토큰**에서 모든 층의 은닉 상태를 L1 거리로 맞춘다. 교사 쪽은 stop-gradient, 층별로 교사의 표준편차로 정규화한다.
- **구성:** 2층 MLP와 LayerNorm으로 된 투영층, `<bot>`/`<eot>`, continuous thought 6개. 커리큘럼 없이 **한 단계로 학습**한다. 손실은 학생 + 증류 + 교사의 합이다 (GPT-2는 가중치 모두 1, LLaMA-1B는 증류 가중치 20).
- **결과:** GPT-2, GSM8k-Aug에서 명시적 CoT와 동등한 정확도(본문 ablation 기준 43.7%, CoT-SFT 약 44%). 3.1배 압축. 초록 표현으로 "이전 최고 성능을 정확도에서 28.2% 앞선다".
- **ablation:** 증류 손실을 빼면 24.5%. 교사를 별도 모델로 두면 27.1%.

> 이 ablation 숫자들은 연구 과정에서 내려진 **결정**(어디서 정렬할지, 어떤 손실을 쓸지, 교사를 따로 둘지)의 근거다. 이런 결정이 어떻게 기록되는지가 labgate의 핵심 관심사다.

---

## 2. labgate로 연구 시작하기

### 2.1 `lg init`

연구자 A는 읽은 논문 메모와 착상을 `notes/`에 넣을 생각으로 프로젝트를 만든다.

```yaml
# codi.yaml
schema_version: 1
project:
  name: "CODI: Self-Distillation into Continuous CoT"
  slug: codi
  summary: "같은 모델의 언어 CoT 은닉 상태를 교사로 삼아 잠재 추론을 한 단계로 학습한다"
  research_question: "커리큘럼 없이 자기 증류만으로 continuous CoT가 명시적 CoT 성능에 도달하는가?"
people:
  humans:
    - name: "연구자 A"
      email: "a@lab.example"
    - name: "지도교수 P"
      email: "p@lab.example"
milestones:
  - title: "기반 구축과 Coconut 재현"
  - title: "정렬 신호 탐색"
  - title: "CODI 본 학습과 비교"
  - title: "일반화와 확장"
  - title: "분석과 논문"
```

```
$ lg init ~/research/codi --config codi.yaml
✓ 프로젝트를 만들었습니다: /home/a/research/codi
  파일 79개, 초기 커밋 3f2a1c9 (init)
```

사람이 두 명이다(연구자 A, 지도교수 P). 둘 다 `.lg/identities.json`에 등록되므로 **둘 중 누구든 게이트를 판정할 수 있다.** 에이전트는 `agent@codi.local`로 커밋한다.

### 2.2 마일스톤과 그 안의 task (T0에서 에이전트가 분해한 결과의 예)

| 마일스톤 | task 예 (T0 이후 `draft` → 사람이 승인) | Go/No-go 기준 예 |
|---|---|---|
| M0 기반 구축과 Coconut 재현 | M0-T1 데이터(GSM8k-Aug)·평가 파이프라인, M0-T2 CoT-SFT·No-CoT 기준선, M0-T3 Coconut 재현 | 기준선과 Coconut이 논문 수치의 ±3%p 안 |
| M1 정렬 신호 탐색 | M1-T1 정렬 토큰 후보 비교, M1-T2 손실 함수 비교, M1-T3 교사 분리 여부 | 소규모 실험에서 증류가 무증류보다 유의하게 높음 |
| M2 CODI 본 학습과 비교 | M2-T1 GPT-2 본 학습, M2-T2 ablation 세트, M2-T3 효율 측정 | GPT-2, GSM8k-Aug에서 CoT-SFT와 동등 |
| M3 일반화와 확장 | M3-T1 OOD(SVAMP, GSM-Hard, MultiArith), M3-T2 LLaMA-3.2-1B, M3-T3 GSM8k-Aug-NL | OOD에서 CoT-SFT 대비 이점 또는 동등 |
| M4 분석과 논문 | M4-T1 continuous thought 해석, M4-T2 원고 | 원고의 모든 수치에 실행 ID가 있음 |

---

## 3. 단계별 비교: 전통 방식 vs Claude Code + labgate

각 장면에서 왼쪽은 에이전트 없이 연구하는 흔한 방식(가정), 오른쪽은 같은 일을 Claude Code와 labgate로 할 때다.

### 3.1 착수: 착상을 계획으로 (M0-T0)

| 전통 방식 | Claude Code + labgate |
|---|---|
| 착상은 머릿속과 노트 앱에 있다. 관련 문헌(Coconut, iCoT, GSM8k-Aug 출처)을 하나씩 읽고 PDF를 다운로드 폴더에 모은다. 계획은 지도교수와의 면담 메모로 남는다. | 연구자 A가 `notes/`에 착상 메모를 넣고 `plan(M0-T0)` 커밋으로 T0를 승인한다. 에이전트(`/session-start` → `/task-start M0-T0`)는 다음을 한다.<br>• 문헌을 `references/library/hao2024-coconut.pdf`처럼 ID로 저장하고 `catalog.md`에 등록한다.<br>• M0-T1~T3 카드를 `draft`로 쓰고, `task-map.md`에 task별로 읽을 부분을 연결한다.<br>• 기존 착상 메모를 `roadmap.md`와 결정 초안 `decisions/D1.1_distill-token.md`(`proposed`)로 옮긴다.<br>• 게이트 요청서 `reviews/open/M0-T0_gate-01.md`를 낸다. |
| 무엇을 왜 하기로 했는지는 면담 직후에만 선명하다. | 지도교수 P가 요청서를 읽고 응답한다. 사람 신원으로 남는 커밋:<br>`gate(M0-T0): approve, next M0-T1`<br>`Actor: human` / `Task: M0-T0` / `Verdict: approve` / `Source: document` / `Next: M0-T1`<br>tag `gate/M0-T0`. |

**차이:** 계획이 "읽을 수 있는 문서 + 사람의 승인 기록"으로 남는다. 6개월 뒤에도 `git log --grep "^gate"`로 무엇을 언제 누가 승인했는지 볼 수 있다.

### 3.2 재현: Coconut 기준선 (M0-T3)

| 전통 방식 | Claude Code + labgate |
|---|---|
| 공개 코드를 받아 돌린다. 하이퍼파라미터를 바꿔 가며 여러 번 실행한다. 결과는 실험 관리 도구 대시보드와 터미널 기록에 흩어진다. | 에이전트가 `experiments/M0/M0-T3_coconut-repro/`에 코드를 두고 실행마다 `runs/M0-T3_run-001.yaml` 같은 실행 기록을 남긴다(설정, 시드, 커밋, 지표). 장시간 학습은 Claude Code의 백그라운드 실행으로 돌리고, 카드의 GPU 예산 안에서만 실행한다. |
| 재현 수치가 논문(34.1%)보다 낮게 나오면, 원인을 혼자 며칠 파고든다. 시도한 것들이 기록되지 않는다. | (가정) 재현 정확도가 29%로 나오고 원인 후보가 셋(데이터 버전, c 값, 단계별 epoch)이다. 원인을 확인하려면 예산을 넘는 재학습이 필요하므로, 에이전트는 **멈추고 에스컬레이션**한다(`/escalate M0-T3`): `reviews/open/M0-T3_esc-01.md`에 상황, 선택지 3개와 각각의 비용, 추천안을 적는다. 카드는 `blocked`가 된다. |
| — | 연구자 A가 대화로 답한다: "2번으로 가자, GPU 20시간 추가." 에이전트가 응답을 그대로 적고 변경을 stage한 뒤 메시지 초안을 `.lg/pending/COMMIT_MSG`에 쓰고 멈춘다. 연구자 A가 `git diff --cached`를 확인하고 실행한다:<br>`respond(M0-T3): choose option 2, +20 GPU h` (`Source: conversation`) |

**차이:** "재현이 안 되는 이유를 찾는 데 GPU를 더 쓸 것인가"라는 **자원 판단이 사람의 것으로 남는다.** 에이전트가 예산을 넘겨 실험을 계속하는 일이 구조적으로 막히고, 막힌 지점과 선택지가 문서로 남는다.

### 3.3 탐색: 어디서 정렬할 것인가 (M1)

CODI의 핵심 설계 결정이 이 구간에서 내려진다.

| 결정 (가정한 ID) | 선택지 | 근거가 되는 실험 |
|---|---|---|
| D1.1 정렬 토큰 | 답 직전의 `:` / 마지막 continuous thought / 전 구간 평균 | M1-T1 소규모 비교 |
| D1.2 증류 손실 | L1 / MSE / 코사인, 교사 표준편차 정규화 여부 | M1-T2 |
| D1.3 교사 | 같은 모델(자기 증류) / 별도 모델 | M1-T3 |

| 전통 방식 | Claude Code + labgate |
|---|---|
| 몇 가지를 돌려 보고 잘 되는 쪽을 고른다. 고른 이유는 슬랙 대화나 머릿속에 있다. 논문을 쓸 때 "왜 `:` 토큰인가"를 설명하려고 옛 실험을 다시 찾거나 다시 돌린다. | 에이전트는 실험 결과를 근거로 각 결정 문서에 선택지와 추천안을 쓰고 `propose` 커밋을 한다. **결정을 확정할 수 없다.** 게이트 요청서의 "확정이 필요한 결정"에 D1.1–D1.3을 올린다. |
| 지도교수와의 면담에서 결정했다면 그 근거는 면담 메모에만 있다. | 연구자 A가 판정한다: `decide(D1.1): distill at ':' token, all layers` (`Decisions: D1.1`, `Source: document`). 이후 M2의 ablation task(M2-T2)는 `decisions: [D1.1, D1.2, D1.3]`을 카드에 걸고 시작한다. 논문의 ablation 표가 결정 문서와 1:1로 이어진다. |

**차이:** 연구의 **지적 소유권**, 즉 무엇을 믿고 무엇을 채택했는지가 사람의 커밋으로 고정된다. 에이전트가 아무리 많은 실험을 해도 "채택"은 사람만 한다. 증류를 빼면 24.5%, 교사를 분리하면 27.1%라는 논문의 ablation은 이 결정들의 근거를 사후에 정리한 것이다. labgate에서는 이 근거가 결정 당시에 문서로 남는다.

### 3.4 본 실험과 마일스톤 판정 (M2)

| 전통 방식 | Claude Code + labgate |
|---|---|
| 본 학습을 돌리고 결과가 좋으면 다음으로 넘어간다. "충분히 좋은가"는 암묵적으로 판단한다. | M2의 마지막 task 게이트에서 에이전트가 마일스톤 보고(`results/M2/report.md`)와 Go/No-go 근거를 낸다: "GPT-2, GSM8k-Aug에서 CoT-SFT와 동등 (실행 `M2-T1_run-004`, `M2-T1_run-005`)". |
| — | 연구자 A의 판정: `gate(M2-T3): approve` + `Milestone-Verdict: go` + `Next: M3-T0`. tag `milestone/M2-go`. 같은 커밋으로 다음 마일스톤 착수까지 승인한다. |

**차이:** 마일스톤 경계가 **명시적인 Go/No-go**가 된다. 연구가 막다른 길이었다면 `nogo`나 `redirect`도 같은 형식으로 남고, 실패한 방향의 근거가 사라지지 않는다.

### 3.5 확장에서 생긴 기대와 다른 결과 (M3)

(가정) LLaMA-3.2-1B에서 CODI가 CoT-SFT보다 낮게 나온다 (논문 그림 3에서도 1B 규모에서는 CoT-SFT 약 62%, CODI 약 56%로 차이가 있다).

| 전통 방식 | Claude Code + labgate |
|---|---|
| 결과를 어떻게 해석할지, 논문에서 어떻게 다룰지를 혼자 정한다. 증류 가중치를 바꿔 보는 실험이 기록 없이 늘어난다. | 게이트 요청서의 "예상과 달랐던 점"에 이 결과가 올라간다. 에이전트는 증류 가중치 상향(예: β=20)을 결정 `D3.1`로 제안한다. 연구자 A는 `revise`로 판정해 같은 task를 다시 열고, 다음 요청은 `M3-T2_gate-02`가 된다. 판정 이력이 카드의 "게이트 이력"에 쌓인다. |

### 3.6 논문 (M4)

| 전통 방식 | Claude Code + labgate |
|---|---|
| 표의 숫자를 대시보드에서 다시 찾는다. 어떤 체크포인트였는지 헷갈린다. 리뷰어가 "정렬 지점 선택의 근거"를 물으면 옛 실험을 다시 돌린다. | 원고의 모든 수치는 `results/<M>/<Task>_result.md` → 실행 ID → 실행 기록(커밋, 시드)로 이어진다. M4-T2의 완료 기준이 "원고의 모든 수치에 실행 ID가 있다"이고, 게이트에서 사람이 이를 확인한다. 리뷰어 질문에는 `D1.1` 결정 문서와 M1-T1 결과로 답한다. |

---

## 4. 기대효과

### 4.1 효과

| 효과 | 시나리오에서 드러난 장면 | 만드는 장치 |
|---|---|---|
| **추적성** | 논문 수치 → 결과 문서 → 실행 ID → 커밋 | 실행 기록, 결과 문서, ID 체계(conventions §1) |
| **판단의 기록** | D1.1–D1.3이 결정 당시의 근거와 함께 남음 | `decisions/`, 사람 전용 `decide` 커밋 |
| **사람의 판정권** | 결정 확정, 예산 초과, 마일스톤 Go/No-go는 사람만 | 사람 전용 커밋 타입 + hook의 신원 검사 |
| **자원 통제** | 재현 실패 시 GPU 추가 사용을 사람이 결정 | task 카드의 예산, 에스컬레이션 |
| **세션 연속성** | 에이전트가 며칠 뒤 새 세션에서도 바로 이어서 일함 | `STATUS.md`, 작업 일지, 세션 시작 절차 |
| **협업** | 지도교수가 게이트 요청서로 비동기 리뷰 | `reviews/`, 사람 2명 등록 |
| **실패의 보존** | `nogo`·`redirect`·`revise`도 같은 형식으로 남음 | 게이트 판정, 마일스톤 tag |

연구자 A의 시간은 "코드 작성, 실험 실행, 결과 정리"에서 **"요청서 읽기, 판정, 결정"**으로 옮겨 간다. labgate가 의도한 분업이 바로 이것이다.

### 4.2 비용과 한계

- **게이트 대기:** 사람이 판정하기 전까지 에이전트는 다음 task로 가지 못한다. 연구자가 바쁘면 사람이 병목이 된다. 대화 경로 게이트(§3.2)로 대기는 줄일 수 있지만 없앨 수는 없다.
- **문서 읽기 부담:** 문서는 에이전트가 쓰지만 사람이 읽어야 의미가 있다. 요청서를 형식적으로 승인하면 판정권이 형식만 남는다.
- **탐색 구간의 마찰:** M1처럼 하루에 아이디어가 여러 번 바뀌는 구간에서 task를 잘게 나누면 게이트가 너무 잦다. 탐색 task는 "범위 › 포함"을 넓게 잡고 예산으로 묶는 편이 낫다.
- **stub 사양:** 사양 16종 중 11종은 처음에 비어 있다. M0 동안 보완해야 하며, 그 전까지는 문서 형식이 일정하지 않을 수 있다.
- **강제의 범위:** 신원과 커밋 타입은 hook이 강제하지만, "결정 상태를 `confirmed`로 바꾸지 않는다" 같은 규칙은 지침(AGENTS.md)과 사람의 diff 검토에 의존한다.
- **규모:** 혼자 하는 짧은 실험에는 과할 수 있다. labgate는 몇 주 이상 이어지고 판단이 많이 쌓이는 연구에 맞다.

---

## 5. Claude Code × labgate 시너지

| Claude Code가 주는 것 | labgate가 주는 것 | 함께일 때 |
|---|---|---|
| 코드 작성, 장시간 실행(백그라운드), 문헌 정리, 문서 작성 | 승인된 범위, 예산, 기록 형식 | 에이전트의 실행력이 **정해진 경계 안에서** 쓰인다 |
| 세션마다 새 컨텍스트, `/compact` 뒤에는 대화 내용 일부가 사라짐 | `STATUS.md`, 작업 일지, task 카드, 세션 시작 절차 | 새 세션이 저장소 문서에서 상태를 복원한다. 대화가 아니라 저장소가 기억한다 |
| CLAUDE.md의 `@AGENTS.md` import | 도구 중립적인 규칙의 원본(AGENTS.md, specs/) | 규칙은 한 곳에, Claude Code는 연결만 한다. 다른 에이전트로 바꿔도 규칙이 유지된다 |
| 슬래시 커맨드 | 워크플로우 절차(workflow.md §5–7) | `/task-start`, `/task-gate`, `/escalate`가 절차를 한 번에 실행한다 |
| `permissions.deny` | commit-msg hook (신원·타입·trailer 검사) | 같은 위반을 두 층에서 막는다(가외성). deny의 문자열 일치를 피해 가거나, deny를 적용하지 않는 권한 모드로 실행해도 hook이 잡는다. 단 `--no-verify`는 예외 ([§6.5](#65-공백---no-verify)) |
| 대화 | 대화 경로 게이트(`.lg/pending/`) | 사람은 채팅으로 판정하고, 커밋은 사람이 직접 실행한다. 판정의 신원이 보존된다 |
| 서브에이전트, 병렬 작업 | T0의 문헌 조사·task 분해 | 문헌 여러 편을 나눠 읽고 `catalog.md`·`task-map.md`로 모은다 |
| 체크포인트·되돌리기(파일 편집만, Git 이력은 건드리지 않음) | Git 커밋이 사실의 원본 | 커밋 전 시행착오는 체크포인트로, 확정된 사실은 커밋으로. 역할이 겹치지 않는다 |

---

## 6. 충돌 점검

"충돌"은 한쪽 기능이 다른 쪽 규칙을 깨거나 작업을 실패하게 만드는 경우다. 같은 목적을 두 겹으로 지키는 **가외성**은 문제로 보지 않는다.

### 6.1 결과 요약

| # | Claude Code 기능 | labgate 규칙 | 판정 | 확인 방법 |
|---|---|---|---|---|
| 1 | **커밋 공동 작성자 trailer** (기본 `Co-Authored-By: <모델 이름> <noreply@anthropic.com>`) | hook은 **마지막 문단**에서 `Actor` 등 trailer를 찾는다 | **충돌** | 실험 (§6.2) |
| 2 | **워크트리** (`--worktree`, 서브에이전트 `isolation: worktree`) → `worktree-<name>` 브랜치 생성 | `main` 하나의 선형 이력. hook은 `Merge ` 커밋을 검사 없이 통과시킴 | **충돌** | 문서 + 실험 (§6.3) |
| 3 | 자동 메모리 (기본 켜짐, `~/.claude/projects/<project>/memory/`) | 사실의 원본은 저장소(Git) | **긴장** (직접 충돌은 아님) | 문서 |
| 4 | `permissions.deny`의 문자열 일치 | 에이전트의 `--no-verify` 금지 | 공백 (hook으로도 못 막음) | 문서 + 실험 |
| 5 | 내장 커밋 지침 (Claude Code가 커밋 방법을 컨텍스트에 넣음) | `scripts/agent-commit`만 사용 | 가외성 + 경합 | 문서 |
| 6 | 내장 `/init` | CLAUDE.md는 사람만 수정 | 충돌 아님 (사람이 실행, 기존 파일이면 개선 제안만) | 문서 |
| 7 | AGENTS.md 직접 읽기 (v2.1.277+) | CLAUDE.md가 `@AGENTS.md` import | 충돌 아님 (CLAUDE.md가 있으면 CLAUDE.md만 읽고, import로 한 번만 로드) | 문서 |
| 8 | `.claude/settings.local.json` (개인 승인 규칙) | `git status` 깨끗함 | 충돌 아님 (Claude Code가 처음 만들 때 전역 Git 제외 목록에 추가) | 문서 |
| 9 | 체크포인트·되돌리기 | 이력 재작성 금지 | 충돌 아님 (파일 편집만 되돌리고 Git은 건드리지 않음) | 문서 |
| 10 | 계획 모드, 작업 목록 | task 카드 | 가외성 (세션 단위 계획 vs task 단위 계약) | — |
| 11 | `.claude/commands/` 슬래시 커맨드 | — | 충돌 아님 (지원됨. 현재 권장은 `.claude/skills/`) | 문서 |

### 6.2 충돌 1: 공동 작성자 trailer와 hook

Claude Code는 기본적으로 자신이 만드는 커밋에 `Co-Authored-By: <모델 이름> <noreply@anthropic.com>` trailer를 붙인다 (`attribution.commit`의 기본값, 예: `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`). 이 줄은 커밋 **작성자 신원**(`git config user.name/email`, labgate에서는 `agent-commit`이 정함)을 바꾸지 않고 **메시지 본문 끝에 한 줄을 덧붙일** 뿐이다. 이 줄이 labgate trailer와 **다른 문단**에 오면 hook이 거부한다. 생성된 프로젝트에서 시험한 결과:

| 메시지 끝 부분 | 결과 |
|---|---|
| `Actor: agent` ⏎⏎ `🤖 Generated with …` ⏎⏎ `Co-Authored-By: Claude …` | ✗ `Actor trailer가 필요합니다` |
| `Actor: agent` ⏎⏎ `Co-Authored-By: Claude …` | ✗ 같음 |
| `Actor: agent` ⏎ `Co-Authored-By: Claude …` (같은 문단) | ✓ 통과 |
| 대화 경로에서 Claude가 쓴 사람의 `gate` 초안 + 별도 문단의 `Co-Authored-By` | ✗ `Actor`, `Task` 누락으로 거부 |

에이전트는 거부 메시지를 보고 고쳐서 다시 커밋할 수 있다. 하지만 **매 커밋마다 한 번씩 실패**하고, 사람의 판정 커밋 초안(대화 경로)에도 섞여 들어간다. 사람 커밋에 "Claude가 공동 작성자"라는 표시가 붙는 것은 판정의 신원 분리라는 취지와도 어긋난다.

**조치안** (생성 파일 수정, 설계 문서 개정 필요):

1. **핵심:** 생성되는 `.claude/settings.json`에서 커밋 attribution을 끈다. 문서상 `attribution.commit`을 **빈 문자열**로 두면 숨겨진다.
   ```json
   { "attribution": { "commit": "", "pr": "", "sessionUrl": false } }
   ```
   - `"attribution": false` 한 줄로도 모두 끌 수 있지만 Claude Code v2.1.281 이상에서만 읽힌다. 그보다 낮은 버전은 이 값을 거부하고 **설정 파일 전체를 건너뛴다.** 그러면 같은 파일의 deny 규칙까지 사라지므로, 문서가 권하는 대로 하위 호환되는 빈 문자열 형식을 쓴다.
   - 예전 키 `includeCoAuthoredBy`는 v2.0.62부터 사용 중단되었고, `attribution.commit`이나 `attribution.pr`을 설정하면 무시된다. 생성 파일에는 쓰지 않는다.
   - AI 사용을 커밋에 표시하고 싶다면 빈 문자열 대신 문구를 두되, `specs/git-commit.md`에 "trailer는 마지막 한 문단에 모두 쓴다"를 명시한다. Claude Code는 CLAUDE.md 등 프로젝트 지침의 attribution 규칙을 이 설정보다 우선한다고 Claude에게 알린다(관리형 설정 제외).
2. (선택) hook이 마지막 문단에서 `Actor`를 못 찾으면 "trailer 블록이 둘로 나뉘었다"고 구체적으로 알려 준다.

### 6.3 충돌 2: 워크트리 브랜치와 선형 이력

Claude Code는 워크트리를 `.claude/worktrees/<name>/`에 만들고 새 브랜치 `worktree-<name>`을 딴다. 서브에이전트에 `isolation: worktree`를 주거나, 사용자가 "워크트리에서 작업해"라고 하면 생긴다. 이 작업을 `main`에 합치면 다음 문제가 생긴다.

- 병합 커밋은 hook이 검사 없이 통과시킨다. 실험에서 에이전트 신원의 `Merge branch 'worktree-x'` 커밋이 그대로 들어갔다.
- 규약(workflow §1.3)의 "`main` 하나의 선형 이력"이 깨진다.
- `.claude/worktrees/`가 `.gitignore`에 없어서 메인 작업 트리에 추적되지 않은 파일로 보인다 (Claude Code 문서도 이 경로를 무시 목록에 넣으라고 권한다).

**조치안:**

1. 생성되는 `.gitignore`에 `.claude/worktrees/`를 추가한다.
2. AGENTS.md에 "워크트리는 실험 격리에만 쓰고, 결과는 병합하지 말고 `main`에서 다시 커밋한다" 또는 "워크트리 금지" 중 하나를 정해 적는다.
3. `.claude/settings.json`의 deny에 `Bash(git merge *)`를 추가하고, hook의 `Merge ` 통과를 사람 작성자로 제한하는 것을 검토한다.

### 6.4 긴장: 자동 메모리

Claude Code는 기본적으로 사용자의 교정과 선호를 `~/.claude/projects/<project>/memory/`에 스스로 기록한다. 이 기록은 **저장소 밖, 해당 기기에만** 있고 사람의 게이트 검토를 거치지 않는다. labgate의 "사실의 원본은 저장소"와 직접 충돌하지는 않지만, 연구 판단이 메모리에만 남으면 추적성이 새어 나간다. 예를 들어 "D1.1은 `:` 토큰으로 정했음"이 결정 문서가 아니라 메모리에만 남는 경우다.

**조치안:** AGENTS.md나 CLAUDE.md에 "연구 사실과 판단은 `logs/`, `decisions/`, task 카드에 쓴다. 자동 메모리에는 개인 작업 습관만 둔다"를 적는다. 엄격하게 하려면 프로젝트 `.claude/settings.json`에 `"autoMemoryEnabled": false`를 둔다.

### 6.5 공백: `--no-verify`

deny 규칙은 명령 문자열이 맞을 때만 막는다. `git -C . commit --no-verify`처럼 형태를 바꾸면 피해 갈 수 있고, `--no-verify`로 건너뛴 커밋은 hook도 볼 수 없다. 현재는 AGENTS.md 지침과 사람의 이력 검토에만 의존한다.

**조치안:** Claude Code의 PreToolUse hook(설정 파일에 등록, 명령 내용을 검사해 거부)으로 `--no-verify`, `-n`, `core.hooksPath` 변경을 막는다. Claude Code 문서도 "CLAUDE.md는 강제가 아니며, 반드시 막아야 하면 PreToolUse hook을 쓰라"고 안내한다.

### 6.6 가외성과 경합: 내장 커밋 지침

사용자가 "커밋해 줘"라고 하면 Claude Code는 내장 지침대로 `git commit`을 시도한다. labgate는 이를 deny로 막고 CLAUDE.md로 `scripts/agent-commit`을 쓰게 한다. 결과적으로 안전하지만(가외성), 내장 지침과 프로젝트 지침이 컨텍스트에서 경합해 첫 시도가 거부될 수 있다. `includeGitInstructions: false`로 내장 커밋·PR 지침을 컨텍스트에서 뺄 수 있지만, 이 설정은 세션 시작 시의 Git 상태 스냅샷(현재 브랜치, `git status`, 최근 커밋)도 함께 뺀다. 충돌 1의 해소에는 필요 없고 경합은 deny와 hook이 이미 막으므로 **기본 생성 파일에는 넣지 않는다.** 첫 시도 거부가 잦으면 사용자가 선택적으로 켠다.

---

## 7. 설계 점검 결론

**개발 의도는 시나리오 전 구간에서 성립한다.** 착상 → 재현 → 탐색 → 본 실험 → 확장 → 논문의 각 경계에서 사람의 판정이 커밋으로 남고, 에이전트는 승인된 범위와 예산 안에서 일하며, 결정과 수치가 끊기지 않고 이어진다.

**실사용 전에 고칠 것** (우선순위 순, 모두 생성 파일 변경이라 설계 문서 개정 → 템플릿 동기화 → 테스트 순으로 진행):

1. **[충돌 1]** `.claude/settings.json`에 `"attribution": {"commit": "", "pr": "", "sessionUrl": false}` 추가. `git-commit.md`에 "trailer는 마지막 한 문단에" 명시.
2. **[충돌 2]** `.gitignore`에 `.claude/worktrees/` 추가. AGENTS.md에 워크트리·브랜치 정책 명시. `git merge` deny 추가 검토.
3. **[긴장]** 자동 메모리 사용 지침 추가 (또는 `autoMemoryEnabled: false`).
4. **[공백]** `--no-verify` 차단용 PreToolUse hook 추가 검토.
5. **[운영]** 탐색 구간의 task 크기 지침(넓은 범위 + 예산)을 `workflow.md`에 추가 검토.

---

## 출처

- Hao, S., Sukhbaatar, S., Su, D., Li, X., Hu, Z., Weston, J., Tian, Y. *Training Large Language Models to Reason in a Continuous Latent Space.* arXiv:2412.06769 (2024). https://arxiv.org/abs/2412.06769
- Shen, Z., Yan, H., Zhang, L., Hu, Z., Du, Y., He, Y. *CODI: Compressing Chain-of-Thought into Continuous Space via Self-Distillation.* arXiv:2502.21074 (2025). https://arxiv.org/abs/2502.21074
- Claude Code 문서 (2026-10-01 확인):
  - 메모리·AGENTS.md·`/init`: https://code.claude.com/docs/en/memory
  - 설정 범위, `settings.local.json`: https://code.claude.com/docs/en/settings
  - `attribution`, `includeGitInstructions`: https://code.claude.com/docs/en/settings-reference
  - 워크트리: https://code.claude.com/docs/en/worktrees
  - 권한 규칙: https://code.claude.com/docs/en/permissions
- 2026-10-02 정정: `attribution.commit`의 기본값과 끄는 방법(`null` → 빈 문자열)을 문서 원문(`settings-reference.md`)으로 다시 확인해 고쳤다. 처음 작성 때는 웹 요약 도구가 문서를 잘못 옮긴 내용을 그대로 썼다.
- 충돌 실험: 생성된 프로젝트(labgate 0.1.0)에서 `scripts/agent-commit`, `git commit`, `git merge`로 직접 확인.
