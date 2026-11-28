# 연관 지표의 정의 (2.62.7, 과제 러): 어느 것이 변형 비교에 쓸 수 있고 어느 것이 재라벨에 속는가

**이 문서의 쓰임**: 연관 변형(순서 규칙, 모호 처리 스위치, 위치 오차 읽기, 조각을 줄이는 규칙)을 비교하는 보고는 **이 문서의 "변형 비교에 쓴다" 지표만** 쓴다. 다른 지표는 그 옆에 놓을 수 있어도 결론의 근거로 쓰지 않는다. 정의는 코드에서 읽은 것이다(`measure_association.py`의 머리글과 `measure_field`, `regroup.py:score_accuracy`, `rescore_labels.py`). 새 지표를 만들면 여기에 먼저 적는다.

배경: `correct`("붙은 행만 셈")와 `missed`("안 붙은 행 중 다른 객체가 짝을 가짐")는 **그 행이 앵커인가 붙은 행인가**에 따라 값이 바뀐다. 구성이 같고 앵커만 다른 두 경우의 시험이 `Preprocess/tests/test_right_object_metric.py`에 있다. 그래서 순서 키를 바꾸는 변형은 `correct`가 오르고 `rightly_alone`이 내리는 재라벨을 "개선"으로 읽게 만든다. 검토 세션(Codex)이 첫 `right_object`(`correct + rightly_alone`)도 앵커에 따라 움직인다는 것을 찾았고(`rightly_alone`은 자기 객체에 정답 id가 없는 행도 담는데 같은 행이 정답 id 없는 객체에 붙으면 `unknown`이다) 지금의 정의로 바꾸었다. 이 문서의 지표는 **객체의 구성(어느 행이 어느 객체에 있는가)만으로 정해진다**. `pick` 채점이 고른 객체가 바뀌는 것에 속는 것(`WORK_REPORT_2026-11-28c.md`)에 이어 세 번째 함정이다.

## 1. 정답과 행의 정의 (`measure_association.py`)

* 참조 집합 R: HSC i < 25인 COSMOS2020 원천(Weaver et al. 2022). 해상 카탈로그(Legacy Surveys, PS1, SDSS, Gaia, SGA, Galaxy Zoo)의 행은 R의 원천만 볼 수 있다.
* 행의 정답 id: 해상 카탈로그의 행이 0.6″ 안의 가장 가까운 R 원천을 갖는다(없으면 미식별).
* 객체의 정답 id 집합 T(O): 객체의 해상 행들의 id다. 해상 행의 id가 없으면 **고정 규칙으로 고른 구성원 하나**의 위치에서 0.6″ 안의 가장 가까운 R 원천을 쓴다. 규칙은 해상 행 먼저, 그다음 PSF가 좁은 순(2MASS 2.5″, GALEX 5.3″, AllWISE 6.1″), 그다음 그 밖의 카탈로그이고, 같은 순위는 detection id 순이다. 2.62.10 검토 전에는 **앵커 위치**를 썼다. 그래서 앵커만 바뀌는 저해상도 객체(`floored`에서 AllWISE → GALEX)에서 T(O)가 바뀌었고, 아래의 "앵커에 의존하지 않는" 지표도 그 객체들에서는 움직였다(`test_right_object_metric.py`, 앵커만 다른 두 경우).
* 기대 짝(저해상도 행: AllWISE IRAC ch1 / 2MASS Ks / GALEX u 플럭스): 3 FWHM 안의 원천마다 가중치 w = F exp(−r²/2s²), s = FWHM/2.355; 허용 집합 A(d) = w ≥ 0.25 max w인 원천들(블렌드). 양의 플럭스 원천이 없으면 기대 짝 없음(`no_expected`).
* 저해상도 행이 3개 카탈로그(AllWISE, 2MASS PSC, GALEX AIS)이고 그 행들만 센다.

## 2. 지표

행의 분류는 **그 행이 속한 객체가 무엇을 갖는가**로만 정한다(앵커인지 붙은 행인지는 보지 않는다): 객체의 정답 id 집합 T(O)가 행의 허용 집합 A(d)와 만나는가(`identified`), T(O)가 비어 있지 않으나 안 만나는가(`wrong`), T(O)가 비어 있는가(`unidentified`).

| 지표 | 정의 | 앵커에 의존? | 변형 비교에 쓰는가 |
|---|---|---|---|
| `matched` | 행이 기존 그룹에 **붙음**(`association_status == "matched"`) | **예** | 아니오(참고) |
| `correct` | 붙음이고 `identified` | **예**(앵커이던 행이 붙으면 늘고, 안 붙은 행이 앵커 쪽 `alone_identified`에서 빠진다) | **아니오** |
| `false` | 붙음이고 `wrong` | 부분적 | 개수는 `wrong_object`로 |
| `unknown` | 붙음이고 `unidentified` | **예** | 아니오 |
| `rightly_alone` | 안 붙음이고 **다른 객체가** A(d)의 원천을 갖지 않음 | **예**(자기 객체에 정답 id가 없는 행도 담는다) | **아니오** |
| `missed` | 안 붙음이고 다른 객체가 A(d)의 원천을 가짐 | **예**: 같은 구성에서 행이 앵커이면 `missed`, 붙은 행이면 `correct`가 될 수 있다(블렌드; `test_right_object_metric.py` 둘째 시험) | **아니오**(조각은 `shared`로) |
| `alone_identified` / `alone_wrong` / `alone_unidentified` | 안 붙은 행을 **같은 시험**으로 자기 객체에서 읽은 것 | 예(단독 값은 앵커에 의존; 붙은 행의 `correct`/`false`/`unknown`과 합해서만 의미) | 합으로만 |
| **`right_object`** | `correct + alone_identified`: 행이 정답 짝을 가진 객체 안에 있다 | **아니오** | **예(주 지표)** |
| **`wrong_object`** | `false + alone_wrong`: 행이 정답 id는 있으나 짝을 안 가진 객체 안에 있다 | **아니오** | **예** |
| **`unidentified`** | `unknown + alone_unidentified`: 행의 객체에 정답 id가 없다(정답 쪽 원천이 없거나 R 밖) | **아니오** | 예(`right_object`가 늘어난 곳이 여기서 빠졌는지 보려고) |
| `right_object + wrong_object + unidentified` | = 기대 짝이 있는 행의 수(`with_expected`) | | 분할이므로 합이 일정한지 확인 |
| **`shared`**(조각) | 행의 **자기 객체가** 허용 짝을 갖고 **다른 객체도 같은 원천을 가짐**: 한 정답 원천이 두 객체에 있다 | **아니오**(구성만) | **예**: `right_object`가 못 보는 조각을 센다 |
| **`displaced`** | 행의 자기 객체는 허용 짝이 없는데 **다른 객체가** 가짐: 맞는 객체가 있는데 엉뚱한 객체에 있다 | **아니오** | **예** |
| 틀린 연결률 `false_pct_of_matched_known` | `false / (correct + false)` | 부분적: 분모(붙은 행)가 앵커에 따라 바뀐다 | 참고; `wrong_object` 개수를 쓴다 |
| 놓침률 `missed_pct_of_expected` | `missed / with_expected` | **예**(`missed`와 같음) | 아니오(분모를 항상 적는다: 옛 도구 `association_ambiguity`의 `missed_pct`는 분모가 **안 붙은 행**이라 같은 이름에 값이 다르다, 5절) |
| 이동 대조 `shifted_false_pct`(2.49.0 정의) | 이동한 행 중 **이동하지 않은 카탈로그가 앵커인** 객체에 붙은 비율 | **예**(AllWISE가 앵커이면 우연히 붙은 광학 행을 세지 않는다) | **아니오** |
| **우연 연결률 `shifted_any_pct`** | 이동한 행 중 **객체에 이동하지 않은 카탈로그의 행이 하나라도** 있는 비율 | **아니오** | **예(주 지표)** |
| 위치 잔차(`position_residual.py`) | 정답에 닿는 깨끗한 객체의 위치(앵커)와 그 정답 원천의 거리: 중앙값, 90·99 백분위, 0.3·0.5·0.7·1.0″ 밖 비율 | 앵커가 위치를 정하므로 의존하되 **그것이 질문** | 예(순서 규칙을 고르는 기준) |
| 병합 `merged_objects_gt1/gt2` | 해상 행이 서로 1″(2″) 넘게 떨어진 정답 원천 둘 이상을 가진 객체 | 아니오 | 예 |
| 조각(`fragments`) | i < 23 정답 원천이 1.5″ 안에 1카탈로그 최상위 객체를 더 가짐 | 아니오 | 예(해상 행의 조각; `shared`는 저해상도 행의 것) |

주의:

* **`right_object`는 조각을 못 본다.** 안 붙은 AllWISE 행의 객체는 앵커 위치가 정답 원천 0.6″ 안이면 이미 `identified`다. 같은 원천을 광학 객체도 가지면 그 행은 조각인데 `right_object`는 둘을 다 맞다고 센다. 조각은 `shared`로, 엉뚱한 객체에 있는 것은 `displaced`로 센다. **한 변형의 연관 효과를 말하려면 `right_object`, `wrong_object`, `unidentified`, `shared`, `displaced` 다섯 개를 함께 낸다.**
* `unidentified`가 크다(AllWISE 11 %, GALEX 36 %): 행의 객체에 정답 id가 없는 경우(해상 행이 R의 원천에 닿지 않거나 정답 쪽 원천이 어두운 경우)로, 변형 사이에서 이 몫이 늘면 `right_object`가 줄어든다. 늘었다는 것이 틀렸다는 뜻은 아니다.
* `right_object`·`wrong_object`·`unidentified`·`shared`·`displaced`는 `T(O)`의 규칙에 기댄다. 해상 행이 없는 객체의 대체 위치는 2.62.10부터 앵커가 아니라 고정 규칙으로 고른 구성원이다(1절). **5절의 수치는 고치기 전 도구(앵커 위치)로 쟀다.** 그래서 저해상도 객체의 앵커를 바꾸는 변형(`floored`, `allwise_order`, 2.61.0의 순서)에서는 값이 달라질 수 있어 다시 잰다.

## 3. 라벨 정확도의 읽기 (`regroup.score_accuracy`, `rescore_labels.py`; COSMOS2020 STAR / GALAXY, F814W < 24.5)

| 읽기 | 정의 | 고른 객체/위치에 속는가 | 변형 비교에 쓰는가 |
|---|---|---|---|
| `pick` | 1.5″ 안에서 카탈로그가 가장 많은 객체 **하나**의 클래스(부모가 있으면 부모의 클래스) | **예**: 조각을 줄이는 규칙은 어느 객체가 "그" 객체인지를 바꿔 고침/깨짐을 부풀린다 | **아니오**(옛 보고서에서 고침/깨짐 수의 근거로 썼던 것) |
| `exists` | 0.5″ 안에 정답 클래스의 객체가 **있다** | 아니오(고른 객체와 무관); 그러나 **앵커 위치**가 0.5″ 고리를 넘나드는 것에 반응한다 | **예**, `exists_both_near`와 함께 |
| `every` | 0.5″ 안에 객체가 있고 **모두** 정답 클래스 | 아니오 | 예(틀린 클래스 경쟁자의 부재) |
| `exists_both_near` | `exists`를 두 실행 **모두에서** 0.5″ 안에 객체가 있는 정답 원천으로 제한 | 아니오; 위치가 고리를 넘나드는 것을 뺀다 | **예**: 클래스의 변화만 본다 |
| 위치 잔차 | 위 표 | | 예 |

판정: 라벨 변화를 말할 때는 `exists`와 `exists_both_near`를 둘 다 적고, 둘의 차이(고리 넘나듦)를 위치 잔차로 설명한다. McNemar p는 `rescore_labels.py`가 계산한다.

## 4. 지표를 낼 때의 규칙

1. 연관 변형 보고는 `right_object`, `wrong_object`, `unidentified`, `shared`, `displaced`(다섯 개를 함께; 앞 셋의 합이 기대 짝이 있는 행의 수), 앵커 무관 우연 연결률 `shifted_any_pct`, 위치 잔차, 병합을 쓴다. `correct`·`missed`·`rightly_alone`·`shifted_false_pct`·`false_pct_of_matched_known`은 필요하면 옆 열로 두되 **결론에 쓰지 않는다**(`measure_association.py`는 모두 내고 새 열은 끝에 덧붙인다).
2. 재라벨 몫을 따로 적는다: `Δcorrect`가 `right_object`로 얼마나 이어졌는가는 `−Δalone_identified / Δcorrect`이고(`right_object_recount.py`의 `relabel_share_of_d_correct_pct`), 100 %를 넘으면 `right_object`는 오히려 줄었다는 뜻이다.
3. 위치와 클래스가 함께 움직이는 변형은 `exists`(위치 포함)와 `exists_both_near`(클래스만)를 둘 다 적는다.
4. 같은 정답(COSMOS2020)에 대한 비교만 한다. 정답 자체의 위치·플럭스 오차는 변형 사이의 차이에는 대부분 상쇄되지만 절대값의 근거는 아니다.
5. 새 지표는 이 문서에 정의와 "앵커/고른 객체에 속는가"를 먼저 적은 뒤 쓴다.

## 5. 정의가 바뀌면 같은 변형이 어떻게 달라 보이는가 (깊은 COSMOS 26개 영역 실측, `results_2026-11-28d/`, AllWISE 기본값 대비; **잠정**: 2.62.10 검토 전의 T(O) 대체 규칙(앵커 위치)으로 잰 값, 1절)

| 변형 | 옛 읽기 | 앵커 무관 읽기 | 무슨 일인가 |
|---|---|---|---|
| `floored`(순서 키를 바닥 적용 σ로) | `correct` +2,233, `missed` −147, 이동 대조(앵커 정의) +10.79 %p(나빠짐) | `right_object` **−179**(−1.54 %p, 95 % −1.97 – −1.07), `unidentified` +256, `displaced` +173, `shared` +31, 우연 연결률 −2.07 %p | `correct` 증가는 `alone_identified` −2,412의 재라벨이다. 앵커와 무관하게 읽으면 맞는 객체 안의 행이 줄고 엉뚱한 객체 안의 행이 늘었다(우연 연결만 줄었다) |
| 2.60.x 동점 순서 `file`/`position` 대 기본값(밝기, 2.61.0) | `correct` −2 / −3(차이 없어 보임), `missed` +50 | `right_object` −31 / −30(−0.27 / −0.26 %p, −0.46 – −0.07), `shared` **+409 / +418**(기본값은 −49 %), `displaced` +31 / +30 | 2.61.0의 이득은 대부분 **조각 줄이기**(한 정답 원천이 두 객체에 있는 AllWISE 행 841 → 432)이고 `correct`는 못 본다 |
| `same,nearest`(2.61.8), AllWISE | `correct` +67(확인 17: +46) | `right_object` **−1**(확인 17: 0), `shared` **−58**(확인 17: −37), `missed` −69 | 이 규칙의 이득은 "더 많은 행이 정답 객체 안에 있다"가 아니라 **한 원천의 두 객체를 하나로 합친 것**(조각)이다. 옛 주장의 "새 정답 연결 +46"은 재라벨(`alone_identified` −46)이다 |
| `same,nearest`, GALEX | `correct` +50(확인 17: +32) | `right_object` **+32**(+1.07 %p, 0.68 – 1.45; 확인 17: +17), `displaced` −32, `unidentified` −30, `shared` +21 | GALEX 행은 앵커 위치만으로는 정답에 안 닿는 일이 많아 붙어야 객체가 정답을 가진다: 진짜 이득이 절반 남는다(재라벨 몫 36 %) |

* `correct`는 **양쪽으로** 속는다: 앵커가 바뀌면 이득이 없는데 늘고(`floored`), 같은 원천의 조각이 합쳐져 이득인데 안 는다(`file` → 기본값, `same,nearest` AllWISE).
* 옛 도구(`association_ambiguity`, 2.61.8)의 `missed_pct`(−1.17 / −1.04 %p)는 분모가 안 붙은 행이고, `measure_association.py`의 `missed_pct_of_expected`는 분모가 기대 짝이 있는 행이다. 같은 `same_nearest`(확인 17)가 −0.62 %p(AllWISE) / −2.20 %p(GALEX)가 된다. 비율 옆에 분모를 적는다.
* 새 연결의 일부가 `unidentified`이면 `correct` 증가와 `missed` 감소가 같지 않다(`same_nearest` GALEX 확인 17: 붙은 행 +43 = 정답 +32, `unknown` +9, 기대 짝 없는 행 +3, 틀린 연결 −1).
