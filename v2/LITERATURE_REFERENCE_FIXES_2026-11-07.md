# 문헌 확정 천체 검증에서 찾은 문제 4가지의 문헌 근거 (2.47.0)

`reference_objects/validation/REFERENCE_VALIDATION_2026-11-07.md`(2.46.2)에서 찾은 문제를 문헌 근거로 고쳤다. 원문 확인은 `.github/scripts/literature_excerpts.py`(GitHub Actions)로 했다. 인용 수는 OpenAlex 기준이다.

## 1. 문헌 목록 행이 측광 천체와 합쳐지지 않는 문제

| 문헌 | 인용 | 확인한 내용 | 적용 |
|---|---|---|---|
| Wenger et al. 2000, A&AS 143, 9 (SIMBAD) | – | SIMBAD 좌표는 그 천체의 가장 좋은 발표 측정값이다(독립 검출이 아님) | SIMBAD·NED·BZCAT·Suh·HASH·Acker·ATNF 행을 "주석"으로 취급한다. 측정 행을 모두 처리한 뒤 연관하고, 앵커가 되지 않는다 |
| Mazzarella et al. 2007, ASPC 382, 165 (NED) | – | NED는 서로 교차 동정되지 않은 다파장 항목을 별개 객체로 둔다 | 같은 목록의 행이 이미 있는 천체에도 주석 행이 붙을 수 있게 한다 |
| Budavári & Szalay 2008, ApJ 679, 301 | 139 | 위치 가능도의 베이즈 인자 | 후보가 여럿이면 가능성이 가장 큰 천체에 붙인다. 신뢰도는 후보 간 정규화 확률로 낮춘다 |
| Pineau et al. 2017, A&A 597, A89 | 71 | 다목록 χ-match 뒤 후보별 확률로 판정 | 같은 방식 |

**찾은 원인(진단 실행, 천체별 연관 표):**
- NED가 한 위치에 여러 항목을 돌려준다(광학·IR·X선 이름).
- "한 천체에 같은 목록 1행" 규칙 때문에 둘째 행부터는 0.01–0.3″ 거리인데도 별도 천체가 되었다.
- 진단 40개 천체를 재생하니 문헌 전용 천체가 104 → 24개로 줄었다.

**보완(첫 재검증 후):**
- 같은 목록의 행을 모두 합치니, NED가 일부러 따로 둔 천체까지 합쳐졌다.
  - 예: 초신성 SN 2005mq와 숙주 은하 SDSS J232021.69−002059.3(같은 위치), ABELL 2195와 소속 은하.
  - 한 행만 읽히므로 문헌 종류가 "Supernova" → "Galaxy"로 바뀌었다(Ia 4 → 1, Ib/c 4 → 2, 은하단 8 → 6).
- 근거(Mazzarella+2007): NED는 교차 동정이 안 된 측정을 대역 검출 종류(IrS·UvS·XrayS·RadioS·VisS)로 따로 둔다. 물리 종류(G, SN, GClstr, C* 등)가 붙은 항목은 NED가 서로 다른 천체로 판단한 것이다.
- 고친 것:
  - 물리 종류가 있는 NED·SIMBAD 행은 같은 목록의 물리 종류 행이 이미 있는 천체에 붙지 않는다.
  - 대역 검출 행은 그대로 합친다.
  - 합쳐진 경우 물리 종류 행을 우선해서 읽는다(`association_model.BAND_ONLY_TYPES`).

## 2. 변광성 하위 종류 (Gaia DR3 분류기)

| 문헌 | 인용 | 원문 | 적용 |
|---|---|---|---|
| Rimoldini et al. 2023, A&A 674, A14 (arXiv 2211.17238) | 114 | "δ Scuti (DSCT) or γ Doradus (GDOR) or SX Phoenicis (SXPHE) star … labelled as DSCT\|GDOR\|SXPHE"; "solar-like star (SOLAR_LIKE), including BY Draconis type (BY), rotating spotted star (ROT)"; "cataclysmic variable (CV)"; "RS Canum Venaticorum variable (RS)" | Gaia 분류 이름을 그대로 하위 종류로 내보낸다(DSCT\|GDOR\|SXPHE, BY_DRA\|ROT, RS_CVN, CV 등). RS는 자전 변광성으로 옮긴다(이전에는 "기타") |

## 3. 펄서 후보 (전파 전용 천체)

| 문헌 | 인용 | 원문 | 적용 |
|---|---|---|---|
| Jankowski et al. 2018, MNRAS 473, 4436 (arXiv 1709.08864) | 221 | "weighted mean spectral index of all pulsars … −1.60 ± 0.03" | 기존 규칙(Frail+2018, α ≤ −1.5)의 근거를 재확인 |
| de Gasperin, Intema & Frail 2018, MNRAS 474, 5008 | – | TGSS–NVSS 스펙트럼 지수 지도를 위치 교차 일치로 만듦 | 전파 목록 행은 전파 목록끼리 묶는다. 빔이 넓어 광학 후보가 여럿인 NVSS·TGSS 행이 각각 따로 남던 문제를 고친다 |

**찾은 원인:**
- 펄서 3개 모두 NVSS 행과 TGSS 행이 별개 천체였다(빔 45″·25″ 안의 광학 후보 때문에 "모호" 판정).
- 그래서 150 MHz–1.4 GHz 스펙트럼 지수를 한 번도 계산하지 못했다.
- 재생하니 세 천체 모두 NVSS+TGSS(+VLASS) 한 천체로 묶였다.

## 4. 행성상 성운과 X선 쌍성

| 문헌 | 인용 | 원문 | 적용 |
|---|---|---|---|
| Akras, Guzman-Ramirez & Gonçalves 2019, MNRAS 488, 3238 (arXiv 1907.10026) | 28 | "W1−W4 ≥ 7.87 and J−H < 1.10; H−W2 ≥ 2.24 and J−H < 0.50; and Ks−W3 ≥ 6.42 and J−H < 1.31" | 세 분류 나무 중 하나를 통과하면 PN 후보(2MASS·AllWISE Vega). 은하·QSO로 판정된 천체에는 적용하지 않는다 |
| Lin, Webb & Barret 2012, ApJ 756, 27 (arXiv 1207.1913) | 94 | "Stars have log(FX/FIR) ≲ −0.9, AGN −0.9 ≲ log(FX/FIR) ≲ 2.5, and compact objects log(FX/FIR) ≳ 0.5" | **구현하지 않음.** FIR의 정의(밴드·영점)를 원문 텍스트에서 확인하지 못했다(그림·식 안에 있음). 상수를 지어내지 않으려고 보류했다 |
| Neumann et al. 2023 (XRBcats, arXiv 2303.16137) | – | 고질량 X선 쌍성 목록, 동반성 분류(SG/Be) | 목록 근거만 확인했고 측광 판별 기준은 없음 |

## 5. 함께 찾은 수집 버그 (VizieR 미러)

- 2026-11-07 Strasbourg VizieR가 연결 시간 초과 상태였다.
- 미러 전환 순서상 다음인 CfA는 모든 목록에 "200 + 표 없는 VOTable"을 돌려주었다. IDIA는 같은 질의에 AllWISE 25행을 돌려주었다(진단 실행).
- 빈 응답이 성공으로 받아들여지고 CfA가 우선 미러로 고정되어, 520개 검증의 VizieR 목록(AllWISE·2MASS·GALEX 등)이 모두 비었다.
- 고친 것: 보조 미러의 표 없는 응답은 다음 미러로 넘긴다. 모든 미러가 비었을 때만 빈 결과로 인정한다.
