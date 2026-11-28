# 예측 (측정 전에 씀): 연관 지표를 `right_object` 읽기로 다시 셀 때 값이 어떻게 변하는가 (2.62.7, 과제 러)

쓴 시점: 7개 변형(base, file, position, same, nearest, same_nearest, floored)의 Stage 1·이동 대조·`measure_association.py`가 끝났고 `summary/right_object_false_missed.csv`가 만들어졌으나 **아직 열어 보지 않은** 상태. 이미 알고 있던 것: 2.62.4 `eeMaj`의 `right_object` +0.44 %(28d 5.3절)와 `floored`의 이동 대조 +10.8 %p(옛 정의) / −2.07 %p(앵커 무관)(28d). 아래는 그 밖의 변형에 대한 예측이다.

## 변형 A: `same`, `nearest`, `same_nearest` (모호 처리, 2.61.8) 대 base

모호 처리는 **앵커 순서를 바꾸지 않고** 안 붙던 행(`ambiguous_new`)을 붙이는 규칙이다. 그러므로 재라벨(앵커→붙음)이 거의 없고 새 연결은 진짜여야 한다.

| # | 예측 | 틀리는 조건 |
|---|---|---|
| A1 | 보정 9개 영역에서 `same_nearest`의 Δcorrect(AllWISE)는 +46 ± 10, GALEX +32 ± 10(앞선 주장이 재현된다) | 이 범위 밖 |
| A2 | `\|Δrightly_alone\|` ≤ 0.15 × Δcorrect, 즉 재라벨 몫 < 15 %. 따라서 Δright_object ≥ 0.85 × Δcorrect | 재라벨 몫이 15 % 이상 |
| A3 | Δmissed ≈ −Δcorrect (±10 %): 늘어난 correct는 놓침이 줄어든 것이다 | 어긋남이 10 % 넘음 |
| A4 | Δfalse = 0 (±3행): 앞선 "틀린 연결 0"이 right_object 읽기에서도 유지된다 | \|Δfalse\| > 3 |
| A5 | 앵커 무관 우연 연결률 `shifted_any_pct`는 AllWISE·GALEX에서 0 ~ +0.5 %p 늘고, 2MASS는 ±0.1 %p 안 | 줄거나 +0.5 %p 넘게 늚 |
| A6 | `same` 단독과 `nearest` 단독은 합이 `same_nearest`와 ±20 % 안에서 맞는다(교호작용 작음) | 합이 20 % 넘게 어긋남 |
| A7 | 확인 17개 영역(test가 아닌 확인 분할)에서도 부호가 같고 크기는 보정의 ±40 % 안 | 부호가 다르거나 40 % 넘게 다름 |

## 변형 B: 같은 순서 키, 다른 동점 순서 (`file`, `position`) 대 base(= brightness)

동점 순서는 앵커를 바꿔 재라벨을 만든다. 그러므로 `correct`의 차이는 크고 `right_object`의 차이는 작다.

| # | 예측 |
|---|---|
| B1 | AllWISE: `\|Δright_object\|` ≤ 0.5 % (기대 짝 행 대비), `\|Δcorrect\|` ≥ 3 × `\|Δright_object\|`(재라벨이 지배) |
| B2 | GALEX·2MASS: `\|Δright_object\|` ≤ 0.5 %, 2MASS는 ≤ 0.1 % |
| B3 | `file` 변형이 2.60.9 기준선(틀린 연결률 AllWISE 2.08 %, GALEX 6.2 %, 2MASS 0.10 %; 놓침률 13.25 / 20.55 / 1.48 %)을 소수 둘째 자리 안에서 재현한다(2.60.9 이후 코드 변화는 기본값을 안 바꿈) |
| B4 | 이동 대조의 옛 정의(`shifted_false_pct`)와 새 정의(`shifted_any_pct`)의 차이는 순서가 바뀐 변형(file/position)에서 AllWISE ≥ 1 %p, 모든 변형에서 새 정의가 옛 정의 이상 |

## 변형 C: `floored`(순서 키를 바닥 적용 σ로) 대 base

| # | 예측 |
|---|---|
| C1 | `Δright_object`(AllWISE) ∈ [−0.7 %, +0.7 %]; `Δcorrect`는 그보다 3배 이상(앞선 eeMaj와 같은 재라벨 구조) |
| C2 | `shifted_false_pct`(옛 정의)는 +10 %p 이상 늘고 `shifted_any_pct`는 0 이하(앞선 28d 값 +10.8 / −2.07의 재확인, 같은 숫자) |

## 정의가 바뀌면 결론이 바뀌는 경우의 예측 (표 2의 핵심)

| # | 예측 |
|---|---|
| D1 | 옛 정의(`correct`, `shifted_false_pct`)로 "개선"이라 읽히던 변형 중 **적어도 하나**(floored의 correct, file/position의 correct)는 right_object·shifted_any로 읽으면 개선이 사라지거나 부호가 바뀐다 |
| D2 | `same_nearest`의 개선(A1~A4)은 정의와 무관하게 남는 유일한 개선이다 |

## 판정 방식

숫자를 연 뒤 위 표를 그대로 두고 맞음/틀림을 보고서에 적는다. 틀린 예측은 지우지 않는다. 범위의 경계(예: 정확히 ±15 %)는 경계를 포함해 맞음으로 센다.
