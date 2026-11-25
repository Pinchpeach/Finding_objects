# Gaia DR4 전환 준비 (2026-11-25, 2.60.6)

DR4는 2026-12-02 약 12:00 CET에 공개된다. Gaia ESA 아카이브는 2026-11-25 12:00 CET부터 그때까지 중단이고, 그동안 Gaia는 VizieR I/355 사본(DR3)으로 온다(2.57.0). 이 문서는 **전환을 하기 전에** 세 가지를 정해 둔다: ① 우리 코드가 Gaia의 어떤 열과 어떤 DR3 가정에 기대는지(3절), ② DR4가 무엇을 바꾸는지(`LITERATURE_GAIA_DR4_2026-11-25.md`), ③ 무엇을 어떻게 재고 무엇이 나쁘면 DR3에 머무는지(4절 프로토콜). **4절은 DR4 자료를 본 뒤에 바꾸지 않는다**(바꾸면 5절 개정 기록에 날짜와 이유를 적는다). 실제 전환과 짝 비교는 12-02 이후 별도 지시로 한다.

## 1. 요약

- **DR3 의존은 넓다.** 수집기 3개(+ XP 계수 도구), 증거 규칙 6개와 그 입력, 융합·사전확률 상수 6개, 세부 분류 모듈 5개, 축 4개, 학습된 모델과 보존된 특징 자료가 Gaia DR3 값에 묶여 있다(3절).
- **가장 큰 위험 다섯 개**(초안 데이터 모델 직접 확인):
  1. **`source_id`가 릴리스 사이에 유지되지 않는다.** DR3 `source_id`를 키로 쓰는 외부 표(`gedr3spur.main` fidelity, VizieR 사본)는 DR4 천체에 맞지 않는다. fidelity 규칙 입력은 DR4에서 비게 된다.
  2. **`phot_bp_rp_excess_factor`가 초안 어디에도 없다.** C* 판정(AST 규칙 태그, 호스트 묶기, 별 가지의 호스트 확인, 뜨거운 준왜성 판정)이 DR4 열 그대로는 불가능하다. 플럭스로 계산할 수 있어도 통과대역이 바뀌어 Riello+2021 계수를 그대로 쓸 수 없다.
  3. **시차 영점이 상수에서 천체별 값(`tentative_parallax_bias`)으로 바뀌는 듯하다.** AST-EXT-001과 `normalized_corrected_parallax`가 쓰는 `+0.017 mas`는 DR4에서 틀린다.
  4. **천체물리 매개변수가 표 여럿으로 쪼개졌고**(`ap_xp`/`ap_rvs`/`ap_class`/`ap_emission`), DSC의 백색왜성·쌍성 열이 없고, 변광 분류기가 분류기당 한 행으로 바뀌었다. DR3 열 목록을 DR4 표에 보내면 ADQL 오류다(5.1절).
  5. **`gaia_source`가 모듈마다 다른 solution을 합친 것이다**(`astrometry_origin`). 같은 열의 오차가 모듈마다 다른 성질을 가질 수 있어 10σ 결정적 운동 규칙의 근거(DR3 퀘이사 폭 1.05–1.1배)가 천체마다 다를 수 있다.
- **DR3 결과는 이번에 바꾸지 않았다.** 열 목록과 상수를 릴리스별 표로 모았고, DR3 결과가 같음을 시험과 네 영역 실행으로 확인했다(5.2절).
- **DR4 열·표 이름은 가정하지 않았다.** DR4 제품 지도는 `None`이고 DR4를 고르면 수집기는 DR3 사본으로 돌아가 DR3로 표시한다. 분류 단계는 DR4 행을 만나면 `LookupError`로 멈춘다(DR3 가정으로 조용히 돌리지 않는다).

## 2. 확인된 일정과 사실

`LITERATURE_GAIA_DR4_2026-11-25.md` 1–2절. 아카이브 중단 2026-11-25 12:00 CET – 12-02 12:00 CET(직접 확인, 같은 문구가 TAP `/notification` 응답으로 우리 로그에 있음). DR4 66개월, 기준 시기 J2017.5. **DR3 표가 DR4 공개 뒤에도 같은 아카이브에서 제공되는지는 미확인**이고, 4절 (가)의 첫 점검 항목이다.

## 3. Gaia 의존 목록

"DR4 초안" 칸은 2026-06-26 초안 데이터 모델에서 직접 읽은 것이다(`benchmark/gaia_dr4/`). "조치" 칸의 "프로토콜"은 4절을 가리킨다. 파일 위치는 2.60.6 기준 줄 번호다.

### 3.1 수집

| # | 어디 | 읽는 것 | DR3 가정 | 근거 | DR4 초안과 가능한 변화 | 조치 |
|---|---|---|---|---|---|---|
| A1 | `Get_data/gaia_dr3.py` 기본 질의, 열 목록 `gaia_release.py` `SOURCE`(30열) | `gaiadr3.gaia_source`의 30열 | 표 이름, 열 이름, DR3 `ref_epoch` 2016.0 | Gaia Collab. 2023 DR3 | 27열은 `gaia_source`에 있음. `bp_g`, `g_rp`는 `all_source_photometry`로 이동, **`phot_bp_rp_excess_factor`는 없음**. 새 열 `ref_epoch`, `tentative_parallax_bias`, `astrometry_origin` 등 | 제품 지도(5.1절). DR4 지도는 점검 뒤에 손으로 채운다 |
| A2 | 같은 곳, `astrophysical_parameters` 합치기(`AP` 15열 + `SPEC_AP` 8열) | GSP-Phot, FLAME, DSC, GSP-Spec, ESP-ELS, ESP-UCD | 한 표에서 한 질의 | Creevey+2023, Recio-Blanco+2023, Delchambre+2023, Sarro+2023 | 표가 `ap_xp`/`ap_rvs`/`ap_class`/`ap_emission`으로 나뉨. DSC 백색왜성·쌍성 열 없음, `classlabel_espels_flag` 없음(`flags_espels_classlabel`) | 표마다 질의하는 제품 지도 구조는 이미 있음(5.1절). 열 대응은 점검 뒤 |
| A3 | 같은 곳, `vari_classifier_result` | `best_class_name`, `best_class_score` | 천체당 한 행 | Eyer+2023 | 분류기마다 한 행(`classifier_name`, `classifier_best_class_name`, `classifier_best_class_prob`, `prob_*` 40여 열). 클래스 이름 체계 변화 가능 | 어느 분류기를 쓸지 정하는 규칙이 필요(프로토콜 (가)) |
| A4 | 같은 곳, `vari_summary` | `in_vari_*` 9열 | DR3 플래그 이름 | Eyer+2023 | 8열 그대로, `in_vari_classification_result` → `in_vari_classifier_result`. 새 플래그 여럿 | 이름만 바꾸면 됨 |
| A5 | `gaia_dr3.py` `_merge_fidelity` (GAVO `gedr3spur.main`) | `fidelity_v2` | **DR3 `source_id` 키**, EDR3 solution으로 학습 | Rybizki+2022 (MNRAS 510, 2597) | `source_id`가 릴리스 사이에 안 유지됨. 같은 분류기는 DR4에 없음 | DR4에서는 건너뜀(코드가 `rel.name == "DR3"`일 때만 호출). Stage 4·5의 fidelity 입력은 DR4에서 빔 |
| A6 | `gaia_dr3.py` `_vizier_fallback`, `Get_data/gaia_release.py` `vizier_source` | VizieR I/355/gaiadr3, I/355/paramp, I/358/vclassre | DR3 사본 | CDS | DR4 사본의 소재·ID **미확인**(CDS는 2026-11-15 사고 이후 불안정) | DR4를 고르면 지금은 DR3 사본으로 가고 DR3로 표시. 점검 항목(프로토콜 (가)) |
| A7 | `Get_data/gaia_dr3_variability_sos_vizier.py` | I/358 SOS 표(RR Lyrae, 세페이드, LPV 등) | VizieR DR3 SOS | Clementini+2023, Lebzelter+2023 | DR4 `vari_rrlyrae`, `vari_cepheid`, `vari_long_period_variable` 등 | DR4 수집 경로를 새로 만들어야 함 |
| A8 | `Classifier/collect_gaia_xp_coefficients.py`, `Classifier/apply_wd_subtype_xp.py`, `wd_subtype_xp_data/` | XP 계수 110개(DataLink) | DR3 XP 보정 | Montegriffo+2023 | 보정이 바뀌었다고 읽힘(논문 목록). DataLink 구조 이름도 바뀜(2026-10-14) | 백색왜성 DA/DB XP 모델은 DR3 계수로 학습: DR4 XP에는 쓰지 않는다(프로토콜 (나)) |
| A9 | `Get_data/archive_cache.py` `_code_hash` | 캐시 키 | 키에 `V2_GAIA_RELEASE` 포함 | 우리 설계 | 이미 릴리스별로 갈린다 | 시험 추가(`test_the_cache_key_names_the_release`) |
| A10 | `Get_data/throttle.py`, 수집기 비동기 작업 | ESA 요청 | 작업 수 제한 없음으로 가정 | 아카이브 뉴스 | **사용자당 동시 작업 5개, 대기열 50개**(2026-10-14) | 수집기는 순차라 영향 낮음. 검증 워크플로가 같은 계정으로 병렬이면 한도에 닿을 수 있음(과제 3과 함께 점검) |

### 3.2 연관과 단위

| # | 어디 | 읽는 것 | DR3 가정 | 근거 | DR4 변화 | 조치 |
|---|---|---|---|---|---|---|
| B1 | `Preprocess/association_model.py` `PROFILES["Gaia DR3"]` | 기준 시기 2016.0(행에 `ref_epoch`가 없을 때), 위치 오차 하한, PSF 0.18″ | 목록 이름이 "Gaia DR3"인 슬롯 | Lindegren+2021 | 행이 `ref_epoch`를 가지므로 2017.5는 자동. 오차 하한은 DR4에서 다시 잴 것(혼잡 영역 모듈) | 짝 비교에서 연관 통계 확인 |
| B2 | `Preprocess/01_source_association.py:280` | 앵커 우선순위 | `catalog == "Gaia DR3"` 슬롯 이름 | 우리 설계 | 슬롯 이름은 릴리스와 무관(`gaia_release.SLOT_CATALOG`) | 변화 없음 |
| B3 | `Preprocess/units.py` | `gaia_dr3__*` 슬롯, G/BP/RP는 Vega로 그대로 | Gaia DR3 G·BP·RP 통과대역 | Riello+2021, Evans+2018 | **통과대역·보정이 개정**(FLAME BC "revised based on the DR4 photometric passbands"). 색 절단(`bp_rp`, `G−W1`)이 DR3 색으로 조정됨 | 짝 비교에서 색 분포 이동 확인 |

### 3.3 증거 규칙과 융합 (1차 분류)

| # | 어디 | 읽는 것 | DR3 가정 | 근거 | DR4 변화 | 조치 |
|---|---|---|---|---|---|---|
| C1 | `Preprocess/04_build_evidence.py` AST-EXT-001 (410줄); `Preprocess/03_extract_features.py` `normalized_corrected_parallax` | 시차, 시차 오차 | **전역 영점 −0.017 mas**: 보정 시차 = 시차 + 0.017; σ ≤ 0.3 mas일 때만 | Lindegren+2021 (A&A 649, A2); Klioner+2022 식 2 | 천체별 `tentative_parallax_bias`(빼기). 레시피 논문 arXiv 링크 없음 | **상수를 `gaia_assumptions.py`로 옮김**(DR3 값 그대로). DR4 값은 비워 둠 |
| C2 | 같은 곳 AST-EXT-002, `_pm_sigma` | 자체 운동, 오차, `pmra_pmdec_corr` | 대각 오차 근사 또는 공분산(옵션) | Li & Fynbo 2026 | `astrometry_origin`별로 오차 성질이 다를 수 있음 | 짝 비교에서 모듈별로 나눠 봄 |
| C3 | AST-GAL-001/002 | S/N 기반 `x/(x+5)` | 릴리스 무관 | 우리 설계 | 없음 | — |
| C4 | `04_build_evidence.py:176–205` `cstar_sigma`; `Classifier/branches/star.py:35–50`; `host_groups.py:99–104`; `05_likelihood_vectors.py:333` | `phot_bp_rp_excess_factor`, `bp_rp`, G | **Riello+2021 계수**(식 6, 표 2; 식 18) | Riello+2021 (A&A 649, A3) | **열이 초안에 없고 통과대역이 개정**. 플럭스로 만들 수 있으나 계수 무효 | 계수를 릴리스 표로 모음(DR3 값 그대로). DR4는 `LookupError`. DR4 판정은 계수를 새로 정한 뒤(문헌 대기) |
| C5 | `04_build_evidence.py:206–209`; `05_likelihood_vectors.py:337–347` | `fidelity_v2`, `FIDELITY_MIN` 0.9 | DR3 천체의 GAVO 표 | Rybizki+2022 | DR4에 같은 분류기 없음(A5) | DR4에서는 입력이 빈다. 규칙이 입력 없음을 이미 허용 |
| C6 | `04_build_evidence.py:238–240, 727` DSC-001, `DSC_PRIOR` | DSC 별/은하/QSO 확률(+ 백색왜성, 쌍성) | DR3 DSC 사전확률(별 계열 0.99881, 은하 0.000198, QSO 0.000989), 5개 클래스 | Delchambre+2023 (A&A 674, A31) 표 2, 부록 C | **3개 클래스**, 사전확률은 퀘이사 1/1000, 은하 1/5000으로 DR3와 같음(원문). 별은 나머지 ≈ 0.9988. 신경망이라 보정이 다름 | 코드는 없는 열을 건너뜀(`ok` 검사가 있는 열만 씀). **융합 가중치 `DSC-001:*`는 DR3 확률로 학습**(C10) |
| C7 | `04_build_evidence.py:737` VAR-001 | `best_class_name`, `best_class_score` | DR3 변광 분류기 클래스 이름 | Eyer+2023 | 이름 체계, 행 구조 변화(A3) | 수집기가 같은 두 열을 주도록 맞추는 것이 간단(클래스 대응 필요) |
| C8 | `05_likelihood_vectors.py:102–112` | 시차·고유운동 ≥ 10σ → STAR; `DECISIVE_MIN_RELIABILITY` 0.8(RUWE ≲ 1.75) | DR3 퀘이사의 정규화 폭 1.05–1.1 | Lindegren+2021; Klioner+2022; El-Badry+2021 | CRF4와 새 solution의 폭은 미확인; 모듈별 차이 | 짝 비교: 결정적 규칙 발동 수와 분광 은하·QSO 오발동 |
| C9 | `05_likelihood_vectors.py:507` `MAGELLANIC_PM_ERROR_SCALE` 1.1과 구름 운동 | 구름 안의 자체 운동 우도 | CRF3 폭 1.1, EDR3의 LMC/SMC 평균 운동 | Gaia Collab. Luri+2021 | 새 solution의 폭 | **`crf_error_scale`을 릴리스 표로 모음**(DR3 값 그대로) |
| C10 | `Preprocess/fusion_weights.json`, `fusion_weights_gbm.npz`, `Preprocess/coarse_gbm.py`, 보존된 `benchmark/catalog_features/` | Gaia 증거 키(AST-*, DSC-001, VAR-001)와 특징(시차 S/N, 자체 운동 S/N, DSC 합, G) | SDSS·DESI 분광 벤치마크 + DR3 Gaia 특징으로 학습·보정 | 우리 학습 | 분포가 바뀐다(DSC 신경망, 새 solution) | 재학습은 프로토콜 (나)의 결과 뒤. 지금은 DR3 가중치 유지 |
| C11 | `Preprocess/qso_options.py:75` `RHO_REF`, `local_density`, `bgs_galaxy.py` `MAX_GAIA_DENSITY`, `sparse_priors.py` `CROWDED_GAIA_DENSITY`, `G_MAX` | 10번째 이웃 Gaia 밀도 | **기준 밀도 5,000 deg⁻²**(DR3 200개 영역의 |b| > 30° 중앙값, 2026-10-24) | Jamal & Bailer-Jones 2024; Hughes+2022 | **DR4는 천체가 더 많다**(DR4 처리 약 28억: ESA 사전 보기 페이지 / DR3 약 18억: 널리 알려진 값; 혼잡 영역 분석). 같은 하늘의 밀도가 올라 GALAXY·QSO 사전확률이 더 낮아진다 | `rho_ref(df)`로 릴리스별 값. DR4 값은 DR4 영역에서 다시 재야 함 |
| C12 | `Preprocess/sparse_priors.py` `gaia_point_star` | `phot_g_mean_mag`, `parallax` 유무 | G < 19의 "전체 solution 있는 별" | 우리 설계 | 일부 천체가 `gaia_source`에서 빠지고 `all_source_*`에 있음 | 짝 비교: Gaia 짝이 있는 천체 비율 |
| C13 | `Preprocess/bgs_galaxy.py` | Gaia G | DESI BGS 은하 판정 `G − r_raw > 0.6` | Ruiz-Macias+2021; Hahn+2023 | G 보정 개정 가능 | 짝 비교 |
| C14 | `host_groups.py` | 시차, 자체 운동과 오차, G | 유의한 운동 예외, C* 5σ | 우리 설계 | C4와 같음 | C4와 같음 |

### 3.4 세부 분류와 축

| # | 어디 | 읽는 것 | DR3 가정 | 근거 | DR4 변화 | 조치 |
|---|---|---|---|---|---|---|
| D1 | `Classifier/subclass.py` 분광형(BP−RP + 온도) | `bp_rp`, `teff_gspphot`, `ebpminrp_gspphot`, `ag_gspphot` | Pecaut & Mamajek 계열, DR3 BP−RP와 GSP-Phot 소광 | Pecaut & Mamajek 2013 | 통과대역·GSP-Phot 개정; 열 이름은 `ap_xp`에서 같음 | 짝 비교: 분광형 문자 변화 |
| D2 | 같은 곳 광도 계급 | 시차, `phot_g_mean_mag` | 시차 영점 **미보정**, ΔM ≤ −3 또는 M_G < 4(거성) | Ruiz-Dern+2018; GF21 식 1 | 영점 보정 도입 가능(C1) | 짝 비교: 광도 계급 변화 |
| D3 | 같은 곳 `RUWE_BINARY = 1.4` | `ruwe` | DR2·EDR3에서 보정된 RUWE 정규화 | Lindegren 2018; Belokurov+2020 | RUWE의 새 solution별 정규화 미확인(3절 문헌) | **`ruwe_binary`를 릴리스 표로 모음**(DR3 값). 별 가지 `Classifier/branches/star.py`의 1.4는 시험으로 묶음 |
| D4 | 같은 곳 GSP-Spec log g·[M/H] | `logg_gspspec`, `mh_gspspec`, `flags_gspspec` | **생산자 보정식(Recio-Blanco+2023)을 코드에서 적용** | Recio-Blanco+2023; Babusiaux+2023 | DR4 `ap_rvs`가 `*_calib` 열을 직접 줌 → 보정식을 또 적용하면 이중 보정 | DR4 전환에서 보정식 적용 여부를 바꿔야 함 |
| D5 | 같은 곳 ESP-ELS | `classlabel_espels`, `classlabel_espels_flag` | DR3 문서 11.3.7 | Creevey+2023 | `ap_emission`; 플래그 이름 변경 | 이름 대응 |
| D6 | 같은 곳, `Classifier/axes/physical.py:121–124` ESP-UCD | `teff_espucd`, `flags_espucd` | 플래그 첫 숫자의 의미 | Sarro+2023 | `ap_xp`에 같은 이름. 정의 미확인 | 점검 |
| D7 | `Classifier/branches/evolved_star.py` FLAME | `mass_flame`, `age_flame`, `evolstage_flame`, `flags_flame`, `logg_gspphot` | DR3 FLAME, 플래그 둘째 숫자 | Creevey+2023 §3.3.2 | 열 이름 유지, BC 개정, 불확도 팽창(arXiv:2607.00264) | 점검 |
| D8 | `Classifier/axes/variability.py` | `best_class_name`(DR3 클래스 이름 `GAIA_MAP`), LPV SOS 진폭·주기, RR·세페이드 SOS | DR3 클래스 | Eyer+2023; Lebzelter+2023 | A3, A7 | 이름 대응 |
| D9 | `Classifier/axes/phenomenon.py`, `compact.py`, `extragalactic.py` | `SN`, `MICROLENSING` 클래스, `in_vari_compact_companion`, `in_vari_agn`, AGN 클래스 | DR3 분류기 | 위와 같음 | A3, A4 | 이름 대응 |
| D10 | `Classifier/axes/physical.py` 뜨거운 준왜성, 백색왜성 문 | 시차 S/N > 5, |C*| < 0.6, BP−RP, G 절대 등급 | Culpan+2022 (DR3 선택); GF21 식 1 | Culpan+2022; Gentile Fusillo+2021 | C* 없음(C4), 영점·광도 개정 | C4와 함께 |
| D11 | `Classifier/axes/physical.py:41` | `teff_gspphot` | — | — | `ap_xp` 같은 이름 | — |

### 3.5 학습된 자료와 기준값

| # | 무엇 | DR3에 묶인 점 | 조치 |
|---|---|---|---|
| E1 | `Preprocess/fusion_weights.json`, `fusion_weights_gbm.npz`, `Preprocess/coarse_gbm.py` | DR3 Gaia 특징으로 학습(C10) | 프로토콜 (나)·(다) |
| E2 | `benchmark/catalog_features/*.gz`, `benchmark/truth_data/`, 세트 A/B/C 원자료 | `gaia_dr3` 열(DR3) | DR3 벤치마크로 보존. DR4 짝 비교는 새로 수집 |
| E3 | `Preprocess/faint_class_prior_cosmos.csv`, `Classifier/high_confidence.json`(순도표), `Classifier/calibration/` | DR3 Gaia 증거를 쓴 분류 결과에서 센 값 | 전환 뒤 다시 재야 함(프로토콜 (다)) |
| E4 | `Classifier/wd_subtype_xp_data/`, `Classifier/fit_wd_subtype_xp_model.py` | DR3 XP 계수 | DR4 XP에는 쓰지 않음(A8) |

## 4. 전환 프로토콜 (잠금)

**목적:** DR4 자료를 보기 전에, 무엇을 재고 무엇이 나쁘면 DR3에 머무는지 정한다. 문턱은 이 문서가 커밋될 때 확정이다.

### (가) 스키마 점검 — 아카이브가 다시 열린 직후
1. `python v2/Get_data/check_gaia_release.py --release DR4 [--schema NAME]`를 돌려 결과를 `v2/benchmark/gaia_dr4/schema_check_<날짜>.txt`로 커밋한다. 스크립트는 DR4 스키마를 찾고(`gaia_source`에 `tentative_parallax_bias`가 있는 곳), 필요한 표 12개의 메타데이터를 초안과 비교하고(초안이 약속했는데 없는 열, 초안에 없던 열), DR3 열 64개가 새 스키마 어디에 있는지, `ref_epoch` 값, **DR3 스키마가 아직 제공되는지**를 적는다.
2. VizieR에 DR4 사본이 있는지(`Vizier.find_catalogs("Gaia DR4")`)와 I/355(DR3)가 유지되는지를 같은 보고서에 적는다.
3. 이 결과로 DR4 제품 지도(`gaia_release.RELEASES["DR4"].products`)와 분류 단계 상수(`gaia_assumptions.ASSUMPTIONS["DR4"]`)를 손으로 채운다. **점검이 통과하기 전에는 DR4 분류를 돌리지 않는다.**

### (나) 같은 원자료에서 Gaia만 바꾼 짝 비교
- **자료:** 다른 아카이브의 원자료는 그대로 두고 Gaia 파일만 DR4로 바꾼다. ① 깊은 COSMOS 26개 영역(`validation-data`의 `deep_cosmos1/45325505343/`, `deep_cosmos2/45322742717/`; Gaia는 ESA DR3로 수집됨), ② 실사용 영역 세 곳(NGC 4522 2′, COSMOS 2′, 은하면 1′), ③ 가능하면 세트 A/B에서 고정 규칙으로 뽑은 영역(두 세트 각각의 이름 정렬 순서에서 5번째마다, 약 40개). 세트 C는 쓰지 않는다((라)).
- **절차:** DR4 Gaia를 수집(수집기 하나만, 같은 원뿔) → 원자료 복사본에서 `gaia_dr3_*.csv`만 바꿈 → 두 변형을 `pipeline.py --raw-dir`로 분류 → 천체는 Legacy Surveys `ls_id`(없으면 PS1 `objid`, 그것도 없으면 1″ 안 가장 가까운 것)로 짝짓는다.
- **재는 것:**
  1. 1차 라벨 변화(행렬, 비율)와 정답이 있는 천체의 **정확도 차이**: COSMOS2020(26개 영역), 분광·문헌 정답(A/B 부분집합). 영역 부트스트랩 구간과 정확 McNemar.
  2. **고신뢰** 천체 수와 r > 22 GALAXY의 자연 순도(`natural_purity`, 목표 0.98, 84 % 하한).
  3. **결정적 운동 규칙**(≥ 10σ → STAR)의 발동 수와, 그중 정답이 은하·QSO인 오발동 수. `astrometry_origin`별로 나눈다.
  4. **세부 분류 변화:** 분광형 문자, 광도 계급, 물리 상태 축(백색왜성, 뜨거운 준왜성, 적색 거성, 초저온 왜성), 변광 축, AGN 표지의 라벨 변화 수(축마다).
  5. 연관: Gaia 짝이 있는 천체 비율, `gaia_source`에 없는 천체 수, 옮긴 목록 시험(2.48–2.49)의 거짓 연관률.
  6. 수집 시간과 요청 수(빈 캐시, `V2_CACHE=0`).
  7. DR4만의 진단: 영역당 Gaia 천체 수(DR4/DR3), `astrometry_origin` 모듈 구성비, `unreliable_astrometry` 비율, `tentative_parallax_bias` 크기 분포.

### (다) 채택 기준 (DR4를 기본으로 하는 조건; 하나라도 어기면 DR3에 머문다)
1. **정확도 비열등:** 깊은 COSMOS 26개 영역 COSMOS2020 정확도의 (DR4 − DR3) 차이의 95 % 구간 하한이 **−0.10 %p 이상**(32,814개 기준 약 33개), 그리고 어느 영역 묶음(보정/시험, 은위)에서도 −0.5 %p보다 나빠지지 않는다. 정확 McNemar에서 DR4가 DR3보다 유의하게(p < 0.05) 더 많이 깨뜨리지 않는다.
2. **고신뢰 순도 유지:** r > 22 GALAXY 고신뢰 순도의 84 % 하한 ≥ 0.98, 고신뢰 천체 수는 DR3 대비 −5 % 이내.
3. **밝은 하늘·QSO 비열등:** A/B 부분집합 블라인드 정확도 −0.2 %p 이내, QSO 재현율이 1 %p 넘게 떨어지지 않는다.
4. **결정적 운동 규칙:** 분광 은하·QSO에 대한 오발동 수가 DR3보다 늘지 않는다(독립 영역 점수표 정의).
5. **세부 분류:** 어느 축도 DR3 라벨의 5 % 넘게를 근거 없이 잃지 않는다(원인이 DR4 열 부재로 설명되면 기록하고 기본값 결정에서 별도 표시).
6. **수집 시간:** DR3보다 20 % 넘게 느려지지 않는다.
- (1)–(3) 중 하나라도 어기면 DR3가 기본으로 남고 DR4는 `V2_GAIA_RELEASE=DR4`로 고르는 선택 사항이다. (4)–(6)만 어기면 원인을 고치고 (나)를 다시 한다.
- **정당화:** 1번의 −0.10 %p 여유는 이전 변형 비교에서 관측된 정확도 차이(2.55.0 +0.01 %p, 2.60.2 변형 −0.02–−0.03 %p)의 몇 배 안쪽이다. 컴퓨터 비용이 아니라 되돌릴 수 없는 것(기본값 변경)이라 비열등 쪽으로 엄격히 둔다. 이 값은 DR4 자료를 보기 전에 정한 것이다.

### (라) 세트 C
- 전환 뒤 **한 번만** 채점한다(집계만, 판마다 한 번 규칙 유지). 결정 근거로 쓰지 않는다. 결과는 **전환 전 DR3 기준 채점과 묶음별(csth/cpln/clam)로** 비교한다. 기준은 2026-11-25에 2.60.4로 채점한 것이다(`v2/benchmark/locked_c/2.60.4/`, run 45590188973). 2.60.4의 1차 분류 코드는 2.60.2·2.60.3과 같고, 점수는 99.65 %(99.40–99.86)다. 영역마다 어느 Gaia를 썼는지는 그 `run.json`의 `gaia_source_regions`에 있다(ESA 57개 영역, VizieR 사본 3개 영역). 그 기준이 없으면 2.52.0 기준(99.65 %, 99.40–99.86)과 비교한다. 채점은 검토·병합 세션이 한다.
- **입력(2.60.6 검토에서 추가):** 기준 채점의 블라인드 입력(run 45590188973의 영역별 `craw-<영역>` 아티팩트, 90일, 2027-02-23 무렵 만료)에서 `gaia_dr3_*.csv`만 DR4 원뿔로 바꾼다. 원뿔은 같은 중심과 반지름이고, (가)를 통과한 DR4 제품 지도로 수집한다. 바꾼 입력을 `pipeline.py --raw-dir`로 분류한다. 이렇게 하면 다른 아카이브의 수집 날 차이가 섞이지 않는다. 2.51.0과 2.52.0 사이에는 코드가 수집을 바꾸지 않았는데도 아카이브 상태만으로 DSC 적용률이 91.5 → 97.8 %로 움직였다.
- **짝짓기 없음:** DR4에서는 `source_id`가 유지되지 않는다. 하지만 세트 C는 천체별로 비교하지 않으므로(`LOCKED_TEST_SET_C.md` 규칙 2·5) (나)처럼 `ls_id`로 천체 짝을 만들지 않는다. Gaia 행과 다른 목록의 연관은 파이프라인 Stage 1이 위치로 다시 한다. 이때 각 행의 `ref_epoch`(DR4 J2017.5)로 고유운동을 전파한다. 정답 대조도 위치로 하므로, 비교는 두 채점의 집계끼리다.
- 아티팩트가 만료됐거나 영역 일부가 없으면 새로 수집해 채점한다. 그때는 점수표에 아카이브 날 효과가 섞였다고 적는다.

### (마) DR3 경로 유지
- `V2_GAIA_RELEASE=DR3`는 계속 선택할 수 있다(기본값). DR3 열 목록과 상수는 릴리스 표에 남고, DR3 결과가 같음은 시험으로 묶여 있다(5.2절). ESA가 DR3 표를 더 이상 제공하지 않으면 DR3는 VizieR I/355 사본으로 온다(이미 지원, 사본이 못 주는 열은 경고와 `run_archives_missing`에 적힌다).
- **사본으로 오래 머물 때 약해지는 것(2.60.6 검토에서 추가).** 기준 (1)–(3)을 어겨 DR3에 머물러야 하는데 ESA가 DR3 표를 내리면, DR3는 사본에서만 온다. 사본이 비우는 18열은 두 묶음이다. 각 열을 어디서 읽는지는 코드에서 찾았다.
  - **1차 클래스:** 거의 같다. 원래 9개 깊은 COSMOS 영역을 ESA 원본과 사본으로 각각 분류해 비교했을 때, 공통 26,024개 중 1차 라벨 6개(0.02 %)가 달랐다(`WORK_REPORT_2026-11-24.md`; 수집 날도 달랐으므로 사본 효과의 상한이다). 1차 규칙(`Preprocess/`)은 18열 가운데 어느 것도 읽지 않는다.
  - **G / BP / RP 플럭스와 그 오차(9열 묶음):** `Classifier/branches/star.py` `_colour_error`가 BP−RP 색 오차를 플럭스 오차로 계산한다. 사본에서는 색 오차가 0이 되어, 백색왜성 궤적 확률(`wd_locus_probability`)이 경계 근처에서 과신한다. `bp_g`, `g_rp`, `rv_nb_transits`는 분류 코드가 읽지 않는다(학습 스크립트만).
  - **변광 요약 플래그(`in_vari_*` 9열):** compact 축의 Gaia 밀집 동반성 후보(`in_vari_compact_companion`, `Classifier/axes/compact.py`)와 extragalactic 축의 Gaia AGN 후보 플래그(`in_vari_agn`, `Classifier/axes/extragalactic.py`)가 빠진다. 변광 분류 자체(`best_class_name`, I/358)는 사본에도 있으므로 "AGN" 분류 결과는 남는다.
  - 사용자에게는 실행마다 경고 띠와 `run_archives_missing`으로 보인다(`catalog_coverage.ALTERNATIVE`, 2.57.0). DR4를 골랐는데 사본이 답한 경우에는 실행 기록에도 "Gaia DR4 was requested; answered by the VizieR DR3 copy"가 찍힌다(2.60.6 검토, 시험).

## 5. 코드 준비

### 5.1 구조: 이름이 바뀌는 열을 한 곳(릴리스 설정)에서 다루는가
**지금 구조는 DR4에 충분하지 않았다.** `gaia_release.py`는 스키마 이름과 기준 시기만 가졌고, 열 목록(`SOURCE`, `AP`, `SPEC_AP`, `VAR_SUMMARY`)과 어느 표에서 읽는지는 `gaia_dr3.py`의 상수와 코드였다. DR4는 천체물리 표가 여럿으로 나뉘어 DR3 목록을 보내면 ADQL 오류가 난다. 고친 것(2.60.6):

- **제품 지도** `GaiaRelease.products`: 제품마다 `Product(table, columns, status_column)`. DR3는 지금까지 수집기가 물은 것 그대로(`DR3_PRODUCTS`). 수집기는 지도를 순서대로 돌며 합친다. DR4는 `None`(점검 전). DR4를 고르면 수집기는 질의를 만들지 않고 DR3 사본으로 가서 행에 DR3로 적는다(시험).
- **분류 쪽 상수** `Preprocess/gaia_assumptions.py`: 시차 영점(0.017), 영점이 적용되는 오차 한도(0.3 mas), CRF 오차 배율(1.1), RUWE 이중성 문턱(1.4), 밀도 기준(5,000 deg⁻²), C* 계수. 데이터의 `gaia_release` 열로 릴리스를 고르고(열이 없으면 DR3: 보존 특징, 예전 원자료), DR4는 값이 없어 `LookupError`로 멈춘다. 호출부: Stage 3(`normalized_corrected_parallax`), Stage 4(AST-EXT-001, C*), Stage 5(구름 운동), `qso_options.rho_ref`(밀도 사전확률 세 곳).
- **아직 옮기지 않은 것:** `Classifier/branches/star.py`와 `Classifier/subclass.py`의 RUWE 1.4와 C* 식(Classifier는 Preprocess 모듈을 경로로 불러 쓰지 않는 구조라 복사본이 있다). 시험이 `star.py`의 식이 릴리스 표의 DR3 값과 같음을 묶는다. DR4 전환 때 같이 옮긴다.
- **스키마 점검:** `check_gaia_release.py`는 DR3(제품 지도 대조)와 DR4(발견 모드, 4절 (가))를 한다.
- **DR4 초안 열 대조:** `benchmark/gaia_dr4/` (`parse_dr4_draft.py`, `dr4_draft_tables.json`, `dr3_columns_vs_dr4_draft.csv`).

### 5.2 DR3 결과 동일성
- **시험(`test_gaia_release_table.py`, 11개):** 옛 열 목록의 해시(30/15/8/9열), 제품 지도의 표·상태 열·순서, 수집기가 보내는 SQL과 합치는 순서가 이전과 글자까지 같음, DR4는 DR4 표에 질의하지 않고 DR3로 표시, 캐시 키가 릴리스를 가름, DR3 상수의 값, C* 식이 옛 인라인 식·`star.py`와 같음, DR4 행은 `LookupError`.
- **실행 비교:** 같은 원자료(저장된 NGC 4522 2′, COSMOS 2′, 은하면 1′ 원자료와 커밋된 NGC 4522 원자료)를 2.60.3 코드와 이번 코드로 분류해 `classified_objects.csv`, `objects_summary.csv`, `evidence.csv`, `features.csv`, `likelihood_vectors.csv`를 **모든 셀** 비교했다: 4개 영역 × 5개 파일, **다른 셀 0**(천체 수 674, 3,583, 597, 89; 열 수 같음).
- 전체 시험 330개 통과(319 + 11).

### 5.3 DR4 전환 때 할 코드 일(이번에 하지 않음)
1. DR4 제품 지도와 분류 상수를 (가)의 결과로 채운다(영점은 `tentative_parallax_bias`로 바꾸는 방식이 필요해 상수 하나가 아니라 열 읽기를 바꾼다).
2. C*: DR4의 통과대역에 맞는 계수 또는 판정 대체.
3. 변광 분류기 행 구조와 클래스 이름 대응, 천체물리 표별 질의.
4. GSP-Spec 보정식을 `*_calib` 열과 이중 적용하지 않게.
5. `Classifier/branches/star.py`, `subclass.py`의 RUWE·C*를 릴리스 표로.
6. DR4 DSC 3개 클래스와 융합 가중치 재보정(필요하면).

## 6. 개정 기록
- 2026-11-25: 초판(DR4 자료는 보지 못했다).
- 2026-11-25, 병합 전 검토(코드 개발 세션, 2.60.6; DR4 자료는 여전히 보지 못함): (라)에 세트 C 입력(보존한 블라인드 입력에서 Gaia 파일만 교체)과 짝짓기를 하지 않는 이유를, (마)에 사본으로 오래 머물 때 약해지는 판정을 더했다. (다)의 문턱은 바꾸지 않았다.
