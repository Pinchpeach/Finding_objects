# 인용 문헌 목록 (v2)

v2의 코드·문서·규칙표가 인용하는 논문, 카탈로그 출판물, 문서를 분야별로 모은 표입니다. 학술지·권·쪽, DOI, ADS bibcode는 **저장소에 적힌 경우에만** 적었고, 없으면 "—"입니다. "(저장소 표기 그대로)"는 원문 표기가 모호해 확인이 필요한 항목입니다. 사용처 경로는 `v2/` 기준입니다. 같은 내용의 기계 판독용 표는 [`papers.csv`](papers.csv)입니다.

## 분야별 항목 수

| 분야 | 항목 수 |
|---|---:|
| [측성·Gaia](#gaia) | 20 |
| [측광 체계·단위](#phot) | 8 |
| [탐사·카탈로그 데이터](#survey) | 22 |
| [데이터 출처 카탈로그 (논문 인용 없음)](#data) | 13 |
| [교차 대응·통계·분류 방법](#method) | 8 |
| [별 분류](#star) | 25 |
| [은하 분류](#galaxy) | 23 |
| [퀘이사·AGN](#qso) | 14 |
| [전파·X선·밀집성](#radio) | 4 |
| [행성상성운·초신성·과도 현상](#trans) | 6 |
| [기타 문서](#doc) | 13 |
| **합계** | **156** |

<a id="gaia"></a>
## 측성·Gaia

Gaia 데이터 릴리스, Gaia 처리·검증 논문, 측성 품질 기준.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Gaia Collaboration 2023 (Gaia DR3 summary/content paper) | A&A 674, A1; doi:10.1051/0004-6361/202243940 | — | `Classifier/LITERATURE.md`<br>`designations.py` | Gaia DR3 내용 요약; Gaia DR3 지정명 우선순위의 근거. designations.py는 'Gaia Collaboration 2023'으로만 표기(같은 논문으로 보고 병합) |
| Creevey et al. 2023 (Gaia DR3 Apsis methods overview) | A&A 674, A26; doi:10.1051/0004-6361/202243688 | — | `Classifier/LITERATURE.md`<br>`Classifier/LITERATURE_SUBCLASS.md` (쌍성 후보 속성, Classifier/subclass.py GAIA_DSC_BINARY) | Gaia DSC의 QSO/은하/별/백색왜성/쌍성 사후확률; DSC 쌍성 확률 ≥ 0.8 → 쌍성 후보 |
| Delchambre et al. 2023 (Gaia DR3 Apsis III: non-stellar content and source classification) | A&A 674, A31 | — | `Preprocess/LITERATURE.md` (DT-HIER-001)<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_gaia_dsc) | Gaia DSC 분류기 구조(Specmod/Combmod), classlabel_dsc 확률 > 0.5 기준, 외부은하 순도 주의 |
| Andrae et al. 2023 (Gaia DR3 GSP-Phot) | A&A 674, A27; doi:10.1051/0004-6361/202243462 | — | `Classifier/subclass.py` (GAIA_TEFF 분광형, E(BP−RP), METAL_POOR)<br>`Classifier/LITERATURE.md`<br>`Classifier/LITERATURE_MULTI_AXIS.md`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | BP/RP 기반 Teff·log g·[M/H]·소광; [M/H]는 참고용이라 '후보'로만 표시 |
| Montegriffo et al. 2023 (Gaia DR3 synthetic photometry) | A&A 674, A33 | — | `Classifier/LITERATURE_MULTI_AXIS.md` | XP 스펙트럼 합성 측광과 백색왜성 DA/non-DA 목록 |
| Eyer et al. 2023 (Gaia DR3 variability overview) (저장소 표기 그대로) | A&A 674, A13 | — | `Classifier/LITERATURE.md` | Gaia DR3 변광성 처리 개요(약 1천만 개, 약 20여 그룹); 변광 축을 STAR 세부 축으로 둔 근거 |
| Rimoldini et al. 2023 (Gaia DR3 supervised variability classification) | — | — | `Classifier/LITERATURE.md`<br>`Classifier/LITERATURE_SUBCLASS.md` (변광 유형 속성) | Gaia DR3 지도학습 변광 분류(vari_classifier_result) |
| Clementini et al. 2022/2023 (Gaia DR3 SOS RR Lyrae) (저장소 표기 그대로) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | RR Lyrae 검증: 주기-진폭, Fourier 위상 φ21·φ31 |
| Ripepi et al. 2022/2023 (Gaia DR3 SOS Cepheids) (저장소 표기 그대로) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 세페이드 하위 유형의 다파장 시계열 특성화·검증 |
| Lebzelter et al. 2023 (Gaia DR3 LPV table) (저장소 표기 그대로) | — | — | `benchmark/build_agb_chemistry_truth.py`<br>`Classifier/subclass.py` (GAIA_LPV_CSTAR) | gaiadr3.vari_long_period_variable의 is_cstar로 AGB 화학형 정답을 독립 점검; 세부 분류에서 C-star 판정 |
| (저자 미기재) "Gaia DR3 all-sky variability classification" (저장소 표기 그대로) | URL: https://www.aanda.org/articles/aa/full_html/2023/06/aa45591-22/aa45591-22.html | — | `Classifier/STELLAR_EVIDENCE_CONFIGURATION_2026-10-08.md` (Sources) | Gaia DR3 SOS 변광 세부 유형(RRab/RRc/RRd, 세페이드 유형·모드, LPV 탄소별 후보)과 XP 기반 백색왜성 유형 설정의 근거 |
| (저자 미기재) "Gaia DR3 RR Lyrae SOS catalogue" (저장소 표기 그대로) | URL: https://www.aanda.org/articles/aa/full_html/2023/06/aa43964-22/aa43964-22.html | — | `Classifier/STELLAR_EVIDENCE_CONFIGURATION_2026-10-08.md` (Sources) | Gaia DR3 SOS 변광 세부 유형(RRab/RRc/RRd, 세페이드 유형·모드, LPV 탄소별 후보)과 XP 기반 백색왜성 유형 설정의 근거 |
| (저자 미기재) "Gaia DR3 long-period-variable catalogue" (저장소 표기 그대로) | URL: https://www.aanda.org/articles/aa/full_html/2023/06/aa44241-22/aa44241-22.html | — | `Classifier/STELLAR_EVIDENCE_CONFIGURATION_2026-10-08.md` (Sources) | Gaia DR3 SOS 변광 세부 유형(RRab/RRc/RRd, 세페이드 유형·모드, LPV 탄소별 후보)과 XP 기반 백색왜성 유형 설정의 근거 |
| (저자 미기재) "Gaia XP white-dwarf primary-type classification" (저장소 표기 그대로) | URL: https://www.aanda.org/articles/aa/full_html/2024/02/aa47694-23/aa47694-23.html | — | `Classifier/STELLAR_EVIDENCE_CONFIGURATION_2026-10-08.md` (Sources) | Gaia DR3 SOS 변광 세부 유형(RRab/RRc/RRd, 세페이드 유형·모드, LPV 탄소별 후보)과 XP 기반 백색왜성 유형 설정의 근거 |
| (저자 미기재) "Gaia DR3 Apsis II stellar-parameter processing" (저장소 표기 그대로) | URL: https://www.aanda.org/articles/aa/full_html/2023/06/aa43919-22/aa43919-22.html | — | `Classifier/STELLAR_EVIDENCE_CONFIGURATION_2026-10-08.md` (Sources) | Gaia DR3 SOS 변광 세부 유형(RRab/RRc/RRd, 세페이드 유형·모드, LPV 탄소별 후보)과 XP 기반 백색왜성 유형 설정의 근거 |
| Riello et al. 2021 (corrected BP/RP excess) | A&A 649, A3 | — | `Classifier/branches/star.py` (corrected_excess_factor, sigma_corrected_excess, HR_GATES)<br>`Classifier/WD_HR_GATE_EVALUATION.md`<br>`WORK_LOG_2026-10-08.md` | 보정 BP/RP 초과 계수 C* = C − f(BP−RP) (Eq. 6, Table 2)와 1σ 산포 (Eq. 18) |
| Lindegren et al. 2021 | A&A 649, A2 | — | `Preprocess/05_likelihood_vectors.py` (DECISIVE_MOTION_SIGMA)<br>`Preprocess/LITERATURE.md`<br>`CHANGELOG.md` | 퀘이사의 규격화 시차·고유운동 폭 ≈ 1.05–1.1 → 10σ 운동이면 STAR로 확정 |
| Klioner et al. 2022 (Gaia-CRF3) | — | — | `Preprocess/05_likelihood_vectors.py`<br>`Preprocess/LITERATURE.md`<br>`Preprocess/classification_rules.csv` AST-EXT-001/002 (reference 'Gaia-CRF3') | 외부은하 천체의 시차·고유운동이 0과 일관한지 보는 기준(퀘이사 기준계) |
| El-Badry, Rix & Heintz 2021 | — | — | `Preprocess/05_likelihood_vectors.py`<br>`Preprocess/LITERATURE.md` | 어두운 쪽 시차 오차가 약 1.5배 과소평가되어도 10σ 기준이 유지됨 |
| Lindegren et al. 2018 (RUWE) | — | — | `Classifier/subclass.py` (RUWE_BINARY)<br>`Classifier/LITERATURE_SUBCLASS.md` | RUWE > 1.4를 위치천문 쌍성 후보 기준으로 사용 |

<a id="phot"></a>
## 측광 체계·단위

측광 체계, 영점(Vega→AB), 소광·적색화 계수, 필터 변환.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Tonry et al. 2012 | — | — | `Preprocess/units.py`<br>`Preprocess/LITERATURE.md` | Pan-STARRS1 측광이 AB 체계임 |
| Morrissey et al. 2007 | — | — | `Preprocess/units.py`<br>`Preprocess/LITERATURE.md` | GALEX 측광이 AB 체계임 |
| Jarrett et al. 2011 | — | — | `Preprocess/units.py` (WISE Vega→AB)<br>`Classifier/subclass.py` (WISE_AB)<br>`Preprocess/LITERATURE.md` | WISE W1–W4 Vega→AB 보정 +2.699/+3.339/+5.174/+6.620 |
| Blanton & Roweis 2007 | — | — | `Preprocess/units.py`<br>`Preprocess/LITERATURE.md` | 2MASS J/H/Ks Vega→AB 보정 +0.91/+1.39/+1.85 |
| Schlafly & Finkbeiner 2011 | — | — | `Preprocess/units.py` (std_ebv)<br>`Classifier/subclass.py` (R_DECAM_G)<br>`Preprocess/LITERATURE.md` | DECam g 소광 계수 R_g = 3.214 (LS mw_transmission_g → E(B−V)) |
| Schlafly et al. 2019 (unWISE) | — | — | `Preprocess/units.py`<br>`Preprocess/LITERATURE.md` | Legacy Surveys W1/W2(unWISE 강제 측광)가 AllWISE에 맞춰 보정됨 |
| Casagrande & VandenBerg 2018 | MNRAS 479, L102 | — | `Classifier/subclass.py` (E_BPRP_PER_EBV, A_G_PER_EBV)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | Gaia 소광 계수: E(BP−RP) = 1.339 E(B−V), A_G ≈ 2.740 E(B−V) |
| Lupton 2005 (SDSS→Johnson transformations) (저장소 표기 그대로) | — | — | `Classifier/subclass.py` (M_B, Johnson R)<br>`Classifier/LITERATURE_SUBCLASS.md` | B = g + 0.313(g−r) + 0.227, R = r − 0.1837(g−r) − 0.0971 |

<a id="survey"></a>
## 탐사·카탈로그 데이터

저장소가 논문으로 인용하는 탐사·데이터 릴리스·카탈로그 논문.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Dey et al. 2019 (Legacy Surveys) | AJ 157, 168 | — | `Preprocess/classification_rules.csv` LS-MORPH-001/002, LS-COLOR-001<br>`Preprocess/04_build_evidence.py`<br>`Preprocess/03_extract_features.py`<br>`Preprocess/units.py`<br>`Get_data/desi_legacy.py`<br>`Classifier/unknown_reason.py`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | Tractor 형태 모형(Sec. 8, S/N ≥ 10에서만 사용), nanomaggy→AB, unWISE 강제 측광, DEV/EXP 광도 분포 |
| Chambers et al. 2016 (Pan-STARRS1 3π) | arXiv:1612.05560 | — | `Preprocess/classification_rules.csv` PS1-CKNN-001 | PS1 3π가 Dec > −30°를 덮어 LS 영역 밖에서도 색 kNN 사용 가능 |
| Flewelling et al. 2020 (Pan-STARRS1) | — | — | `Classifier/unknown_reason.py`<br>`host_groups.py`<br>`designations.py` | MeanObject의 −999 평균 PSF 등급(검출 1–2회), 큰 은하 조각화, PS1 지정명 |
| York et al. 2000 | — | — | `Classifier/unknown_reason.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | SDSS 점광원 95 % 완전도 r = 22.2 (UNKNOWN 사유) |
| Stoughton et al. 2002 | — | — | `Classifier/unknown_reason.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | SDSS 점광원 95 % 완전도 r = 22.2 (UNKNOWN 사유) |
| Bolton et al. 2012 (SDSS spectrum class/subclass) | AJ 144, 144 | — | `Preprocess/05_likelihood_vectors.py` (_spectroscopic, SPC-* 규칙)<br>`Classifier/subclass.py` (은하 활동성, 1형/2형 AGN)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | SDSS CLASS/ZWARNING와 SUBCLASS(STARFORMING/AGN/STARBURST/BROADLINE) |
| Blanton et al. 2005 (NYU-VAGC) | AJ 129, 2562 | — | `host_groups.py`<br>`WORK_REPORT_2026-10-10.md` | SDSS가 가까운 큰 은하를 여러 검출로 쪼갬(조각화) → 큰 은하 묶기 근거 |
| Moustakas et al. 2023 (Siena Galaxy Atlas 2020) | ApJS 269, 3; VizieR J/ApJS/269/3 | — | `Get_data/sga2020.py`<br>`Preprocess/classification_rules.csv` SGA-001<br>`host_groups.py`<br>`designations.py`<br>`WORK_LOG_2026-10-08.md`<br>`WORK_REPORT_2026-10-10.md` | 큰 은하 D26 타원(PA, b/a), 큰 은하 내부 검출 판정 보류, 은하 이름 |
| DESI Collaboration 2025 (DESI DR1) | VizieR V/161/zcatdr1 | — | `Get_data/desi_spectroscopy.py`<br>`benchmark/build_desi_truth.py` | DESI DR1 적색편이 카탈로그: 분광 증거와 SDSS 독립 정답 집합 |
| Bianchi et al. 2017 (GUVcat_AIS) | VizieR II/335 | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_galex)<br>`Get_data/galex.py` (II/335/galex_ais) | GALEX AIS 자외선 카탈로그와 등급 오차·결함 플래그 |
| Condon et al. 1998 (NVSS) | — | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_nvss)<br>`Get_data/nvss.py` (VIII/65/nvss) | NVSS 1.4 GHz 카탈로그; 전파 검출만으로 1차 분류 규칙을 만들지 않음 |
| Wenger et al. 2000 (SIMBAD) | A&AS 143, 9 | — | `designations.py`<br>`Classifier/literature.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | SIMBAD 주 식별자와 큐레이터 지정 천체 유형(문헌 기반) |
| Oberto et al. 2018 (SIMBAD object types) (저장소 표기 그대로) | — | — | `Preprocess/classification_rules.csv` SIMBAD-TYPE-001<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_simbad_type) | SIMBAD 계층적 천체 유형 체계 |
| Suh 2021 (Galactic AGB catalogue) | ApJS 256, 43; VizieR J/ApJS/256/43 | `2021ApJS..256...43S` | `Get_data/agb_suh2021.py` (table9–12)<br>`Classifier/literature.py`<br>`Classifier/axes/physical.py`<br>`Preprocess/association_model.py`<br>`benchmark/build_agb_chemistry_truth.py` (table11/12)<br>`Classifier/VALIDATION_REPORT_2026-09-28.md` | O-rich/C-rich AGB 목록: 물리 축 AGB 증거, AGB 화학형 정답, 'from paper' 분류 |
| Parker, Bojicic & Frew 2016 (HASH PN database) | — | `2016JPhCS.728c2008P` | `Classifier/literature.py`<br>`Classifier/LITERATURE_MULTI_AXIS.md`<br>`Get_data/hash_pn.py` (V/163/pnmain, 'HASH PN Catalog') | 흉내 천체를 걸러낸 은하계 행성상성운 DB; 외부 정답·출처 |
| Manchester et al. 2005 (ATNF Pulsar Catalogue) | AJ 129, 1993 | `2005AJ....129.1993M` | `Classifier/literature.py`<br>`Classifier/LITERATURE_MULTI_AXIS.md`<br>`Get_data/atnf_pulsar.py` (HEASARC ATNFPULSAR)<br>`Classifier/truth/build_independent_truth_sets.py` (VizieR B/psr/psr) | 펄서 기준·정답 카탈로그 |
| Barbon et al. 1999 (Asiago Supernova Catalogue) | A&AS 139, 531 | `1999A&AS..139..531B` | `Classifier/literature.py`<br>`Get_data/asiago_supernova.py` (B/sn/sncat)<br>`Classifier/truth/build_independent_truth_sets.py` | 2017년까지의 초신성 목록(과도 현상 증거, SN 정답) |
| Holoien et al. 2017 (ASAS-SN supernovae) | MNRAS 464, 2672 | `2017MNRAS.464.2672H` | `Classifier/literature.py` ('ASAS-SN Supernova Catalog') | 'from paper' 초신성 분류의 출처 논문. 주의: 같은 카탈로그 이름의 수집기는 Neumann et al. 2023 표를 조회함 |
| Neumann et al. 2023 (ASAS-SN bright supernovae 2018–2020) | VizieR J/MNRAS/520/4356 | — | `Get_data/asas_sn_supernova.py` (table1, table2) | 2018–2020 밝은 초신성 목록(과도 현상 증거) |
| Acker et al. (연도 미기재; Galactic PN catalogue VizieR V/84) (저장소 표기 그대로) | VizieR V/84 (main, intens) | — | `Get_data/pn_spectroscopy.py`<br>`Classifier/truth/build_independent_truth_sets.py`<br>`Classifier/axes/phenomenon.py` ('Acker PN Spectroscopy') | PN 방출선 세기(H, He, [O III], [N II], [S II])와 PN 정답 집합 |
| Guo et al. 2022 (LAMOST DR5 white dwarfs) | VizieR J/MNRAS/509/2674 (table3, table6) | — | `Classifier/build_lamost_star_external_truth.py`<br>`Classifier/build_wd_subtype_truth.py`<br>`Classifier/WD_SUBTYPE_VALIDATION.md`<br>`Classifier/WD_SUBTYPE_XP_VALIDATION.md`<br>`Classifier/WD_SUBTYPE_XP_EXTERNAL_VALIDATION.md`<br>`Classifier/STAR_WD_EXTERNAL_VALIDATION.md` | 백색왜성 외부 정답과 DA/DB 학습 정답 |
| Kepler et al. 2019 (SDSS DR14 white dwarfs) | VizieR J/MNRAS/486/2169 (table2) | — | `Classifier/build_sdss_wd_subtype_external_truth.py`<br>`Classifier/WD_SUBTYPE_XP_EXTERNAL_VALIDATION.md` | DA/DB 독립 외부 검증 정답(213개) |

<a id="data"></a>
## 데이터 출처 카탈로그 (논문 인용 없음)

코드가 VizieR ID·서비스 이름으로만 쓰고, 저장소 어디에도 출판 논문이 적혀 있지 않은 카탈로그. 논문을 찾아 추가해야 할 목록.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| AllWISE — 저장소에 논문 인용 없음 | VizieR II/328/allwise | — | `Get_data/allwise.py`<br>`benchmark/build_agb_chemistry_truth.py` | 중적외선 W1–W4 측광 |
| 2MASS Point Source Catalog — 저장소에 논문 인용 없음 | VizieR II/246/out | — | `Get_data/twomass.py`<br>`benchmark/build_agb_chemistry_truth.py` | 근적외선 J/H/Ks 측광 |
| FIRST (first14) — 저장소에 논문 인용 없음 | VizieR VIII/92/first14 | — | `Get_data/first.py`<br>`benchmark/RADIO_XRAY_BENCHMARK_RESULTS.md` | 1.4 GHz 전파 플럭스, 전파 선택 벤치마크 |
| LoTSS DR2 — 저장소에 논문 인용 없음 | VizieR J/A+A/659/A1 | — | `Get_data/lotss.py` | 144 MHz 전파 플럭스 |
| VLASS — 저장소에 논문 인용 없음 | VizieR J/ApJS/255/30 | — | `Get_data/vlass.py` | 3 GHz 전파 플럭스 |
| Chandra Source Catalog 2.0 — 저장소에 논문 인용 없음 | VizieR IX/57/csc2master | — | `Get_data/chandra.py` | X선 대응체 |
| XMM-Newton 4XMM-DR13 — 저장소에 논문 인용 없음 | VizieR IX/74/4xmmdr13s | — | `Get_data/xmm.py` | X선 대응체 |
| eROSITA eRASS1 — 저장소에 논문 인용 없음 | VizieR J/A+A/682/A34 | — | `Get_data/erosita.py` | X선 대응체 |
| LAMOST DR5 — 저장소에 논문 인용 없음 | VizieR V/164/dr5 | — | `Get_data/lamost_spectroscopy.py`<br>`Classifier/build_lamost_star_external_truth.py` | 분광 분류·적색편이, 일반 별 외부 정답 |
| SDSS DR18 (PhotoObj, spectroscopy) — 저장소에 논문 인용 없음 | SDSS CAS (VizieR ID 없음) | — | `Get_data/sdss_dr18.py`<br>`Get_data/sdss_spectroscopy.py` | 측광·형태(type), 분광 class/subclass/z — 벤치마크 정답 |
| NED — 저장소에 논문 인용 없음 | NASA/IPAC NED (astroquery) | — | `Get_data/ned.py` | 외부은하 선호 유형·적색편이·참고문헌 수 |
| ASAS-SN Variable Stars — 저장소에 논문 인용 없음 | VizieR II/366/catv2021 | — | `Classifier/truth/build_independent_truth_sets.py` | 변광성 축 독립 정답(RRAB, RRC, DCEP, M, SR) |
| Gaia DR3 VizieR 사본 — 저장소에 논문 인용 없음 | VizieR I/355/gaiadr3, I/355/paramp, I/358/vclassre, I/358/vrrlyr, I/358/vcep, I/358/vlpv | — | `Get_data/gaia_dr3.py`<br>`Get_data/gaia_dr3_physical_vizier.py`<br>`Get_data/gaia_dr3_variability_vizier.py`<br>`Get_data/gaia_dr3_variability_sos_vizier.py` | Gaia TAP 장애 시 대체 경로, SOS 변광 세부 유형 (논문은 측성·Gaia 표 참조) |

<a id="method"></a>
## 교차 대응·통계·분류 방법

교차 대응 사후확률, 사전확률 추정, kNN·결정트리 등 분류기, 별/은하 형태 분리.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Budavári & Szalay 2008 | ApJ 679, 301 | — | `Preprocess/association_model.py`<br>`CHANGELOG.md`<br>`WORK_LOG_2026-10-08.md` | 베이즈 교차 대응 멤버십 사후확률 L/(L+ρ) |
| Saerens, Latinne & Decaestecker 2002 | Neural Computation 14, 21 | — | `Preprocess/05_likelihood_vectors.py` (estimate_field_prior, --field-prior)<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | 레이블 이동에서 필드별 클래스 사전확률 EM 재추정 |
| Ball et al. 2006 | ApJ 650, 497; DOI 10.1086/507440 | — | `Preprocess/color_knn.py`<br>`Preprocess/classification_rules.csv` LS-CKNN-001, PS1-CKNN-001<br>`Preprocess/LITERATURE.md` (DT-HIER-001)<br>`CHANGELOG.md`<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | 색 공간 kNN 분류, SDSS DR3 결정트리 별/은하 분류와 외삽 경고 |
| Suchkov, Hanisch & Margon 2005 (ClassX) | AJ 130, 2439; DOI 10.1086/497363 | — | `Preprocess/LITERATURE.md` (DT-HIER-001) | 사선 결정트리 10개 가중 투표, 클래스 확률 분포 |
| Vasconcellos et al. 2011 | AJ 141, 189; DOI 10.1088/0004-6256/141/6/189 | — | `Preprocess/LITERATURE.md` (DT-HIER-001) | 결정트리 13종 별/은하 분리 비교, 등급 의존성 |
| Clarke et al. 2020 | A&A 639, A84 | — | `Preprocess/LITERATURE.md` (DT-HIER-001) | SDSS+WISE 랜덤 포레스트 별/은하/퀘이사 분류, 확률·검증 분리 |
| Tachibana & Miller 2018 | PASP 130, 128001; DOI 10.1088/1538-3873/aae3d9 | — | `Preprocess/classification_rules.csv` PS1-MORPH-001/002 (Sec. 4.1)<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_ps1_morphology)<br>`Preprocess/LITERATURE.md` | PS1 iPSF − iKron > 0.05 확장원 판별과 한계 |
| Farrow et al. 2014 | MNRAS 437, 748–770; DOI 10.1093/mnras/stt1933 | — | `Preprocess/LITERATURE.md` | PS1 별/은하 분리 배경과 검증 |

<a id="star"></a>
## 별 분류

분광형·광도 계급, 백색왜성, 적색 거성군, 운동학 집단, 금속 결핍, 쌍성, 변광, AGB/RGB.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Pecaut & Mamajek 2013 | ApJS 208, 9 | — | `Classifier/subclass.py` (분광형 GAIA_BPRP0/LS_GR0/PS1_IZ/GAIA_TEFF, 주계열 M_G)<br>`Preprocess/units.py`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | 왜성 색–Teff 계열(분광형 척도) |
| Mamajek, "A Modern Mean Dwarf Stellar Color and Effective Temperature Sequence", v2022.04.16 | — | — | `Classifier/reference/mamajek_dwarf_sequence.csv`<br>`Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` (E1) | Pecaut & Mamajek 계열의 유지 판 표(SpT, Teff, BP−RP, M_G, g−r, i−z 등) |
| Ciardi et al. 2010/2011 (저장소 표기 그대로) | — | — | `Classifier/subclass.py` (star_luminosity_class, GAIA_LOGG)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | Kepler 대상의 Teff–log g 거성 경계(시차 없을 때 광도 계급) |
| Hurley & Tout 1998 | — | — | `Classifier/subclass.py` (star_luminosity_class)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | 같은 질량 쌍성은 주계열 위 최대 0.75 mag → V 계급 경계 ΔM > −1 |
| Kuiper 1939 | — | — | `Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | 준왜성(VI)이 주계열 아래 1–2 mag |
| Gizis 1997 | — | — | `Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | 준왜성(VI)이 주계열 아래 1–2 mag |
| Gentile Fusillo et al. 2021 (Gaia EDR3 white-dwarf candidate catalogue) | MNRAS 508, 3877 | — | `Classifier/branches/star.py` (HR_GATES, _wd_hr_signal)<br>`Classifier/train_validate_star_wd.py`<br>`Classifier/subclass.py`<br>`Preprocess/units.py`<br>`Classifier/WD_HR_GATE_EVALUATION.md`<br>`Classifier/STAR_WD_VALIDATION.md`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`CHANGELOG.md`<br>`WORK_LOG_2026-10-08.md`<br>`WORK_REPORT_2026-10-10.md` | 백색왜성 HR 궤적 M_G > 6 + 5(BP−RP), ϖ/σ ≥ 4 또는 고유운동 유의도 > 10 |
| Vincent et al. 2023 | MNRAS 521, 760; doi:10.1093/mnras/stad580 | — | `Classifier/LITERATURE.md`<br>`Classifier/STAR_WD_VALIDATION.md` | Gaia+SDSS 백색왜성 후보 선택·분광형 분류 파이프라인(모듈 구조 근거) |
| García-Zamora et al. 2023 (저장소 표기 그대로) | A&A 679, A127 (Classifier/STAR_WD_VALIDATION.md); Classifier/LITERATURE_MULTI_AXIS.md는 'MNRAS 521, 760'으로 표기 — 불일치 | — | `Classifier/train_validate_wd_subtype_xp.py`<br>`Classifier/WD_SUBTYPE_VALIDATION.md`<br>`Classifier/STAR_WD_VALIDATION.md`<br>`Classifier/LITERATURE_MULTI_AXIS.md` | XP 110개 Hermite 계수 랜덤 포레스트로 DA/non-DA 분류(약 90 %) |
| Jiménez-Esteban et al. 2023 | MNRAS 518, 5106; doi:10.1093/mnras/stac3382 | — | `Classifier/LITERATURE.md`<br>`Classifier/LITERATURE_MULTI_AXIS.md` | Gaia DR3 100 pc 백색왜성 분광 분류, DA/non-DA > 90 % |
| Babusiaux et al. 2018 (Gaia DR2 HRDs) | A&A 616, A10 | — | `Classifier/subclass.py` (POPULATION_VT)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | 접선 속도 창: 얇은 원반 < 40, 두꺼운 원반 60–150, 헤일로 > 200 km/s |
| Belokurov et al. 2020 | — | — | `Classifier/subclass.py` (RUWE_BINARY)<br>`Classifier/LITERATURE_SUBCLASS.md` | RUWE > 1.4 = 분해되지 않은 동반성(위치천문 쌍성 후보) |
| Gaia Collaboration, Smart et al. 2021 (Gaia Catalogue of Nearby Stars) | — | — | `Classifier/subclass.py` (NEARBY)<br>`Classifier/LITERATURE_SUBCLASS.md` | 100 pc 근거리 별 부피(ϖ > 10 mas) |
| Lépine & Shara 2005 (LSPM-North) | — | — | `Classifier/subclass.py` (HIGH_PM)<br>`Classifier/LITERATURE_SUBCLASS.md` | 고유운동 > 150 mas/yr 한계 |
| Ruiz-Dern et al. 2018 | A&A 609, A116 | — | `Classifier/subclass.py` (RED_CLUMP)<br>`Classifier/LITERATURE_SUBCLASS.md` | 적색 거성군 M_G = 0.495 + 1.121(G−Ks−2.1), 고유 산포 ~0.2 mag |
| Koenig et al. 2012 | — | — | `Classifier/subclass.py` (IR_EXCESS)<br>`Classifier/LITERATURE_SUBCLASS.md` | class II 궤적 하한 W1−W2 > 0.25, W2−W3 > 1.0 (적외선 초과) |
| Beers & Christlieb 2005 | — | — | `Classifier/subclass.py` (METAL_POOR)<br>`Classifier/LITERATURE_SUBCLASS.md` | [M/H] < −1 '금속 결핍' 정의 |
| Covey et al. 2007 | AJ 134, 2398 | — | `Preprocess/color_knn.py`<br>`Preprocess/classification_rules.csv` LS-CKNN-001, PS1-CKNN-001<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | 휘어진 항성 궤적(선형 색 모형이 못 따라감 → kNN) |
| Elsworth et al. 2019 (APOKASC evolutionary states) | MNRAS 489, 4641 | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 성진학 기반 적색거성 진화 단계; AGB 분리는 어려움 |
| Vrard et al. 2025 (Kepler red-giant evolutionary states) (저장소 표기 그대로) | VizieR J/A+A/697/A165 (table4) | — | `Classifier/truth/build_independent_truth_sets.py`<br>`Classifier/truth/generated/README.md`<br>`Classifier/MODEL_STATUS_AND_IMPROVEMENT_2026-10-08.md`<br>`Classifier/LITERATURE_MULTI_AXIS.md` ('Vrard et al. (2024 preprint)') | RGB(EV=1)/AGB 후보(EV=2) 독립 정답. LITERATURE_MULTI_AXIS.md의 2024 preprint 표기와 같은 연구로 보고 병합 |
| Groenewegen 2017 | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 미라·RR Lyrae·세페이드 주기-광도 관계 |
| Lebzelter et al. 2018 | A&A 616, L13 | — | `Classifier/subclass.py` (agb_chemistry, GAIA_2MASS_WESENHEIT) | Gaia–2MASS Wesenheit 차 W_RP−W_KJ로 O-rich/C-rich AGB 구분 |
| Mowlavi, Trabucchi & Lebzelter 2019 | arXiv:1907.05359 (저장소 표기 그대로) | — | `Classifier/subclass.py` (AGB_DW_C) | 은하계 LPV의 O/C 경계 ≈ 0.9 mag |
| Abia et al. 2020 | A&A 633, A135 | — | `Classifier/subclass.py` (AGB_DW_XC) | 은하계 탄소별 Gaia–2MASS 도표, 극단 C-rich 경계 ≈ 1.7 mag |
| Lian et al. 2014 | A&A 564, A84 | — | `Classifier/subclass.py` (WISE_LIAN14) | AllWISE W1−W2 대 W3−W4 직선으로 O-rich/C-rich AGB 구분 (87 %/86 %) |

<a id="galaxy"></a>
## 은하 분류

활동성(BPT), 형태·광도 분포, 색, 광도, 환경, 녹색 계곡.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Baldwin, Phillips & Terlevich 1981 | PASP 93, 5 | — | `Classifier/LITERATURE.md`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | BPT 진단도 [O III]/Hβ vs [N II]/Hα |
| Veilleux & Osterbrock 1987 | ApJS 63, 295 | — | `Classifier/LITERATURE.md` | [S II]·[O I] 포함 방출선 진단 |
| Kauffmann et al. 2003 | — | — | `Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | BPT 별생성/AGN 경계(SDSS subclass의 근거) |
| Kewley et al. 2001 | — | — | `Classifier/LITERATURE_SUBCLASS.md` | BPT 최대 별폭발 경계(SDSS subclass의 근거) |
| Jarrett et al. 2017 | ApJ 836, 182 | — | `Classifier/subclass.py` (galaxy_activity WISE W2−W3)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | W2−W3 > 3.0 별생성 원반, < 1.5 구상체 |
| Jarrett et al. 2019 | ApJS 245, 25 | — | `Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | W2−W3 > 3.0 별생성 원반, < 1.5 구상체 |
| Kaviraj et al. 2007 | — | — | `Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | (NUV−r)₀ > 5 → 정지 은하 |
| Wyder et al. 2007 | — | — | `Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | NUV−r 적색 계열과 녹색 계곡 |
| Salim 2014 | SerAJ 189, 1 | — | `Classifier/subclass.py` (green valley)<br>`Classifier/LITERATURE_SUBCLASS.md` | 녹색 계곡 4 < NUV−r ≤ 5, 전이 단계·AGN이 많음 |
| Shen et al. 2003 | MNRAS 343, 978 | — | `Classifier/subclass.py` (galaxy_profile)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | Sérsic n ≥ 2.5 조기형 / < 2.5 원반 |
| Blanton et al. 2003 (저장소 표기 그대로) | — | — | `Classifier/subclass.py` (galaxy_profile)<br>`Classifier/LITERATURE_SUBCLASS.md` | Sérsic n 기준의 보조 근거 |
| Strateva et al. 2001 | AJ 122, 1861 | — | `Classifier/subclass.py` (SDSS_UR)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | SDSS (u−r)₀ = 2.22 조기형/만기형 경계 |
| Khachikian & Weedman 1974 | — | — | `Classifier/LITERATURE_SUBCLASS.md` | 1형/2형 AGN(세이퍼트) 구분 |
| Tammann 1994 | — | — | `Classifier/subclass.py` (dwarf)<br>`Classifier/LITERATURE_SUBCLASS.md` | 왜소은하 M_B > −16 |
| Best & Heckman 2012 | — | — | `Classifier/subclass.py` (radio-loud AGN candidate)<br>`Classifier/LITERATURE_SUBCLASS.md` | 정지 은하의 전파 방출 = 전파 모드 AGN |
| Hubble 1926 | — | — | `Classifier/subclass.py` (edge-on/face-on)<br>`Classifier/LITERATURE_SUBCLASS.md` | 경사각 cos²i = (q² − q0²)/(1 − q0²) |
| Holmberg 1958 | — | — | `Classifier/subclass.py`<br>`Classifier/LITERATURE_SUBCLASS.md` | 고유 두께 q0 = 0.2 |
| Kenney et al. 2004 | — | — | `Classifier/LITERATURE_SUBCLASS.md` | NGC 4522 경사각 i ≈ 78° (계산값 81°와 비교) |
| Tago et al. 2010 | — | — | `host_groups.py` (DV_MAX_KMS) | 은하군 연결 속도 ~250–1000 km/s → 같은 은하 판정 1500 km/s |
| Zhou et al. 2023 | AJ 165, 58 | — | `Preprocess/color_knn.py`<br>`Preprocess/classification_rules.csv` LS-CKNN-001<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | DESI 표적 선택에 쓰인 은하의 중적외선 초과 |
| Banerji et al. 2010 (Galaxy Zoo ML) | MNRAS 406, 342; doi:10.1111/j.1365-2966.2010.16713.x | — | `Classifier/LITERATURE.md` | 기계학습으로 Galaxy Zoo 형태 재현 |
| Walmsley et al. 2020 (Galaxy Zoo Bayesian CNN) | MNRAS 491, 1554; doi:10.1093/mnras/stz2816 | — | `Classifier/LITERATURE.md` | 확률적 형태 분류·능동 학습 |
| Walmsley et al. 2022 (Galaxy Zoo DECaLS) | MNRAS 509, 3966; doi:10.1093/mnras/stab2093 | — | `Classifier/LITERATURE.md` | 세부 시각 형태 측정 → 계층적 형태 분기 |

<a id="qso"></a>
## 퀘이사·AGN

AGN/퀘이사 선택, 전파 세기, 광도, 가려진 퀘이사, 고적색편이, 분석에 쓴 우주론 매개변수.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Stern et al. 2012 | ApJ 753, 30 | — | `Preprocess/classification_rules.csv` WISE-AGN-001 (Sec. 3.5 / Fig. 6)<br>`Preprocess/04_build_evidence.py`<br>`Preprocess/03_extract_features.py`<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_allwise)<br>`Classifier/subclass.py` (galaxy_activity)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | W1−W2 ≥ 0.8, W2 < 15.05 (Vega) 중적외선 AGN; COSMOS 신뢰도 ~95 %, 완전도 ~78 % |
| Assef et al. 2018 (The WISE AGN Catalog) | ApJS 234, 23; DOI 10.3847/1538-4365/aaa00a | — | `Preprocess/classification_rules.csv` WISE-AGN-R90-001 (Eq. 4)<br>`Preprocess/04_build_evidence.py`<br>`Preprocess/LITERATURE.md` | AllWISE R90 경계 (α, β, γ) = (0.650, 0.153, 13.86) |
| Bañados et al. 2016 (PS1 distant z > 5.6 quasar survey) | ApJS 227, 11; DOI 10.3847/0067-0049/227/1/11 | — | `Preprocess/classification_rules.csv` PS1-QSO-Z6-001 (Sec. 2.1.1, Eq. 1–3)<br>`Preprocess/04_build_evidence.py`<br>`Preprocess/LITERATURE.md` | i-dropout 선택(i−z > 2.0 등) z ≈ 6 퀘이사 후보 |
| Chaussidon et al. 2023 (DESI QSO target selection) | ApJ 944, 107 | — | `Preprocess/classification_rules.csv` LS-MORPH-001/002, LS-COLOR-001<br>`Preprocess/03_extract_features.py`<br>`Preprocess/color_knn.py`<br>`Get_data/desi_legacy.py`<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | 퀘이사도 점광원(PSF 형태) → 점광원은 STAR/QSO 공통 증거; 중적외선 초과·청색 광학색 |
| Richards et al. 2002 (SDSS quasar target selection) | — | — | `Preprocess/LITERATURE.md` | 항성 궤적 거리 기반 선택 — 단순 색 절단으로 근사하지 않는다는 미채택 근거 |
| Richards et al. 2006 | — | — | `Classifier/subclass.py` (qso_tags ABS_MAG_RICHARDS06)<br>`Classifier/LITERATURE_SUBCLASS.md` | M_i(z=2)와 연속 K-보정(α_ν = −0.5) |
| Schneider et al. 2010 (SDSS DR7 quasar catalogue) | — | — | `Classifier/subclass.py` (H0, OMEGA_M, 퀘이사 광도 절단)<br>`Classifier/LITERATURE_SUBCLASS.md` | 퀘이사 M_i < −22 절단; 거리 계산용 평탄 ΛCDM H0 = 70, Ωm = 0.3 |
| Ivezić et al. 2002 | AJ 124, 2364 | — | `Classifier/subclass.py` (전파 세기)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md`<br>`app/APP_DESIGN.md` | R_i = 0.4(m_i − t), R_i > 1 전파 강함 |
| Kellermann et al. 1989 | — | — | `Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | 전파/광학 플럭스 비 > 10 = 전파 강함 |
| Ross et al. 2012 | — | — | `Classifier/subclass.py` (redshift class)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | z ≥ 2.1(Lyα forest가 광학에 들어옴) 고적색편이 |
| Hickox et al. 2007 | — | — | `Classifier/subclass.py` (HICKOX07)<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | 가린(붉은) 퀘이사 R − [4.5] > 6.1 (Vega), 신뢰도 ≈ 80 % |
| Fan et al. 2001 | — | — | `Classifier/subclass.py` (VERY_HIGH_Z)<br>`Classifier/LITERATURE_SUBCLASS.md` | z ≥ 5 재이온화 시대 퀘이사 |
| Fan et al. 2006 | — | — | `Classifier/subclass.py` (VERY_HIGH_Z)<br>`Classifier/LITERATURE_SUBCLASS.md` | z ≥ 5 재이온화 시대 퀘이사 |
| Joshi & Shinde 2026 | Eur. Phys. J. C 86, 766; doi:10.1140/epjc/s10052-026-15968-7 | — | `Classifier/LITERATURE.md` | SDSS DR16Q 전파 세기 ML 분류; 불균형 문제·QSO 라우팅 후에만 평가 |

<a id="radio"></a>
## 전파·X선·밀집성

전파 스펙트럼 지수, 펄서·중성자별 후보 선택.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Condon 1992 | ARA&A 30, 575 | — | `Preprocess/units.py` (std_radio_1p4ghz_mjy)<br>`Classifier/subclass.py` (RADIO_OTHER)<br>`Preprocess/LITERATURE.md`<br>`Classifier/LITERATURE_SUBCLASS.md`<br>`WORK_REPORT_2026-10-10.md` | 광학적으로 얇은 싱크로트론 지수 α = −0.7 (LoTSS 144 MHz·VLASS 3 GHz → 1.4 GHz) |
| Bates et al. 2014 (SPINN) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 신경망 펄서 후보 선택 |
| Hui et al. 2020 | MNRAS 495, 1093 | — | `Classifier/LITERATURE_MULTI_AXIS.md` | Fermi 펄서형 천체 ML 선택 후 X선/광학/IR 대응체 분석 |
| "Saz Parkinson et al.-style / later Fermi ML work" (저장소 표기 그대로) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 감마선 스펙트럼·변광 특징으로 펄서형과 AGN형 구분 |

<a id="trans"></a>
## 행성상성운·초신성·과도 현상

PN 진단, 광도곡선 기반 초신성/과도 현상 분류.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| Akras et al. 2019 | MNRAS 488, 3238 | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 2MASS/WISE 색 진단과 분류 트리로 조밀 PN과 흉내 천체 구분 |
| Akyuz et al. 2024 | MNRAS 527, 1481 | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 방출선 비·SMB/BPT 진단으로 PN 분광 확인 |
| Lochner et al. 2016 | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 광도곡선 특징 추출 + ML, 대표성 있는 학습 집합의 중요성 |
| Möller & de Boissière 2020 (SuperNNova) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | RNN 광도곡선 초신성 분류(극대 이전 곡선 포함) |
| "HSC transient ML work (2020)" (저장소 표기 그대로) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 시간 자료가 늘수록 성능 향상 |
| "Recent 4MOST transient classifier comparison (2025): SNID, DASH and NGSF" (저장소 표기 그대로) | — | — | `Classifier/LITERATURE_MULTI_AXIS.md` | 분광 과도 현상 유형 분류 도구 비교 |

<a id="doc"></a>
## 기타 문서

규칙의 근거로 인용된 설명서·릴리스 노트·소프트웨어 문서.

| 인용 | 학술지·권·쪽 | ADS bibcode | 사용처 | 무엇에 쓰였나 |
|---|---|---|---|---|
| STScI/MAST Pan-STARRS Public Archive, "How to separate stars and galaxies" | URL: https://outerspace.stsci.edu/spaces/PANSTARRS/pages/298812369/How+to+separate+stars+and+galaxies | — | `Preprocess/classification_rules.csv` PS1-MORPH-001/002<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_ps1_morphology)<br>`Preprocess/LITERATURE.md` | PSF−Kron 0.05(i), i ≈ 21보다 어두우면 불안정, i ≈ 14보다 밝으면 포화 |
| SDSS DR14 flux-calibration notes | — | — | `Preprocess/units.py`<br>`Preprocess/LITERATURE.md` | SDSS u_AB = u − 0.04, z_AB = z + 0.02 |
| WISE Explanatory Supplement, Sec. IV.4.h | — | — | `Preprocess/units.py`<br>`Preprocess/LITERATURE.md` | WISE Vega→AB 보정값 |
| AllWISE Explanatory Supplement | — | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_allwise) | W1/W2 SNR·결함·혼잡(nb) 품질 기준 |
| 2MASS All-Sky Explanatory Supplement | — | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_2mass) | ph_qual 등급·cc_flg 품질 기준 |
| Gaia DR3 documentation Sec. 7.1.2 / DR2 RUWE documentation | — | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_gaia_astrometry) | RUWE 1.4 경고 척도 |
| Gaia DR3 DSC documentation | — | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_gaia_dsc) | DSC Combmod 확률 사용 조건 |
| SDSS spectroscopic pipeline documentation | — | — | `Preprocess/catalog_reliability.csv` (catalog_confidence_sdss_spectroscopy)<br>`Preprocess/classification_rules.csv` SPC-SDSS-001/002/003 (reference 'SDSS spectroscopy') | ZWARNING 품질 플래그 |
| SDSS photometric pipeline — Morphology/Classification and clean-photometry guidance | — | — | `Preprocess/classification_rules.csv` SDSS-PHOTO-001/002<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_sdss_photometry) | type = 3 확장 / type = 6 점광원, clean = 1 |
| NASA/IPAC Extragalactic Database — object-type and preferred-data documentation | — | — | `Preprocess/classification_rules.csv` NED-TYPE-001<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_ned_type) | NED 선호 천체 유형의 의미 |
| SIMBAD object-type guide / documentation | — | — | `Preprocess/classification_rules.csv` SIMBAD-TYPE-001<br>`Preprocess/catalog_reliability.csv` (catalog_confidence_simbad_type) | SIMBAD 주 천체 유형 계층 |
| desitarget (targets.encode_targetid) | — | — | `Preprocess/association_model.py`<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md`<br>`WORK_LOG_2026-10-08.md` | DESI TARGETID에 LS RELEASE/BRICKID/OBJID가 들어 있음 → ID로 정확히 연결 |
| Redrock (DESI spectral classification, SPECTYPE) | — | — | `benchmark/build_desi_truth.py`<br>`Get_data/desi_spectroscopy.py`<br>`Preprocess/COARSE_BENCHMARK_RESULTS.md` | DESI 정답 레이블 SPECTYPE (ZWARN = 0, DELTACHI2 > 25) |

## 확인이 필요한 인용

저장소 안에서 확정할 수 없어 표에 "(저장소 표기 그대로)"로 남기거나 표에서 뺀 항목입니다.

- **García-Zamora et al. 2023** — `Classifier/STAR_WD_VALIDATION.md`는 A&A 679, A127, `Classifier/LITERATURE_MULTI_AXIS.md`는 MNRAS 521, 760으로 적습니다. 후자는 Vincent et al. 2023과 같은 권·쪽이라 둘 중 하나가 잘못 적혔을 수 있습니다.
- **ASAS-SN 초신성** — `Classifier/literature.py`는 'ASAS-SN Supernova Catalog'의 출처를 Holoien et al. 2017(2017MNRAS.464.2672H)로 적지만, 같은 이름의 수집기 `Get_data/asas_sn_supernova.py`는 Neumann et al. 2023(J/MNRAS/520/4356)을 조회합니다.
- **Vrard et al.** — `LITERATURE_MULTI_AXIS.md`는 "2024 preprint", 코드는 "Vrard+2025"(J/A+A/697/A165)입니다. 같은 연구로 보고 하나로 합쳤습니다.
- **Acker et al.** — 연도·학술지 없이 VizieR V/84로만 인용됩니다.
- **Clementini et al. 2022/2023, Ripepi et al. 2022/2023, Ciardi et al. 2010/2011** — 어느 해 논문인지 특정하지 않습니다.
- **Gaia DR3 논문 URL 5건** (`STELLAR_EVIDENCE_CONFIGURATION_2026-10-08.md`) — 저자 없이 제목과 A&A URL만 있습니다. 위 Rimoldini/Clementini/Lebzelter 항목과 같은 논문일 수 있으나 저장소에서 확인되지 않아 따로 두었습니다.
- **"Saz Parkinson et al.-style", "HSC transient ML work (2020)", "4MOST transient classifier comparison (2025)"** — 특정 논문을 가리키지 않습니다.
- **SFD E(B−V)** (`Preprocess/units.py`, `Classifier/subclass.py`) — 약어만 있고 논문 인용이 없어 표에서 뺐습니다.
- **"Schechter M*_B ~ −20.5"** (`Classifier/subclass.py`) — 광도 함수 이름으로만 쓰여 표에서 뺐습니다.
- **규칙표의 일반 참조** — `classification_rules.csv`의 "Gaia astrometry"(AST-GAL-001/002), "Gaia DR3"(DSC-001, VAR-001)는 특정 문헌이 아니어서 표에 넣지 않았습니다.
- **"데이터 출처 카탈로그 (논문 인용 없음)"** 13건 — 코드는 VizieR ID나 서비스 이름만 씁니다. 출판 논문을 확인해 탐사·카탈로그 표로 옮겨야 합니다.
