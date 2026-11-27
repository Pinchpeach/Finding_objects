# 작업 보고서 2026-11-27c — 둘 이상의 카탈로그가 같은 이름으로 내는 "접두어 없는 열" 정리 (2.61.4)

계획 세션 지시서 "2.61 후속" 과제 마. Stage 2 통합표에는 모든 원래 열이 `<카탈로그>__<열>`로 있고, 그 옆에 접두어 없는 이름(`type`, `pmra`, `objid`, `_r`, `RAJ2000` …)의 열이 한 벌 더 있었다. 후자는 "그 객체의 그룹 안에서 처음 유효한 값"이라서, 두 카탈로그 이상이 같은 이름으로 내는 열은 **어느 카탈로그의 값인지 알 수 없고 그룹의 행 순서에 따라 달라졌다**. 이 이름들의 접두어 없는 열을 더 이상 쓰지 않고(80개), 읽는 코드가 카탈로그 접두어가 붙은 열을 읽게 했다. 분류 결과는 같다.

## 1. 한 줄 결과

- **분류 결과 동일**: 입력 320개(저위도 309 + 깊은 COSMOS 8 + 실사용 3), 객체 **380,492개**에서 전/후 코드의 `primary_class`·`classification_status`·`classification_basis` 차이 **0**, `p_star`·`p_galaxy`·`p_qso` 최대 변화 **0.0**. 달라진 열은 `rule_feature_coverage`(정보용 개수) 하나뿐이다.
- **열 수**: 입력당 19–63개(전체 열의 1.8–4.7 %, 중앙값 3.0 %)가 사라진다. 예: NGC 4522 2′ 1,648 → 1,587(−61), COSMOS 2′ 2,512 → 2,457(−55), 은하면 1′ 832 → 812(−20), 깊은 COSMOS 6′ 2,467–3,005 → 2,410–2,942(−50…−63).
- **공용 이름 80개**를 표로 만들었다(`benchmark/shared_columns/shared_columns.csv`): 어느 카탈로그들이 내는지, 코드 어디서 읽는지, 바꾼 것, 앱·요약·시험 의존성. 접두어 없는 열을 **직접 읽던 실행 코드는 6곳**이고 그중 3곳을 고쳤다(2절).
- **앱·요약표는 영향 없음**: `objects_summary.csv`(29열)에 공용 이름이 하나도 없고 앱은 접두어 열 또는 객체 단위 열을 읽는다. 앱 시험 포함 전체 시험 468개 통과.
- 되돌리기: `V2_KEEP_SHARED_BARE=1`이면 예전 열을 다시 쓴다(A/B, 외부 스크립트).

## 2. 무엇이 문제였나 (왜 고쳤나)

예전 Stage 2는 raw 필드마다 `rec["<접두어>__<열>"] = 값`을 쓰고, 이어서 `if 열 not in rec or 비어 있음: rec[열] = 값`을 했다. 열 이름이 한 카탈로그에만 있으면 접두어 없는 열은 그 카탈로그의 값이라 모호하지 않다(`W1mag` = AllWISE). 두 카탈로그 이상이 같은 이름으로 내면(예: `type` = Legacy Surveys 문자열 "PSF"와 SDSS 정수 3, `pmra` = Gaia와 SIMBAD, `RAJ2000` = 7개 카탈로그) **그룹의 처음 값이 이긴다**. 2.61.0에서 그룹 행 순서는 정해졌지만(밝기 기준) 어느 카탈로그가 이기는지는 여전히 우연이고, 읽는 쪽은 알 수 없다. 코드를 훑어 접두어 없는 열이 다른 카탈로그 값으로 읽힐 수 있는 자리를 찾았다.

| 자리 | 무슨 일이 생길 수 있었나 | 고침 |
|---|---|---|
| `Classifier/branches/star.py:_gaia_num` | Gaia 행이 없는 객체에서 접두어 없는 `pmra`(= SIMBAD의 것)를 Gaia 고유운동으로 읽음 | `gaia_dr3__` 열만 읽음 |
| `Classifier/subclass.py:669` `star_tags` | 같은 이유로 SIMBAD의 `pmra`/`pmdec`로 접선 속도를 계산해 THICK_DISC/HALO 태그를 붙일 수 있음 | `gaia_dr3__pmra/pmdec`만 읽음 |
| `Classifier/validate_real_samples.py:science_snapshot` | `pmra`/`pmdec`를 접두어 없는 열에서 | 키 이름은 그대로 두고 `gaia_dr3__` 열에서 읽음 |
| `Preprocess/coarse_gbm.py:71` | LS 점광원 여부를 `desi_legacy_surveys_dr10__type`이 표에 없으면 접두어 없는 `type`에서 읽음: LS 행이 하나도 없고 SDSS 행이 있는 영역에서 SDSS의 정수 `type`("3"·"6")을 읽어 `ls_psf`가 NaN(모름) 대신 0(PSF 아님)이 됨 | 코드 그대로(폴백은 벤치마크의 한 카탈로그 표를 위한 것): 접두어 없는 열이 없어지면 폴백이 비어 NaN이 됨 |
| `Preprocess/03_extract_features.py:333` `field("ned","Type")` | NED 접두어가 표에 없으면 접두어 없는 `Type`을 받아들여 전부 빈 `catalog_confidence_ned_type` 열을 만듦(입력 95개에서) | 코드 그대로: 폴백이 비게 되어 그 열이 더는 생기지 않음 |
| `Preprocess/04_build_evidence.py` `CatalogFields` | 표에 그 카탈로그 접두어가 하나도 없으면 접두어 없는 이름으로 폴백 | 코드 그대로(독스트링만 갱신): 공용 이름은 비어 있게 됨 |

**주의: 이 중 라벨을 바꾼 것은 확인되지 않았다.** 위 6곳이 실제로 다른 카탈로그 값을 읽은 객체가 있었는지는 이번 380,492개 객체에서 전/후 라벨 차이 0이라는 사실로만 말할 수 있다(= 이 표본에서는 없었거나 라벨을 못 바꿨다). 그래서 이 변경의 근거는 "버그를 고쳤다"가 아니라 "읽는 값의 출처를 알 수 있게 했고, 출처 불명의 값을 읽을 수 있던 자리를 닫았다"이다.

## 3. 공용 이름 80개 (`shared_columns.csv`)

접두어가 다른 raw 파일 30종(깊은 COSMOS 26개 영역, 저위도 309개 영역, 실사용 3곳, 저장소의 NGC 4522 파일)의 머리글에서 둘 이상이 내는 이름을 모았다. 읽는 곳별로:

| 묶음 | 이름 | 읽는 곳 |
|---|---|---|
| 위치·오차 | `RAJ2000` `DEJ2000` `_RAJ2000` `_DEJ2000` `RA_ICRS` `DE_ICRS` `RAICRS` `DEICRS` `GLON` `GLAT` `e_RAJ2000` `e_DEJ2000` `ePos` `poserr_arcsec` | `04_build_evidence.py:482,548`이 WISE 규칙의 R90 하늘 판정에 AllWISE의 `RAJ2000`을 `CatalogFields`로 읽음(접두어 있음); `poserr_arcsec` 등은 1단계가 raw 행에서 읽음. 나머지는 읽는 곳 없음 |
| 유형·식별 | `type` `Type` `objid` `objID` `ID` `Name` `Source` `recno` `Field` `Mosaic` | `type`: 4단계 SDSS 규칙(`CatalogFields`), coarse_gbm 폴백; `Type`: 4단계 NED 규칙, 3단계 `field()`; `objid`: 정수 dtype 처리(`table_io.ID_NAMES`)와 1단계 |
| 고유운동·시차 | `pmra` `pmdec` `pmRA` `pmDE` | `star.py`, `subclass.py`, `validate_real_samples.py`(2절, 고침); 3·4단계는 `gaia_dr3__` 접두어로 읽음 |
| 측광 | `Jmag` `Hmag` `Kmag` `e_Jmag` `e_Hmag` `e_Kmag` | `units.py:118`이 2MASS와 AllWISE의 접두어 열을 읽음 |
| 선 플럭스·EW | `line_ha_*` `line_hb_*` `line_nii6584_*` `line_oiii5007_*` `line_source` (12개) | `subclass.py:1271`이 `{접두어}line_ha_ew`로 읽음 |
| 그 밖 | `z` `e_z` `MJD` `mjd` `B_MJD` `b_MJD` `PA` `e_PA` `fPA` `Maj` `Min` `e_Maj` `e_Min` `Fpeak` `Fr` `Nd` `Nr` `Obs` `r1` `_r` `DCMaj` `DCMin` `DCPA` `e_DC*` `Islrms` `SCode` `Speak` `e_Speak` `psf_fwhm_arcsec` `query_radius_arcmin` | 읽는 곳 없음(1단계가 `psf_fwhm_arcsec`·`query_radius_arcmin`을 raw 행에서 읽음) |
| 객체 단위로 남는 것 | `entity_kind` `ref_epoch` | raw 필드로서는 공용이지만 Stage 2가 객체 단위 값을 **자기 열로** 쓰므로 접두어 없는 열이 남는다(raw 사본은 접두어 열만) |

시험(`test_shared_columns.py`)이 표의 이름 집합 = 코드의 `SHARED_FIELDS`임을 지킨다.

## 4. 설계와 이유

**구조.** `SHARED_FIELDS`(고정 80개) ∪ 이번 실행 raw 파일 머리글에서 **서로 다른 카탈로그** 둘 이상이 가진 이름(`shared_fields()`). 복사 루프에서 `col in shared`이면 접두어 없는 열을 쓰지 않는다(`02_integrate_objects.py`).

- *고정 목록과 머리글 검사를 합친 이유*: 고정 목록만이면 앞으로 추가될 수집기(예: 새 전파·적외선 목록)가 같은 이름을 써도 모르고 지나간다. 머리글만이면 어느 아카이브가 응답했는지에 따라 **출력 열 집합이 달라진다**(한 카탈로그가 비어 있으면 그 이름이 "공용"이 아니게 됨). 합집합이면 알려진 이름은 늘 같고 새 이름은 처음 실행에서 잡힌다. 실제로 첫 후보 목록(58개)이 빠뜨린 22개(`ID`, `Nr`, `e_Maj` …)를 머리글 검사가 잡았고, 그것들을 고정 목록에 넣어 80개로 늘렸다. 마지막 동일성 검사에서 고정 목록 밖으로 사라진 열은 `catalog_confidence_ned_type`(파생 열) 하나뿐이었다.
- *고정 규칙으로 한 카탈로그의 값을 고르는 안은 버림*: "`type`은 LS 우선"이라는 순서가 어디선가 암묵 결합이 된다(어느 읽기가 어느 카탈로그를 원하는지는 읽는 쪽마다 다르다). 접두어 열은 이미 모든 값을 갖고 있으므로 읽는 쪽이 원하는 것을 이름으로 지정하는 것이 더 단순하다.
- *접두어 없는 열 전부 제거는 버림*: 한 카탈로그에만 있는 이름은 모호하지 않고, 벤치마크의 한 카탈로그 표(`catalog_features`)와 `CatalogFields`·`coarse_gbm`의 폴백이 접두어 없는 이름을 쓴다. 공용 80개만 지우면 열의 약 3 %가 줄고 위험이 있던 자리는 모두 닫힌다.
- *읽는 코드는 Gaia 3곳만 고침*: 나머지는 이미 접두어를 읽거나(3·4단계, `units.py`, `variability.py`) 폴백이 한 카탈로그 표용이라서 접두어 없는 열이 없어지면 자동으로 비게 된다. 폴백을 지우면 벤치마크의 한 카탈로그 표를 읽는 길이 깨지므로 지우지 않았다(`coarse_gbm.features` 독스트링에 이유 기록).
- *`V2_KEEP_SHARED_BARE=1`*: 외부 스크립트가 접두어 없는 열에 기대고 있다면 되돌릴 수 있고, 전/후 A/B가 같은 코드로 된다(시험 포함).

## 5. 동일성 검증 (`benchmark/shared_columns/equivalence.py`, `results_2026-11-27/`)

같은 raw 폴더를 **2.61.3 코드(`git worktree`)와 이번 코드**로 오프라인 분류해(`pipeline.py --raw-dir`, 같은 해시 시드, 캐시 끔) 비교했다.

| 입력 | 개수 | 객체 | 라벨·상태·근거 차이 | p 최대 변화 | 열 전 → 후 (중앙값) | 사라진 열 (최소–최대) |
|---|---|---|---|---|---|---|
| 확인용 저위도 영역 | 140 | 130,551 | 0 | 0.0 | 1,006 → 963 | 19–57 |
| 보정용 저위도 영역 | 169 | 163,502 | 0 | 0.0 | 1,010 → 975 | 19–55 |
| 깊은 COSMOS 6′ | 8 | 81,669 | 0 | 0.0 | 2,851 → 2,798 | 50–63 |
| 실사용 3곳(NGC 4522, COSMOS 2′, 은하면 1′) | 3 | 4,770 | 0 | 0.0 | 1,648 → 1,587 | 20–61 |
| 합계 | 320 | **380,492** | **0** | **0.0** | | |

- 저위도 309개 영역은 카탈로그 구성이 다양하다(LS 영역 밖이 많음, 일부는 SDSS·NED 없음): 폴백이 다른 카탈로그 값을 잡을 수 있던 조건을 많이 포함한다.
- **병합 뒤 다시 확인**: main(2ce3ba2 = 검토를 거친 2.61.3)을 병합한 최종 트리를 main과 견주었다(입력 68개 = 실사용 3 + 깊은 COSMOS 2 + 저위도 63, 객체 83,657개): 라벨·상태·근거 차이 0, p 변화 0, 달라진 열 `rule_feature_coverage`뿐, 사라진 열 19–61개(`benchmark/shared_columns/results_2026-11-27/equivalence_vs_main_2ce3ba2.csv`).
- 사라진 열: 이름이 있는 78개 공용 열(접두어 없는 열) + 빈 파생 열 `catalog_confidence_ned_type` 1개(95개 입력). 새로 생긴 열 0.
- **다른 열이 달라진 것은 `rule_feature_coverage` 하나**(320개 입력 모두): 규칙 입력 열 중 값이 있는 열의 개수(정보용)라 접두어 없는 열이 사라지면 그만큼 준다(실사용 3곳에서 바뀐 객체는 정확히 1씩 줄었다). 이 열을 읽는 코드는 `03_extract_features.py` 안의 기록뿐이다.
- 로컬 벤치마크(`validate_catalog_truth.py` + `evaluate_rule_baseline.py`, CLAUDE.md 명령): 전/후 출력 3개 파일의 md5가 같다(1,991행). 이 벤치마크는 카탈로그별 특징표라 Stage 2를 거치지 않으므로 "한 카탈로그 표가 접두어 없는 이름을 계속 읽는다"는 확인이다.
- 시험: 468개 통과(새 시험 8개: `test_pipeline_smoke.py` 4개(옛 시험은 "첫 값이 이긴다"를 단언하던 것을 새 동작으로 고침), `test_shared_columns.py` 3개, `test_subclass.py` 1개).

## 6. 외부 영향

- 출력 표(`integrated_objects.csv`, `features.csv`, `evidence.csv`, `likelihood_vectors.csv`, `classifier_input.csv`, `classified_objects.csv`)에서 위 80개 이름의 접두어 없는 열이 없다(`entity_kind`, `ref_epoch`는 객체 단위 값으로 남음). `type`/`pmra` 등을 접두어 없이 읽던 **외부 스크립트**는 `desi_legacy_surveys_dr10__type`처럼 접두어 열을 읽거나 `V2_KEEP_SHARED_BARE=1`을 써야 한다.
- 앱(`app/`): 공용 이름을 읽는 곳이 없다(전수 검색, 앱 시험 통과). 화면을 직접 띄워 보지는 않았다.
- 요약표 `objects_summary.csv`: 29열, 공용 이름 없음.
- 커밋된 검증표(`Classifier/validation/real_sample_validation.csv`): 다시 만들지 않았다(살아 있는 아카이브가 필요). `science_json`의 `pmra`/`pmdec`는 Gaia 값을 쓰게 되었으므로 Gaia 행이 없는 객체에서 SIMBAD의 값이 사라진다.
- 문서: `ALGORITHM.md` 통합 절, `benchmark/shared_columns/README.md`.

## 7. 한계

- 목록은 이번 raw 파일 30종의 머리글에서 모았다. 수집기가 늘면 머리글 검사가 잡지만, 표(`shared_columns.csv`)는 `build_table.py`로 다시 만들어야 한다.
- 동일성은 라벨·확률·열에 대한 것이다. 접두어 없는 열을 읽는 **외부** 코드는 우리가 볼 수 없다.
- 위 6곳이 실제로 다른 카탈로그 값을 읽은 객체의 수는 재지 않았다(라벨 차이가 0이라 라벨에는 영향이 없었다는 것만 안다). 읽던 값이 틀린 채로 라벨이 안 바뀐 경우는 이번 표본에서 구분하지 않았다.
- `rule_feature_coverage`의 의미는 "개수"이므로 이전 실행의 값과 직접 비교하면 줄어 보인다.

## 8. 번호

라벨이 바뀌지 않으므로 PATCH(2.61.4)로 올렸다. 다만 **출력 표의 열이 바뀌는 인터페이스 변화**이므로 검토 세션이 MINOR로 판단할 수 있다(그 경우 번호는 검토 세션이 다시 매긴다).

## 9. 산출물

코드: `Preprocess/02_integrate_objects.py`(`SHARED_FIELDS`, `shared_fields`, `V2_KEEP_SHARED_BARE`), `Classifier/branches/star.py`, `Classifier/subclass.py`, `Classifier/validate_real_samples.py`(+ 독스트링 `04_build_evidence.py`, `coarse_gbm.py`). 시험: `test_shared_columns.py`, `test_pipeline_smoke.py`, `test_subclass.py`. 표·도구: `benchmark/shared_columns/{shared_columns.csv, shared_candidates.json, build_table.py, equivalence.py, README.md, results_2026-11-27/}`.
