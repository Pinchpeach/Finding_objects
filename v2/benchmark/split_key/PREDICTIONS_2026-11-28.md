# 예측 (측정 도구 `split_key_impact.py`를 돌리기 전에 씀, 2026-11-28)

배경: 벤치마크의 train(60 %) / calibration(20 %) / test(20 %) 분할은 `SHA-256(benchmark_id)`의 첫 8자리 mod 10으로 정해진다(`validate_catalog_truth.py:split_for`,
`train_validate_star_wd.py`·`train_validate_wd_subtype.py`는 접두사 `star-wd:`·`wd-subtype:`를 붙인다). `benchmark_id`는 빌더가 목록을 만든 **행 번호**다(`TRD%06d`, `RXTRD%06d`,
`STARTRD%06d`, `LAMTRD%06d`, `WDSUB%05d`). 이 번호가 아니라 천체의 안정적 식별자(목록의 ID `specobjid`·`external_id`, 또는 좌표 해시)로 분할을 정하면 어떻게 되는가(설계만; 실행은 사용자 결정).

해시 두 개가 서로 독립이면 분할이 같을 확률은 0.6² + 0.2² + 0.2² = 0.44다. 이 값에서 예측을 낸다.

| # | 예측 | 틀렸다고 볼 기준 |
|---|---|---|
| P1 | 키를 `benchmark_id` → 안정 ID(`specobjid` / `external_id`)로 바꾸면 분할이 **바뀌는 객체 비율은 56 %**다. 표별 허용 폭(이항 3 SE): `truth_data` 9,999행 ±1.5 %p, `radio_xray_truth` 951행 ±5 %p, `star_truth`·`lamost_star_external` 1,000행 ±5 %p, `wd_subtype` 300행 ±9 %p | 폭을 벗어나면 해시가 독립이 아니다(예: 행 번호와 ID가 상관) |
| P2 | 새 test 집합의 **60 %가 옛 train에 있던 객체**다(조건부 P(옛=train 또는 …)). 옛 train을 쓴 적합(융합 가중치 등)을 그대로 두고 새 test로 평가하면 test의 6할이 이미 본 객체 → **재적합이 필요**하다 | 40 % 미만이면 예측 틀림 |
| P3 | 좌표 해시(RA·Dec을 1e-5°로 반올림한 문자열)를 키로 써도 P1·P2와 같은 값이다(해시 입력이 달라도 독립). 좌표 충돌(같은 키의 두 객체)은 `truth_data`에서 0–1개 | 충돌 3개 이상이면 반올림이 너무 거칠다 |
| P4 | **표 한 행을 빼고 번호를 다시 매기면**(예: 100번째 행을 삭제) 옛 키에서는 뒤따르는 행 9,899개의 약 56 %(≈ 5,540개 ± 100)가 분할을 바꾸고, 안정 키에서는 0이다 | 옛 키 변화가 4,500개 미만이거나 안정 키 변화가 0이 아니면 틀림 |
| P5 | 새 키에서도 분할별 클래스 균형은 무작위 수준이다(각 분할에서 STAR/GALAXY/QSO 비율이 1/3 ± 2 %p, `truth_data`) | 어느 한 분할에서 클래스 비율이 4 %p 넘게 벗어나면 틀림 |
| P6 | "분할 고정" 방안(현재 분할을 안정 키별로 저장한 표를 두고, 새 객체만 안정 키의 해시로 정함)은 기존 객체의 분할을 **0개** 바꾼다(정의상). 재적합은 필요 없다 | — |
| P7 | 이미 안정 키를 쓰는 표(`sdss_sky`: `cell:<sky_cell>`, `star_diverse`: 해시 ID, `desi_external`·`desi_fusion`: 분할을 쓰지 않음 `--split all`/`--split-all train`)는 바뀌는 것이 없다 | 소비 코드를 확인해 틀리면 정정 |
