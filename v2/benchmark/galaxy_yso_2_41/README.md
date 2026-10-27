# 2.41.0 측정 자료: 어두운 은하 조각 묶기, 2MASS 점광원 사전확률

- `fragment_sweep_kinds.csv`, `fragment_sweep_steal.csv`: `host_groups.attach_galaxy_fragments` 매개변수 탐색.
  - 저장된 400개 영역(blind)에 규칙만 적용해 재채점했다.
  - `chance`는 대조군(숙주가 아닌 천체를 30″ 옮겨 다시 적용)의 묶인 수 / 실제 묶인 수다.
  - 만든 스크립트: `sweep_fragments.py`.
- `final_score.py`: 최종 채점. 특수 영역 106곳은 2.41.0 코드로 다시 실행했다. 나머지 영역은 저장된 결과에 조각 규칙을 적용했다. 2.40.0과 천체별로 비교한다.

결과는 `../../WORK_REPORT_2026-10-27.md`에 있다.
