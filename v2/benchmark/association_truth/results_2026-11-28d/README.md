# 과제 러: 연관 지표를 앵커와 무관한 읽기로 다시 센 결과 (2.62.7 → 2.62.10 후보)

정의는 `../METRICS.md`, 예측은 `../PREDICTIONS_RIGHT_OBJECT_2026-11-28.md`. 이 폴더의 표는 모두 `../right_object_recount.py`(필드별 JSON의 합)와 `../right_object_tables.py`가 만든다.

**이 폴더는 두 번 만들어졌다.** 첫 판(커밋 b0ec093의 `results_2026-11-28d/`)은 `right_object = correct + rightly_alone`로 셌다. 검토 세션(Codex)이 이 정의가 앵커에 따라 움직인다고 지적하고 main(2.62.7, #101)이 `correct + alone_identified`로 고쳤다. 이 판은 **고친 정의**로 같은 1단계 출력 위에서 `measure_association.py`를 다시 돌려 만들었고, 첫 판의 결론 중 상당수가 뒤집혔다(아래 "무엇이 뒤집혔나"). 첫 판 숫자는 쓰지 않는다.

## 재현

```
bash v2/benchmark/association_truth/run_right_object_variants.sh FIELDS_ROOT TRUTH_FLUX_DIR OUT       # Stage 1 x 7 변형(+이동 사본), 측정, 요약
python v2/benchmark/association_truth/right_object_recount.py --root OUT --variants base file position same nearest same_nearest floored --out RES
python v2/benchmark/association_truth/right_object_tables.py --recount RES > tables.md
# 순서 키 / eeMaj 변형(`run_order_key_variants.sh`의 출력)도 같은 도구로: --variants base allwise allwise_order allwise_sigma floored allwise_floored allwise_order_floored
```

입력: 깊은 COSMOS 26개 영역의 원자료, COSMOS2020 정답(`collect_truth_flux.py`). 측정은 병합된 `measure_association.py`(`alone_*`, `shared`, `displaced` 열)로 돌렸고, `*.run_info.json`의 `dirty = true`는 그 열의 변경이 커밋되기 전이었기 때문이다(변경은 같은 커밋에 들어 있다).

| 파일 | 내용 |
|---|---|
| `recount_counts.csv`, `recount_delta.csv` | 7개 변형 × 분할 × 목록: 개수와 기본값 대비 변화(재라벨 몫, 영역 부트스트랩 95 %) |
| `recount_counts_order_key.csv`, `recount_delta_order_key.csv` | 순서 키 / AllWISE `eeMaj` 변형 7개(과제 너의 1단계 출력) |
| `right_object_false_missed.csv`, `right_object_structure.csv` | 기존 요약 도구의 형식(보정 15 / 시험 11 분할) |
| `tables.md` | 보고서의 표 |

분할: **보정 9 / 확인 17**(COSMOS 필드 1–9 / 10–26)은 2.61.8(`association_ambiguity`, "정답 연결 +46 / +32")의 분할, **보정 15 / 시험 11**(`fields_split.csv`)은 2.60.9의 분할이다. 둘을 섞어 부르지 않는다.

## 지표 (`../METRICS.md` 2절)

행(기대 짝이 있는 것)을 **자기 객체가 무엇을 갖는가**로 나눈다: `right_object`(정답 짝을 가진 객체 안), `wrong_object`(정답 id는 있으나 짝은 없는 객체 안), `unidentified`(정답 id가 없는 객체 안). 세 값의 합은 기대 짝이 있는 행의 수이고 앵커에 무관하다. 여기에 객체 구성만으로 정해지는 둘을 더했다: `shared`(자기 객체가 짝을 갖는데 **다른 객체도 같은 원천을 가짐** = 조각)와 `displaced`(자기 객체엔 짝이 없고 다른 객체가 가짐). `right_object`는 조각을 못 보므로 연관 규칙의 효과는 다섯 값을 함께 읽는다.

## 결과 (전체 26개 영역, 기본값 = 밝기 순서 대비 변화)

| 목록 | 변형 | Δcorrect | Δalone_identified | **Δright_object** (%p; 95 %) | Δshared | Δdisplaced | Δunidentified | Δmissed | Δ우연 연결률 %p |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| AllWISE | `same_nearest` | +67 | −68 | **−1** (−0.01; −0.03 – 0) | **−58** | +1 | +1 | −69 | 0 |
| AllWISE | `nearest` / `same` | +65 / +3 | −66 / −3 | −1 / 0 | −58 / 0 | +1 / 0 | +1 / 0 | −67 / −3 | 0 |
| AllWISE | `file` (2.60.x 순서) | −2 | −29 | **−31** (−0.27; −0.46 – −0.07) | **+409** | +31 | +26 | +50 | 0 |
| AllWISE | `position` | −3 | −27 | −30 (−0.26) | +418 | +30 | +23 | +50 | 0 |
| AllWISE | `floored` | +2,233 | −2,412 | **−179** (−1.54; −1.97 – −1.07) | +31 | **+173** | +256 | −147 | **−2.07** |
| AllWISE | `allwise`(eeMaj, σ와 순서) | +378 | −399 | −21 (−0.18; −0.31 – −0.04) | −12 | +20 | +32 | −51 | **+0.63** |
| GALEX | `same_nearest` | +50 | −18 | **+32** (+1.07; 0.68 – 1.45) | +21 | **−32** | −30 | −61 | +0.09 |
| GALEX | `nearest` / `same` | +18 / +60 | −8 / −17 | +10 / +43 | −1 / +43 | −10 / −43 | −9 / −43 | −27 / −63 | +0.03 / +0.06 |
| GALEX | `file` | −23 | +5 | −18 (−0.60; −1.07 – −0.20) | +42 | +18 | +20 | +42 | 0 |
| GALEX | `floored` | +38 | −7 | +31 (+1.03; 0.50 – 1.58) | 0 | −31 | −19 | −26 | −0.15 |
| 2MASS | `same_nearest` | +4 | −4 | 0 | −7 | 0 | 0 | −5 | 0 |
| 2MASS | `floored` | −1 | +1 | 0 | +5 | 0 | 0 | +1 | −1.05 |

확인 17개 영역만(옛 주장의 분할): `same_nearest` AllWISE Δcorrect +46 · Δalone_identified −46 · **Δright_object 0** · Δshared −37 · Δmissed −46; GALEX Δcorrect +32 · Δalone_identified −15 · **Δright_object +17** (+0.96 %p; 0.43 – 1.45) · Δdisplaced −17 · Δunidentified −16 · Δmissed −39. 보정 15 / 시험 11로 보면 `floored` AllWISE `right_object`는 −99 / −80(둘 다 구간이 0 밖), `same_nearest` GALEX는 +25 / +7이다.

기본값의 절대값(전체 26): AllWISE `right_object` 10,023 / 11,590 (86.5 %), `wrong_object` 246 (2.1 %), `unidentified` 1,321 (11.4 %), `shared` 432, `displaced` 1,331; GALEX 1,812 (60.4 %) / 118 / 1,068 (35.6 %) / 93 / 1,047; 2MASS 1,055 (97.8 %) / 1 / 23 / 63 / 19.

## 무엇이 뒤집혔나 (첫 정의 대비)

1. **`same,nearest` AllWISE의 "새 정답 연결 +46"은 `right_object`로는 0이다.** 46행은 안 붙었을 때 이미 자기 객체(AllWISE 위치로 정답 원천에 닿는 단독 객체)가 정답 짝을 갖고 있었다(`alone_identified`). 같은 원천을 광학 객체도 가졌으므로 한 원천이 두 객체에 있던 조각이고, `same,nearest`가 그것을 합쳤다: `shared` −37(확인 17) / −58(전체), `missed` −46 / −69. 이득은 **실제로 있으나 "더 많은 행이 맞는 객체에 있다"가 아니라 "조각이 줄었다"**다. 첫 판의 "재라벨 몫 0 %, `right_object` +46"은 틀린 정의의 결과였다.
2. **GALEX는 이득의 일부가 진짜다**: `right_object` +32(+1.07 %p), `displaced` −32, `unidentified` −30; 재라벨 몫 36 %. GALEX 행은 위치 오차(~1″)가 커서 단독 객체로는 정답에 안 닿는 일이 많아 붙어야 객체가 정답을 가진다.
3. **`floored`는 첫 판에서 "+129 / −147 / −2.07 %p로 더 낫다"였으나 앵커 무관 읽기로는 AllWISE에서 나쁘다**: `right_object` −179(−1.54 %p), `displaced` +173, `unidentified` +256. `correct` +2,233의 108 %가 재라벨(`alone_identified` −2,412)이고, 이동 대조의 앵커 정의 +10.79 %p는 틀린 읽기이지만 우연 연결률 −2.07 %p는 맞는 개선이다. 위치 잔차(0.5″ 밖 4.51 → 3.27 %)와 우연 연결률은 좋아지고 연관은 나빠졌다.
4. **2.61.0의 순서 변경(`file` → 밝기)은 첫 판에서 "+52"였으나 새 읽기로는 `right_object` +31(+0.27 %p), `shared` −409(−49 %), `displaced` −31**: 이득의 주성분은 조각 줄이기(AllWISE 행 841 → 432)이고 `correct`(+2)는 못 본다.
5. **AllWISE `eeMaj`의 "올바른 연결 +5.2 %"는 `right_object` −21(−0.18 %p, 95 % −0.31 – −0.04)**다. 첫 판의 "+0.44 %"가 아니라 소폭 음의 방향이고 우연 연결률도 +0.63 %p 나빠진다. `allwise_sigma`(eeMaj를 σ에만)는 모든 지표가 0, 즉 효과는 전부 순서에서 온다(`allwise` = `allwise_order`).

## 예측 판정

첫 판의 예측(A–D, 옛 정의)은 폐기된 정의의 값에 대한 것이라 다시 판정하지 않는다(그 판정은 b0ec093의 README). 고친 정의에 대한 추가 예측(E1–E5, `PREDICTIONS_RIGHT_OBJECT_2026-11-28.md` 끝, 새 요약을 열기 전에 커밋 b06fdf0)은 **다섯 개 모두 틀렸다**:

| # | 예측 | 결과 |
|---|---|---|
| E1 | `same_nearest` 확인 17 AllWISE Δright_object +46 ± 2, GALEX +31 ± 3 | **0 / +17** |
| E2 | `file`/`position` AllWISE Δright_object −52 ± 5 | −31 / −30 (확인 17: −15) |
| E3 | `floored` AllWISE Δright_object는 옛 +129보다 크다(+135 ~ +160) | **−179**(부호가 반대) |
| E4 | `floored` 재라벨 몫 ≤ 94 %, `alone_identified` −2,000 안팎 | 108 %, −2,412 |
| E5 | 순위 floored > same_nearest > base > file ≈ position | base ≈ same_nearest > file ≈ position > **floored** |

모든 예측이 같은 방향으로 틀렸다: 나는 새 정의가 옛 정의를 수십 행 보정할 뿐이라고 보았는데, 단독 AllWISE 객체가 이미 "정답을 가진 객체"로 읽힌다는 사실(`T(O)`의 앵커 위치 규칙)이 `correct`의 이득 대부분을 재라벨로 바꾸었다. 옛 숫자를 이미 본 뒤에 쓴 예측(맹검이 아님)조차 틀렸다.

**2.62.10 review.** These tables were made before the review changed the truth id of an object without a resolving row. That id now comes from a member chosen by a fixed rule, not from the anchor position (`METRICS.md` section 1). So the anchor-independent readings here are provisional for variants that change the anchor of low-resolution-only objects (`floored` above all), and are to be re-measured with the fixed `measure_association.py`.
