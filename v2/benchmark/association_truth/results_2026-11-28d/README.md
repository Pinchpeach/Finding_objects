# 과제 러: 연관 지표를 `right_object` 읽기로 다시 센 결과 (2.62.7)

정의는 `../METRICS.md`, 예측은 `../PREDICTIONS_RIGHT_OBJECT_2026-11-28.md`(측정 요약을 열기 **전에** 커밋, 584fc1e). 이 폴더의 표는 모두 `../right_object_recount.py`(필드별 JSON의 합)와 `../right_object_tables.py`(마크다운)가 만든다.

## 재현

```
bash v2/benchmark/association_truth/run_right_object_variants.sh FIELDS_ROOT TRUTH_FLUX_DIR OUT     # Stage 1 x 7 변형(+이동 사본), measure_association.py, 요약
python v2/benchmark/association_truth/right_object_recount.py --root OUT --variants base file position same nearest same_nearest floored --out RES
python v2/benchmark/association_truth/right_object_tables.py --recount RES > tables.md
```

입력: 깊은 COSMOS 26개 영역(`benchmark/deep_cosmos/`의 원자료), COSMOS2020 정답(`collect_truth_flux.py`). 측정은 커밋 78e2c97 위에서 `measure_association.py`의 `right_object`·`shifted_any_pct` 추가가 **커밋되기 전**에 돌렸다(`*.run_info.json`의 `dirty`=True와 `dirty_files`에 그것이 보인다; 그 변경은 이 폴더와 같은 커밋에 들어 있다).

| 파일 | 내용 |
|---|---|
| `recount_counts.csv` | 변형 × 분할 × 목록의 개수와 비율 (분할: `cal9`, `conf17`, `cal15`, `test11`, `all26`) |
| `recount_delta.csv` | 기본값 대비 변화: 각 개수의 차, 재라벨 몫, 영역 부트스트랩 95 % 구간 |
| `right_object_false_missed.csv`, `right_object_structure.csv` | 기존 요약 도구(`summarize_native_error_variants.py`)의 형식(보정 15 / 시험 11 분할) |
| `tables.md` | 보고서의 표 1–3 |

분할이 둘이다: **보정 9 / 확인 17**은 2.61.8(`association_ambiguity`, "정답 연결 +46 / +32")의 분할이고, **보정 15 / 시험 11**은 2.60.9(`fields_split.csv`, 이름 해시)의 분할이다. 둘을 섞어 부르지 않는다.

## 예측 판정 (예측 표를 그대로 두고 적는다; 틀린 것은 지우지 않았다)

| # | 예측 | 결과 | 판정 |
|---|---|---|---|
| A1 | **보정 9**에서 `same_nearest` Δcorrect AllWISE +46 ± 10, GALEX +32 ± 10 | 보정 9: +21 / +18. **확인 17**: +46 / +32(정확히 같음) | **틀림**(분할 이름을 잘못 적었다: 옛 주장의 +46 / +32는 확인 17의 값이다). 재현은 됨 |
| A2 | 재라벨 몫 < 15 % | AllWISE 0 %, GALEX 확인 17 3 %(전체 2 %), 2MASS 0 % | 맞음 |
| A3 | Δmissed ≈ −Δcorrect (±10 %) | AllWISE −46 대 +46 맞음. GALEX 확인 17 −39 대 +32(22 % 어긋남): 새로 붙은 행 +43 중 `unknown` +9, 기대 짝 없는 행 +3 | AllWISE 맞음, GALEX 틀림 |
| A4 | Δfalse = 0 (±3행) | AllWISE 0, GALEX −1 / −2, 2MASS 0 | 맞음 |
| A5 | 우연 연결률 AllWISE·GALEX 0 ~ +0.5 %p, 2MASS ±0.1 | AllWISE +0.01, GALEX +0.10(확인 17), 2MASS 0 | 맞음 |
| A6 | `same` + `nearest` ≈ `same_nearest` (±20 %) | AllWISE 3 + 65 = 68 대 67 맞음. GALEX(전체 26) 58 + 17 = 75 대 49(+53 %), 2MASS 3 + 2 = 5 대 4(+25 %) | AllWISE 맞음, GALEX·2MASS 틀림(두 규칙이 같은 행을 고친다) |
| A7 | 확인 17의 크기가 보정 9의 ±40 % 안 | 비율(%p): AllWISE +0.51 → +0.62(+21 %), GALEX +1.47 → +1.75(+19 %). **개수**로 보면 +119 % / +78 %(확인 17의 행이 1.8 / 1.4배) | 비율로 맞음; "크기"를 개수로 읽으면 틀림(쓸 때 단위를 안 적었다) |
| B1 | 동점 순서 `file`/`position`: AllWISE \|Δright_object\| ≤ 0.5 %p, \|Δcorrect\| ≥ 3 × \|Δright_object\| | −0.449 / −0.457 %p(앞 절반 맞음). Δcorrect는 −2 / −3인데 Δright_object는 −52 / −53 | 앞 절반 맞음, **뒤 절반 틀림**: 재라벨이 아니라 `correct`가 못 보는 실제 변화였다 |
| B2 | GALEX·2MASS \|Δright_object\| ≤ 0.5 %p(2MASS ≤ 0.1) | GALEX −0.73 / −0.77 %p(확인 17 −1.02 / −1.07), 2MASS 0 | 2MASS 맞음, **GALEX 틀림** |
| B3 | `file` 재측정이 2.60.9 보고 수치를 소수 둘째 자리까지 재현 | 틀린 연결률 2.08 / 6.23 / 0.10 %(보고 2.09 / 6.23 / 0.10), `correct` 7,280(`position` 7,279)와 1,745(보고 7,279 / 1,745). 놓침 AllWISE 13.68 %(보고 표 13.8 %는 전체 26의 13.68 %가 아니라 보정 15의 13.86 %에 가깝다) | 틀린 연결률·개수는 맞음(±1행, 0.01 %p); 놓침은 **보고 표의 숫자 쪽이 어긋남**(13.8 대 13.68) |
| B4 | 옛 이동 대조와 새 정의의 차이는 AllWISE ≥ 1 %p | 수준 차 7.63 대 20.66 %(맞음, 정의상 `shifted_any` ≥ `shifted_false`). `file`/`position`은 두 읽기 모두 기본값과 0.00 %p 차이 | 자명하게 맞음(쓸모 없는 예측이었다) |
| C1 | `floored` Δright_object(AllWISE) ∈ [−0.7, +0.7] %p, Δcorrect ≥ 3배 | **+1.113 %p**(95 % 0.45–1.83), Δcorrect +2,233 = Δright_object +129의 17배 | **틀림**(범위 밖); 3배 조건은 맞음 |
| C2 | 이동 대조 +10 %p 이상(옛) / 0 이하(새) | +10.79 / −2.07 %p | 맞음(28d와 같은 숫자) |
| D1 | 옛 정의 "개선" 중 적어도 하나는 새 읽기에서 사라지거나 부호가 바뀐다 | `floored` 이동 대조 +10.79 → −2.07(부호 뒤집힘); `correct` +2,233 → `right_object` +129(94 %가 재라벨) | 맞음 |
| D2 | `same_nearest`의 개선이 정의와 무관하게 남는 **유일한** 개선 | `floored`의 `right_object` 이득(+1.11 / +1.23 %p)도 구간이 0을 넘어 남는다. `same_nearest`는 세 목록 모두 개선하고 우연 연결률을 거의 안 키우는 점이 다르다 | **틀림**(유일하지 않다) |

15개 중 온전히 맞음 7(A2, A4, A5, A7[비율로], B4[자명], C2, D1), 부분적으로 맞거나 틀림 8(A1, A3, A6, B1, B2, B3, C1, D2).

## 결과 요약 (숫자는 `tables.md`와 `recount_delta.csv`)

1. **`same,nearest`의 이득은 right_object로 읽어도 그대로다.** 확인 17: `same_nearest` AllWISE `right_object` +46(+0.617 %p, 95 % 0.431–0.853), GALEX +31(+1.750 %p, 1.016–2.393), 틀린 연결 0 / −1, 우연 연결률 +0.01 / +0.10 %p. 재라벨 몫 AllWISE 0 %, GALEX 3 %. 이득의 출처: AllWISE는 전부 `nearest`(+46), GALEX는 대부분 `same`(+38; `nearest` +9; 둘을 합친 것이 +31이라 같은 행을 고친다). 옛 주장의 놓침 −1.17 / −1.04 %p는 분모가 안 붙은 행이었고, 기대 짝이 있는 행 기준으로는 −0.62 / −2.20 %p다(표 3과 METRICS.md 5절).
2. **2.61.0의 순서 변경(`file` → 밝기)은 right_object로 읽어도 이득이고, 오히려 `correct`가 이를 못 보았다.** AllWISE `right_object` 9,411 → 9,463(+52, +0.45 %p, 95 % 0.26–0.65): 놓침 1,586 → 1,536, `rightly_alone` 2,131 → 2,181, `correct`는 7,280 → 7,282(+2). 즉 `correct`는 2.61.0 AllWISE 개선을 **거의 0으로** 읽는다. GALEX는 +22(+0.73 %p, 0.29–1.26).
3. **`floored`(순서 키를 바닥 적용 σ로)**: AllWISE `correct` +2,233이 `right_object` +129(+1.11 %p)로 줄어든다(재라벨 94 %). 이동 대조는 옛 정의 +10.79 %p(나빠짐), 앵커 무관 −2.07 %p(좋아짐). GALEX `right_object` +37(+1.23 %p), 틀린 연결 −12, 2MASS −1(−0.09 %p). 이 변형은 출력 위치 설계(`best_member`)와 함께 판단할 몫이다(28d 5.6절, 승격은 보류).
4. **2.60.9 기준선**: 틀린 연결률은 어느 읽기에서도 그대로다(AllWISE 2.08–2.09 %, GALEX 6.23–6.26 %, 2MASS 0.10 %: 정의가 붙은 행에 대한 것이라 앵커에 덜 의존). 계획 세션이 "2.60.9 기준"으로 적은 놓침 13.25 / 20.55 / 1.48 %는 **현재 기본값**(2.61.0 이후)의 값이고, 2.60.9 당시 코드는 13.68 / 21.95 / 1.48 %다.
5. **위치 잔차**(2.61.0 순서 변경, 28d 5.6절, `../results_2026-11-28c/`)는 다시 세지 않고 그대로 옮긴다:

| 변형 | 깨끗한 객체 | 중앙값 ″ | 90 % ″ | 0.5″ 밖 % | 1.0″ 밖 % |
|---|---|---|---|---|---|
| `file`(2.60.x 순서) | 138,014 | 0.0721 | 0.288 | 4.46 | 1.92 |
| `position` | 138,021 | 0.0721 | 0.288 | 4.46 | 1.92 |
| 기본값(밝기, 2.61.0) | 136,820 | 0.0723 | 0.289 | 4.51 | 1.94 |
| `floored` | 136,296 | 0.0702 | 0.259 | 3.27 | 1.36 |
| `allwise_order`(eeMaj 순서 키) | 136,794 | 0.0719 | 0.283 | 4.26 | 1.78 |

   짝지은 비교(기본값 기준, 0.1″ 넘게 나빠진 / 좋아진 정답 천체): `file` 169 / 266(0.5″ 안으로 216, 밖으로 154), `floored` 62 / 2,568(안으로 1,876, 밖으로 22). 출력 위치 설계는 앵커 4.51 → `best_member` 3.16 → `ivw_mean` 3.28 %(0.5″ 밖). 2.61.0의 순서 변경은 위치 잔차를 **거의 그대로**(+0.05 %p) 둔다.
