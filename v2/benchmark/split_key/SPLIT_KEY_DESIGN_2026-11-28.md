# 분할 키를 행 번호에서 안정적인 천체 식별자로: 설계와 영향 (2026-11-28, 설계만)

**이 문서가 하는 일**: 벤치마크의 train/calibration/test 분할이 지금은 행 번호(`benchmark_id`)로 정해진다. 이것을 천체 자신의 식별자(목록 ID 또는 좌표 해시)로 바꾸면 무엇이 얼마나 바뀌는지 재고, 선택지를 비교한다. **코드·분할·문서 수치는 하나도 바꾸지 않았다.** 실행은 사용자의 결정이다.
예측은 측정 전에 `PREDICTIONS_2026-11-28.md`(커밋 92d590c)에 적었고, 도구는 `split_key_impact.py`, 결과는 `results_2026-11-28/`.

## 1. 지금 어떻게 되어 있나

* 분할: `SHA-256(salt + benchmark_id)`의 앞 8자리를 10으로 나눈 나머지가 0–5면 train(60 %), 6–7이면 calibration(20 %), 8–9면 test(20 %). `benchmark/validate_catalog_truth.py:split_for`(salt 없음), `Classifier/train_validate_star_wd.py`(`star-wd:`), `Classifier/train_validate_wd_subtype.py`(`wd-subtype:`).
* `benchmark_id`는 빌더가 그때 만든 목록의 **행 번호**다: `TRD%06d`(`build_truth_sets.py:124`), `DESI%06d`, `RXTRD%06d`(`build_radio_xray_truth.py:190`), `STARTRD%06d`(`build_star_truth.py:67`), `LAMTRD%06d`(`build_lamost_star_external_truth.py:128`), `WDSUB%05d`. 목록의 순서는 선택 방식에 따라 정해진다(`truth_data`는 `specobjid` 순이 아니다).
* 이미 안정적인 곳: `sdss_sky`(`--split-column sky_cell` → `cell:<번호>`의 해시, 공간 분할), `star_diverse`(`DIVERSE_<해시>`가 `source:id`의 해시), `desi_fusion`(분할 없이 전부 train).
* **내 예측 P7은 절반 틀렸다**: `desi_external`도 행 번호 분할을 쓴다. `evaluate-preprocess-coarse.yml`의 회귀 관문과 README의 "DESI 시험 분할 n = 962", 융합 학습(`fit_fusion_weights.py`의 train 분할)이 그것이다. 분할을 쓰지 않는 쪽은 `v2_desi_external_validation.yml`(`--split all`)뿐이다.

## 2. 측정 (예측과 결과)

모든 값은 같은 해시 함수와 같은 salt에서 키만 바꾼 것이다. 해시 둘이 독립이면 분할이 같을 확률은 0.6² + 0.2² + 0.2² = 0.44, 곧 56 %가 바뀐다.

| 표 (행) | 새 키 | 분할이 바뀐 객체 | 새 test 중 옛 train이던 것 | 행 하나(100번째)를 지우고 번호를 다시 매기면 바뀌는 객체: 현재 키 / 안정 키 |
|---|---|---|---|---|
| `truth_data` SDSS (9,999) | `specobjid` | 5,741 (57.4 %) | 1,265 / 2,072 = 61.1 % | 5,563 (55.6 %) / **0** |
| | 좌표 해시 | 5,589 (55.9 %) | 59.1 % | 5,563 / **0** |
| `desi_external` (4,795) | `desi_targetid` | 2,642 (55.1 %) | 60.2 % | 2,646 (55.2 %) / **0** |
| | 좌표 해시 | 2,651 (55.3 %) | 59.5 % | 2,646 / **0** |
| `radio_xray_truth` (951) | `specobjid` | 539 (56.7 %) | 62.6 % | 493 (51.9 %) / **0** |
| `star_truth` (1,000) | `specobjid` | 572 (57.2 %) | 60.4 % | 508 (50.9 %) / **0** |
| `lamost_star_external` (1,000) | — | 빠짐(아래) | — | — |
| `wd_subtype_truth` (300) | `external_id` | 178 (59.3 %) | 60.0 % | 122 (40.8 %) / **0** |

| 예측 | 결과 |
|---|---|
| P1 바뀌는 비율 56 %(표별 3 SE 안) | **맞음** (12개 모두 3 SE 안; `truth_data`의 57.4 %는 허용폭 54.5–57.5 %의 끝) |
| P2 새 test의 60 %가 옛 train | **맞음** (57.8–62.6 %) → 옛 train에서 적합한 것을 새 test로 평가하면 test의 6할이 이미 본 객체다 |
| P3 좌표 해시도 같은 값, `truth_data` 충돌 0–1개 | **맞음** (충돌 0). 단 `lamost_star_external`에 같은 좌표(0.01″ 이내)의 서로 다른 `external_id` 쌍이 1개(132809061, 149305095, 둘 다 DA 백색왜성) |
| P4 한 행 삭제 시 ≈ 5,540 ± 100 변화(옛), 0(안정) | **맞음** (5,563; 0). 작은 표는 지운 행 앞쪽이 안 변해서 비율이 낮다(300행 표 40.8 %) |
| P5 `truth_data` 분할별 클래스 비율 1/3 ± 2 %p | **맞음** (현재 키 최대 편차 1.9 %p, 새 키 1.0 / 1.6 %p). 작은 표는 무작위 변동이 크다(`wd_subtype` 최대 11 %p, `radio_xray` 5 %p) |
| P6 "분할 고정"은 기존 객체 0개 변경 | 정의상 맞음(아래 B) |
| P7 이미 안정적인 표는 바뀔 것 없음 | `sdss_sky`·`star_diverse`는 맞음. **`desi_external`은 틀림**(위 1절) |

**읽는 법**: 키를 바꾸면 어느 표든 객체의 56–59 %가 다른 분할로 옮겨 가고, 새 test의 약 60 %는 옛 train 객체다. 이것이 바뀌는 크기이고 키의 종류(목록 ID냐 좌표냐)로는 달라지지 않는다.

## 3. 바꾸면 다시 해야 하는 것 (소비자)

분할을 읽거나 만드는 코드와 문서(확인한 것, 모두 `grep`):

* 분할을 만드는 곳: `validate_catalog_truth.py`(SDSS·DESI·radio/X-ray·sky), `train_validate_star_wd.py`, `train_validate_wd_subtype.py`(+`_xp`, `fit_wd_subtype_xp_model.py`, `validate_*_external.py`).
* train 분할로 **적합**하는 곳: `fit_fusion_weights.py`(융합 가중치와 GBM 혼합, calibration 분할로 규칙화·기권 문턱), `build_color_reference.py`(색 kNN 참조 집합), `train_validate_rx_adaptive.py`(자체 해시 `rx-select:`).
* test 분할로 **보고**하는 곳: `evaluate_rule_baseline.py`, `evaluate_subclass.py`, `partial_data_compare.py`, `evaluate-preprocess-coarse.yml`의 회귀 관문(DESI 시험 분할).
* 수치가 문서에 있는 곳: `README.md:143`, `ALGORITHM.md:165-166, 174`, `document/overview_content.py:473`, `document/deck_content.py:363`(개요 PDF·발표), `STATUS_2026-11-12.md:107, 121`.

**재학습이 필요한가: 예, 분할을 새 키로 다시 정하면 필요하다.** 새 test의 60 %가 옛 train이므로 지금의 융합 가중치·색 참조 집합을 새 test로 평가하면 누설이다. 그러면 융합 가중치 재적합, 색 참조 집합 재생성, 옛 SDSS/DESI 벤치마크의 모든 수치(97.99 % / 90.33 % 등)를 다시 내야 한다. 이 수치들은 README가 이미 "대표성 없음, 융합 학습 계보 때문에 유지"라고 적은 것이다.

## 4. 선택지

| | 내용 | 기존 객체 분할 | 재학습 | 비용·위험 |
|---|---|---|---|---|
| **A** 키만 바꿈 | `split_for(안정 키)`로 다시 정한다 | 56–59 % 바뀜 | 필요 | 위 3절 전부. 모든 옛 수치가 새 수치로 대체되어 이력이 끊긴다 |
| **B** 현재 분할을 고정 (권장) | 지금의 분할을 안정 키별로 저장한 표(`split_frozen.csv`: 안정 키, 분할)를 커밋하고, `validate_catalog_truth.py`가 그 표를 먼저 읽는다. 표에 없는 새 객체만 안정 키의 해시로 정한다 | **0개** | 불필요 | 파일 1개와 코드 몇 줄. 표별 안정 키를 정해야 한다(SDSS `specobjid`, DESI `desi_targetid`, LAMOST·WD `external_id` + 좌표 쌍 점검). 목록을 다시 만들어도 이미 있던 객체의 분할은 그대로고, 행 번호가 밀려도 영향 없다 |
| **C** 그대로 + 매니페스트 | 이번에 넣은 `truth_tables_manifest.json`(SHA-256)과 시험이 목록이 조용히 바뀌는 것을 막는다. 분할은 행 번호로 둔다 | 0개 | 불필요 | 목록을 **일부러** 바꾸는 순간(행 추가·삭제)에는 보호가 없고, 그때는 A와 같은 일이 생긴다 |

**권장은 B**(C는 이미 들어가 있다): 분할을 "해시로 다시 계산하는 값"에서 "한 번 정해서 저장한 값"으로 바꾸는 것이라 기존 수치가 그대로 유지되고, 새 객체를 더하는 일도 안전해진다. A는 객체의 절반 이상이 옮겨 가는 데 비해 얻는 것이 없다(키의 안정성은 B가 같이 준다).

B를 하게 되면 정할 것(사용자 결정): (1) 표별 안정 키. (2) `lamost_star_external`의 같은 좌표 쌍(`external_id`가 다른 같은 별)을 좌표로 묶어 같은 분할에 둘지. 지금도 행 번호가 독립이라 갈라질 수 있다. (3) `desi_external`을 서버 앞쪽 채움 문제 때문에 다시 뽑게 된다면(`benchmark/server_fill/`) 그때 B의 "표에 없는 새 객체" 규칙이 처음으로 쓰인다.

## 5. 하지 않은 것, 한계

* 분할 코드·`benchmark_id`·표를 바꾸지 않았다. B는 설계일 뿐 구현하지 않았다.
* 모델 재적합의 영향(정확도가 얼마나 바뀌는지)은 재지 않았다. 재려면 A를 실제로 돌려야 하고 이 과제의 범위 밖이다. 이 문서가 말하는 것은 "바뀌는 객체의 수와 누설 가능성"까지다.
* `validate_star_wd_external.py`가 `lamost_star_external`에 같은 해시를 쓰는지는 처음에 소스의 `split_for` 언급만 보고 가정했다. **Codex 검토(2.62.7)로 틀린 가정임이 드러났다.** 그 도구는 SDSS 표만 train / calibration으로 가르고 외부 표는 전부 예측한다. 그래서 이 표의 "분할 이동"(처음 값 578개 57.8 %, 새 test 중 옛 train 61.8 %)은 존재하지 않는 분할을 잰 것이라 표에서 뺐다(`split_key_impact.py`의 `UNSPLIT`). 같은 좌표 쌍 점검(2행)은 남겼다. 나머지 다섯 표의 범위는 그대로다(바뀌는 객체 55.1–59.3 %, 새 test 중 옛 train 57.8–62.6 %).
* 클래스 층화 없이 해시로 가르므로 작은 표(300행)에서는 클래스 비율이 분할마다 최대 11 %p 흔들린다. 키를 바꿔도 마찬가지다(층화 분할은 별도의 설계 주제).
