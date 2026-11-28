# 과제 머: README·개요·덱·ALGORITHM·세트 C 문서가 인용하는 벤치마크 수치를 커밋된 자료로 다시 센 표 (2.62.7)

**무엇을 했나**: 문서가 적은 표본 크기·영역 수·플레이트 수·정확도 30개를 `doc_claims_check.py`가 커밋된 자료에서 다시 세어 맞음/틀림을 적었다(`doc_claims_check.csv`, 아래 표는 `doc_claims_table.md`와 같다). 문서 자체는 고치지 않았다: README·개요·덱·`LOCKED_TEST_SET_C.md`의 틀린 것은 `v2/document/NEXT_RELEASE_DOCS.md` 7–14번에 넣었고, 내부 문서인 `ALGORITHM.md`(LS-GBM 두 곳, 플레이트 142)와 `build_sdss_sky_truth.py` 머리 주석(플레이트 142)만 지금 고쳤다.

재현: `python v2/benchmark/doc_claims_check.py --out v2/benchmark/doc_claims` (네트워크 필요 없음; 입력은 `run_info.json`에 해시로 남는다). 판정 열: `ok`(문서와 같음), `differs`(다름), `misleading`(숫자는 맞으나 읽기가 오해를 부름), `not recountable`(커밋된 자료로 못 셈), `not recounted`(자료는 있으나 이번에 안 셈).

## 1. 두 불일치의 원인 (git 이력으로 추적)

### 1.1 검증 계획 520개 중 54개가 공개 목록에 없다

* 지금 `reference_objects/validation/plan.csv`의 520개 중 `reference_objects.csv.gz`(14,108행)에 **466개만** 있다. 없는 54개는 7종류에 몰려 있다: QSO_SPECTROSCOPIC 10, DELTA_SCUTI_HADS 10, ECLIPSING_BETA_LYR 10, ROTATIONAL_VARIABLE 10, DELTA_SCUTI 8, CEPHEID_CLASSICAL 4, YSO_VARIABLE 2.
* 2.46.1(85f8853, #54)의 목록에서는 **520개 모두** 있다. 검증 계획은 이 목록에서 뽑았다(종류마다 10개, seed 7).
* 2.46.2(a6d47e1, #55 스쿼시)가 계획·검증과 함께 `reference_objects.csv.gz`(355,276 → 355,356 바이트)와 `REFERENCE_OBJECTS.md`를 **같은 병합에서 바꿨다**. 스쿼시 메시지의 첫 항목이 "Reference objects (literature-confirmed, per type)"로, 2.46.1 당시 `build-reference-objects.yml`이 `github-actions[bot]`으로 커밋하던 메시지와 글자까지 같다(`git show 85f8853:.github/workflows/build-reference-objects.yml`). 2.46.1과 지금 목록을 대면 14,108행의 크기와 종류별 행 수는 같고 **1,686행이 서로 다르다**(QSO_SPECTROSCOPIC 299, ROTATIONAL_VARIABLE 299, ECLIPSING_BETA_LYR 293, DELTA_SCUTI_HADS 281, DELTA_SCUTI 275, CEPHEID_CLASSICAL 204, YSO_VARIABLE 22, CEPHEID_TYPE_II_CWA 13).
* **원인**: 이 종류들은 VizieR 질의의 행 수 상한(`Vizier(..., row_limit=limit)`, `build_reference_objects.py:184`)에 걸리는 큰 목록인데 정렬 키(`ORDER BY`)가 없어 서버가 주는 앞 N행이 실행마다 달라진다. 이것은 과제 파(`WORK_REPORT_2026-11-28a.md`)가 전수 조사한 "순서 없는 TOP/row_limit" 유형이고, 과제 거가 2.62.7에서 막은 재생성 경로(`truth_manifest.py`, 덮어쓰지 않음)가 같은 이유다. 2.46.1 → 2.46.2 사이에 목록이 다시 만들어졌다.
* **기록되지 않은 것**: 그 봇 커밋을 일으킨 트리거. 당시 워크플로의 푸시 트리거는 빌더(`build_reference_objects.py`)나 그 워크플로 파일이 바뀐 푸시에만 걸리는데 #55의 순변경 목록(`git show --stat a6d47e1`)에 둘 다 없으므로 `workflow_dispatch`(손으로 실행)였을 가능성이 크다. 중간 푸시가 빌더를 건드렸다가 되돌렸을 가능성은 스쿼시로 이력이 사라져 배제하지 못한다(추정이지 기록이 아니다).
* **영향**: 점수(blind 89.5 % / 45.8 %, full 87.9 % / 55.0 %, 410/458·202/441·407/463·253/460)는 `reference_validation_summary.csv`에서 정확히 다시 세어진다 = 맞다. 틀린 것은 "520개가 공개 목록의 천체"라는 읽기뿐이다: 그 54개의 문헌 근거(코드·이름·카탈로그)는 `plan.csv`에는 있으나 공개 목록에서는 따라가지 못한다(NEXT_RELEASE_DOCS 11번).

### 1.2 QSO_SPECTROSCOPIC의 검증은 실제로 돌았나

돌았다. `reference_validation_objects.csv.gz`에 10개 행이 있고 `full_rc = blind_rc = 0`(520행 모두 0), 위치는 `plan.csv`의 좌표(RA 0.14–1.51°, 이 목록 안에서는 별도 정답이 아니라 **계획의 좌표**)를 쓴다. 결과는 큰 범주 **blind 8/10, full 9/10**(`REFERENCE_VALIDATION_2026-11-07.md` 67행: 세부 종류는 이 종류에 정의가 없어 "–"). 즉 검증 자체는 유효하지만, 그 10개는 지금 공개 목록(RA 1.60–3.26°, 300행)에 없고 2.46.1 목록(RA 0.0–1.61°)에만 있었다. "10/10"은 결과가 아니라 **공개 목록에 없는 개수**(10 중 10)다.

### 1.3 "플레이트 142개"와 84개

* `benchmark/truth_data/ground_truth.csv`(옛 SDSS 벤치마크 9,999개)의 서로 다른 플레이트는 **84개**이고 클래스별로는 별 51, 은하 7, QSO 84다. `142 = 51 + 7 + 84`가 정확히 맞는다.
* 출처: 과학 검토 `SCIENTIFIC_REVIEW_2026-11-11.md:123`이 클래스별 플레이트 수(은하 3,333개는 7개, 별 51개, QSO 84개 플레이트)를 적었고, 하늘 전체 벤치마크 빌더의 머리 주석(2.51.1, 1f73b81, 2026-11-12)이 이를 "9,999 objects from 142 plates"로 더했다. 이후 README·ALGORITHM·개요·덱이 그 숫자를 옮겼다. 플레이트는 클래스 사이에 겹치므로(별 51개와 은하 7개 플레이트가 모두 QSO 84개 플레이트의 부분집합임을 `ground_truth.csv`에서 확인) 합은 서로 다른 플레이트 수가 아니다.
* 서버 선채움 보고(`benchmark/server_fill/SERVER_FILL_DEPENDENCE_2026-11-28.md` 3절)가 먼저 "이 파일 하나로는 재현되지 않는다"고 적었고, 이 점검이 합으로 설명했다. 은하 "7개 플레이트"는 맞다.

## 2. 전수 표 (30개)

| id | 무엇 | 문서에 적힌 값 | 커밋된 자료로 다시 센 값 | 판정 | 인용 위치 |
|---|---|---|---|---|---|
| sky_objects | sky-spread SDSS benchmark: objects | 9,999 | 9,999 | **ok** | `README.md:138`, `v2/ALGORITHM.md:167`, `v2/document/overview_content.py:443` 외 2곳 |
| sky_per_class | objects per class | 3,333 | 3333/3333/3333 | **ok** | `README.md:138`, `v2/ALGORITHM.md:170`, `v2/document/overview_content.py:444` 외 2곳 |
| sky_cells | equal-area sky cells | 768 | 355 occupied (STAR 355, GALAXY 261, QSO 263) | **misleading** | `README.md:138`, `README.md:164`, `v2/ALGORITHM.md:169` 외 5곳 |
| sky_accuracy | sky-spread benchmark accuracy (fusion) | 93.79 % (93.24-94.30) | 93.79 % (93.24-94.30) | **ok** | `README.md:138`, `v2/ALGORITHM.md:167`, `v2/document/overview_content.py:443` 외 4곳 |
| sky_recalls | recall STAR / GALAXY / QSO | 98.7 / 98.5 / 84.1 % | 98.7 / 98.5 / 84.1 | **ok** | `README.md:138`, `v2/document/overview_content.py:444`, `v2/document/deck_content.py:342` |
| sky_r21 | r > 21: accuracy, QSO recall, star precision | 87.99 %, 71.6 %, 69.9 % | 87.99 %, 71.6 %, 69.9 % | **ok** | `README.md:138`, `v2/document/overview_content.py:444`, `v2/document/deck_content.py:343` 외 1곳 |
| sky_lowb | |b| < 20 deg: accuracy, galaxies, QSOs | 96.09 %, 32 galaxies, 49 QSOs | 96.09 %, 32 galaxies, 49 QSOs (537 objects) | **ok** | `README.md:138`, `v2/document/overview_content.py:444`, `v2/STATUS_2026-11-12.md:118` |
| sky_plates | sky-spread benchmark: SDSS plates per class | 1,957-2,533 plates | 1,957-2,533 (STAR 1,957, QSO 2,137, GALAXY 2,533); 4,821 distinct | **ok** | `v2/ALGORITHM.md:169`, `v2/STATUS_2026-11-12.md:94` |
| old_sdss_test | old SDSS benchmark, test split | n = 1,991 | n = 1,991 | **ok** | `README.md:143`, `v2/ALGORITHM.md:165`, `v2/document/overview_content.py:473` 외 1곳 |
| old_desi_test | DESI external benchmark, test split | n = 962 | n = 962 | **ok** | `README.md:143`, `v2/ALGORITHM.md:166`, `v2/document/overview_content.py:473` 외 1곳 |
| old_plates | SDSS plates of the old benchmark | 142 plates (7 for galaxies) | 84 distinct plates (7 for galaxies; per class STAR 51, GALAXY 7, QSO 84); 142 = the sum of the three per-class counts | **differs** | `README.md:143`, `v2/ALGORITHM.md:89`, `v2/ALGORITHM.md:170` 외 2곳 |
| old_sdss_acc | old SDSS / DESI test accuracy | 97.99 % / 90.33 % | not recountable | **not recountable** | `README.md:143`, `v2/ALGORITHM.md:137`, `v2/ALGORITHM.md:165` 외 5곳 |
| setc_n | locked test set C: objects, accuracy | 3,162 objects, 99.65 % (99.40-99.86) | 3,162 objects, 99.65 % (99.40-99.86) | **ok** | `README.md:137`, `v2/document/overview_content.py:437`, `v2/document/deck_content.py:335` 외 3곳 |
| setc_regions | locked test set C: regions | 60 regions | 60 scored, 59 with truth (pools: clam 30, cpln 11, csth 18) | **ok (60 scored; 59 have truth)** | `README.md:137`, `README.md:163`, `v2/document/overview_content.py:435` 외 8곳 |
| setc_classes | locked test set C: share of stars, galaxies, QSOs | 95.26 % stars; about 143 galaxies and 7 QSOs | 95.26 % stars (3012), 143 galaxies, 7 QSOs | **ok** | `README.md:137`, `v2/document/overview_content.py:438`, `v2/document/deck_content.py:336` 외 1곳 |
| setc_pools | set C by pool: low latitude / south / LAMOST sky | 99.89 % (11 regions, 879), 99.08 % (218), 99.61 % (2,065) | 99.89 % (11 regions, 879), 99.08 % (218), 99.61 % (2,065) | **ok** | `README.md:137`, `v2/document/overview_content.py:438`, `v2/benchmark/LOCKED_TEST_SET_C.md:103` 외 2곳 |
| setc_dsc | set C: Gaia DSC coverage, DSC alone, pipeline on the same objects | 98.0 %, 99.52 %, 99.81 % | 98.0 %, 99.52 %, 99.81 % | **ok** | `README.md:137`, `v2/document/overview_content.py:438`, `v2/document/deck_content.py:337` 외 3곳 |
| cosmos17 | COSMOS, 17 new fields: objects, accuracy, ECE | 16,057 and 16,757; 96.68 % and 96.75 %; ECE 0.37 and 0.33 % | 16,057 and 16,757; 96.68 % and 96.75 %; ECE 0.365 and 0.331 % | **ok** | `README.md:141`, `v2/document/overview_content.py:461`, `v2/document/deck_content.py:353` |
| cosmos_test_fields | COSMOS test fields (2.52.0): objects, accuracy before / after the prior layer, ECE | 12,245; 96.36 % (was 94.48 %); ECE 0.37 % (was 1.52 %) | 12,245; 96.36 % (was 94.48 %); ECE 0.365 % (was 1.516 %) | **ok** | `README.md:140`, `v2/document/overview_content.py:455` |
| cosmos9 | COSMOS, 9 deep fields (2.51.0): objects, accuracy | 28,194 objects, 94.31 % (91.09 % always GALAXY) | 2.52.0 report of the same fields: 28,195 objects, base label accuracy 94.30 % | **differs by 1 object / not recountable for 2.51.0** | `README.md:59`, `README.md:87`, `README.md:139` 외 7곳 |
| gbm_rows | LS-GBM: DESI spectra it was trained on | 149,769 | 149,769 rows in train.csv.gz; the fit used 132,207 (+ 14,447 held out = 146,654) | **differs** | `README.md:76`, `v2/ALGORITHM.md:122`, `v2/document/overview_content.py:267` 외 1곳 |
| gbm_acc | LS-GBM test accuracy | 95.6 % | hold-out 96.0 % (96.0 % weighted over the r bins; 95.6 % is the 21-22 bin) | **differs** | `README.md:76`, `v2/ALGORITHM.md:122`, `v2/document/overview_content.py:267` 외 1곳 |
| hc17 | r > 22 high-confidence GALAXY on the 17 new COSMOS fields: flagged objects, purity, 84 % lower bound | 24,169 flagged; purity 0.983 (0.982) | 24,169 flagged (calibration 11,868 + test 12,301); purity 0.9831 (0.9822, pooled row) | **ok** | `README.md:151`, `v2/document/overview_content.py:498` |
| ref520_scores | 520 literature-confirmed objects: blind / full coarse-class and sub-type accuracy (2.47.0) | blind 89.5 % / 45.8 %; full 87.9 % / 55.0 % | blind 89.5 % (410/458) / 45.8 % (202/441); full 87.9 % (407/463) / 55.0 % (253/460) | **ok** | `README.md:127`, `README.md:214`, `v2/document/overview_content.py:408` 외 2곳 |
| ref520_design | 520 objects, 52 types, 10 each | 520, 52, 10 each | 520 plan rows, 52 types, 10-10 each | **ok** | `README.md:127`, `README.md:311`, `v2/document/overview_content.py:408` 외 2곳 |
| ref520_in_list | the 520 validated objects are objects of the published reference list (reference_objects.csv.gz) | implied (the list is the source of the 520) | 466 of 520 plan objects are in the published list today (520 of 520 in the 2.46.1 list) | **differs** | `README.md:311`, `v2/document/overview_content.py:868`, `v2/benchmark/LOCKED_TEST_SET_C.md:6` |
| cand_purity | 'QSO?' candidate flag on the 21 deep COSMOS fields: purity, recall | purity 29/119 = 24 % (18-33 %), recall 47/97 = 48 % (39-58 %) | not recounted in this pass | **not recounted** | `README.md:154`, `v2/ALGORITHM.md:184`, `v2/document/overview_content.py:511` 외 1곳 |
| agn33 | type-1 AGN at r >= 24 that received the QSO label | none of 33 | not recounted in this pass | **not recounted** | `README.md:157`, `v2/document/overview_content.py:526` |
| lit_only_2361 | COSMOS 2' field: objects with only a NED or SIMBAD type | 2,361 of 3,621 (2.54.0) | not recounted in this pass | **not recounted** | `README.md:158`, `v2/document/overview_content.py:530`, `v2/document/deck_content.py:267` |
| indep_fields | independent blind fields, sets A and B: objects | 24,663 objects (200 regions each) | not recountable | **not recountable** | `README.md:142`, `v2/document/overview_content.py:467`, `v2/document/deck_content.py:358` |

## 3. 한계

* 맞다고 적힌 것은 **커밋된 자료 안에서** 다시 센 것이다. `not recountable` 2개(옛 SDSS/DESI 2.52.0 정확도 97.99 / 90.33 %: 2.52.0 분류기가 커밋되어 있지 않다; 독립 블라인드 영역 24,663개: 원자료가 `validation-data` 브랜치에만 있다)는 점검하지 못했다. `not recounted` 3개(`QSO?` 후보 순도 29/119·재현율 47/97, X선 type-1 AGN 33개 중 0, 2.54.0의 2,361 / 3,621)는 자료는 있으나 깊은 영역의 2.54.0 / 2.56.0 분류 출력을 다시 돌려야 해 이번에 하지 않았다.
* 표는 README 7–9절과 개요·덱의 해당 표를 훑어 고른 30개이고, README 8절의 서술형 수치(예: 0.51–0.81 %, 3–7배)는 포함하지 않았다.
* ECE는 문서의 0.37 / 0.33 %를 소수 셋째 자리(0.365 / 0.331)로 반올림 안에서 맞는 것으로 적었다.
