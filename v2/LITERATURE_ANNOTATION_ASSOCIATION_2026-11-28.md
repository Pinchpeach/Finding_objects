# 문헌 근거: NED·SIMBAD 행의 위치 품질, 문헌 위치를 탐사 검출에 맞추는 관례, AllWISE/GALEX 오차 열 (2026-11-28, 2.62.6)

`V2_ANNOT_ASSOC`·`V2_POSERR_NATIVE`·`lit_keep`(과제 하)의 근거. 모든 인용은 조사 에이전트가 **2026-11-28에 원문을 가져와서** 읽은 것이고, 가져오지 못한 것은 `NOT-VERIFIED`로 적었다. 이 환경에서 CDS(`cdsarc.cds.unistra.fr`, `simbad.cds.unistra.fr`)는 접속되지 않아 VizieR ReadMe와 SIMBAD 문서는 **CDS가 유지하는 CfA 미러**(`vizier.cfa.harvard.edu`, `simbad.harvard.edu`)에서 읽었다(CDS 원본과 바이트 비교는 하지 않았다). 아래 "우리 자료" 표시는 문헌이 아니라 저장소 자료에서 직접 잰 값이다.

## 1. SIMBAD

| 항목 | 원문 | 출처 | 상태 |
|---|---|---|---|
| 좌표 품질 등급(현재) | `quality : flag of quality — E ≥ 10" / D : 1-10" (and some old data) / C : 0.1-1''; as well as Tycho2, UCAC4, and Gaia DR2/3 without proper motions / B : 0.01-0.1''; as well as Tycho2 and UCAC4 with proper motions / A : Hipparcos and Gaia DR2/3 with proper motions; sometimes VLBI` | simbad.harvard.edu/simbad/sim-id?Ident=M_53 의 범례 | VERIFIED(미러) |
| 등급 (원 논문) | `a quality code from 'A' (reference data) to 'E' (unreliable origin); an error box (either a standard error, or an ellipse), and the bibliographic reference of the data.` 초 단위 한계는 적혀 있지 않다 | Wenger et al. 2000, A&AS 143, 9 (arXiv astro-ph/0002110) §3.2.2 | VERIFIED |
| 불확실한 좌표 | `uncertain coordinates (SIMBAD quality E or coordinates without reference): 5 to 30 arsec (risky!)` (VizieR 측광 도구의 검색 반경 안내) | 같은 M_53 페이지 | VERIFIED(미러) |
| `coo_err_maj`, `coo_err_min`, `coo_err_angle` | 단위 mas, mas, deg. 설명은 "Coordinate error major axis". **1σ인지, 반장축인지는 문서가 말하지 않는다**(utype은 `semiMajorAxis`, 설명은 "major axis") | simbad.harvard.edu/simbad/sim-tap/tables, 표 `basic` | VERIFIED(단위), NOT STATED(1σ) |
| `coo_wavelength` | TAP 설명: `Wavelength class for the origin of the coordinates (R,I,V,U,X,G)`. 문서와 자료가 다르다: 에이전트의 2026-11-28 TAP 집계에서 코드 O 19.7 M, 빈칸 0.84 M, N 0.58 M, R 0.39 M, I 0.17 M, Y, F, M, X, S, G, U가 있고 `V`는 없다. N·Y·F·S의 뜻은 문서를 못 찾음 | 같은 TAP 스키마와 질의 | 문서 VERIFIED, 코드 뜻 NOT-VERIFIED |
| `coo_err_maj` 채움 비율 | 전체 72 %, 품질 A 99.999 %, B 98.7 %, **C 29.6 %, D 25.5 %, E 25.2 %**, 품질 빈칸 0 % (에이전트의 2026-11-28 TAP 집계) | 에이전트 질의(재현은 이 환경에서 못 함) | 에이전트 보고 |

**우리 자료**(COSMOS 2′, SIMBAD 3,226행): `coo_err_maj`가 채워진 것은 19행(0.6 %)이고 중앙값 150 mas(0.15″), 최댓값 1050 mas. 단위가 mas인 것은 이 범위(arcsec라면 150″)와도 맞는다. `coo_qual`은 수집하지 않는다(`Get_data/simbad.py`의 `MAIN_COLUMNS`에 없다). `coo_wavelength`는 N 2,277, O 900, U 29, R 8, S 4, X 2, I 2, M 1이고, 좌표를 낸 서지코드(`coo_bibcode`)는 2017ApJS..228....7N 1,426, 2016ApJ...830...51S 776, 2007ApJS..172...99C 438, 2013A&A...556A..55I 175, 2022ApJS..258...11W 158(COSMOS2020) 등 깊은 COSMOS 카탈로그다.

## 2. NED

| 항목 | 원문 | 출처 | 상태 |
|---|---|---|---|
| cone-search 출력 | astroquery가 쓰는 legacy `nph-objsearch`(열: No., Object Name, RA, DEC, Type, Velocity, Redshift, Redshift Flag, Magnitude and Filter, Separation, References, Notes, Photometry Points, Positions, Redshift Points, Diameter Points, Associations)와 현재 API `ConeSearchByTarget` 모두 **위치 불확실성 열이 없다** | NED 인터페이스 문서, 에이전트의 실제 응답 확인 | VERIFIED |
| 개체별 위치 표 | `NED::API/PositionsOfObject`(`Ned.get_table('positions')`): `unc_sma` "Semi-Maj Unc", `unc_smi` "Semi-Min Unc", `equ_j2000_unc_pa` "PA of unc", 단위 arcsec·deg. 설명: `95 percent uncertainty ellipse in semi-major axis` | 같은 API 문서 | VERIFIED |
| NED TAP | 표는 `NEDTAP.objdir` 하나. `uncmaja`: "Uncertainty Ellipse, Semimajor Axis in arcseconds", `uncmina`, `uncposa`(deg, East of North), `pos_bibcode`. 3C 273 0.2° 원뿔에서 7,363개 중 7,357개가 `uncmaja`를 가짐(2XMM ≈4.7″, GALEXASC ≈2–3″, WISEA ≈0.3–0.5″). TAP 열 설명은 신뢰 수준을 적지 않는다 | ned.ipac.caltech.edu/tap/tables, 에이전트의 실제 질의 | VERIFIED |
| 신뢰 수준 | `Many pairs and triplets in NED have position errors that -- rather than representing the 95% confidence ellipse -- represent half the separation of the objects.` 즉 보통의 NED 위치 오차는 95 % 신뢰 타원 | NED SearchFAQ(M51 문항) | VERIFIED |
| 채택 위치 | `We try to adopt the best published position for each object. In many cases, this will be the position in the catalog in which the object originally appeared…`; 은하와 연관된 원천은 광학 위치를 선호하고, 은하핵의 조밀한 전파원이면 더 나은 전파 위치를 채택 | NED Calculations FAQ | VERIFIED |
| 'Positions'·'Object Names'·'Position uncertainty' 도움말, 수치 정확도 | 옛 `/help/` 페이지가 403/404 | — | NOT-VERIFIED |

**결론(우리 수집과 관련)**: 우리 NED 수집(`Get_data/ned.py`, astroquery cone search)은 불확실성을 받지 못한다. 읽으려면 수집을 NED TAP(`objdir.uncmaja`)로 바꿔야 하고, 그 값은 95 % 신뢰 타원이라 1σ로 쓰려면 2.45(2차원 95 %)로 나눠야 한다는 점이 FAQ에서 따라 나오지만, TAP 열 설명이 신뢰 수준을 적지 않아 **NED TAP 값에 같은 환산을 해도 되는지는 확인되지 않았다**. 이 환경은 NED·SIMBAD에 접속되지 않아 수집을 바꾸는 시험은 하지 않았다.

## 3. 문헌 위치를 탐사 검출에 맞추는 관례

번호는 에이전트가 정정한 것이다(제 질문의 번호 일부가 틀렸다): Milliquas v8 = arXiv:2308.01505, MORX v1 = 1609.05973, MORX v2 = 2308.01507, HMQ = 1502.06303, QORG = astro-ph/0407310, Marchesi+2016 = 1512.01105, Bianchi+2017 = 1704.05903, Morrissey+2007 = 0706.0755.

| 출처 | 반경·관례 | 원문 | 상태 |
|---|---|---|---|
| Milliquas v8 §10 | 위치 정확도만 말하고 반경은 없음 | `Astrometry is 0.01 arcsecond accurate for most objects… Radio and X-ray associations for these objects are presented as found` | VERIFIED |
| Milliquas v8 §8 | 전파·X선 연관은 우도, 오프셋 0.1″ 구간 | `likelihoods are now calculated at a granularity of 0.1 arcsecond astrometric offsets for all radio/X-ray source catalogs`; `RASS… has been dropped, as it has become clear over time that its resolution is too coarse to confidently identify optical sources in isolation.` | VERIFIED |
| MORX v2 §2 | 전파 탐사의 천문 정확도 | VLASS ≈0.5″, LoTSS 0.2″, FIRST ≈1″, RACS ≈2″, NVSS ≈5″ | VERIFIED |
| MORX v1 §5, Table 2 각주 | 고정 반경이 아니라 면밀도 방법: `a 2 arcsecond offset is more significant in sparse sky than in dense sky`; Chandra 80 %가 2″ 안, XMM 상대 정렬 평균 2″ | | VERIFIED |
| QORG (Flesch & Hardcastle 2004) | `co-positionality was a sufficient sole criterion for association only out to a 1.2 arcsec separation` (FBQS, 은하면 밖); 혼잡 구간에서는 `we have chosen to require co-positional fit within 1 arcsec` | astro-ph/0407310 p.10–13 | VERIFIED |
| HMQ | `Astrometry is arcsecond accurate for most objects, out to 2 arcsec precision for some legacy objects.` | 1502.06303 p.2, p.10 | VERIFIED |
| SDSS DR16Q (Lyke+2020) | 문헌 목록 대 상위집합 `0.5″ radius`; FIRST `2.0″`; 2RXS는 좌표만으로는 신뢰할 수 없다고 하고 AllWISE 짝과 `within 1″`; XMM `10″`(59 %가 1″ 안), 3XMM `5.0″`, Gaia `0.5″` | 2007.09001 §3, §7.4–7.8 | VERIFIED |
| Véron-Cetty & Véron 13판 | 플래그 `'O' for an Optical position with an accuracy better than 1arcsec; 'R' for a Radio position with an accuracy better than 1arcsec; 'A' for an approximative position` | CfA 미러 VII/258 ReadMe | VERIFIED(카탈로그), 논문 NOT-VERIFIED(403) |
| Chandra-COSMOS Legacy (Marchesi+2016) | 우도비 연관의 과밀도 반경 1″; 배경 5–30″ 고리; 광학 위치 오차 가정 K 0.2″, i 0.3″, 3.6 µm 0.5″; `More than 90% of the secure counterparts have a distance from the X-ray source smaller than 1′′` | 1512.01105 §3.1, §4, §5 | VERIFIED |
| COSMOS2020 (Weaver+2022) | 부속 카탈로그 매칭 `a conservative radius of 0.″6 consistently for all ancillary catalogs`; Chandra 연관은 하지 않고 Chandra COSMOS Legacy를 가져온다 | 2110.13923 §2.6 | VERIFIED |
| NWAY (Salvato+2018) | `If the number density of sources in the optical catalogue is high, there can always be a possible counterpart due to chance association`; XMM-COSMOS 평균 위치 오차 1.8″(0.1–7.33″); 광학·IRAC 카탈로그 오차는 상수 0.1″·0.5″ 가정 | 1705.10711 p.18–19 | VERIFIED |
| Fleuren+2012 | `With a search radius of 2″ we are unlikely to identify a wrong SDSS counterpart… around 2% (170 objects)` (SDSS 밀도 기준); 단순 최근접 방법은 밀도가 높으면 비효율 | 1202.3891 p.2, p.8 | VERIFIED |
| Sutherland & Saunders 1992 | ADS 500, OUP 403 | | NOT-VERIFIED |

어느 출처도 **깊은 장의 NED/SIMBAD 행에 대한 기본 위치 오차를 정하지 않는다**("no source states a default"). 에이전트의 제안(출처가 말한 것이 아님): 좋은 행 ≈1″, 근사·옛 위치 ≈2″, 2–3″에서는 위치만이 아니라 등급·색 사전을 함께 쓴다.

## 4. AllWISE `eeMaj`, GALEX `Nerr`/`Ferr` (VizieR II/328, II/335)

| 열 | 원문 | 출처 | 상태 |
|---|---|---|---|
| AllWISE `eeMaj`, `eeMin` | `arcsec eeMaj Semi-major axis of the error ellipse (1)`, `arcsec eeMin …` | CfA 미러 `ftp/cats/II/328/ReadMe` | VERIFIED(미러) |
| AllWISE `eePA` | `deg eePA Position angle of the error ellipse (1)`. 2021-02-16 갱신: "the position angle was wrongly computed as being north-of-east instead of east-of-north. The correct position angle from the previous version is thus 90-eePA" | 같은 ReadMe | VERIFIED(미러) |
| 노트 (1) | `the parameters of the error ellipse are computed from the 1-{sigma} in RA and Dec (sigra, sigdec) and the co-{sigma} sigradec with the formulae: {Delta} = (sigra^2^-sigdec^2^)^2^ + 4*sigradec^2^; eeMaj^2^ = 0.5*(sigra^2^+sigdec^2^+sqrt({Delta})); eeMin^2^ = 0.5*(sigra^2^+sigdec^2^-sqrt({Delta}))` → `eeMaj`는 1σ 오차 타원의 반장축(arcsec) | 같은 ReadMe | VERIFIED(미러) |
| `sigra`, `sigdec` | `One-sigma uncertainty in right ascension coordinate from the non-moving source extraction.` (arcsec) | IRSA AllWISE Explanatory Supplement `sec2_1a.html` | VERIFIED |
| `e_RA_pm`, `e_DE_pm` | `arcsec e_RA_pm ? Error on RA_pm` (IRSA `sigra_pm`과 대응하는지는 ReadMe가 적지 않음) | II/328 ReadMe | 단위 VERIFIED, 대응 NOT-VERIFIED |
| AllWISE 정확도 | `The positions of non-saturated, high SNR AllWISE Catalog sources (8<W1<12 mag) in non-confused region are accurate to ~50 mas radially… AllWISE position accuracy gradually decreases with decreasing source brightness.`; 추가해야 할 체계 오차 하한은 적혀 있지 않다 | `sec2_1.html` (II.1.e.ii), `sec2_5.html` | VERIFIED(하한은 NOT stated) |
| GALEX `Nerr` | `arcsec Nerr [0.4/3.3] Position error of the source in the NUV image (nuv_poserr)`; `Ferr` FUV `[0.4/2.4]`; `Ierr` 대역 사이 오차; `Nperr`/`Fperr` 푸아송 위치 오차(`[0.001/2.8]`); `Sep` FUV–NUV 간격(불확실성 아님). 1σ인지·방사 오차인지는 **적혀 있지 않다** | CfA 미러 `ftp/cats/II/335/ReadMe`, Bianchi+2017 부록 B | 단위·설명 VERIFIED, 1σ NOT stated |
| GALEX 절대 천문 | `Astrometry (1σ, R ≤ 0.6°): ±0.59″ (FUV band), ±0.49″ (NUV band)`; `matches between GALEX and other surveys can be safely performed with a 2″ window`; Bianchi: `GALEX astrometry is more accurate than 2.5″` | Morrissey+2007 Table 1, §6, 초록; Bianchi+2017 §6.1 | VERIFIED |

Morrissey의 0.49″/0.59″은 S/N ≥ 10 점원, 시야 중심 0.6° 안의 RMS이므로 `Nerr`/`Ferr`(0.4–3.3″)와 같은 양이 아니다.

## 5. 우리 자료에서 직접 잰 위치 정밀도 (문헌이 아님)

`benchmark/association_ambiguity/literature_position_accuracy.py`, 실사용 COSMOS 2′ 문헌 행에서 가장 가까운 COSMOS2020 원천(모든 등급)까지의 거리. 무작위 대조는 위치를 15–40″ 옮긴 것.

| 행 | 개수 | 중앙값 | ≤0.1″ | ≤0.3″ | ≤0.5″ | ≤1.0″ | 무작위 대조 (≤0.3″ / ≤0.5″ / ≤1.0″) |
|---|---|---|---|---|---|---|---|
| SIMBAD 전체 | 3,226 | 0.19″ | 17.7 % | 64.4 % | 70.7 % | 76.0 % | 1.2 % / 3.6 % / 14.8 % |
| SIMBAD `coo_wavelength`=O | 900 | 0.12″ | 38.4 % | 89.6 % | 92.8 % | 95.1 % | 1.6 % / 4.3 % / 15.2 % |
| SIMBAD `coo_wavelength`=N | 2,277 | 0.24″ | 9.8 % | 55.5 % | 63.2 % | 69.6 % | 1.1 % / 3.2 % / 14.5 % |
| NED 전체 | 1,476 | 0.20″ | 19.9 % | 63.5 % | 72.4 % | 78.5 % | 1.2 % / 3.6 % / 13.5 % |
| NED `Type`=G | 622 | 0.16″ | 25.1 % | 69.5 % | 73.3 % | 77.2 % | 1.6 % / 3.4 % / 13.7 % |

즉 이 영역의 문헌 행은 약 70 %가 COSMOS2020 원천의 0.5″ 안에 있고(무작위 3.6 %), 그중 중앙값이 0.1–0.2″라서(출처는 위 서지코드의 COSMOS 카탈로그), 코드가 가정하는 0.6″보다 3–5배 정밀하다(나머지 약 25 %는 COSMOS2020에 짝이 없는 행: 전파·X선·옛 위치 또는 더 어두운 원천). 반면 이 숫자는 COSMOS 카탈로그에서 온 행에 대한 것이고, 전파·X선 위치나 다른 장의 행에는 적용되지 않는다.
