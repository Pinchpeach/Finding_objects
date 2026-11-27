# 은하면 뒤 퀘이사 선택에서 오염을 줄이는 방법: 문헌 확인 (2026-11-27, 과제 라)

**목적**: 저위도(|b| < 20°)에서 우리 분류기가 QSO로 부르는 객체의 대부분이 거짓으로 보인다(`benchmark/lowlat_qso/LOWLAT_QSO.md`).
문헌이 오염을 어떻게 줄이는지, 어느 수치로 확인했는지 적는다.

**확인 방법**: arXiv 원문 PDF를 직접 내려받아 `pdftotext`로 읽었다(절·식 번호와 짧은 인용). 읽지 못한 것과 다른 논문을 통해서만 본 것은 따로 표시했다.
읽은 판: Fu 2021 arXiv:2102.09770, Fu 2022 arXiv:2206.05704, Huo 2025 arXiv:2502.05480, Stern 2012 arXiv:1205.0811,
Assef 2018 arXiv:1706.09901, Koenig & Leisawitz 2014 arXiv:1407.2262, Storey-Fisher 2024 (Quaia) arXiv:2306.17749,
Gaia Collaboration & Bailer-Jones 2023 arXiv:2206.05681.

## 1. 은하면 퀘이사 탐색 (Fu 2021, 2022; Huo 2025)

| 논문 | 확인한 것 (절) | 우리에게 |
|---|---|---|
| **Fu et al. 2021**, ApJS 254, 6 (arXiv:2102.09770) | 후보는 PS1 + AllWISE 점원, XGBoost 두 단계(별 / 은하 · 퀘이사, 퀘이사 / 은하). **5.3절 Gaia 고유운동 컷**: 고유운동 0의 확률밀도 f_PM0(식 10)를 이변량 정규분포로 계산하고 `log(f_PM0) ≥ −4`를 남긴다. 외부 불확도 σ_ext = (k²σ_i² + σ_s²)^½, k = 1.08, σ_s = 0.032 mas/yr (G < 13) 또는 0.066 mas/yr (G > 13)(Lindegren et al. 2018 방식). 이 컷은 LAMOST 은하면 별과 Stripe 82 표준별의 **94.1 %**를 제외하고 퀘이사의 **99.8 %**를 남긴다. "Nevertheless, faint stars can be major contaminants even with such strict cut". Gaia 고유운동이 없는 후보는 `log(f_PM0) = 99`로 남긴다. 로그의 밑은 읽은 본문에 적혀 있지 않다 | 컷의 모양과 값. 우리 파이프라인에도 Gaia 고유운동 시험(`AST-GAL-002`)이 있다 |
| 같은 논문 5.3절 | 중적외선 별 오염원: YSO, AGB, 행성상 성운(Kozlowski & Kochanek 2009; Koenig & Leisawitz 2014; Assef 2018). "Class II and Flat spectrum YSOs are the most-likely contaminants since they have optical and mid-IR SEDs similar to those of quasars"; Class I · II · Flat YSO는 대략 W1−W2 > 0.25, 1.0 < W2−W3 < 4.5(Koenig & Leisawitz 2014 그림 5의 요약)이고 이는 퀘이사 영역과 겹친다. AGB는 그 일부만 겹친다. 알려진 PN은 SIMBAD 교차로 제거 | 오염원의 종류와 색 영역 |
| 같은 논문 | SIMBAD 교차 2,786개로 본 퀘이사 순도 **~90 %**. "The true purity may vary at different locations in the Galactic plane" | 순도는 위치에 따라 다르다는 단서 |
| **Fu et al. 2022**, ApJS 261, 32 (arXiv:2206.05704) | 관측한 후보 243개: QSO 204, 별 17, 은하 2, 알 수 없음 20(표 1). 후보 230개(2021 목록)의 순도 하한 **85.2 %**(196/230), 별 오염 하한 6.1 %(14/230)(4.1절). 밝은 쪽(i_P1 < 16)에서 별 오염 < 36 %. 후보의 i_P1 범위 15.5–21.0 | 같은 후보 목록에서 별은 약 6–7 %. 순도는 선택 안에서만 |
| **Huo et al. 2025** (arXiv:2502.05480) | LAMOST DR10에서 확인한 퀘이사 1,982개. 후보 2,454개 중 QSO 1,949(79 %). 성공률은 10 < \|b\| < 20°, E(B−V) < 0.3에서 ~80 %이고 \|b\| < 5°, E(B−V) > 0.6에서 "very low", E(B−V) ≥ 1.0에서는 하나도 없음. 알려진 은하면 퀘이사 밀도는 \|b\| ≤ 20°에서 < 1 deg⁻², \|b\| ≤ 10°에서 ~0.1 deg⁻²(5.1절). Milliquas 개수 892(\|b\| ≤ 10°), 3,447(≤ 15°), 14,279(≤ 20°) | 기대 밀도 기준과 재현율이 소광·위도에 줄어든다는 확인 |

## 2. 중적외선 AGN 선택의 적용 범위 (Stern 2012; Assef 2018)

| 논문 | 확인한 것 | 우리에게 |
|---|---|---|
| **Stern et al. 2012**, ApJ 753, 30 (arXiv:1205.0811) | 기준 `W1 − W2 ≥ 0.8`(Vega)은 W2 ~ 15.0까지 61.9 ± 5.4 AGN deg⁻², **신뢰도 95 %**(COSMOS). "In terms of Galactic contamination, only the coolest brown dwarfs and the most heavily dust-reddened stars will exhibit such red WISE colors. ... **In a high Galactic latitude survey**, neither cool brown dwarfs nor dust-reddened stars will be significant contaminants at the flux limit of WISE." W2 < 15.05(160 μJy) 한계로 측정 | 신뢰도 95 %는 **고위도** 시험이다. `WISE-AGN-001`의 근거는 이 조건에서만 성립한다 |
| **Assef et al. 2018**, ApJS 234, 23 (arXiv:1706.09901) | R90(90 % 신뢰도)·C75 기준은 W1−W2 > α exp[β(W2 − γ)²]. 3.1.1절 "To avoid these issues, the first spatial filter we apply removes all sources closer than 30 deg from the GC, and all sources closer than 10 deg from the GP." 이유: YSO, AGB, H II 영역과 혼잡. Nikutta et al. (2014)는 YSO가 주로 GP 6° 안에 있다고 하므로(**2차 인용**) 이 컷이 대부분을 제거. 남은 것은 높은 위도의 별 형성 영역: 3.1.3절에서 H II 영역(Anderson et al. 2014; 반경의 2배)과 Lynds 어두운·밝은 성운(LDN, LBN; 반경)을 지우고, 3.1.2절에서 PN(Acker 1992; 반경의 2배)을 지운다. 3.1.1절: GP 15°에서 AllWISE 원천 밀도는 고위도의 50 %(혼잡 잡음)이라 "completeness ... lower for low Galactic latitudes, although reliability should not be severely affected" | R90은 \|b\| > 10°에서만 정의됐고, \|b\| 10–20°에는 별 형성 영역 마스크가 필요하다. 우리 규칙은 \|b\| > 10°와 GC 30°만 쓴다 |

## 3. 중적외선 별 오염원의 색 (Koenig & Leisawitz 2014)

arXiv:1407.2262, 4절(AllWISE 색 기준). W1·W2·W3 신호대잡음 조건과 χ² 컷 뒤:
- Class I(식 12–15): W2−W3 > 2.0, W1−W2 > −0.42(W2−W3) + 2.2, W1−W2 > 0.46(W2−W3) − 0.9, W2−W3 < 4.5.
- Class II(식 16–20): W1−W2 > 0.25, < 0.9(W2−W3) − 0.25, > −1.5(W2−W3) + 2.1, > 0.46(W2−W3) − 0.9, W2−W3 < 4.5.
- AGN 후보로 빼는 색-등급 컷(식 9–11): W1 > 1.8(W1−W3) + 4.1 이고 W1 > 13.0, 또는 W1 > (W1−W3) + 11.0.
- AGB 제거(식 34–37): W1 < (−10/3)(W1−W2) + 9 또는 W1 < (6/7)(W1−W2) + 5.5, 또는 네 밴드가 있고 W3−W4 < 1.9 이면서 W1−W2 < (W3−W4) − 0.45.
- "AGN occupy a similar part of color space to protostars": AGN과 원시별은 같은 색 영역에 있고, W4가 충분히 밝은 것만 원시별로 되찾는다.
- PN은 신호대잡음·χ² 컷을 통과하면 주로 YSO 영역 밖에 있다(4.3절); 단 Nikutta et al. (2014)가 YSO가 있을 것이라 예측한 `10 < W1 < 11, 0.4 < W1−W2 < 1.4, 4 < W2−W3 < 5.7`에는 PN이 대부분이다(**2차 인용**).

그러므로 **색만으로 AGN과 YSO를 가를 수 없다**: 색-등급 컷(둘째 항목)은 어두운 쪽을 AGN으로 두는 가정이고, 이 가정은 별 형성 영역이 아닌 외부 은하 시선(북극 근처)에서 세워졌다.

## 4. 전천 퀘이사 목록의 저위도 처리 (Quaia; Gaia DR3)

| 논문 | 확인한 것 | 우리에게 |
|---|---|---|
| **Storey-Fisher et al. 2024**, ApJ 964, 69 (Quaia, arXiv:2306.17749) | Gaia DR3 퀘이사 후보(전체 표)에서 오염을 줄이는 두 단계. 3.1절 고유운동 컷: μ < 10^{0.4(G − 18.25)} mas/yr(식 1; G = 18.25에서 약 2.5 mas/yr)으로 상위 집합의 2.6 %(39,470개)를 제거하고 SDSS 퀘이사의 거의 모두를 남긴다. 그다음 Gaia + unWISE 색 컷. 후보는 G < 20.6. "The dearth of quasars in the Galactic plane is due largely to dust extinction and stellar crowding, as well as the fact that the SDSS training set quasars ... are not representative of quasars in this dust-reddened region." 선택 함수는 "significantly lower accuracy around the galactic plane; precision measurements may require masking this region" | 별 오염 제거는 고유운동 + 색의 두 조건, 은하면은 마스크가 권고 |
| **Gaia Collaboration, Bailer-Jones et al. 2023**, A&A 674, A41 (arXiv:2206.05681) | `qso_candidates` 전체 순도 50–70 %, "significantly higher when we exclude the Galactic plane, high density regions ...". DSC `classlabel_dsc`의 순도 24 %(전천), \|b\| > 11.5°에서 41 %; `classlabel_dsc_joint` 62–63 %(전천), \|b\| > 11.54°에서 79–80 %. 8절 천문측정 선택: 1단계는 시차·고유운동이 통계적으로 유의하지 않은 원천인데, 이것만으로는 "insufficient ... about 214 million sources in Gaia EDR3, dubbed 'confusion sources', satisfy these astrometric criteria. These are mostly stars"이고 "astrometry cannot be used as an independent quasar classifier"; 2단계는 정규화한 시차·고유운동 분포가 거의 정규인 표본만 남긴다. 이 천문측정 선택(`astrometric_selection_flag`)의 순도는 "98 % or perhaps better" | 같은 분류기도 \|b\| 11.5° 밖에서 순도가 크게 오른다. 천문측정 일치는 별을 가르는 필요조건이고 충분조건이 아니다 |

## 5. 종합 — 문헌이 가리키는 것과 우리 코드

| 문헌 | 우리 코드의 현재 |
|---|---|
| Stern 2012의 95 %는 고위도 시험, 별 오염이 중요하지 않다는 말도 고위도 조건 | `WISE-AGN-001`(Stern)은 위도 제한이 없음(2.44.0이 "WISE 색 연속 특징은 단독으로 근거가 아님"이라고 한 것은 `WISE-COLOR-001` 선형 특징이고, 이 규칙은 별개의 문헌 신뢰도 근거로 단독 발화한다) |
| Assef 2018: R90은 \|b\| > 10°, GC 30° 밖에 정의, 별 형성 영역(H II, LDN, LBN)과 PN은 마스크 | `WISE-AGN-R90-001`은 \|b\| > 10°와 GC 30° 밖에서만 켜짐. 별 형성 영역 마스크는 없다 |
| Fu 2021: W1−W2·색 선택 + Gaia 고유운동 컷 `log f_PM0 ≥ −4`, 순도 ~90 %(SIMBAD), 85 %(분광) | 고유운동 시험은 별 쪽 증거로만 쓰이고 QSO의 필요조건은 아님 |
| Quaia: 고유운동 컷 + 색 컷 + G < 20.6, 은하면은 마스크 권고 | G 제한 없음 |
| Gaia DR3: \|b\| > 11.5°에서 순도가 크게 오르고, 천문측정은 필요조건 | 위도 사전확률(국소 Gaia 밀도) |
| 한 서베이만의 측정으로 퀘이사를 고르는 방법은 확인한 논문에 없음: 모든 선택이 둘 이상의 서베이(PS1 + WISE, Gaia + unWISE) | 한 서베이만의 행도 QSO가 될 수 있음 |

**읽지 못한 것**: Hughes, Bailer-Jones & Jamal 2022(Gaia DSC 위도 사전확률)와 Nikutta et al. 2014의 원문(Assef 2018과 Koenig & Leisawitz 2014를 통해서만 봄), Kozlowski & Kochanek 2009, Lindegren et al. 2018의 외부 불확도 식.
