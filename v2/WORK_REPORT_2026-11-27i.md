# 작업 보고서 2026-11-27i — 과제 카: 위치 오차 입력의 단위 (VLASS e_RAJ2000은 도, NVSS e_RAJ2000은 시간 초)

버전 제안: **2.62.0 (MINOR 후보)**. 기본 동작이 바뀐다(영향받는 영역에서 객체의 앵커와 위치, 일부 연결·라벨). 예전 동작은 `V2_POSERR_UNITS=legacy`로 그대로 재현된다. 과제 차는 같은 브랜치에서 2.61.10(PATCH, 기본값 그대로)이다.

## 0. 내가 이해한 요청과 한눈에 보는 답

**요청**: VLASS `e_RAJ2000`이 도(deg)로 보이는데 코드는 초각(arcsec)으로 읽어 오차가 ≈ 0이 된다는 의심을 (1) VizieR ReadMe·Gordon et al. 2021로 확인하고 모든 카탈로그의 위치 오차 열(수집기 열 이름, 문서의 단위, 코드가 가정한 단위) 전수표를 만든다. (2) 틀린 것을 고치고 전파 연관의 변화와 거짓·놓침을 잰다(깊은 COSMOS 26, 저위도 309, 실사용 3). 전파·X선이 1차 클래스에 기여 0이라 라벨 변화가 작을 거라는 **예측을 먼저 쓰고** 확인한다. 축(전파·X선 활동)과 하위 분류 변화도 센다. (3) 기본 동작이 바뀌므로 MINOR 후보, `legacy` 스위치, 버전 제안. (4) 저장소 문서의 Fleuren 2012 arXiv 번호를 원문으로 확인해 고친다.

**답**
1. **단위가 틀린 것은 두 곳뿐이다**: **VLASS**(도, 코드는 초각) 와 **NVSS의 RA 오차**(시간 초, 코드는 초각; Dec는 초각이라 맞다). 저장된 22개 카탈로그 약 86만 행을 행 단위로 비교하면 두 모드에서 `poserr_arcsec`가 다른 카탈로그는 이 둘뿐이다(VLASS 384행 중 314, NVSS 223행 중 70). 나머지는 코드의 가정이 맞거나(TGSS, LoTSS, eRASS1, 4XMM, Chandra, LS는 문서 또는 데이터로 확인) 단위 문제가 아니다(상수를 쓰는 AllWISE, GALEX, FIRST, SDSS, SIMBAD). 2MASS·Gaia·PS1은 이번에 문서를 다시 읽지 못했다(데이터의 크기는 가정과 맞음). 근거 수준은 항목마다 다르다: **VizieR ReadMe 원문은 이 환경에서 읽지 못했다**(`cdsarc` DNS/502). VLASS·NVSS 단위는 (a) 같은 표 안의 이름이 도인 열(`e_RAMdeg`)과 384행 모두 같은 값, (b) 값의 물리적 크기, (c) NVSS는 RA·Dec 오차비가 시간 초로 읽을 때 0.94, 초각으로 읽을 때 0.071(등방 오차여야 1)이라는 **데이터 근거**이고, TGSS는 논문 원문, 나머지는 표 1절의 수준대로이다 (UNITS.md).
2. **고쳤다**: `association_model.native_radec_errors_arcsec`가 카탈로그별로 변환한다(VLASS ×3600, NVSS RA × 15 cos δ). 예전 읽기는 `V2_POSERR_UNITS=legacy`. 시험 10개 + 도구 시험.
3. **영향**(338개 영역 중 값이 바뀌는 179개, 객체 366 964개): 전파 위치를 앵커로 가진 객체 116 → 55개(−53 %), 객체 수 −37, VLASS 행 중 광학 행과 한 객체인 것 151 → 173, 1차 라벨 변화 28개(23개는 분류되지 않았던 단편이 분류된 객체에 흡수된 것, 5개는 이미 분류된 객체의 클래스 변화), `compact_class` 0개. COSMOS2020 진실로 본 AllWISE·2MASS·GALEX 거짓·놓침은 1행 이내로 같다.
4. **내 예측의 일부가 틀렸다**: 앵커(116 → 55)와 컴팩트 축은 맞았지만, 연결 상태가 바뀐 VLASS 행(예측 ≤ 10, 실제 26), NVSS 행(≤ 2, 실제 15), 객체 수 변화(≤ 10, 실제 −37), 1차 라벨 변화(0–10, 실제 28)는 예측을 넘었다. 그리고 "전파·X선은 1차 클래스에 기여 0"이라는 전제 자체가 **정확하지 않다**: 융합 모델에 `radio_log_r`·`xray_log_fx_fo`의 학습된 계수가 있다(`*_detected` 항만 0).
5. **Fleuren et al. 2012 = arXiv:1202.3891(v2)**. 저장소에는 올바른 번호가 이미 두 문서에 있었고, 틀린 번호(1204.0467 = Škulj, "Interval matrix differential equations")는 내가 쓴 문헌 문서 한 곳에 "이 번호는 아니다"라는 경고로만 있었다. 원문 PDF를 읽고 식 번호까지 확인해 그 문서와 `posterior_calibration.py`(신뢰도 식을 eq. 6으로 적음, 실제는 eq. 3)를 고쳤다 (6절).

## 1. 단위 전수표 (요약; 전체와 근거 수준은 `benchmark/position_errors/UNITS.md`)

근거 수준: **원문** = 논문·문서를 직접 읽음 / **요약** = 가져오기 에이전트가 긴 문서의 요약을 전해 줌 / **데이터** = 저장된 행으로 측정 / **없음** = 확인 못함.

| 카탈로그 | 수집기 열 | 문서의 단위 (수준) | 코드가 가정한 단위 | 판정 |
|---|---|---|---|---|
| VLASS QL | `e_RAJ2000`, `e_DEJ2000` (= `e_RAMdeg`, `e_DEMdeg`) | **도** (데이터: `e_RAMdeg`와 384/384행 같음, 중앙값 0.079″; 열 문서 원문 없음) | 초각 | **틀림** |
| NVSS | `e_RAJ2000`, `e_DEJ2000` | RA **시간 초**, Dec 초각 (데이터: 0.94 vs 0.071, 223행) | 둘 다 초각 | **틀림(RA)** |
| TGSS ADR1 | `e_RAJ2000`, `e_DEJ2000` | 초각 (원문: Intema+2017 3.4절) | 초각 | 맞음 |
| LoTSS DR2 | `e_RAJ2000`, `e_DEJ2000` | 초각 (요약 + 데이터 8행: 피크 플럭스가 낮을수록 0.06 → 1″) | 초각 | 맞음(8행) |
| FIRST | 없음 (`Rms`는 mJy 잡음) | — (원문: unc(90 %) = Size(1/SNR + 1/20) 초각) | 상수 1.0″ | 단위 문제 아님, 행별 정보 미사용 |
| eRASS1 | `posErr` | 초각, 1σ (원문: Merloni+2024 6.2절) | 초각 | 맞음 |
| 4XMM | `ePos` | 초각, 1σ (원문: Webb+2020 3.3절; 단위는 계통오차가 초각이라는 간접) | 초각 | 맞음 |
| Chandra CSC | `r0`, `r1` | 초각, **95 %** 반축 (원문 + 요약) | `r0/2.448` ⊕ 0.16″ | 맞음 |
| GALEX AIS | `Nerr`, `Ferr`, `Ierr`, `Nperr`, `Fperr` | 초각 (요약: GUVcat); VizieR 이름 대응은 없음 | 상수 0.8″ | 단위 문제 아님, **미사용**(`Nerr` 중앙값 1.5″) |
| AllWISE | `eeMaj`, `eeMin`, `e_RA_pm`, `e_DE_pm` (`sigra` 아님) | 초각 (`sigra`만 원문) | 상수 0.5″ | 단위 문제 아님, **미사용**(`eeMaj` 중앙값 0.34″) |
| 2MASS PSC | `errMaj`, `errMin` | 초각 (데이터; 재확인 안 함) | 초각 | 맞음(미재확인) |
| Gaia DR3 | `ra_error`, `dec_error` | mas (재확인 못함: 문서 쪽이 빈 페이지) | ÷ 1000 | 맞음(미재확인) |
| PS1 DR2 | `raMeanErr`, `decMeanErr` | 초각, 단일 에폭 RA의 **표준편차**(평균의 오차가 아님) (요약) | 초각 | 단위 맞음; 하한은 쌍 바닥값 0.02″뿐 |
| Legacy Surveys DR10 | `ra_ivar`, `dec_ivar` | 1/deg², RA에 cos δ 없음, "천문 보정 오차 제외" (원문) | cos δ / √ivar ×3600, 해상된 형은 0.6″ 바닥 | 맞음 |
| SDSS, SIMBAD, 나머지 | 없음 / `coo_err_maj`(mas, 미사용) | — | 상수 0.6″ 등 | 단위 문제 아님 |

**확인하지 못한 것과 닫는 법**: VizieR ReadMe의 열 단위(VLASS `J/ApJS/255/30`, NVSS `VIII/65`, GALEX, AllWISE 등)는 `benchmark/position_errors/dump_vizier_units.py`가 astroquery로 VizieR가 저장한 `unit`과 `description`을 찍는다. 네트워크가 되는 곳(워크플로)에서 한 번 돌리면 표의 "없음"이 닫힌다. CIRADA 사용자 안내(`sao.ru`)는 503이었다.

## 2. 코드와 설계 이유

변경: `Preprocess/association_model.py` — `native_radec_errors_arcsec(catalog, row)`가 `e_RAJ2000`/`e_DEJ2000` 쌍을 카탈로그별 단위로 초각으로 바꾸고, `infer_poserr_arcsec`의 일반 분기가 그것을 쓴다. `POSERR_UNITS`는 `fixed`(기본)·`legacy`이고 다른 값은 **오류**(오타가 아무 일도 안 하는 변형처럼 보이지 않게).

* **카탈로그별 변환(작은 표)을 택했다**. 대안: 수집기가 VizieR 열의 `unit`을 행마다 저장해 코드가 단위를 읽게 하는 것. 14개 수집기의 출력 형식이 바뀌고 모든 원자료를 다시 모아야 하며(네트워크가 필요, 진행 중인 모든 검증이 달라짐), 이번에 틀린 것은 둘뿐이라 과하다. 단위를 표로 고정하고 `dump_vizier_units.py`로 나중에 VizieR 쪽 값과 맞춰 보는 쪽이 작고 검증 가능하다.
* **VLASS 값을 cos δ로 곱하지 않았다**. PyBDSF가 쓰는 `E_RA`가 적경 좌표의 오차인지 하늘 위의 각 오차인지 이번에 확인하지 못했다. 이 연구의 VLASS 오차는 한쪽(적경·적위 중 큰 것)이고 중앙값 0.08″로 쌍 바닥값(0.02″) 위 약간이라, 이 선택이 결과를 바꾸는 크기는 아니다. (한계 5절.)
* **VLASS의 계통 오차(Gordon+2021 2.1절: ~1″, Dec > −20°에서 0.5″)는 기본에 넣지 않았다**. 단위 수정(틀린 입력을 맞게)과 모형 추가(맞는 입력에 계통 항을 더함)는 별개이고, 후자는 `V2_ASSOC_AMBIG=profiles`에 이미 있다. 이번 연구는 `legacy`와 `fixed`의 비교만이고 `profiles`는 재지 않았다(사전기록에서 "세 번째 열로 잰다"고 했으나 하지 못했다).
* **`legacy`를 남겼다**: 예전 결과(세트 C 포함)를 재현할 방법이 없으면 이번 변경의 효과를 검토 세션이 직접 확인할 수 없다.
* **영향 영역만 전체 파이프라인으로 돌렸다**. 두 모드에서 `poserr_arcsec`가 다른 행이 있는 영역 179개(338개 중)만 두 번 돌렸다. 나머지 159개는 입력이 같고 파이프라인이 결정적이라(PYTHONHASHSEED=0, 순서 무관) 출력이 같다. 비용: 전체 338 × 2 대신 179 × 2.
* **객체를 위치가 아니라 구성한 검출 ID로 짝지었다**(`compare_by_members.py`). 이 연구에서는 앵커가 전파에서 광학 행으로 바뀌어 객체 위치가 0.1–4″ 움직인다. 아 과제의 위치 짝짓기(0.2″)는 이런 쌍을 놓친다. `detection_id`(`파일 이름:행`)는 두 실행에서 같다. 구성이 같으면 "같은 객체"(라벨 차이는 입력만의 효과), 구성이 다르면 가장 많이 겹치는 객체와 짝지었다.
* **합성 실험 하나를 예측 전에 했다**: PS1 행 하나와 VLASS 행 하나(0.15–3″)를 Stage 1에 넣어 보았다(`test_poserr_units.py`). 이것이 예측의 초안(연결이 +10–40개 바뀐다)을 바꿨다: 연결은 오차만으로 갈리지 않고(반경 ≈ 5 결합 σ, PS1 쌍 바닥값 0.2″가 지배), 큰 변화는 **앵커**라는 것을 알았다. 그래서 예측 2–4를 실제 영역 실행 전에 고쳐 썼고, 그 사실을 `PREDICTIONS.md` 머리말에 적었다.

## 3. 예측과 결과 (`benchmark/position_errors/PREDICTIONS.md`는 실행 전 커밋, 결과는 `results_2026-11-27h/summary/predictions.csv`)

| 양 | 예측 | 결과 | 판정 |
|---|---|---|---|
| 오차가 바뀌는 카탈로그 | VLASS, NVSS뿐 | VLASS, NVSS뿐 (22개 카탈로그 86만 행) | 맞음 |
| 광학 행을 가진 채 전파가 앵커인 객체 | 20–60 % 감소(약 100–140에서) | **116 → 55 (−53 %)** | 맞음 |
| 연결 상태가 바뀐 VLASS 행 | ≤ 10 (384 중) | **24 + 2 = 26** (374 중; 151 → 173) | 틀림 |
| 연결 상태가 바뀐 NVSS 행 | ≤ 2 | **4 + 11 = 15** (212 중; 69 → 62) | 틀림 |
| 객체 수 변화 | ±10 이내 | **−37** (366 964 → 366 927) | 틀림 |
| 1차 클래스 변화 | 0–10 | **28** (단편 흡수 23 + 분류된 객체의 변화 5) | 총수는 틀림, 후자는 범위 안 |
| `compact_class` 변화 | 0–2 | **0** | 맞음 |
| `extragalactic_class` / `subclass` | 0–10 | 16 / 46 | 틀림 |

**예측이 틀린 이유**: 합성 실험은 쌍 하나만 보아서 처리 순서의 **연쇄 효과**를 못 보았다. 전파 행의 오차가 바뀌면 그 행이 앵커가 되느냐가 바뀌고, 그러면 같은 영역의 다른 광학·적외선 행(AllWISE, GALEX, 2MASS, SDSS 등)이 어느 객체에 붙는지가 바뀐다. NVSS는 오차가 4.25″ → 4.98″(+16 %)로 커져 FIRST(1″)·TGSS(2″)·VLASS와의 상대 순서가 바뀌고 광학 객체에 붙던 행 11개가 따로 서는 쪽으로 간 것으로 **보이지만**, 개별 사례로 확인하지 않았다(추정).

**전파·X선의 1차 기여**: 주문의 "기여 0"은 정확하지 않다. `fusion_weights.json`에 `RADIO-001:FEATURE:radio_log_r`(GALAXY +0.196, QSO +0.050, STAR −0.246)와 `XRAY-001:FEATURE:xray_log_fx_fo`의 학습된 계수가 있고(`*_detected` 항만 0), 전파 플럭스가 붙거나 떨어지면 증거가 달라진다. 실제로 분류된 객체의 클래스가 바뀐 5개(전부 전파 행이 객체에 붙거나 구성이 바뀐 객체)를 보면: `deep_cosmos_18` LS 단독 STAR → LS+VLASS GALAXY(같은 광학 행에 VLASS가 붙은 순수한 전파 효과), `lq1_024` QSO → STAR, `lq1_043` STAR → QSO, `lq3_004`와 `lqc2_003` STAR → GALAXY(AllWISE·광학 행이 다른 객체로 옮겨 간 연쇄). 28 / 366 964 = 0.008 %이다.

## 4. 결과 상세 (179개 영역, 객체 366 964개)

**객체와 앵커** (`results_2026-11-27h/compare/`, `summary/`):

| 세트 | 영역 | 객체(legacy → fixed) | 구성이 같은 객체 | 구성이 바뀐 객체 | 전파 앵커 객체(광학 행 보유) | 라벨 또는 전파 열이 바뀐 객체 |
|---|---|---|---|---|---|---|
| 깊은 COSMOS | 22 | 215 604 → 215 594 | 215 566 | 38 → 28 | 45 → 27 | 22 |
| 저위도 보정 | 93 | 89 071 → 89 052 | 89 013 | 58 → 39 | 40 → 18 | 51 |
| 저위도 확인 | 63 | 61 680 → 61 672 | 61 646 | 34 → 26 | 31 → 10 | 31 |
| 실사용 | 1 | 609 → 609 | 609 | 0 | 0 | 0 |
| 합계 | 179 | 366 964 → 366 927 | 366 834 | 130 → 93 | 116 → 55 | 104 |

**전파 행** (`summary/radio_rows.csv`): VLASS 374행 — 광학 등 비전파 검출과 한 객체인 것 151 → 173(분리 → 연결 24, 연결 → 분리 2), NVSS 212행 69 → 62(4 / 11), FIRST 61행 37 → 38, TGSS 69행 12 → 12, LoTSS 8행 4 → 5. 자기 객체의 앵커가 VLASS인 VLASS 행 328 → 246(전파 행만 있는 객체 포함).

**앵커가 넘어간 곳** (객체 **118개** = 구성이 바뀐 86 + 구성은 같고 앵커만 바뀐 32; 위치 이동 중앙값 0.45″ / 평균 1.5″ / 최대 20.7″; 2.62.7에 고친 도구로 다시 쟀다, 처음 낸 86개는 구성이 바뀐 객체만 센 것): VLASS → PS1 **62개** (0.37″ / 4.04″), VLASS → Gaia 10개 (0.65″ / 1.50″), VLASS → AllWISE 4개 (1.82″ / 4.12″), VLASS → NVSS 4개 (2.7″ / 10.2″), VLASS → LS 2개 (1.84″ / 1.95″), NVSS → VLASS 5개 (9.4″ / 20.7″: 45″ 빔의 위치가 0.5–1″ 정확도 위치로 바뀐다), TGSS → VLASS 1개 (14.4″), 그 밖(Gaia → PS1 7개 등 연쇄) 17개.

**라벨 열별 변화 객체 수** (`summary/label_changes.csv`): 1차 클래스 **27**, `detailed_class` 12, `extragalactic_class` 16, `subclass` 45(`subclass_code` 43), `compact_class` **0**, `classification_status` 31, `high_confidence` 21, `secondary_class` 2, 전파 플럭스 열만 바뀐 객체 50. 1차 변화 27 = 단편이 분류된 객체에 흡수 22(UNKNOWN → GALAXY/STAR/QSO, 전파 행만 있던 객체가 광학 객체에 붙음) + 이미 분류된 객체의 클래스 변화 5. (2.62.7에 고친 도구로 다시 쟀다: 처음 낸 값은 1차 28, subclass 46, 상태 32, 고신뢰 22, 전파 플럭스만 48.)

**실사용 3개 영역**: NGC 4522에 NVSS 행 1개의 오차가 바뀌지만 객체·라벨 변화는 0, COSMOS·은하면 영역은 바뀌는 행이 없어 출력이 같다.

**COSMOS2020 진실로 본 연결** (깊은 COSMOS 영향 22개 필드; 진실이 있는 카탈로그만): AllWISE 정답 6151 → 6151, 거짓 126 → 126, 놓침 1272 → 1271; 2MASS 짝지음 1159 → 1160, 정답 894 → 895, 놓침 15 → 14; GALEX 모든 값이 같다. **전파 연결의 거짓·놓침은 잴 수 없었다**: VLA-COSMOS 3 GHz(Smolčić et al. 2017, A&A 602, A1: 2 deg²에 전파 원천 10 830개, 0.75″ 해상도; 광학·중적외선 대응체는 A&A 602, A2의 9 161개 표)는 진실로 쓸 수 있지만(문헌 검색 확인, 논문 본문은 읽지 않음) VizieR 표라 이 환경에서 받지 못했다. 그리고 그 영역의 VLASS 행은 61개(광학 행이 1″ 안인 것 41개)라 틀린 연결률을 0/41 = 8.6 %(Wilson 상한) 아래로는 못 잰다.

## 5. 한계

* 열 단위의 VizieR ReadMe 원문 확인 못함(1절). VLASS·NVSS의 판정은 데이터 근거이고 매우 강하지만(NVSS 0.94 대 0.07, VLASS `e_RAMdeg`와 일치), "문서에 그렇게 적혀 있다"는 확인은 `dump_vizier_units.py` 실행 몫이다.
* 전파 연결이 **맞는지**는 못 잰다(진실 없음). 잰 것은 상태·앵커·라벨의 변화이고 방향(좋아졌나)은 COSMOS2020로 본 AllWISE·2MASS·GALEX에서만 "같다"이다.
* 계통 오차(`profiles`)를 더한 열, VLASS의 cos δ, PS1의 오차 하한(PS1 `raMeanErr` 중앙값 0.044″, 하위 10 %가 0.004″: 쌍 바닥값 0.02″가 아니면 거의 0)은 이번 연구 밖이다. 과제 차의 깨진 라벨 21번(은하동물원 행이 PS1 앵커를 피함)이 이 하한과 관련되어 보인다(추정).
* 미사용 오차 열: AllWISE `eeMaj`(중앙값 0.34″ 대 상수 0.5″), GALEX `Nerr`(1.5″ 대 0.8″). 단위 문제가 아니고 이번 과제 범위 밖이다. 후속으로 개별 오차를 쓰는 변형을 잴 만하다.
* 영향 영역 179개를 한 번씩 돌린 값이다(두 모드 모두 결정적이므로 재현되지만 반복 시행의 분산은 없음). 라벨 변화가 28개뿐이라 정확도(세트 C) 영향은 이 크기로는 잴 수 없다. 기본값을 바꾸는 판단은 세트 C 재채점과 함께 검토 세션 몫이다.

## 6. Fleuren et al. 2012 인용 정정

* 원문(`arXiv:1202.3891v2`, "Herschel-ATLAS: VISTA VIKING near-IR counterparts in the Phase 1 GAMA 9h data", S. Fleuren 외 40명; 관련 DOI 10.1111/j.1365-2966.2012.21048.x)의 PDF를 읽었다. 식 (2) `P(id) = L/(L+1)`; 식 (3) `R_j = L_j / (Σ_i L_i + (1 − Q))`; 식 (5) `L = q(m,c) f(x,y)/n(m,c)`; 식 (6) `f(r) = exp(−r²/2σ²)/(2πσ²)`; 식 (7) `σ_pos = 0.655 × FWHM/SNR`(하한 1″); Q0는 3.3절의 빈 공간 세기로 추정(Q0 = 0.73 ± 0.03).
* arXiv 쪽에는 권·쪽(MNRAS 423, 2407)이 적혀 있지 않아 이 대응은 DOI·저자·주제에 의한 것이다.
* `1204.0467`은 Škulj의 수학 논문이다. 저장소에서 이 번호는 `LITERATURE_ASSOCIATION_AMBIGUITY_2026-11-27.md`에만 "이 번호는 아니다"라는 경고로 있었고(그 문서는 "원문을 읽지 못했다"고 했다), `git log -S`로 전 이력을 찾아도 이 번호를 **인용으로** 쓴 문서는 없다. 올바른 번호 1202.3891은 `WORK_REPORT_2026-11-25d.md`와 `LITERATURE_REMAINING_ITEMS_2026-11-13.md`에 이미 있었다.
* 고친 것: 문헌 문서의 행(원문 확인으로 갱신), `posterior_calibration.py`(신뢰도 식 eq. 6 → eq. 3), 코드 주석 두 곳(`association_model.py` eq. 5, `01_source_association.py` eq. 7)에 arXiv 번호 추가.

## 7. 오류와 고친 것

* **내가 준 arXiv 번호가 틀렸다**: 가져오기 에이전트에게 VLASS 논문을 `arXiv:2105.12259`로 알려 주었는데 다른 논문(통계학)이었다. 올바른 번호는 `2102.11753`(Gordon et al. 2021, ApJS 255, 30)이다(검색으로 확인).
* **LoTSS 행이 없다고 UNITS.md에 썼으나 8행이 있었다**: 전수 행 검사가 찾아 고쳤다.
* **예측의 합성 실험 이전 초안이 틀렸다**(3절).
* 과제 차와 같은 **실행 중 코드 수정** 문제(차 보고서 6절).

## 8. 시험과 재현

`Preprocess/tests/test_poserr_units.py` 10개(VLASS·NVSS·TGSS/LoTSS/알 수 없는 카탈로그, 다른 카탈로그가 바뀌지 않음, `profiles`가 VLASS에서 우선, 잘못된 값은 오류, Stage 1에서 앵커가 전파 행이 되는 것과 연결 반경), `test_position_error_tools.py` 6개. 전체 `python -m pytest -q Preprocess/tests Classifier/tests app/tests` 통과.

```
python benchmark/position_errors/check_units_from_rows.py --roots <raw...> --out benchmark/position_errors/results_2026-11-27h
python benchmark/position_errors/run_pe.py --regions .../regions_changed.csv --out OUT --roots raw=.. ll_run=.. ll_conf=.. B1=.. --cosmos-fields fields_all26.csv
python benchmark/position_errors/compare_by_members.py --a OUT/legacy --b OUT/fixed --regions .../regions_changed.csv --out .../compare
python benchmark/position_errors/summarize_compare.py --compare .../compare --out .../summary
python benchmark/position_errors/dump_vizier_units.py   # 네트워크가 되는 곳에서
```

## 9. 병합 시 알아 둘 것

* `.github/workflows/v2_scientific_cross_validation.yml`은 `v2/Preprocess/association_model.py`가 바뀐 main push에서 자동으로 돈다(경로 목록에 있다). 이 변경을 병합하면 수 시간짜리 검증이 시작된다(자 과제의 고정 목록 위에서).
* 앱·분류기 시험은 통과하지만, 앱의 `app/` 문서에 수치가 있으면 기본 동작 변경에 맞춰 다시 볼 곳이다(이번에 앱 코드는 건드리지 않았다).

## 병합 전 검토 (2.62.2로 병합, 기본 `legacy`)

- **기본값을 `legacy`로 두고 병합했다.** VLASS·NVSS의 단위는 저장된 행으로 본 것이다. VLASS `e_RAJ2000`은 같은 표의 `e_RAMdeg`와 384행 모두 같고, NVSS RA 오차 × 15 cos δ / Dec 오차는 0.99다. 근거는 강하지만 VizieR가 적어 둔 단위는 아직 읽지 못했다.
  - 이 세션에서 `cdsarc.cds.unistra.fr`·`cdsarc.u-strasbg.fr`는 이름을 찾지 못했다. VizieR 미러 4곳(CfA, 스트라스부르, NAOJ, IDIA)도 이 컨테이너의 프록시가 막는다.
  - 작업 규칙 1(문헌·카탈로그 문서 근거 먼저)에 따라 문서를 확인한 뒤 기본값을 바꾼다.
  - 그 전까지 출력은 2.62.1과 같다. 실사용 3개 필드의 Stage 1 출력이 main과 바이트 단위로 같다. `fixed`로 켜면 NGC 4522의 NVSS 1행 오차가 1.40″ → 1.48″가 되고 상태(`ambiguous_new`)와 객체 수(673)는 같다.
- **확인 수단**: 수동 워크플로 `.github/workflows/v2_vizier_units.yml`가 `dump_vizier_units.py`를 돌려 열마다 VizieR의 `unit`·`description`을 아티팩트와 단계 요약에 남긴다. 이 도구는 이제 `throttle.install()`로 미러를 돌아 스트라스부르 장애에도 답을 얻을 수 있다.
- **바꾸는 순서**: 문서 단위가 이 보고서의 판정(VLASS 도, NVSS RA 시간 초)과 같으면 `POSERR_UNITS`의 기본값을 `fixed`로 바꾼다. 이 MINOR에서 1차 라벨 27개가 바뀐다(이 보고서의 179개 영역; 2.62.7 재측정, 처음 값은 28). 세트 C는 검토 세션의 계획대로 다른 라벨 변경 후보(`same,nearest`, `surveys2`)와 묶어 한 번에 채점하므로 그 MINOR 때도 따로 채점하지 않는다.
- **판 번호**: 작업 세션의 2.62.0(MINOR) 후보를 과제 차(2.61.10 후보)와 함께 2.62.2(PATCH)로 병합했다(main이 이미 2.62.1). 시험 `test_the_default_reading_is_legacy_until_the_documented_units_are_read` 추가.
- **Codex 검토로 고친 도구(`compare_by_members.py`)**: 앵커 변화와 위치 이동을 **구성이 바뀐 객체에서만** 쟀다. 그래서 구성은 같고 앵커만 전파 행에서 광학 행으로 넘어간 객체(단위 수정의 주된 경우)가 `anchor_changes.csv`와 `per_region.csv`의 `median_shift_arcsec`에서 빠졌다. 이제 구성이 같은 객체도 재고 `kind`(`same_members` / `changed_members`) 열을 단다(시험 추가).
  - **2.62.7에 고친 도구로 다시 쟀다**(원 실행 산출물 `pe/legacy`, `pe/fixed`가 작업 세션 스크래치패드에 남아 있었다; 결과 `results_2026-11-27h/compare/`, `summary/`를 교체하고 `run_info.json`을 달았다). 앵커가 넘어간 객체 86 → **118**, VLASS → PS1 31 → 62, 위치 이동 중앙값 0.60″ → 0.45″, 1차 라벨 변화 28 → **27**(단편 흡수 23 → 22), `subclass` 46 → 45. 객체마다 전체 표에서 센 "광학 행을 가진 채 전파가 앵커인 객체 116 → 55"는 변하지 않았다(검토 세션의 예상과 달리 라벨 변화가 1개 줄었다: 같은 구성의 객체를 이제 전부 짝지어 비교한다).
- **문서 단위 확인(2.62.3)**: `v2_vizier_units.yml`(CfA 미러)에서 VizieR 메타데이터를 읽었다. VLASS `e_RAJ2000`·`e_DEJ2000`는 **deg**, NVSS `e_RAJ2000`는 **s**·`e_DEJ2000`는 arcsec로, 이 보고서의 판정과 `fixed` 변환이 맞다. 다른 수집기의 위치 오차 열은 모두 코드가 가정한 단위다(`benchmark/position_errors/UNITS.md` 1b절). 남은 것은 `fixed`를 기본으로 하는 결정(검토 세션)과 그 전의 재측정이다.

