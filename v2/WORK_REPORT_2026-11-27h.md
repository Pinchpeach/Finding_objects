# 작업 보고서 2026-11-27h — 과제 차: 탐사 수 스위치와 연관 규칙을 함께 켠 결정표 (측정만, 기본값 그대로)

버전 제안: **2.61.10 (PATCH)**. 기본 동작과 결과가 바뀌지 않는다(측정 도구·표·문서·정정만). 같은 브랜치의 과제 카(`WORK_REPORT_2026-11-27i.md`)는 기본 동작이 바뀌어 2.62.0(MINOR 후보)이다.

## 0. 내가 이해한 요청과 한눈에 보는 답

**요청**: 저위도 거짓 QSO를 줄이는 탐사 수 스위치(`surveys2/3`)와 1단계 모호 해소(`same,nearest`)를 **함께** 켠 조합의 비용·이득을 한 표로 낸다. 조합은 base / surveys2+spectro_keep / same,nearest / same,nearest+surveys2 / same,nearest+surveys2+spectro_keep / same,nearest+surveys3이고, 특히 연관을 고치면 `spectro_keep`이 필요 없어지는지 가린다. 기본값은 바꾸지 않는다. 검토 세션의 질문 3개에도 답한다: (1) 문턱이 첫 병합 표 뒤에 바뀌었나, (2) "틀린 연결 0"의 분모·상한·정의, (3) 깨진 COSMOS 라벨 3개가 무엇이고 왜인가.

**답**
1. **내 앞선 보고가 틀렸다(정정)**. 2.61.8 보고서의 "고침 2 / 깨짐 3, p = 1.00"은 Legacy Surveys r 등급이 있는 객체만 센 값이다. 정답과 짝지은 객체 **전부**를 세면 확인 17개 필드에서 **고침 20 / 깨짐 5(McNemar p = 0.0041)**, 보정 9개 필드 14 / 3(p = 0.013), 26개 전체 34 / 8(p = 7×10⁻⁵)이다. 다만 정답 위치 0.5″ 안에 기대 클래스 객체가 **하나라도** 있는지로 세면 26개 전체에서 1 / 2뿐이다. 이득은 "새 은하를 찾았다"가 아니라 "정답 천체의 증거가 조각이 아닌 합쳐진 객체에 모여 그 객체가 가장 가까운 객체가 되었다"이다 (5절).
2. **질문 (1)**: 문턱 상수(0.3″, 0.3″, 3배)는 첫 커밋부터 지금까지 모든 커밋에서 같다. 다만 확인 필드를 문턱을 정하기 전에 **한 번(26개 합친 표로)** 보았다는 사실은 git이 아니라 사전기록 문서의 공개 문장에만 남아 있다. 따라서 확인 세트는 "거의 독립"이지 독립이 아니다 (3.1절).
3. **질문 (2)**: "틀린 연결 0"은 변형이 **새로 붙인** 98개 연결(AllWISE 46, 2MASS 3, GALEX 49) 중 정답이 알려진 85개에서의 값이다. Wilson 95 % 상한은 **4.3 %**(AllWISE 7.7 %, GALEX 9.4 %). 2.61.0·2.60.9의 "거짓 연관율"과 **같은 정답 판정**을 쓰지만 **분모가 다르다**(그쪽은 조인된 전체 행, 이쪽은 늘어난 행만). 그래서 보고서의 "틀린 연결이 연결의 1 % 이하 ✔(0건)"은 점추정이 0일 뿐 통계적으로는 확인되지 않았다 (3.2절).
4. **질문 (3)**: 깨진 5개(확인)는 모두 같은 은하가 변형에서도 GALAXY로 분류된 채 있고(진실에서 0.10–0.35″), 가장 가까운 객체가 합쳐지지 않은 이웃 조각이나 이미 있던 STAR 객체와의 0.10″ 동점으로 바뀐 것이다 (3.3절).
5. **결정표**(8행, 4절): `same,nearest + surveys2`는 확인 140개 원뿔에서 표본 퀘이사가 아닌 QSO 라벨을 175 → 81(`surveys2` 단독과 같음)로 줄이면서 표본 퀘이사 재현율을 95 → 96/143으로 올리고 잃는 퀘이사는 0이다. 깊은 COSMOS에서 Chandra type 1 AGN은 모든 행에서 0/123 손실이다.
6. **`spectro_keep`은 필요 없어지는가**: **분광 QSO 32개에 대해서는 그렇다** — 기본 연관에서 `surveys2/3`가 5/32를 막고(`spectro_keep`을 켜면 0), `same,nearest`에서는 `spectro_keep` 없이도 0/32이다. 단 (a) 32개는 `spectro_keep`을 만든 바로 그 객체라 독립 확인이 아니고 Wilson 상한이 10.7 %이며, (b) **다른 종류의 QSO 라벨이 막힌다**: 실사용 COSMOS 영역의 QSO 라벨 16개는 전부 NED·SIMBAD에만 있는 객체(탐사 행 0개)이고 `surveys2/3`가 16개를 모두 막는다. `spectro_keep`은 분광 규칙만 예외로 두므로 이것은 지켜지지 않는다 (4.4절).
7. **보정/확인 이력**: 이 표의 어떤 표본도 문턱이나 스위치를 고르는 데 쓰였다. **세트 C만이 아무것도 맞추지 않은 표본**이고 이 조합들로는 돌리지 않았다.

## 1. 한 일

| 단계 | 내용 | 도구 / 표 |
|---|---|---|
| 정정 | 깊은 COSMOS 26개의 고침·깨짐을 짝지은 객체 전부로 다시 셈, 두 읽기(가장 가까운 객체 / 0.5″ 안에 기대 클래스 존재) | `benchmark/association_ambiguity/recount_fixed_broken.py`, `results_2026-11-27h/fixed_broken_all_matched.csv`, `broken.csv` |
| 저위도 | 보정 169·확인 140개 원뿔 × 6 변형(블라인드 원자료 재분류), 표본 퀘이사·거짓 QSO 밀도(전체 / LS 있는 원뿔 / 없는 원뿔, 영역 부트스트랩)·위치로 짝지은 교환 | `benchmark/lowlat_qso/combos_table.py`, `results_2026-11-27h/inputs/lowlat_{confirmation,calibration}.csv` |
| 분광 | 분광 클래스 QSO 32개(15 + 17개 원뿔)를 연관별로 다시 셈 | `spectro_held.py`, `inputs/held_*.csv` |
| 깊은 COSMOS | 26개 영역, 위도 한계를 푼 6 변형: Chandra type 1 재현율·손실, 후보 표시 순도·재현율, 거짓 QSO | `faint_cost.py`(변형 이름 추가), `inputs/type1_loss_by_r.csv`, `claims.csv` |
| 라벨 변화 | 깊은 COSMOS 26개와 실사용 3개 영역의 1차 라벨 변화(위치로 짝지음) | `label_changes.py`(결함 고침), `inputs/cosmos_label_changes.csv`, `real_use_*.csv` |
| 조립 | 8행 결정표 | `decision_table_combos.py` → `results_2026-11-27h/decision_table.csv` |

## 2. 설계 이유 (왜 이렇게 짰나, 버린 대안)

* **객체를 위치로 짝지었다(`object_id`가 아니라)**. 연관이 바뀌면 `OBJ` 번호는 그 뒤의 모든 그룹에서 밀린다. `ab_variants.py`의 교환 열(`false_removed/added_vs_control`, `removed_per_deg2`)은 `object_id@region`으로 짝지으므로 연관 변형에서는 번호가 밀린 것을 센다. 그래서 표본 퀘이사는 이름으로(구역·표본 이름이 변하지 않는다), 거짓 QSO의 교환은 구역 안 1″ 상호 최근접으로 셌다(`lowlat_exchange.py`). 버린 대안: 번호를 맞추는 열을 추가해 `ab_variants.py`를 고치는 것 — 번호가 달라지는 이유가 연관 자체라 근본적으로 맞출 수 없다.
* **정답 객체 라벨을 두 가지로 읽었다**. "가장 가까운 객체의 라벨"은 사용자가 위치로 조회했을 때 받는 값이고, "0.5″ 안에 기대 클래스가 있나"는 조각 중 어느 것이 가장 가까운지와 무관하다. 둘이 달라야 이득의 정체(조각 정리)가 보인다. 한 지표만 썼다면 정정 전 보고처럼 "이득 없음"이거나 "이득 큼"의 한쪽 오해가 남는다.
* **모든 행을 같은 단위 읽기(`V2_POSERR_UNITS=legacy`)로 돌렸다**. 과제 카가 VLASS·NVSS 오차의 단위를 고쳐 기본 연관을 바꾸므로, 기준(base)과 새 조합이 다른 코드로 돌면 두 효과가 섞인다. 새 조합의 저위도·COSMOS 실행은 모두 `legacy`로 고정했다. (실행 중에 코드를 고쳐서 이 원칙이 한 번 깨졌고 아래 6절에 적었다.)
* **조합을 직접 쟀다(가산 가정 없이)**. 두 스위치가 서로의 효과를 바꿀 수 있다(연관을 고치면 탐사 수가 늘어 `surveys2`가 덜 막는다). 표의 "합쳐도 더해진다"는 결론은 직접 잰 값이다: `same,nearest+surveys2`의 거짓 QSO 81은 `surveys2` 단독의 81과 같고, 표본 퀘이사는 1개 더 산다.
* **저위도 비용은 블라인드 원자료를 오프라인으로 다시 분류**했다(`variant.sh`). 수집을 다시 하지 않아 입력이 같고, 스위치만 바뀐다. 한 변형이 5분이라 6 변형 × 2 세트가 가능했다.
* **`faint_cost.py`를 재사용**했다(변형 이름만 추가). 같은 도구가 `surveys2/3`의 COSMOS 비용을 이미 쟀기 때문에 새 변형도 같은 정의(Chandra type 1 = 진실, 위도 한계를 푼 실행, 슬림 복사)로 나온다.
* **버린 대안 — 6개 조합을 하나의 거대 표에 넣지 않고 입력 표를 따로 둠**. 입력 CSV(`results_2026-11-27h/inputs/`)를 커밋해 두어 `decision_table_combos.py`만으로 결정표를 재생성할 수 있다. 입력을 만드는 단계(수 시간)와 조립(수 초)이 분리된다.

## 3. 검토 세션의 질문 3개

### 3.1 질문 (1): 문턱이 첫 병합 표 뒤에 바뀌었나

* `SAME_OBJECT_ARCSEC = 0.3`, `NEAREST_SEP_ARCSEC = 0.3`, `NEAREST_RATIO = 3`은 18d42c4(19:37, 첫 커밋)에서 지금(HEAD)까지 **어느 커밋에서도 바뀌지 않았다**: 18d42c4, 24c0698(20:27), 27bf5fb(20:51), 4b78757(22:02), d75b030(22:03), 이후 HEAD를 `git show <커밋>:v2/Preprocess/01_source_association.py | grep`으로 하나씩 확인했다.
* 그러나 **"첫 병합 표"는 첫 커밋보다 먼저 있었다**. 그 시점은 git에 없고, `benchmark/association_ambiguity/PREDICTIONS.md`의 공개 문장이 유일한 기록이다: "첫 `candidate_truth.py` 표가 26개 COSMOS 필드를 합쳐서 확인 필드를 문턱을 정하기 전에 합친 개수로 한 번 보았다. 그 뒤 표를 1–9번만으로 다시 만들어 그것에서 문턱을 읽었다. 값은 합친 표도 지지하는 둥근 값이다. 확인 저위도 원뿔에서는 모호 행 개수 말고는 읽지 않았다."
* **결론**: 확인 17개 필드는 "거의 독립"이다. 합친 표가 같은 값을 지지한다는 것이 두 번째 근거이지만, 완전히 독립이라고는 못 한다. 그 뒤 확인 세트로 한 결정(`best` 기각, `profiles`를 SDSS 밝은 점광원·VLASS·LoTSS로 줄이기)은 확인 세트를 다시 썼다. 결정표의 이력 열에 이것을 적었다.

### 3.2 질문 (2): "틀린 연결 0"의 분모, 상한, 정의

`benchmark/association_ambiguity/results_2026-11-27f/confirmation/cosmos/exchange.csv`(확인 17개 필드):

| 카탈로그 | 새로 붙은 연결 | 정답 | **틀림** | 모름 | Wilson 95 % 상한(틀림 0 / 정답이 알려진 수) |
|---|---|---|---|---|---|
| AllWISE | 46 | 46 | 0 | 0 | 7.7 % (0/46) |
| 2MASS PSC | 3 | 2 | 0 | 1 | (0/2, 의미 없음) |
| GALEX AIS | 49 | 37 | 0 | 8 | 9.4 % (0/37) |
| 합계 | 98 | 85 | **0** | 9 | **4.3 % (0/85)** |

* **분모**: 변형이 늘린 연결 98개 중 정답이 알려진 85개. 모름 9개를 전부 틀린 것으로 세는 최악의 경우는 9/98 = 9.2 %(Wilson 95 % 4.9–16.5 %).
* **정의**: 정답 판정(correct / false / unknown)은 `association_truth/measure_association.py`의 것과 같다. 2.61.0·2.60.9 보고서의 "거짓 연관율"은 `false / (correct + false)`를 **조인된 전체 행**에서 센 값이다(확인 17개 필드 기준 AllWISE 85/4837 = 1.76 %, GALEX 80/1125 = 7.1 %; 26개 전체로는 AllWISE 2.08 %, GALEX 6.23 %). "틀린 연결 0"은 같은 판정을 **새로 늘어난 행만**에 적용한 **한계(증분) 비율**이라 다른 양이다.
* **의미**: 증분 비율의 상한(AllWISE 7.7 %)은 기존 연결 전체의 거짓율(1.76 %)보다 크다. 0/46은 기존 거짓율과 모순되지 않는다(기존 거짓율이면 0건일 확률이 0.45). GALEX는 0/37이고 기존 6.8 %면 0건일 확률이 0.073이라 새 연결이 평균보다 깨끗했을 가능성이 있지만 5 %에서 유의하지는 않다. 2.61.8 보고서의 채택 기준 "틀린 연결이 연결의 1 % 이하"는 점추정(0)으로 통과했지 **통계적으로 확인된 것이 아니다**(상한 4.3 % > 1 %). 이 문장은 이 보고서가 정정한다.

### 3.3 질문 (3): 깨진 COSMOS 라벨

위치로 짝지은 객체 중 깨진 것은 **보정 3개, 확인 5개**(`results_2026-11-27h/broken.csv`에 진실 위치 3″ 안의 모든 객체를 두 실행에 대해 적었다). 확인 5개:

| 필드 | 진실 | 기준에서 가장 가까운 객체 | 변형에서 가장 가까운 객체 | 변형에 남은 GALAXY 객체 | 새로 붙은 조인 / 원인 |
|---|---|---|---|---|---|
| deep_cosmos_10 | GALAXY | SDSS 단독 GALAXY, 0.21″ | PS1 단독 UNKNOWN, 0.28″ | DESI+PS1+SDSS GALAXY, 0.35″ | DESI → PS1(`same`, 0.048″), SDSS → 그 객체. 합쳐진 객체의 앵커가 PS1 위치로 0.35″라, 다른 PS1 조각(0.28″)이 더 가깝다 |
| deep_cosmos_21 | GALAXY | DESI+은하동물원 GALAXY, 0.02″ | AllWISE+GALEX+은하동물원 UNKNOWN, 0.02″ | DESI+PS1+SDSS GALAXY, 0.13″ | DESI+SDSS → PS1(`same`). 은하동물원(DESI 영상에 붙인 주석) 행이 합쳐진 객체가 아니라 AllWISE+GALEX 객체에 붙었다(0.21″). 이 객체에는 광학 증거가 없다 |
| deep_cosmos_22 | GALAXY | DESI 단독 GALAXY, 0.05″ | SDSS 단독 UNKNOWN, 0.21″ | DESI+PS1 GALAXY, 0.30″ | DESI → PS1(0.25″). SDSS는 합쳐진 객체의 앵커에서 0.63″라 조각으로 남았다 |
| deep_cosmos_24 | GALAXY | DESI 단독 GALAXY, 0.04″ | PS1 단독 UNKNOWN, 0.21″ | AllWISE+DESI+SDSS GALAXY, 0.23″ | DESI·SDSS → AllWISE 객체. PS1(오차 0.037″)이 조각으로 남았다 |
| deep_cosmos_25 | GALAXY | SDSS 단독 GALAXY, 0.09″ | DESI+PS1 STAR, 0.10″ | DESI+GALEX+SDSS GALAXY, 0.10″ | SDSS → DESI 행, GALEX도. 기준에도 있던 STAR 객체(PS1 + 1.31″ 떨어진 DESI 행)와 0.10″ 동점. 이 STAR 객체는 변형이 만든 것이 아니다 |

* **공통점**: 5개 모두 같은 은하가 변형에서도 GALAXY 객체로 분류되어 있다(진실에서 0.10–0.35″). **라벨이 사라진 객체는 없다.** 가장 가까운 객체가 합쳐지지 않은 이웃 조각이 되었을 뿐이다.
* "어떤 새 조인이 어떤 규칙을 밀었는가": 분류 규칙(`classification_rules.csv`)은 바뀌지 않았다. 바뀐 것은 객체의 구성과 앵커 위치다. 합쳐진 객체의 앵커(첫 처리된 행의 위치)가 진실에서 조금 멀어지고, 합쳐지지 않은 이웃 조각 — 증거가 한 탐사의 한 행뿐이라 `NO_EVIDENCE`로 UNKNOWN인 — 이 더 가까워진다.
* 21번은 유일하게 연관 자체가 아쉬운 경우다: 은하동물원 행이 광학 객체 대신 AllWISE+GALEX 객체에 붙었다. 합쳐진 객체의 앵커가 PS1 행(오차 0.0016″, 쌍 바닥값 0.02″)이라 은하동물원 행과의 정규화 거리가 약 5(0.099″ ÷ 0.02″)인 반면 AllWISE 앵커는 0.21″ ÷ 0.5″ = 0.4라서 후자가 선택된 것으로 **추정**한다(후보 점수는 `V2_ASSOC_DIAG=1`로 확인하지 않았다). 이 문제는 과제 카의 PS1 오차 하한(0.02″)과 관련된다(보고서 i, 5절 한계).
* 반대 방향(20개 고침)도 같은 구조다: 가장 가까운 객체가 조각이었다가 합쳐진 객체로 바뀐다.

## 4. 결정표 (`results_2026-11-27h/decision_table.csv`)

모든 행은 `V2_POSERR_UNITS=legacy`, 기본값 외 스위치는 표에 적은 것만. `spectro_keep`은 분광 클래스 객체에만 작용하므로 블라인드 저위도·COSMOS 열은 `keep`이 없는 행과 같고, 분광 열이 둘을 가른다.

### 4.1 저위도 확인 140개 원뿔 (표본 퀘이사 143개)

| 행 | 표본 퀘이사 QSO | QSO 라벨 중 표본 퀘이사가 아닌 것 (deg⁻², 영역 부트스트랩, 개수) | LS가 있는 원뿔 | LS가 없는 원뿔 | 기준 대비 잃음 / 얻음 (위치로 짝지음) |
|---|---|---|---|---|---|
| base | 95/143 | 159 [90–242] (175) | 811 [409–1280] | 57 [42–73] | — |
| surveys2 | 95/143 | 74 [45–108] (81) | 335 [161–550] | 33 [22–44] | 94 / 0 |
| surveys3 | 95/143 | 32 [17–50] (35) | 134 [47–248] | 16 [8–23] | 140 / 0 |
| surveys2 + spectro_keep | 95/143 | 74 (81) | 335 | 33 | 94 / 0 |
| same,nearest | 96/143 | 156 [88–236] (171) | 791 [395–1260] | 56 [42–70] | 10 / 6 |
| same,nearest + surveys2 | 96/143 | 74 [45–108] (81) | 335 [161–550] | 33 [22–44] | 96 / 2 |
| same,nearest + surveys2 + spectro_keep | 96/143 | 74 (81) | 335 | 33 | 96 / 2 |
| same,nearest + surveys3 | 96/143 | 33 [18–51] (36) | 141 [60–255] | 16 [8–23] | 139 / 0 |

잃는 표본 퀘이사는 모든 행에서 0이다. 보정 169개 원뿔(퀘이사 150개): base 86 → 88(`same,nearest`), 거짓 QSO 170 → 93(`surveys2`) / 95(`same,nearest + surveys2`) / 43(`surveys3`) / 44(`same,nearest + surveys3`).

### 4.2 분광 클래스 QSO 32개가 막히는가 (`spectro_held.py`)

| 연관 | surveys2 | surveys3 | surveys2 + spectro_keep | surveys3 + spectro_keep |
|---|---|---|---|---|
| 기본 | **5/32** | **5/32** | 0/32 | 0/32 |
| same,nearest | **0/32** | **0/32** | 0/32 | 0/32 |

기본 연관에서 막힌 5개는 모두 탐사 수가 1인 조각(분광 행만 따로 객체)이었다. `same,nearest`가 그 행을 광학 객체에 붙여 탐사 수가 늘어난다.

### 4.3 깊은 COSMOS 26개 영역 (위도 한계를 푼 실행)

| 행 | Chandra type 1 QSO 라벨 (진실 327) | 잃음 | 후보 표시 22 ≤ r < 24 (라벨 QSO 또는 후보) | 라벨이 바뀐 객체 (위치로 짝지음) |
|---|---|---|---|---|
| base | 123 | — | 순도 0.365, 재현율 0.468 | — |
| surveys2 | 123 | **0/123** | 같음 | 36 / 253 811 (전부 QSO → UNKNOWN) |
| surveys3 | 123 | 0/123 | 같음 | 51 (전부 QSO → UNKNOWN) |
| same,nearest | 124 | 0/123 | 같음 | 165 (0.065 %, QSO에서 1) |
| same,nearest + surveys2 | 124 | 0/123 | 같음 | 198 (QSO에서 34) |
| same,nearest + surveys3 | 124 | 0/123 | 같음 | 214 (QSO에서 50) |

막힌 QSO 라벨 36개(`surveys2`)는 전부 탐사 수 1(LS 단독 또는 AllWISE 단독)이고 Chandra type 1이 아니다. 진실 별·은하·type 2 중 QSO로 표시된 것은 기준에서 7·14개가 `surveys2`로 5·13, `surveys3`로 3·12가 된다(`inputs/false_removed.csv`).

### 4.4 실사용 3개 영역 (NGC 4522, COSMOS, 은하면; 위도 한계를 푼 실행)

* 객체 수: 603 / 3570 / 597(기준) → `same,nearest`에서 601 / 3568 / 596. 라벨이 바뀐 객체는 `same,nearest` 단독에서 1개(UNKNOWN → GALAXY).
* **COSMOS 영역의 QSO 라벨 16개는 전부 NED·SIMBAD에만 있는 객체**(`catalogs` = `NED` 또는 `NED|SIMBAD`, 탐사 행 0개, 문헌 규칙이 만든 QSO)이고, `surveys2/3`는 `same,nearest`와 함께든 아니든 **16개를 전부** UNKNOWN(LOW_CONFIDENCE, "탐사 0개, 2개 필요")으로 막는다. 어댑터(`ANNOTATION` 집합)가 NED·SIMBAD를 탐사로 세지 않기 때문이다. 5개는 1.2–2.3″ 안에 광학 행이 있는 객체가 따로 있고 그 객체는 GALAXY이다.
* 해석: 실제 저위도 사용에서 SIMBAD·NED가 QSO라고 하는 천체가 광학·적외선 객체에 합쳐지지 않고 따로 남으면 같은 일이 생긴다. 이것은 분광 규칙이 아니라서 `spectro_keep`이 막지 못하고, 기본값 변경을 판단할 때 별도 비용이다(대응 후보: 문헌 라벨 예외 스위치, 또는 NED·SIMBAD 행이 광학 객체에 붙도록 하는 연관 개선 — 이번 과제에서 만들지 않았다).

### 4.5 연관 지표 (COSMOS2020 진실, 세 카탈로그, 보정 9 / 확인 17개 필드)

| 연관 | AllWISE 거짓 % / 놓침 % | GALEX 거짓 % / 놓침 % | 추가 조각 객체 |
|---|---|---|---|
| 기본 | 2.69 / 41.7 · 1.76 / 41.1 | 4.99 / 93.8 · 7.11 / 88.4 | 867 · 1493 |
| same,nearest | 2.67 / 40.7 · 1.74 / 39.9 | 4.76 / 93.3 · 6.83 / 87.4 | 817 · 1393 |

(보정 · 확인.) 탐사 수 스위치는 1단계 뒤에 작용하므로 연관 지표를 바꾸지 않는다.

### 4.6 고위도 벤치마크는 1단계를 거치는가

거치지 않는다. `benchmark/catalog_features/*.gz`(SDSS 하늘·DESI·ground_truth)는 진실 객체마다 카탈로그별로 따로 모은 행이고 `evaluate_rule_baseline.py`·`validate_catalog_truth.py`·`fit_fusion_weights.py`에 1단계 호출이 없다. 연관 변형의 영향은 이 벤치마크에 나타나지 않으므로 깊은 COSMOS 26개와 실사용 3개 영역으로 보았다(탐사 수 스위치의 이 벤치마크 비용은 `benchmark_cost.py`가 카탈로그 존재만으로 센다, 2.61.5).

## 5. 정정 상세

* 2.61.8 보고서 §6.2의 고침 / 깨짐은 r 등급이 없는 객체(확인 132, 보정 103)를 빠뜨렸다. 모두 세면:

| | 짝지은 객체 | r 등급 없음 | 고침 | 깨짐 | McNemar p | 0.5″ 안 기대 클래스(고침 / 깨짐) | 0.5″ 안 객체 수(기준 → 변형) |
|---|---|---|---|---|---|---|---|
| 보정 1–9 | 26 046 | 103 | 14 | 3 | 0.013 | 1 / 1 | 0.983 → 0.972 |
| 확인 10–26 | 30 609 | 132 | **20** | **5** | **0.0041** | 0 / 1 | 0.985 → 0.974 |
| 26개 전체 | 56 655 | 235 | 34 | 8 | 7×10⁻⁵ | 1 / 2 | 0.984 → 0.973 |

* r 등급이 있는 객체만으로는 확인 2 / 3이고 없는 132개에서 18 / 2가 더 나온다: 조각 정리의 이득은 한 탐사에서만 보이는 객체에서 크다.
* 정정은 `WORK_REPORT_2026-11-27f.md` §6.2 아래 주석과 7절 표에 달았다. CHANGELOG 2.61.8 행은 병합된 기록이라 고치지 않고, 새 행(2.61.10)이 정정을 적는다. `best`·`all`·`profiles`는 입력이 지워져 다시 세지 못했다.

## 6. 오류와 고친 것 (내가 낸 오류 포함)

1. **실행 중 코드를 고쳐 기준과 변형이 다른 코드로 돌았다**. 백그라운드 체인(`same,nearest+surveys2/3`)이 도는 중에 과제 카의 단위 수정을 `association_model.py`에 넣었다(22:43:52). 그 뒤에 시작한 구역(`a_same_nearest_surveys3`, `c_same_nearest_surveys3` 전부, `c_same_nearest_surveys2` 끝 약 19개)이 새 코드를 썼다. 파일 수정 시각과 구역 완료 시각을 비교해 발견했고, 체인을 멈춰 오염된 결과를 지운 뒤 `V2_POSERR_UNITS=legacy`로 모두 다시 돌렸다. 이후 `faint_cost.py`의 새 변형 3개에도 `legacy`를 넣었다.
2. **정정 위의 오류**(5절): 내 2.61.8 보고의 고침 / 깨짐.
3. **`label_changes.py` 결함**: 두 필드가 쌍을 못 짓는 객체 수가 다르면 `pd.concat`이 `attrs`의 numpy 배열을 비교하다 죽는다(`surveys2`로 처음 만남). 배열을 `attrs`에서 꺼내도록 고쳤고 회귀 시험을 추가했다.
4. VizieR ReadMe(단위 확인용)는 이 환경에서 읽을 수 없었다(`cdsarc` DNS/502). 이는 과제 카의 근거 수준에 영향을 준다(보고서 i).

## 7. 한계

* **분광 32개**: 점추정 0/32이지만 Wilson 상한 10.7 %이고, `spectro_keep`을 만든 객체 그대로라 독립 확인이 아니다.
* 저위도 표본 퀘이사는 PS1 + AllWISE로 뽑은 것이라 재현율은 상한이다(2.61.2). 거짓 QSO는 "표본 퀘이사가 아닌 QSO 라벨"의 수이지 거짓으로 확인된 수가 아니다(LS 영역 14개 밖에서는 판정 불가).
* 깊은 COSMOS의 진실 type 1은 Chandra X선으로 고른 것이라 X선에 안 보이는 퀘이사는 놓친다. 막힌 QSO 라벨 36개가 진짜 퀘이사인지는 이 진실로 모른다(type 1이 아닌 것만 안다).
* 실사용 3개 영역은 위도 한계를 인위적으로 풀어 돌렸다(COSMOS는 |b| = 42°).
* 세트 C(미사용 표본)로 돌리지 않았다. 문턱·스위치를 고른 모든 표본은 이력 열에 적었다.
* `profiles` 단독 효과, `best`·`all`의 정답 라벨 재집계는 하지 못했다.

## 8. 시험과 재현

시험: `Preprocess/tests/test_position_error_tools.py`(차 쪽: `compare`·`recount`·`decision_table_combos.held`·`label_changes` 회귀), 전체 `python -m pytest -q Preprocess/tests Classifier/tests app/tests` 통과.

```
# 저위도 (한 세트마다)
python benchmark/lowlat_qso/combos_table.py --variants base=ROOT surveys2=ROOT surveys3=ROOT same_nearest=ROOT same_nearest_surveys2=ROOT same_nearest_surveys3=ROOT \
    --regions benchmark/lowlat_qso/fields_lowlat_confirm.csv --truth benchmark/lowlat_qso/lowlat_truth.csv.gz --out inputs/lowlat_confirmation.csv
# 깊은 COSMOS
python benchmark/lowlat_qso/faint_cost.py classify --deep DIR --fields-file fields_all26.csv --variants same_nearest_surveys2,same_nearest_surveys3
python benchmark/lowlat_qso/faint_cost.py tables  --deep DIR --fields-file fields_all26.csv --variants base,surveys2,surveys3,same_nearest,same_nearest_surveys2,same_nearest_surveys3 --out OUT
# 고침 / 깨짐
python benchmark/association_ambiguity/recount_fixed_broken.py --deep DIR9 DIR17 --names calibration confirmation --fields fields_all26.csv --out OUT
# 조립
python benchmark/lowlat_qso/decision_table_combos.py --inputs benchmark/lowlat_qso/results_2026-11-27h/inputs --assoc benchmark/association_ambiguity/results_2026-11-27f --out decision_table.csv
```

## 병합 전 검토 (2.62.2로 병합)

- **판 번호**: 2.61.10 후보를 과제 카와 함께 2.62.2(PATCH)로 병합했다. 작업 가지가 main의 2.61.8·2.62.0·2.62.1 squash 병합을 받지 않은 상태였으므로, 이 두 과제의 변경(e1f9f3c..920939f)만 main 위에 얹었다. 충돌은 CHANGELOG·VERSION뿐이었다.
- **`legacy` 재실행의 확인**: 6절 1의 오염(실행 중 카 수정이 들어감)은 파일 수정 시각과 구역 완료 시각으로 찾았다. 결과 파일(`results_2026-11-27h/`)에는 실행마다 단위 모드(`V2_POSERR_UNITS`)나 실행 시각이 기록되어 있지 않다. 그래서 "모든 행이 `legacy`로 돌았다"는 이 보고서의 진술로만 확인된다. 다시 돌린다면 결과 파일에 환경 변수와 코드 커밋을 함께 적는 것을 권한다.
- **고침·깨짐 수의 읽기**: 이 보고서는 정정한 수(확인 17개 필드 20 / 5, 26개 34 / 8)를 라벨 정확도의 이득으로 쓰지 않는다. 3.3절의 공통점("라벨이 사라진 객체는 없다", 반대 방향도 같은 구조)과 0.5″ 읽기(1 / 2)가 그 해석을 막는다. 이득은 **정답 천체의 증거가 한 객체에 모이는 것**이다.
- **같은 산물이 과거 수치에 있을 가능성**(평가만, 다시 재지 않음): 깊은 COSMOS의 고침/깨짐 표(`faint_qso_candidates.py`; `match`가 정답마다 `MATCH_ARCSEC` 안의 최근접 객체 하나를 고름)는 2.60.11·2.61.0의 조각·순서 변형에도 쓰였다. 그래서 그 수치도 "정답 위치에서 가장 가까운 객체"로 채점되었다. 조각을 합치거나 순서를 바꾸는 변형에서는 같은 산물이 들어 있을 수 있다.
  - 깊은 COSMOS의 m15hc(+11 / −1)처럼 조각이 줄어드는 변형은 이 보고서의 same,nearest와 같은 방향의 산물(합쳐진 객체가 최근접이 됨)을 이득으로 셌을 가능성이 있다.
  - 세트 B의 2.61.0 순서 변화 1건(bngp_162p01)은 같은 객체(`OBJ005408`)의 라벨이 바뀐 경우라 이 산물이 아니다.
  - 과거 수치를 0.5″ 기대 클래스 읽기로 다시 세는 것은 다음 과제 후보다.

