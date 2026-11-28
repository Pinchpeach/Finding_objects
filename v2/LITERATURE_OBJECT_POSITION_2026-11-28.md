# 문헌: 여러 목록이 잰 객체의 대표 좌표를 어떻게 정하는가 (과제 버, 2026-11-28)

**질문**: 한 객체에 여러 목록의 행이 붙어 있을 때 사용자에게 보이는 좌표는 무엇이어야 하는가. 지금은 그룹의 앵커(연관 순서가 정한 것)의 좌표다. 앵커는 `unfloored poserr`로 정해지는데, 연관에 쓰는 유효 σ(`max(poserr, 0.02″, PSF/6)`)로는 AllWISE(PSF/6 = 1.02″)가 광학 행(LS 0.6″ 바닥, PS1 0.2″)보다 크다. 그래서 AllWISE가 앵커인 객체는 위치가 정답에서 멀다(0.5″ 밖 71 %, `WORK_REPORT_2026-11-28d.md` 5.6절).

**읽은 것과 읽지 못한 것** (원문 확인 / 미확인을 구분한다; 확인한 인용은 짧게):

| 출처 | 확인 | 내용 | 우리 설계에 주는 것 |
|---|---|---|---|
| Wenger et al. 2000, A&AS 143, 9 (SIMBAD), 3.2.2절, arXiv:astro-ph/0002110 | **원문 확인** | "When astrometric data are available, the most accurate one has been selected for the 'basic data'. Other values may be available as measurements"; 좌표에 품질 부호 'A'(기준 자료) – 'E'(믿기 어려운 출처)와 오차 타원, 서지 참조가 붙고, 기본 표시는 ICRS 에포크 2000.0이며 시점 변환에 고유운동·시차·시선속도를 쓴다. | **가장 정확한 측정 하나를 고르고 나머지는 측정값으로 남기는** 관례. 우리의 `best` + `position_source` 열과 같은 구조. |
| Wilson & Naylor 2018, MNRAS, "Improving Catalogue Matching By Supplementing Astrometry with Additional Photometric Information", 7절, arXiv:1710.04896 | **원문 확인**(HTML v2) | 여러 목록을 차례로 맞출 때 "the position of a counterpart pair merge" 를 맞출 때마다 갱신하므로 "the most precise catalogues are used initially"; 새 위치는 "the weighted mean position of the two matched stars"; 갱신된 위치의 오차 분포는 다루기 어려워 "the appropriate covariance matrix and AUF of the most positionally precise of the two merged stars"를 쓰길 권한다. | 가중 평균은 표준이지만 **오차 모형은 가장 정밀한 쪽을 그대로 쓰는** 단순화가 문헌에 있다. |
| Makarov et al. 2023, "Radio-Optical Reference Catalog, version 1", VI절, arXiv:2305.17755 | **원문 확인**(HTML) | 목록 사이의 **계통 차(벡터 구면조화 적합)를 빼고 나서** "Compute a weighted average position for each source using all available corrected catalog positions and their formal covariances"; 출력 공분산 C0 = (Σ C_q⁻¹)⁻¹. | 가중 평균은 **목록 사이 계통 오차를 먼저 제거할 때** 이득을 준다. 우리는 목록별 계통 보정이 없다. |
| NED의 대표 위치 선택 규칙 | **읽지 못함** | NED 도움말·문서 페이지(`ned.ipac.caltech.edu/help/`, `/docs/objname/`)가 403/404였고 열린 FAQ는 적색편이 규칙(불확도와 기법으로 fiducial 값 선택)만 말한다. | 근거로 쓰지 않는다. |
| SIMBAD 사용자 안내서(`guide/*.htx`) | **읽지 못함** | 404 / 호스트 불가. 위 2000년 논문만 확인했다(현재 규칙이 같다는 보장은 없다). | 위 논문의 "most accurate"를 최소 근거로만 쓴다. |
| Gaia DR3 기준 계와 시점 | 저장소의 `LITERATURE_GAIA_DR4_2026-11-25.md`와 `association_model.PROFILES`("Gaia DR3": 에포크 2016.0) | ICRS, 에포크 2016.0. | `position_epoch` 열에 목록의 시점을 적는다. |

**결론(설계)**:

1. 대표 좌표는 **구성원 중 유효 σ가 가장 작은 행 하나의 좌표**(`best`)로 한다. 가중 평균(`ivw_mean`)이 아니다. 이유: (가) SIMBAD가 같은 규칙(가장 정확한 측정 하나)을 쓴다. (나) 가중 평균은 목록 사이 계통 차를 빼 준 뒤에 이득이 있는데(Makarov+2023) 우리는 그 보정이 없다. (다) 서로 다른 에포크의 좌표를 섞으면 고유운동이 큰 별에서 좌표가 어느 시점의 것도 아닌 값이 된다. 한 행의 좌표는 그 행의 시점의 값이다. (라) **우리 자료의 실측**: 정답 대비 0.5″ 밖이 앵커 4.51 %, `best_member` 3.16 %, `ivw_mean` 3.28 %(`results_2026-11-28c/design_summary.csv`): 가중 평균이 낫지 않다.
2. 우선순위는 **연관에 쓰는 유효 σ**(`association_model.effective_sigma_arcsec`에서 고유운동 항만 뺀 것, `poserr_arcsec`(열의 단위는 `benchmark/position_errors/UNITS.md`가 문서에서 확인한 것; 기본 `legacy` 단위에서는 일부 목록의 값이 틀린 단위로 읽히므로 `V2_POSERR_UNITS=fixed`와 함께 켜면 결과가 더 정확하다))로 정하고, 같은 값이면(대개 PSF / 6 바닥이 같은 광학 목록끼리) **바닥 밑의 측정 오차**(`poserr_arcsec`)가 작은 쪽, 그다음 목록의 천체측량 우선순위(Gaia, LS, PS1, SDSS, 2MASS, AllWISE, GALEX, SIMBAD, NED), 목록 이름, 검출 id로 가른다(입력 순서에 의존하지 않는다). 첫 구현은 우선순위만으로 갈라 깊은 COSMOS에서 0.5″ 밖이 3.24 %였고(28d의 입력 순서 가름은 3.16 %), 바닥이 같을 때 측정 오차를 먼저 보면 3.16 %가 재현된다(`WORK_REPORT_2026-11-28g.md`).
3. **시점**: 한 행의 좌표라서 시점을 섞지 않는다. 그 행의 시점을 `position_epoch`에 적고, Gaia 고유운동으로 공통 시점에 옮기는 것은 하지 않는다(한계: 고유운동이 큰 별에서 `best`가 Gaia(2016.0)가 아닌 목록 행이면 그 목록의 시점이다. 앵커도 이미 같은 한계를 가진다).
4. **SIMBAD·NED 행은 후보에서 빼지 않는다**: 이 행들의 좌표는 이미 다른 측정에서 온 값이고 우리가 읽는 오차 열이 없으면 기본 오차(0.6″)를 받아 다른 목록보다 정밀한 적이 거의 없다(문헌 전용 객체는 유일한 구성원이라 그대로).
