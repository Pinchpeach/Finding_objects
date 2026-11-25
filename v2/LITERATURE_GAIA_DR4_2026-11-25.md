# Gaia DR4: 지금까지 문헌·공식 문서로 확인된 것 (2026-11-25, DR4 공개 일주일 전)

DR4 전환 준비(`GAIA_DR4_READINESS_2026-11-25.md`)의 근거 조사다. **DR4 자료는 아직 아무도 보지 못했다.** 아래는 ESA 공식 페이지, DR4 사전 공개(2026-06-26)의 데이터 모델 초안, 공개된 DR4 논문 두 편이다. 확인 수준을 항목마다 적는다.

- **직접 확인:** 이 세션이 원문을 읽었다(데이터 모델 PDF는 내려받아 열 이름을 구문 분석, ESA 페이지는 읽기 에이전트가 원문 인용을 돌려주었고 중요한 것은 같은 문장이 파이프라인 로그에도 있다).
- **요약만:** 읽기 에이전트가 긴 페이지의 뒷부분을 모델 요약으로만 읽었다. 원문 대조 전이다.
- **미확인:** 찾지 못했거나 페이지가 말하지 않는다.

## 1. 일정과 아카이브

| 사실 | 수준 | 근거 |
|---|---|---|
| DR4 공개 2026-12-02 약 12:00 CET | 직접 확인 | ESA 데이터 공개 일정 페이지 "Gaia DR4 (based on 66 months of data) 2 December 2026", DR4 안내 페이지 "Coming up: 2 December 2026 at ~12:00 CET" |
| Gaia ESA 아카이브는 2026-11-25 12:00 CET부터 중단, 2026-12-02 12:00 CET에 "새 DR4 공개와 함께" 다시 열림 | 직접 확인 | ESA 뉴스 2026-10-08 "Advance warning: Gaia ESA Archive downtime". 같은 문장이 TAP `/notification` 응답으로 우리 수집 로그에도 찍혔다("The Gaia ESA Archive will be down as of 25 November 12:00 CET for preparation of the Gaia DR4 release on 2 December 12:00 CET") |
| 중단 기간의 Gaia는 VizieR I/355 사본(DR3)으로만 온다 | 코드가 보장 | 2.57.0 `V2_GAIA_SOURCE`, 점검 페이지 인식, DR3로 표시 |
| **DR3·EDR3 표가 DR4 공개 뒤에도 같은 아카이브에서 계속 제공되는지** | **미확인** | 읽은 페이지(DR4 내용, DR4 안내, 일정, 뉴스, 사전 공개)에 말이 없다. `check_gaia_release.py --release DR4`가 `gaiadr3.gaia_source`를 직접 읽어 답한다(12-02 첫 점검 항목) |
| 아카이브 "breaking changes"(2026-10-14): DataLink 구조 이름 `RAW`/`INDIVIDUAL` → `DATAMODEL_GAIA`/`DATAMODEL_STANDARD`; **사용자당 동시 실행 작업 5개, 대기열 50개**, 동기·비동기 시간 제한과 최대 행 수 갱신 | 직접 확인(뉴스 원문) | ESA 뉴스. 우리 영향: 수집기는 Gaia 요청을 순차로 보내 5개 한도에 안 닿는다. XP 계수 수집(`Classifier/collect_gaia_xp_coefficients.py`)은 DataLink 이름이 바뀐 영향을 받는다. 검증 워크플로가 같은 계정으로 여러 작업을 동시에 내면 한도에 닿을 수 있다 |
| 다음 공개: DR5는 "2030년 말 이전은 아님" | 직접 확인 | ESA 일정 페이지 |

## 2. 관측 기간과 기준 시기

- DR4는 2014-07-25 10:30 UTC부터 2020-01-20 22:00 UTC까지 **66개월**, 공칭 임무 전체를 쓴다(DR3: 34개월). **기준 시기 J2017.5**("The reference epoch for Gaia DR4 is J2017.5."). 직접 확인(DR4 내용 페이지 원문 인용). `gaia_release.py`의 DR4 기준 시기 2017.5와 같다.
- 초안의 `gaia_source`에는 `ref_epoch` 열이 있다(직접 확인, 데이터 모델 초안). 우리 수집기는 행마다 `ref_epoch`를 적고 연관 단계가 그 값을 쓴다(2.16.0).
- 천체는 ICRS에 맞추고 시간은 TCB, 기준틀은 Gaia-CRF4(요약만).

## 3. 표와 열: DR4 데이터 모델 초안(2026-06-26)에서 직접 읽은 것

초안은 PDF 1,231쪽("Gaia DR4: preliminary catalogue data model", 2026-05-20 작성)이다. `benchmark/gaia_dr4/parse_dr4_draft.py`가 표 141개와 열 4,629개를 읽어 `dr4_draft_tables.json`으로 남겼다. DR3 수집기가 요청하는 64열의 위치는 `dr3_columns_vs_dr4_draft.csv`에 있다.

**`gaia_source`가 달라졌다.**
- "an entry for each source ... considered to have both high-quality astrometry and high-quality photometry from at least one module". 그 밖의 천체는 `all_source_astrometry`, `all_source_photometry`, `all_source_rvs`, `all_source_flags`에 있다(약 28억 천체 중 약 20억이 `gaia_source`, 페이지 요약).
- "the parameters ... correspond to a consolidation of the best results obtained across DPAC, and as such they do not correspond to those of a homogeneous module". 천체마다 어느 모듈이 천체측정을 냈는지 `astrometry_origin`(AGIS의 `all_source_astrometry`, 근접 환경 분석 `gaia_source_environment`, 혼잡 영역 `crowded_field_source`, 비단일성 solution 등)에 적힌다. 광도·색(`g_photometry_origin`, `colour_origin`), 시선속도, 항성 매개변수(`ap_origin`), 소광(`extinction_origin`)도 마찬가지다. **같은 열의 오차가 모듈마다 다른 성질을 가질 수 있다.**
- 새 열: `ref_epoch`, `tentative_parallax_bias`("This is the parallax bias correction computed based on the recipe in ?. This correction is to be subtracted from parallax to get the corrected parallax." 인용의 참고문헌이 초안에서 `?`), `unreliable_astrometry`, `unreliable_g_photometry`, `astrometry_origin` 등, `phot_variable_*`, DSC 3열, `teff, logg, mh, ag, ebpminrp, distance_gspphot`(접미사 없는 통합 열).
- **`gaia_source`에 없는 것(DR3 수집기가 요청):** `bp_g`, `g_rp`(→ `all_source_photometry`), **`phot_bp_rp_excess_factor`는 초안 어디에도 없다.** `in_vari_*` 플래그는 `gaia_source`에서 `vari_summary`로 옮겨졌다.

**`source_id`는 릴리스 사이에 유지되지 않는다.** "it is not guaranteed that the same astronomical source will always have the same source_id in different Data Releases"(데이터 모델 초안 직접 인용), 안내 페이지: "the source list for Gaia DR4 should be treated as independent from Gaia DR3". 대응표는 `dr3_neighbourhood`(`source_id`, `dr3_source_id`, `angular_distance`, `magnitude_difference`, `proper_motion_propagation`, `probable_match`)로 따로 있다. → DR3 `source_id`를 키로 쓰는 외부 표(`gedr3spur.main` fidelity, VizieR I/355·I/358 사본)는 DR4 천체에 맞지 않는다.

**천체물리 매개변수는 여러 표로 나뉜다**(`astrophysical_parameters`라는 표는 없다).

| DR3 수집기가 읽는 것 | DR4 초안의 위치 |
|---|---|
| GSP-Phot(`teff_gspphot`, `logg_gspphot`, `mh_gspphot`, `distance_gspphot`, `ag_gspphot`, `ebpminrp_gspphot`), FLAME(`mass_flame`, `age_flame`, `evolstage_flame`, `flags_flame`), ESP-UCD(`teff_espucd`, `flags_espucd`) | `ap_xp` (같은 이름) |
| GSP-Spec(`teff_gspspec`, `logg_gspspec`, `mh_gspspec`, `flags_gspspec`) | `ap_rvs` (같은 이름; **`*_calib` 열이 새로 있다**) |
| DSC(`classprob_dsc_combmod_quasar/galaxy/star`) | `ap_class`, `ap_class_ir`, 그리고 `gaia_source` (같은 이름) |
| DSC `..._whitedwarf`, `..._binarystar` | **없다**(백색왜성·쌍성 부류 철회, 5절) |
| ESP-ELS(`classlabel_espels`) | `ap_emission` (같은 이름); `classlabel_espels_flag`는 없고 `flags_espels_classlabel`이 있다 |
| 변광 요약 `in_vari_rrlyrae` 등 8열 | `vari_summary` (같은 이름); `in_vari_classification_result` → `in_vari_classifier_result` |
| 변광 분류기 `best_class_name`, `best_class_score` | `vari_classifier_result`가 **분류기마다 한 행**이 되었다: `classifier_name`, `classifier_best_class_name`, `classifier_best_class_prob`, 그리고 클래스별 `prob_*` 40여 열. 천체당 행이 여럿일 수 있어 합칠 때 분류기를 골라야 한다 |

**DR3 표 64열 중** `gaia_source`에서 27열이 같은 표에 남고(3열은 옮기거나 없어짐), 천체물리 23열은 20열이 다른 표로 갔고 3열이 없고, 변광 요약 9열은 8열이 남는다. 같은 이름조차 정의(오차 모형, 보정)가 같은지는 초안만으로 알 수 없다.

**RUWE:** `ruwe` 열은 있고 정의는 DR3와 같은 문장("re-scaled version of the Unit Weight Error")이다. 다만 천체측정이 여러 모듈에서 오므로(`astrometry_origin`) 어느 모듈의 값인지 함께 봐야 한다. 정규화 표(DR3: Lindegren 2018 DR2 표에서 파생)가 새 solution에 맞게 다시 만들어졌는지는 미확인.

**XP(BP/RP) 스펙트럼:** `xp_continuous_mean_spectrum`(DataLink, 이름 유지) 외에 `xp_epoch_spectrum`, `xp_summary`가 새로 있다. 논문 목록에 "BP/RP calibrations and catalogue", "External calibration of BP/RP low-resolution spectroscopic data"가 있어 **계수가 DR3와 같다고 볼 수 없다**(요약 수준). 우리 백색왜성 DA/DB XP 모델(110개 계수)은 DR3 계수로 학습했다.

## 4. 천체측정 품질·영점·오차

- 공식 페이지(DR4 내용, 안내, 일정, 사전 공개, 뉴스)에는 **시차 영점, 오차 팽창, RUWE 권고에 대한 문장이 없다**(직접 확인, 부정 결과).
- DR4 논문 목록(2026-11-25)에 "Gaia Data Release 4: A tentative recipe for the parallax bias versus magnitude, colour, and position", "The astrometric solution", "Content and properties"가 있으나 **arXiv 링크가 비어 있어** 초록을 읽지 못했다. 데이터 모델의 `tentative_parallax_bias`가 그 레시피의 결과다(위 인용). 즉 DR4의 영점은 **전역 상수(DR3: −0.017 mas)가 아니라 천체별 보정**이 될 가능성이 높다. 레시피의 입력(등급, 색, 위치)이 `gaia_source`에 있다.
- 2026년 arXiv 논문("Gaia parallax bias via spherical harmonics", 2608.12619)이 "DR4 시차 영점이 DR3와 같은 특징을 가진다고 가정하면"이라고 쓴다는 검색 결과 요약이 있다(요약만, 원문 미확인).
- DR4 논문 "Global Patterns in the Quasar Proper Motions"와 "Gaia Celestial Reference Frame 4"가 목록에 있다. CRF4의 퀘이사 운동·시차 분포 폭(DR3: 1.05–1.1배, Klioner+2022)이 우리 결정적 운동 규칙의 근거다(`05_likelihood_vectors.py`). 새 값은 **미확인**.

## 5. 분류기 산출물

**DSC** (`arXiv:2605.23388`, "Performance analysis of extragalactic classifications in Gaia Data Release 4", 2026-05; 읽기 에이전트가 앞 40k자는 원문, 나머지는 요약으로 읽음)
- "DSC classifies all sources into one of three classes: quasar, galaxy, or star." 원문. **백색왜성·쌍성 부류는 철회**: "We have also decided to withdraw the white dwarf and binary star classes from DSC due to their poor classification performance in GDR3."(원문, 3.1절)
- 표와 열: "DSC provides posterior probabilities and class labels in the main table (gaia_source), the astrophysical parameter tables (ap_class and ap_class_ir), as well as the extragalactic tables (qso_candidates and galaxy_candidates)."(원문, 2절). 초안 `ap_class`에는 변형별 열(`combmod`, `specmod`, `allosmod`, `combmodalpha`, `specmodsupp`, `combmodsupp`)이 있다.
- **사전확률은 DR3와 같다:** "The prior probabilities of any source being a quasar or a galaxy are 1/1000 and 1/5000, respectively, corresponding to the same values used in GDR3."(원문). 별 사전확률은 적혀 있지 않다(나머지 약 0.9988). 우리 `DSC_PRIOR`(별 계열 0.99881, 은하 0.000198, QSO 0.000989)는 근사로 그대로 맞는다. 분류기는 DR3의 Extratrees·GMM에서 **신경망**으로 바뀌었다(요약 수준).
- 성능(원문 표 1, Gaia 단독, 시험 표본, 모든 등급, 조정 지표): Combmod는 퀘이사/은하 완전도 0.972/0.941, **순도 0.608/0.373**; 더 순도 우선인 Combmod-α는 완전도 0.843/0.762, 순도 0.762/0.741. 초록: G < 20에서 최선 분류기의 외계천체 "at least 88% completeness and 96% purity", 20 ≤ G < 20.5에서 "55% completeness and 71% purity". DR3는 완전도 92 %, 순도 22 %.
- 권고 품질 절단(요약만, 원문 미확인): `phot_[bp,rp]_n_obs` ≥ 10, |sin b| > 0.20, `unreliable_astrometry` 거짓, 확률 > 0.5 또는 0.9. "DSC outputs are not calibrated probabilities".
- **우리 시스템 영향:** DSC 열이 3개뿐이어도 Stage 3·4·`coarse_gbm.py`는 있는 열만 쓰도록 되어 있다(`dsc_star`는 별 + 백색왜성 + 쌍성 합이라 백색왜성·쌍성이 없으면 별만). 그러나 **융합 가중치는 DR3 DSC 사후 확률로 학습했다.** 신경망 DSC의 보정이 다르면 같은 확률의 의미가 다르다.

**변광 분류기:** DR4 논문 목록에 "Supervised classification of variable sources", "MACCHININOS", "A neural network's view on organizing 100 million variable sources", "Summary of the variability processing and analysis"가 있다. 초안의 `vari_classifier_result`는 40여 개 클래스 확률 열(`prob_rr`, `prob_dcep`, `prob_lpv`, `prob_agn`, `prob_sn`, `prob_microlensing`, ...)을 가진다. **클래스 이름은 DR3의 `best_class_name`과 같지 않을 수 있다**(대문자 약어가 `prob_` 소문자 접미사로). 이름 대응은 미확인.

**FLAME** (`arXiv:2607.00264`, 2026-06-30; 읽기 에이전트가 앞 40k자 원문): "In GDR4 the table structure of the astrophysical parameters has been updated and the Flame results will be available in the ap_xp and ap_rvs, respectively."(원문) FLAME 결과 약 5억 천체(GSP-Phot 기반), GSP-Spec 기반 3,400만(DR3: 약 3억과 600만). 열 이름은 DR3와 같다(`mass_flame`, `age_flame`, `evolstage_flame`, `flags_flame`; 모델 매개변수 열 새로 제공). "In gdr4, these values (BC zero point) are revised based on the DR4 photometric passbands."(원문). 불확도 팽창 매개변수와 금속도 오프셋은 요약 수준.

**GSP-Spec:** DR4 논문 "The General Stellar Parametriser from spectroscopy (GSP-Spec)" 목록에 있고(초록 미확인), `ap_rvs`에 `*_calib`(보정된 값) 열이 직접 있다. 우리는 DR3에서 생산자 보정식(Recio-Blanco+2023)을 코드에서 적용했다.

## 6. 읽지 못한 것(12-02 이후 확인 항목)

1. DR3 표가 DR4 공개 뒤에도 같은 아카이브에서 제공되는지(1절).
2. DR4 TAP 스키마 이름(ESA 페이지는 표 이름만 적는다. `gaiadr4`는 우리 가정).
3. `ruwe`, 오차(특히 `astrometry_origin`별), 시차 영점 레시피의 정의, `tentative_parallax_bias`의 근거 논문.
4. `phot_bp_rp_excess_factor`의 소재(초안에는 없다; 플럭스 `phot_bp_mean_flux + phot_rp_mean_flux) / phot_g_mean_flux`로 계산할 수 있어도 DR4 통과대역이 바뀌어 Riello+2021 계수는 그대로 쓸 수 없다).
5. 변광 분류기 클래스 이름 대응과 `classifier_name` 값.
6. VizieR에 DR4 사본이 언제 어떤 ID로 오는지(CDS는 2026-11-15 사고 이후 불안정). I/355(DR3)가 유지되는지.
7. astroquery가 새 DataLink 이름과 5개 작업 한도에서 그대로 동작하는지.

## 7. 출처

- ESA Gaia DR4 내용: https://www.cosmos.esa.int/web/gaia/dr4 (마지막 갱신 2026-09-14로 적혀 있음; "under development and changes can be expected")
- ESA Gaia DR4 안내, 일정: https://www.cosmos.esa.int/web/gaia/data-release-4, https://www.cosmos.esa.int/web/gaia/release
- ESA 뉴스 2026: https://www.cosmos.esa.int/web/gaia/news-2026 (2026-10-08 중단 예고, 2026-10-14 아카이브 "breaking changes")
- DR4 사전 공개, 데이터 모델 초안(ZIP, 2026-06-26): https://www.cosmos.esa.int/web/gaia/dr4-prerelease, https://anonftp.cosmos.esa.int/pub/GAIA_PUBLIC_DATA/Gaia_DR4/dr4-prerelease/gaia-dr4-prerelease-draft-data-model_2026-06-26.zip
- DR4 논문 목록: https://www.cosmos.esa.int/web/gaia/dr4-papers
- DSC: arXiv:2605.23388 (A&A 711, A62). FLAME: arXiv:2607.00264. DR3 DSC: Delchambre et al. 2023 (A&A 674, A31).
- DR3 영점과 CRF3: Lindegren et al. 2021 (A&A 649, A2, A4), Klioner et al. 2022 (A&A 667, A148). C*: Riello et al. 2021 (A&A 649, A3). fidelity: Rybizki et al. 2022 (MNRAS 510, 2597).
