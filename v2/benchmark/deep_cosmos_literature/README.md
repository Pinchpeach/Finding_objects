# 깊은 COSMOS 26개 영역의 NED·SIMBAD 행 (2.62.7, 과제 더)

**목적**: 지금까지의 문헌(NED·SIMBAD) 행 측정은 실사용 COSMOS 2′ 한 영역에서만 했다(`WORK_REPORT_2026-11-28b.md`). 깊은 COSMOS 26개 영역의 묶음(`v2_deep_cosmos.yml`)은 블라인드라 NED·SIMBAD 행이 없다.
이 폴더의 도구는 그 26개 영역의 문헌 행만 따로 모으고, 저장된 블라인드 행 옆에 **오프라인에서** 붙여 1단계를 다시 돌릴 수 있게 한다. **이 세션은 수집을 실행하지 않았다**(서비스에 접속할 수 없고, 워크플로 실행은 검토 세션의 일이다).

| 구성 | 파일 | 하는 일 |
|---|---|---|
| 수집 워크플로 | `.github/workflows/v2_deep_cosmos_literature.yml` | `workflow_dispatch` 전용. 계획 → **스키마 점검(probe)** → 영역별 수집(동시 2개, 요청마다 3–5초 대기) → `validation-data` 브랜치의 `deep_cosmos_lit/<run id>/<field>/`에 저장(`push_with_retry.sh`). 블라인드 묶음(`deep_cosmos1/`, `deep_cosmos2/`)은 건드리지 않고, Gaia 가용 확인에 묶여 있지 않다 |
| 수집기 | `benchmark/collect_deep_cosmos_literature.py` | SIMBAD: 일반 수집기의 행 + `coo_qual`·`otypes`(요청 1개 더). NED: 일반 수집기의 행 + `NEDTAP.objdir`의 `uncmaja/uncmina/uncposa`를 이름으로(실패하면 0.3″ 위치로) 붙임. `probe`는 두 서비스의 표 목록을 읽어 필요한 열·단위가 다르면 실패 |
| 오프라인 병합 | `benchmark/merge_deep_cosmos_literature.py` | 블라인드 `raw/<tag>/`의 **복사본**에 두 파일을 더한 새 디렉터리를 만든다. 블라인드 파일은 쓰지 않고(전후 SHA-256 비교), 이미 SIMBAD·NED 파일이 있는 묶음과 끝나지 않은 영역은 거부 |
| 분석 | `analyse_deep_cosmos_literature.py` | 문헌 전용 몫, 가장 가까운 탐사 객체까지의 거리(무작위 대조군과 비교), 변형별 새 연결과 다리 정답, 열 채움 비율. COSMOS 2′의 저장 자료에서 `typed_close`의 126행·55 / 0 / 71·0.6″ 밖 17행을 그대로 재현함을 확인했다 |
| 스위치 | `V2_ANNOT_ASSOC=qual`, `ned_unc` (`association_model.py`, 기본 꺼짐) | SIMBAD `coo_err_maj`(mas → ″)를 `coo_qual` 등급의 하한으로 받쳐 읽기; NED 타원 장반경 / 2.448 |
| 예측 | `PREDICTIONS_2026-11-28.md` | 실행 전에 적은 D1–D8 |

## 스키마 사실 (2026-11-28, 서비스의 표 목록 원문을 에이전트가 읽음; 기억이 아님)

| 항목 | 읽은 것 | 상태 |
|---|---|---|
| NED TAP 표 | `https://ned.ipac.caltech.edu/tap/tables`: `NEDTAP.objdir`(view), `prefname` CHAR(30), `ra`·`dec` deg, `uncmaja`·`uncmina` arcsec("Uncertainty Ellipse, Semimajor / Semiminor Axis in arcseconds"), `uncposa` deg("PA in degrees (East of North)"), `objid`, `pos_bibcode` | 확인함 |
| NED 타원의 신뢰 수준 | 그 페이지에 없음 (`95%`라는 말이 없다). 이전 문헌 확인은 NED FAQ가 95 %라고 했으나 이번에 다시 읽지 않음 | **확인 못 함** |
| NED `prefname` = 콘 검색의 'Object Name' | 어느 페이지에도 없음 | **확인 못 함**: 수집기가 이름 일치율을 `literature_state.json`에 적고, 이름이 안 맞는 행은 위치(0.3″)로 붙인다 |
| NED TAP sync 주소 | `/tap/` 페이지는 가용성만 답함. `https://ned.ipac.caltech.edu/tap/sync`는 표준 경로 | **확인 못 함**: 첫 실행에서 실패하면 상태 파일에 남는다 |
| SIMBAD `basic` | (Harvard 거울에서 읽음; CDS 호스트는 그날 404) `coo_err_maj`·`coo_err_min` REAL **mas**, `coo_err_angle` SMALLINT deg, `coo_qual` CHAR(1), `coo_wavelength` CHAR(1)(R, I, V, U, X, G), `coo_bibcode` CHAR(19), `otype` | 확인함 |
| SIMBAD `otypes` | `basic`의 열이 아니라 **별도 표**(`otypes.oidref` → `basic.oid`). 파이프로 이은 열 하나는 뷰 `alltypes`(`alltypes.otypes`) | 확인함 |
| SIMBAD `coo_qual`의 등급 값 | 이 읽기에서는 "Coordinate quality"만; A–E의 오차 구간(B 0.01–0.1″, C 0.1–1″, D 1–10″, E ≥ 10″)은 이전 문헌 확인(SIMBAD 도움말)에서 | 이번에 다시 읽지 않음 |

**NED 불확실성을 TAP으로 못 얻을 때의 대안**: (a) NED 콘 검색 행만 쓰고 불확실성을 기본 0.6″로 둔다(지금의 상태; `ned_unc`는 꺼진 채). (b) `astroquery.ipac.ned`의 객체별 위치 표(`Ned.get_table(name, table="positions")`)는 객체마다 요청 1개라 영역당 1,500개 가까운 요청이 되어 3–5초 대기 규칙과 맞지 않는다. (c) 위치 불확실성을 문헌 카탈로그가 제공하는 값(COSMOS2020의 위치 오차 등)으로 대신하는 것은 이 과제의 질문(문헌 자신의 불확실성)과 다르다. 그래서 (a)를 기본으로 두고, probe가 통과하면 TAP을 쓴다.

## 실행 순서 (검토 세션)

1. `v2_deep_cosmos_literature.yml`을 `validation-data`가 아니라 **작업 가지에서** dispatch한다(코드는 작업 가지에 있다; 데이터는 워크플로가 `validation-data`에 커밋한다). 먼저 `only`에 영역 하나(예: `deep_cosmos_1`)로 시험한다. `probe` 단계가 실패하면 로그의 `schema_probe.json`을 보고 스키마가 달라진 것이다.
2. 블라인드 묶음(`deep_cosmos1/<run>/*.tar.gz`, `deep_cosmos2/<run>/*.tar.gz`)을 풀어 `BLIND/<field>/raw/<tag>/`로 둔다.
3. `python v2/benchmark/merge_deep_cosmos_literature.py --blind-root BLIND --literature-root LIT --out MERGED`
4. 변형별 1단계: `python v2/benchmark/association_truth/run_variant.py --fields-root MERGED --out RUNS/base` (그리고 `--env V2_ANNOT_ASSOC=typed_close` → `RUNS/typed_close`, `--env V2_ANNOT_ASSOC=err` → `RUNS/err`, `--env V2_ANNOT_ASSOC=qual,ned_unc` → `RUNS/qual_ned_unc`). `V2_POSERR_UNITS`는 기본(`legacy`)으로 둔다.
5. `python v2/benchmark/deep_cosmos_literature/analyse_deep_cosmos_literature.py --runs RUNS --merged-root MERGED --truth-flux TRUTH_FLUX_DIR --out OUT`
6. `surveys2` / `lit_keep` 관계(위도 제한을 푼 채): `python v2/benchmark/lowlat_qso/faint_cost.py classify --deep MERGED --fields-file v2/benchmark/deep_cosmos_confirmation/fields_all26.csv --variants base surveys2 surveys2_litkeep typed_close_surveys2_litkeep` 후 같은 도구의 `tables`.

수집기의 기본 출력은 바뀌지 않았다(`Get_data/simbad.py`의 열은 그대로, 시험이 고정). 블라인드 결과 파일은 어느 단계에서도 덮어쓰지 않는다.
