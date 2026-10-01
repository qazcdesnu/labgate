"""stub 사양 정의 표 (설계 문서 부록 B.7)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Stub:
    name: str
    title: str
    purpose: str
    location: str


STUBS: tuple[Stub, ...] = (
    Stub("roadmap", "로드맵",
         "연구 질문, 가설, 마일스톤 목록, 공통 실험 원칙을 정의한다",
         "plan/roadmap.md"),
    Stub("milestone", "마일스톤",
         "마일스톤의 목표, task 목록, Go/No-go 기준을 정의한다",
         "plan/milestones/<M>/milestone.md"),
    Stub("task-map", "Task–문헌 매핑",
         "마일스톤의 각 task에 필요한 참고문헌과 읽을 부분을 연결한다",
         "references/<M>/task-map.md"),
    Stub("catalog", "참고문헌 목록",
         "참고문헌마다 ID, 서지 정보, 원본 파일, 요약을 한 행으로 기록한다",
         "references/catalog.md"),
    Stub("decision", "결정",
         "하나의 설계·실험 결정의 선택지, 근거, 상태를 기록한다",
         "decisions/<D-ID>_<slug>.md"),
    Stub("experiment-readme", "실험 설명",
         "task별 실험 폴더의 목적, 실행 방법, 연결된 task·결정을 설명한다",
         "experiments/<M>/<Task>_<slug>/README.md"),
    Stub("run-record", "실행 기록",
         "실행 한 번의 설정, 시드, 커밋, 환경, 지표 요약을 기록한다",
         "experiments/<M>/<Task>_<slug>/runs/<Run-ID>.yaml"),
    Stub("task-result", "Task 결과",
         "task의 결과와 해석을 정리해 게이트 판정의 근거로 삼는다",
         "results/<M>/<Task>_result.md"),
    Stub("milestone-report", "마일스톤 보고",
         "마일스톤 전체 결과를 종합하고 Go/No-go 판단 근거를 제시한다",
         "results/<M>/report.md"),
    Stub("worklog", "작업 일지",
         "에이전트 세션마다 한 일과 판단 이유를 기록한다",
         "logs/YYYY-MM-DD_sNN.md"),
    Stub("status", "상태판",
         "현재 위치, 사람 판단 대기, 진행·막힘·최근 게이트를 보여준다",
         "STATUS.md"),
)
