# 작업 보고서 2026-11-27d — 탐사 수 스위치의 어두운 쪽·분광 QSO 비용 (2.61.5)

계획 세션 지시서 "과제 바"(와 5가지 추가 설명 요청). `surveys2`/`surveys3`/`wise_second`를 기본으로 켤지 정하려면 "어둡고 탐사가 둘뿐인 진짜 퀘이사를 얼마나 잃는가"가 필요했다. 기본값은 바꾸지 않았다. 새 스위치 `spectro_keep` 하나가 추가되고(기본 꺼짐), 나머지는 측정·도구·표다.

## 1. 한 줄 결과

- **(a) 검토를 거친 탐사 단위 세기로 다시 분류해도 커밋된 표와 같다**: 보정 169 + 확인 140 영역, 변형 5개 모두 `ab_variants.csv` 행과 객체 단위 라벨이 같다(확인 175 / 보정 170개 "표본 밖 QSO", 표본 퀘이사 143 / 150). Gaia SOS·ZTF·DESI 적합·SGA를 한 탐사로 묶은 것이 이 영역들의 어느 보류도 바꾸지 않았다.
- **(b) 분광으로 QSO 등급이 정해진 객체도 막힌다**: 저위도 290개 원뿔에 SDSS·DESI·LAMOST 분광을 수집해 보니 스펙트럼 등급 QSO가 **34개**, 기준 분류가 QSO로 부른 것 32개 중 **`surveys2`와 `surveys3`가 각각 5개(16 %)를 막는다.** 5개는 모두 **LAMOST 행 하나뿐**(어느 영상 카탈로그에도 짝이 없음)이다. 새 스위치 **`spectro_keep`**(스펙트럼 등급 QSO는 `surveys2`/`surveys3`/`pm`에서 제외)을 켜면 0개 막힌다. 블라인드 측정에는 스펙트럼이 없어 영향이 없고 실사용에만 있다.
- **(c) 확인용 수집의 시작·종료 시각**: 수집 스크립트 13:15:59 UTC, 첫 영역 로그 13:16:02, 마지막 영역 14:08:24 UTC. 예측 커밋 8b108c2는 13:15:51 UTC이므로 **수집은 커밋 8초 뒤에 시작**했다(`LOWLAT_QSO.md` 8.2절). 시각은 스크래치 폴더의 파일 시각이고, 커밋을 푸시한 시각은 기록에 없다.
- **어두운 쪽 비용은 측정되지 않는다(= 0): 기준 분류가 애초에 어두운 1–2개 탐사 객체를 QSO로 부르지 않기 때문이다.** 깊은 COSMOS 26개 영역(위도 한계를 풀어 둠), Chandra 1형 AGN 327개 중 기준이 QSO로 부른 **123개 중 잃은 것 0**(95 % 상한 3.0 %; r < 22는 0/97, 22–24는 0/26 상한 12.9 %; 분광 1형 0/107). 탐사 1–2개짜리 1형 AGN 90개 중 **QSO로 불린 것은 0개**(상한 4.1 %), 불린 123개는 모두 탐사 3개 이상이다.
- **그러나 `surveys3`는 구조적으로 어두운 쪽 천장을 낮춘다**: LS 밖 저위도 원뿔의 PS1 i 21–22 객체 중 탐사 3개 이상은 **1.0 %**(2개 이상 16.4 %), i ≥ 22는 0.7 %(8.0 %)다. COSMOS 1형 AGN은 r 22–23에서 3개 이상 84.6 %(LS 없이 67.9 %), 23–24에서 54.1 %(21.3 %), ≥ 24에서 27.8 %(5.6 %). **LS 밖에서 `surveys3`는 i ≳ 21의 어떤 객체도 QSO로 부를 수 없다.** 이것은 잃은 양이 아니라 "기준이 앞으로 부를 수 있는 양"의 상한이다.
- **결정표(6절)**: `surveys2` + `spectro_keep`은 확인 영역에서 거짓 QSO 밀도를 159 → 74 deg⁻²로 줄이고(LS 영역 811 → 335, LS 밖 57 → 33), 밝은 표본 퀘이사 0/143, COSMOS 0/123, 분광 QSO 0/32를 잃는다. `surveys3`는 159 → 32이지만 어두운 쪽 천장이 낮다. `wise_second`는 효과가 작다(159 → 129). **기본값은 바꾸지 않는다.**
- **해야 했지만 못 한 것**: 세트 A/B 원자료(`validation-data` 브랜치에만 있고 이 작업은 건드리지 않는다)에서의 같은 측정, 그리고 bngp_162p01 한 개 조사(같은 원자료가 필요). 7절.

## 2. 무엇을 했나 (지시서 순서)

| 지시 | 한 것 | 결과 |
|---|---|---|
| (a) main 판으로 재분류 | 보정 169 + 확인 140 영역을 저장한 원자료에서 오프라인으로 다시 분류(`base`, `surveys2`, `surveys3`, `wise_second`, `surveys2+wise_second+wise_footprint`) | 모든 숫자·객체 동일 |
| (b) 분광 예외 변형 | `spectro_keep` 구현, 290개 원뿔에 분광만 따로 수집(`collect_spectra.py`), 스펙트럼 등급 QSO를 센다 | 34개, 5/32 막힘, `spectro_keep`이면 0 |
| (c) 수집 시각 | 로그·파일 시각에서 찾아 `LOWLAT_QSO.md`에 적음 | 커밋 8초 뒤 시작 |
| 1 깊은 COSMOS | 26개 영역에서 `V2_LOWLAT_QSO_ABSB=90`으로 세 스위치를 켜고 Chandra 1형·분광 정답으로 r 구간별·탐사 수별 손실, 후보 표시 변화 | 0/123, 표 |
| 2 벤치마크 | 로컬 SDSS 일반, SDSS 하늘, DESI 외부, DESI 융합 벤치마크의 분광 퀘이사 탐사 수(`benchmark_cost.py`) | 4절 |
| 3 탐사 수 분포·천장 | 저위도 290개 원뿔 전 객체의 탐사 수 분포(PS1 i, LS 유무), COSMOS 손실률 재가중, LS 밖 `surveys3` | 4절, 재가중 추정은 0(이유 4절) |
| 4 결정표 | `decision_table.py` | 6절 |
| 추가 설명 5가지 | 독립 탐사 세기, 강등 라벨, 쌍 제거 밀도, 구간, |b| = 20° 경계 | 5절 |

## 3. 설계와 이유

- **`spectro_keep`을 별도 스위치로, 기본 꺼짐**: 분광 근거 QSO는 색 추론이 아니라 등급을 직접 잰 것이라 "탐사가 둘 이상이어야 한다"는 문헌 근거(색 선택의 오염)가 적용되지 않는다. 그러나 `surveys2`/`surveys3` 자체의 의미(저위도 거짓 라벨 억제)는 그대로 두고 예외만 켜고 끄게 해야 A/B에서 예외의 몫이 따로 보인다. 구현은 5단계 한 곳(`_spectroscopic_qso(items)`: SPC-SDSS/DESI/LAMOST-003, raw score ≥ 0.5, `_spectroscopic`과 같은 문턱)이고 스위치 모듈이 보류 목록에서 그 객체를 뺀다. 스펙트럼이 없는 블라인드 실행에서는 아무것도 바꾸지 않는다(시험으로 고정).
- **분광은 따로 수집해 합쳤다**: 블라인드 원자료에는 분광 카탈로그가 없으므로(`V2_SKIP_COLLECTORS=blind`) 290개 원뿔에 SDSS·DESI·LAMOST 분광 수집기만 돌려 저장한 원자료 복사본에 넣고 다시 분류했다(`collect_spectra.py collect/merge`, 영역당 평균 24 s). 전체 파이프라인을 다시 수집하는 안은 SIMBAD/NED가 영역당 8–19회 요청이라 버렸고, 분광만 있으면 질문("스펙트럼이 있는 객체가 몇 개 막히나")에 답한다. SIMBAD·NED 유형도 카탈로그 라벨이지만 이번에는 수집하지 않았다(8.6절).
- **COSMOS는 위도 한계를 풀어 측정**: COSMOS는 |b| = 42°라 스위치가 꺼져 있다. `V2_LOWLAT_QSO_ABSB=90`으로 일부러 켜서 "스위치가 켜졌다면 잃었을 것"만 잰다. 전체 파이프라인 결과는 영역당 수백 MB라 26개 영역 × 4변형이 디스크 한도를 넘으므로 필요한 열만 저장한 복사본으로 줄였다(`faint_cost.py classify`).
- **재가중 대신 "천장"을 중심에 둔다**: 요청대로 COSMOS의 손실률(탐사 수 k × PS1 i 구간별 QSO 라벨 확률 q(k, i))을 저위도의 탐사 수 분포로 다시 가중하는 추정을 냈다(`reweight.py`). 그런데 COSMOS에서 k ≤ 2인 1형 AGN은 라벨이 0개라 q = 0이고 추정도 0이다(밝은 구간은 COSMOS에 k ≤ 3인 1형이 없어 q가 정의되지 않고 0으로 둠). 그 값에 신뢰 상한을 붙이려 해도 저위도의 어두운 객체는 대부분 탐사 1개라 가중치가 모델 가정(퀘이사의 탐사 수 = 평균 객체의 탐사 수)에 지배된다. 그래서 "이 객체 수준의 탐사 수로는 QSO 라벨이 가능한 비율은 얼마인가"인 **천장**(`share_ge_need`)을 따로 낸다. 퀘이사는 평균 객체보다 WISE에서 더 밝아 천장은 평균 객체의 값보다 높을 수 있다(가정 한계).
- **"탐사 수"는 검토된 `n_surveys`(탐사 단위)를 그대로 쓴다**(독립 탐사의 정의는 5절): 벤치마크는 카탈로그 파일 하나 = 탐사 하나로 센다(Gaia, PS1, LS, AllWISE, 2MASS, GALEX, 전파·X선, ZTF 모두 서로 다른 탐사). SDSS 벤치마크의 객체는 SDSS 분광 객체이므로 실제 파이프라인에서는 SDSS 영상(`SDSS DR18 PhotoObj`)이 탐사 하나 더 되어 `+SDSS 영상` 열도 낸다.

## 4. 결과

### (a) 재분류

보정 169개와 확인 140개 영역을 2.61.3 코드(탐사 단위 세기)로 다시 분류했다. `ab_variants.csv`의 모든 열(재현율, 거짓 밀도, 쌍 제거 밀도와 구간, 잃은 퀘이사)과 객체별 표(`qso_labelled_not_sample_by_variant`, `sample_quasars_by_variant`)가 5개 변형에서 **전부 같다**(`results_2026-11-27c/recheck_main_version/`). 그래서 `results_2026-11-27b`의 표를 새로 내지 않았다.

### (b) 분광 QSO (`results_2026-11-27c/spectro/`)

290개 원뿔(보정 150 + 확인 140; 별·은하 정답 원뿔 19개는 뺀다)에 분광 수집기를 돌렸다: LAMOST 199개 원뿔 931행, SDSS 10개 원뿔 13행, DESI 15개 원뿔 65행(DESI 영역 안은 36개 원뿔뿐). 스펙트럼 등급 QSO는 34개: 기준 라벨 QSO 32 / STAR 1 / UNKNOWN 1. **`surveys2`·`surveys3`: 32개 중 5개를 UNKNOWN으로**(모두 탐사 1개 = LAMOST 행 하나). `spectro_keep`: 0개. **막힌 5개는 표본 퀘이사 자신이다**(Huo 퀘이사와 0.0″). 이 5곳에서는 LAMOST 행이 Gaia·PS1 객체와 0.02″ 떨어져 있는데도 합쳐지지 않고 따로 객체가 된다(1단계 `association_status = ambiguous_new`, 후보 3개: 붐비는 장에서는 후보가 둘 이상이면 합치지 않는 보수적 규칙). 그래서 같은 퀘이사가 객체 2–4개(LAMOST 단독, AllWISE 단독, Gaia + PS1 …)로 나온다. 5곳 중 3곳은 광학·적외선 객체가 따로 QSO이고 2곳(lq3_026, lqc2_031)은 그것이 STAR, AllWISE 단독이 QSO라 `surveys2`가 AllWISE 단독까지 막으면 그 퀘이사의 QSO 라벨이 남지 않는다: `spectro_keep`이 필요한 이유다. 단독 한 탐사 거짓 QSO 162개 중 2″ 안에 2개 이상 탐사 이웃이 있는 것은 10개(6 %)뿐이라 이 중복이 거짓 QSO의 주된 원인은 아니다. 표본 퀘이사 대부분은 LAMOST DR10이라 DR5 카탈로그의 스펙트럼 등급이 없다.

### 1 깊은 COSMOS (`results_2026-11-27c/faint_cost/`)

26개 영역(6′), 위도 한계를 풀어 변형 `base`, `surveys2`, `surveys3`, `wise_second`를 분류하고 Chandra 1형(분광 분류 `Clsp` 0–2는 "분광")·COSMOS2020 ACS 은하·별·Chandra 2형 정답에 대었다.

| LS r | 1형 AGN | 기준이 QSO | `surveys2` 잃음 | `surveys3` 잃음 | `wise_second` 잃음 |
|---|---|---|---|---|---|
| < 20 | 16 | 15 | 0 | 0 | 0 |
| 20–21 | 48 | 41 | 0 | 0 | 0 |
| 21–22 | 59 | 41 | 0 | 0 | 0 |
| 22–23 | 78 | 22 | 0 | 0 | 0 |
| 23–24 | 61 | 4 | 0 | 0 | 0 |
| ≥ 24 | 54 | 0 | – | – | – |
| 전체 | 327 | 123 | **0** (상한 3.0 %) | **0** | **0** |

탐사 수별: 1개 28(QSO 0), 2개 62(0), 3개 46(4), 4개 이상 191(119). **기준은 탐사 1–2개의 1형 AGN을 하나도 QSO로 부르지 않는다**(상한 4.1 %). 그래서 `surveys2`/`surveys3`는 COSMOS에서 맞는 라벨을 잃지 않는다.

- **거짓 쪽**: 정답이 별·은하·2형인데 기준이 QSO로 부른 것: 별 2(`surveys*` 0 제거), 은하 7(`surveys2` 2, `surveys3` 4 제거), 2형 14(1, 2 제거).
- **모든 객체의 QSO 라벨**(정답 없음): r ≥ 24에서 25개 → `surveys2` 4, `surveys3` 1(`wise_second` 25). r 21–23에서는 각각 1–3개씩 줄어든다. r ≥ 24는 COSMOS 1형 AGN이 하나도 QSO로 불리지 않는 구간이라 대부분 거짓 라벨로 보인다.
- **QSO 후보 표시(`FAINT_QSO_CANDIDATE`)와 "주장"**: 22 ≤ r < 24에서 "라벨 QSO 또는 후보" 주장 178개, 순도 36.5 %, 재현율 46.8 %로 **변화 없음**(보류된 QSO는 이 구간에서 후보 표시로 흡수됨). 전체 r에서 라벨 QSO의 순도는 기준 84.3 %(123/146) → `surveys2` 86.0 %(123/143) → `surveys3` 87.9 %(123/140).
- **천장(`type1_ceiling_by_r.csv`)**: 위 요약의 비율.

### 2 벤치마크 (`results_2026-11-27c/benchmark_cost/`)

"탐사 수 < 2 / < 3인 비율"(분광 퀘이사의 카탈로그 수; 기준 분류가 QSO로 부르는지와는 별개인 천장):

| 벤치마크 | 퀘이사 | < 2 | < 3 | < 3 (+SDSS 영상) | r ≥ 22 에서 < 2 / < 3 |
|---|---|---|---|---|---|
| SDSS 일반(전파·X선 포함) | 3,333 | 0.06 % | 0.09 % | 0.06 % | (3개) |
| SDSS 하늘 | 3,333 | 0.42 % | 12.6 % | 0.42 % | 3.2 % / 54 % (+SDSS 영상: 0 % / 3.2 %) |
| 〃 \|b\| < 20 | 49 | 0 % | 24.5 % | 0 % | – |
| DESI 외부 | 1,595 | 2.4 % | 9.0 % | – | 9.3 % / 33 % |
| DESI 융합 | 2,691 | 2.8 % | 9.5 % | – | 11.1 % / 36 % |

SDSS 객체는 SDSS 영상이 실제 파이프라인에서 탐사 하나 더 되므로 `+SDSS 영상` 열이 실사용에 가깝다: `surveys3`가 분광 QSO를 막는 몫은 SDSS 하늘 0.4 %(r ≥ 22 3.2 %). DESI 퀘이사는 r ≥ 22에서 3분의 1이 탐사 3개 미만이다.

### 3 저위도 탐사 수 분포 (`results_2026-11-27c/survey_distribution/`)

290개 원뿔의 모든 최상위 객체(약 27만 개)를 PS1 i 구간과 원뿔의 LS 유무로 나눴다.

| PS1 i | LS 밖 원뿔: 2개 이상 | 3개 이상 | LS 원뿔: 2개 이상 | 3개 이상 |
|---|---|---|---|---|
| < 19 | 91.9 % | 70.7 % | 90.7 % | 86.1 % |
| 19–20 | 88.6 % | 27.2 % | 84.1 % | 73.7 % |
| 20–21 | 51.2 % | 9.4 % | 76.7 % | 48.5 % |
| 21–22 | 16.4 % | **1.0 %** | 71.4 % | 25.9 % |
| ≥ 22 | 8.0 % | 0.7 % | 53.1 % | 9.6 % |
| PS1 없음 | 4.3 % | 0.3 % | 10.4 % | 1.2 % |

- 기준이 QSO로 부른 LS 밖 객체(i < 20은 191개): 94–100 %가 2개 이상이다. i 21–22의 20개는 14개가 정확히 2개(`surveys3`가 막을 것).
- **LS 밖에서 쓸 수 있는 탐사는 PS1·AllWISE·Gaia·2MASS(+GALEX)뿐**이라 i > 21의 객체는 사실상 PS1 + AllWISE(2개)가 최대다. `surveys3`가 그 영역에서 "QSO를 부를 수 있는 것"은 1 % 미만이다.

## 5. 지시서가 물은 다섯 가지

1. **독립 탐사를 세는 법**(`lowlat_qso.n_surveys`, `SURVEY_OF`): 탐사 하나 = 한 측정. PS1·LS(DECaLS/BASS/MzLS)·SDSS 영상은 같은 광학 대역이어도 서로 다른 망원경의 독립 검출이라 따로 센다. Gaia DR3 천체측정·측광·SOS 변광 표와 Gaia DSC 확률은 한 탐사(Gaia 행의 열), ZTF 두 표 하나, DESI 스펙트럼과 FastSpecFit 적합 하나, SGA-2020은 LS의 영상으로 만든 것이라 LS와 하나. **AllWISE만 수집한다**(unWISE·CatWISE는 수집하지 않아 같은 WISE 자료가 둘로 세어지는 일이 없다; 나중에 같은 WISE 측광의 카탈로그를 더하면 `SURVEY_OF`에서 AllWISE로 묶어야 한다). LS 행의 W1/W2 강제측광은 그 행의 것이라 LS + AllWISE는 둘로 센다(WISE 플럭스가 양쪽에 있어도 광학 검출이 독립). 주석 카탈로그(NED, SIMBAD, BZCAT, Suh AGB, HASH/Acker PN, ATNF, Galaxy Zoo DESI)는 탐사가 아니다. SkyMapper는 수집하지 않는다.
2. **강등된 객체의 최종 라벨과 사용자에게 보이는 사유**: `primary_class = UNKNOWN`, `classification_status = LOW_CONFIDENCE`, `best_candidate_class = QSO`, `secondary_class = QSO` + `secondary_class_reason = LOWLAT_QSO_HELD`(다른 보조 해석이 없을 때), 열 `lowlat_qso_hold`와 `unknown_reason`에 "QSO label withheld at |b| = 13.8 < 20 deg (V2_LOWLAT_QSO): measured by 1 survey, 2 needed" 같은 문장. STAR로는 바꾸지 않는다(별이라는 정보가 없다). 예: `results_2026-11-27c/spectro/example_held_objects_lq2_012_surveys2.csv`(lq2_012에서 24개가 걸림).
3. **"쌍 제거 밀도"**(`removed_per_deg2`): 대조(`base`)가 QSO로 불렀고 표본 퀘이사가 아닌 객체 중 변형이 QSO로 부르지 않은 것의 밀도(원뿔 면적당). 같은 객체 집합의 차이라서 두 밀도를 뺀 값의 구간(독립 가정)보다 좁은 쌍 부트스트랩으로 구간을 낸다.
4. **구간**: 거짓 밀도와 쌍 제거 밀도는 **영역 단위 부트스트랩**(영역을 복원추출 4,000회, 시드 1, 영역별 개수 합 ÷ 면적 합의 2.5·97.5 백분위수)이고 포아송이 아니다(거짓 라벨이 몇 영역에 몰려 있어서). 재현율과 잃은 비율은 Wilson 95 %.
5. **|b| = 20° 경계**: `|b| < 20`을 **객체 자신의 위치**로 엄격히 검사한다(원뿔이 아니라). 290개 원뿔 중 경계에 걸친 것은 lqc3_014(중심 b = −19.98°: 객체 734개, 20° 아래 587, 위 147) **하나**이고 QSO 라벨 2개가 모두 20° 아래이며 `surveys3`가 그중 하나를 막는다. 나머지는 한쪽에만 있다. `V2_LOWLAT_QSO_ABSB`로 경계를 옮길 수 있다.

## 6. 결정표 (`results_2026-11-27c/decision_table.csv`)

| 변형 | 확인 영역 거짓 QSO 제거(쌍, deg⁻²) | 거짓 밀도 (전체 / LS 원뿔 / LS 밖) | 밝은 표본 퀘이사 손실 (확인 / 보정) | COSMOS 1형 손실 (전체 / r < 22 / 22–24) | 분광 QSO 막힘 | 천장: LS 밖 i 21–22 / COSMOS 22–23 / 23–24 |
|---|---|---|---|---|---|---|
| `surveys2` | 85 [42–141] | 159→74 / 811→335 / 57→33 | 0/143, 0/150 | 0/123, 0/97, 0/26 | 5/32 | 16 % / 95 % / 89 % |
| `surveys2 + spectro_keep` | 85 [42–141] | 같음 | 0/143, 0/150 | 같음 | **0/32** | 같음 |
| `surveys3` | 127 [66–203] | 159→32 / 811→134 / 57→16 | 0/143, 0/150 | 0/123, 0/97, 0/26 | 5/32 | **1 %** / 85 % / 54 % |
| `surveys3 + spectro_keep` | 127 [66–203] | 같음 | 0/143, 0/150 | 같음 | **0/32** | 같음 |
| `wise_second` | 30 [18–43] | 159→129 / 811→737 / 57→34 | 0/143, 0/150 | 0/123 | – | – |

읽는 법: (1) `surveys2 + spectro_keep`은 어느 측정에서도 맞는 라벨을 잃지 않고 거짓 라벨의 54 %를 걷는다(LS 원뿔에서는 59 %). (2) `surveys3`는 거짓을 80 %까지 걷지만 LS 밖에서 i ≳ 21의 퀘이사를 구조적으로 못 부른다(1 %). 지금 기준 분류가 그 영역의 퀘이사를 부르지 못하는 것은 맞지만, 앞으로 기준이 나아지면 `surveys3`가 상한이 된다. (3) `wise_second`는 거짓을 19 % 걷고 부작용이 측정되지 않지만 효과가 작다. (4) **LS 원뿔에서 `surveys2`만으로는 거짓 밀도가 고위도 퀘이사 총 밀도(~300 deg⁻²)와 같은 335가 남는다**(2.61.3 검토의 지적): LS가 있는 곳의 거짓 라벨은 탐사 수가 아니라 다른 원인(LS 한 탐사 색의 LS-CKNN 등)이 큰 몫이다. 권고(결정은 계획 세션): 켠다면 `surveys2,spectro_keep`; `surveys3`는 사용자가 명시적으로 원할 때만. 기본값은 그대로 꺼짐.

## 7. 한계와 하지 못한 것

- **세트 A/B 원자료는 쓰지 못했다**: `validation-data` 브랜치에만 있고 이 작업은 그 브랜치를 건드리지 않는다. 같은 측정을 하려면 그 원자료를 받을 수 있는 세션이 `faint_cost.py`/`spectro_held.py` 대신 `benchmark/independent_fields/README.md`의 채점기에서 스위치를 켜면 된다(`experiment-ab-fields.yml` 변형 `llsurveys2`·`llsurveys3`·`llwise2`·`llsurveys2spectro`·`llsurveys3spectro`).
- **bngp_162p01(세트 B에서 2.61.0의 밝기 순서가 라벨 1개를 나쁘게 한 것)은 조사하지 못했다**: 같은 원자료가 필요하다. 계획 세션이 그 영역의 원자료를 줄 수 있으면 이어서 한다.
- COSMOS는 탐사가 가장 깊고 많은 곳이라 탐사 수 분포가 저위도와 다르다. 그래서 4절의 천장 표를 같이 냈다. 재가중 추정은 COSMOS q(k ≤ 2) = 0이라 0이다.
- COSMOS "정답"은 Chandra 1형이므로 X선에 안 잡히는 퀘이사는 없다(거짓 라벨 수는 하한, 손실은 이 정답 안에서).
- 분광: 파이프라인의 LAMOST 수집기는 DR5 카탈로그라 표본(DR10)의 퀘이사 대부분이 스펙트럼 등급이 없다. SIMBAD·NED 유형은 수집하지 않았다. DESI 영역은 36개 원뿔뿐이다.
- 천장은 "객체 전체의" 탐사 수 분포이고 퀘이사의 분포가 아니다(퀘이사는 WISE에서 더 밝다).
- Gaia는 VizieR 복사본(변광성 요약 플래그 없음), 12-02 전.

## 8. 산출물과 재현

- 코드: `Preprocess/lowlat_qso.py`(`spectro_keep`, `exempt_spectroscopic`), `Preprocess/05_likelihood_vectors.py`(`_spectroscopic_qso`와 보류 목록에서 제외), `benchmark/lowlat_qso/{faint_cost.py, benchmark_cost.py, survey_distribution.py, reweight.py, collect_spectra.py, spectro_held.py, decision_table.py}`.
- 시험: `test_lowlat_switches.py`(+3: 스위치 파싱·단독으로는 아무것도 안 함, 제외 동작, 스펙트럼 등급 QSO 판정), `test_lowlat_cost_tools.py`(5).
- 표: `benchmark/lowlat_qso/results_2026-11-27c/`(`decision_table.csv`, `recheck_main_version/`, `faint_cost/`, `benchmark_cost/`, `survey_distribution/`, `spectro/`), 설명: `LOWLAT_QSO.md` 8절.
- 재현 명령: `faint_cost.py classify|tables --deep DIR --fields-file F --variants base,surveys2,surveys3,wise_second`, `survey_distribution.py --sets ROOT:fields.csv ...`, `collect_spectra.py collect|merge`, 나머지는 각 스크립트의 독스트링.
- A/B 워크플로: 변형 `llsurveys2spectro`(= `V2_LOWLAT_QSO=surveys2,spectro_keep`)와 `llsurveys3spectro`를 `experiment-ab-fields.yml`에 추가했다.
