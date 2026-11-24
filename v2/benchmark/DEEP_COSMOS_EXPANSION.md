# 깊은 COSMOS 영역 확대 (2.59.0 준비): 어두운 QSO 후보 확인용 둘째 묶음

2.58.0의 후보 표시(`secondary_class = QSO`, `FAINT_QSO_CANDIDATE`)의 불확실성은 문턱이 아니라 **표본 크기**에서 온다. 시험 영역(짝수 deep_cosmos 4개)의 Chandra 1형이 21개뿐이라, 후보의 재현율 0.33(95 % 0.17–0.55)과 순도 0.21(0.10–0.37)이 넓다. 같은 하늘의 영역을 더 모아 같은 방식으로 재면 구간이 준다. 이 문서는 그 준비만 한다. **수집은 Gaia ESA 아카이브가 돌아온 뒤에 한다.** 지금 수집하면 Gaia가 VizieR 사본(24열 결손)이라 2.58.0의 기준 자료와 같지 않다.

## 1. 명단 (잠금)

- 파일: `v2/benchmark/deep_cosmos_fields_2.csv` (17개 영역, 반경 6′, `deep_cosmos_10`–`26`).
- 잠금: sha256: `94948fbc9cda04696dca5a952a2f0f913809756b43ad4f06b74e6d1ab0e66e79`
- 워크플로 `v2_deep_cosmos.yml`은 파일의 해시가 위 값과 다르면 멈춘다. 명단을 바꾸려면 이 문서의 해시를 같은 커밋에서 바꾸고, 바꾼 이유를 여기에 적는다(규칙을 바꾼 것이 아니라면 바꾸지 않는다).
- 만드는 규칙(`select_deep_cosmos_2.py` 문서에도 같음, 수집·분류 전에 고정):
  1. **격자:** COSMOS 중심(RA 150.12, Dec 2.21)을 기준으로 간격 0.21°(Dec), 0.21°/cos(Dec)(RA)의 정사각 격자, 색인 −5…+5(121점).
  2. **겹침 없음:** 기존 9개 영역(`measure_cosmos_xray_agn.FIELDS`) 중심에서 0.21°(= 12.6′ = 2 × 6′ + 0.6′) 안인 점은 버린다. 격자 점끼리는 0.21° 이상이다.
  3. **정답 범위:** 반경 5.75′(6′에서 측정의 가장자리 컷 0.25′를 뺀 원) 안의 Chandra COSMOS Legacy 원천이 기존 9개 원 중앙값(68)의 60 %(40.8) 이상. `--check`는 같은 비율을 **COSMOS2020 Classic** 개수(기존 중앙값 대비)와 **Legacy Surveys DR10** 개수에도 적용한다. 분류기 출력은 선정에 쓰지 않았다.
  4. **순서와 이름:** 기준 중심에서 가까운 순(그다음 RA), `deep_cosmos_10`부터.
  5. **분할:** 2.52.0의 번호 홀짝 규칙(홀수 = 보정, 짝수 = 시험).
- 결과(121점 중 Chandra 규칙 통과 17, 아카이브 개수 점검에서 0개 탈락): COSMOS2020 13,083–17,599개, LS DR10 7,184–9,075개로 모두 기존 중앙값(15,570, 8,201)의 60 % 이상. 보정 8개(홀수), 시험 9개(짝수).

| 이름 | RA | Dec | 분할 | Chandra | COSMOS2020 | LS DR10 |
|---|---|---|---|---|---|---|
| deep_cosmos_10 | 150.54021 | 1.79 | 시험 | 59 | 14,438 | 7,508 |
| deep_cosmos_11 | 149.69956 | 2.63 | 보정 | 59 | 14,123 | 7,517 |
| deep_cosmos_12 | 150.54044 | 2.63 | 시험 | 56 | 16,195 | 8,804 |
| deep_cosmos_13 | 149.48953 | 2.21 | 보정 | 45 | 16,348 | 8,275 |
| deep_cosmos_14 | 150.75047 | 2.21 | 시험 | 53 | 15,373 | 7,910 |
| deep_cosmos_15 | 150.12000 | 2.84 | 보정 | 57 | 17,151 | 7,659 |
| deep_cosmos_16 | 150.12000 | 1.58 | 시험 | 53 | 16,197 | 8,052 |
| deep_cosmos_17 | 149.48962 | 2.00 | 보정 | 56 | 15,258 | 8,201 |
| deep_cosmos_18 | 150.75038 | 2.00 | 시험 | 41 | 14,701 | 7,184 |
| deep_cosmos_19 | 149.90992 | 1.58 | 보정 | 57 | 15,465 | 7,928 |
| deep_cosmos_20 | 149.90974 | 2.84 | 시험 | 49 | 16,601 | 7,818 |
| deep_cosmos_21 | 150.33026 | 2.84 | 보정 | 44 | 17,599 | 8,377 |
| deep_cosmos_22 | 149.48944 | 2.42 | 시험 | 46 | 15,955 | 8,458 |
| deep_cosmos_23 | 150.75056 | 2.42 | 보정 | 44 | 15,570 | 9,075 |
| deep_cosmos_24 | 149.69984 | 1.58 | 시험 | 45 | 13,083 | 8,554 |
| deep_cosmos_25 | 150.54052 | 2.84 | 보정 | 65 | 16,147 | 8,723 |
| deep_cosmos_26 | 150.75066 | 2.63 | 시험 | 46 | 14,557 | 9,068 |

## 2. 기대 표본과 구간 폭

기존 9개 영역의 Chandra 1형(22 ≤ LS r < 24, 가장자리 컷 안)은 63개, 원 하나당 평균 7.0개(Chandra 원천 중앙값 68개일 때). 새 영역은 Chandra 원천이 41–65개라, 원마다 `7.0 × n_chandra / 68` ≈ 4.2–6.7개, **17개 합 약 90개**(시험 9개 영역 약 46개, 보정 8개 영역 약 44개)를 기대한다.

문턱 0.1에서 지금 시험 영역의 점추정치(재현율 7/21, 1형당 후보 1.62개, 순도 7/34)가 그대로라고 가정한 Wilson 95 % 구간(`1형 개수`는 기대값):

| 표본 | 1형 | 재현율 | 순도 |
|---|---|---|---|
| 지금: 짝수 4개 영역 | 21 | 0.33 (0.17–0.55), 반폭 0.187 | 0.21 (0.10–0.37), 반폭 0.133 |
| 새 영역 앞의 4개만 | 23 | 반폭 0.182 | 반폭 0.132 |
| 새 영역 앞의 8개만 | 45 | 반폭 0.133 | 반폭 0.091 |
| 새 영역 앞의 12개만 | 65 | 반폭 0.113 | 반폭 0.077 |
| **새 시험 9개(확인용)** | 46 | 0.33 (0.21–0.47), 반폭 0.131 | 0.20 (0.13–0.30), 반폭 0.089 |
| 새 시험 9개 + 기존 시험 4개 | 67 | 반폭 0.110 | 반폭 0.075 |
| **새 17개 전부(확인용)** | 90 | 0.33 (0.25–0.44), 반폭 0.096 | 0.21 (0.15–0.28), 반폭 0.065 |
| 26개 전부 합침 | 153 | 반폭 0.073 | 반폭 0.050 |

- **영역 4개로는 구간이 줄지 않는다**(표본 21 → 23). **8개부터** 순도 반폭이 0.133에서 0.091로 준다. 17개를 다 모으면 0.065, 26개를 합치면 0.050이다.
- 이 계산은 점추정치가 같다고 가정한다. 순도가 보정 영역(0.42)과 시험 영역(0.21)에서 달랐던 것이 우연인지는 새 영역으로 직접 본다.

## 3. 새 영역의 쓰임: 두 안과 권고

**안 A: 전부 확인용, 문턱 0.1 고정 (권고).**
- 문턱은 그대로 두고, 새 영역 17개에서 재현율과 순도를 "예측 대 관측"으로 본다(예측: 재현율 0.33, 순도 0.21).
- 장점: 모두 처음 보는 영역이라 편향 없는 확인이다. 문턱이 바뀌지 않아 동작이 안정적이고 세트 C 같은 별도 채점을 부르지 않는다. 문턱을 고른 보정 영역(1형 42개)의 잡음은 F1 곡선이 0.05–0.3에서 평평(0.42–0.44)해서 크게 문제되지 않는다.
- 단점: 문턱 선택 자체의 불확실성은 줄지 않는다. 새 영역의 결과가 예측과 어긋나면(예: 순도가 0.1 근처) 그때 안 B로 간다.

**안 B: 분할해서 다시 정함.**
- 홀짝 분할대로 보정 = 기존 5 + 새 8(1형 약 86), 시험 = 기존 4 + 새 9(약 67)로 문턱을 다시 정한다.
- 장점: 문턱 추정이 단단해지고 시험 구간이 줄어든다(반폭 0.075).
- 단점: 기존 시험 영역을 한 번 더 쓰는 두 번째 보기가 된다. 문턱이 바뀌면 기본 동작이 바뀌어 별도 보고가 필요하다. 새 영역이 "확인"이 아니라 "개발"이 되어, 독립 확인이 없다.

**권고:** 안 A로 확인하고, 결과가 예측 구간 안이면 26개를 합친 구간을 최종 수치로 낸다(문턱 재조정 없음). 구간 밖이면 안 B로 가되 그 사실을 보고서에 적는다. 이 단계에서는 문턱을 다시 정하지 않는다.

## 4. 수집·분석 절차 (Gaia ESA 복구 뒤)

1. **ESA 복구 확인.** `https://gea.esac.esa.int/tap-server/tap/availability`가 VOSI XML(`available` true)을 돌려주는지. 점검 중에는 HTTP 200으로 점검 안내 HTML이 온다. 워크플로가 같은 확인을 하고 멈춘다.
2. **수집(Actions).** main에 병합된 뒤 `workflow_dispatch`: 워크플로 `v2 deep COSMOS fields`(`.github/workflows/v2_deep_cosmos.yml`, 입력 `set` = `second`가 기본). 입력 `only`는 비워 둔다(일부만 하려면 영역 이름을 공백으로). 영역마다 `collect_deep_cosmos.py --fields-file … --require-gaia-tap`가 돌고, **Gaia 행이 VizieR 사본이면 그 영역은 실패**한다. 수집물은 `validation-data` 브랜치의 `deep_cosmos2/<실행 번호>/<영역>.tar.gz`(raw + COSMOS2020 정답 + field.json)에만 남고 main에는 두지 않는다.
   - GitHub MCP로: `actions_run_trigger`(workflow `v2_deep_cosmos.yml`, ref `main`).
   - **원래 9개 영역(2.60.1):** 같은 워크플로를 `set` = `first`로 돌리면 2.52.0–2.59.0의 9개 영역(`collect_deep_cosmos.FIELDS`)을 같은 방식(블라인드, ESA Gaia 확인, `--require-gaia-tap`)으로 받아 `validation-data`의 `deep_cosmos1/<실행 번호>/`에 남긴다. 명단 해시 확인만 빠진다(명단이 스크립트 안에 있음). 그동안 이 영역들은 잴 때마다 다시 수집해 그날 아카이브 상태에 따라 수치가 흔들렸다(2.58.0 검토).
3. **받기.** `git fetch --depth=1 --filter=blob:none origin validation-data`로 필요한 묶음만 받는다(`v2/benchmark/independent_fields/README.md`의 방식):
   ```
   git cat-file -p FETCH_HEAD:deep_cosmos2/<RUN>/deep_cosmos_10.tar.gz > deep_cosmos_10.tar.gz
   mkdir -p DIR/deep_cosmos_10 && tar -xzf deep_cosmos_10.tar.gz -C DIR/deep_cosmos_10     # 영역마다
   ```
4. **분류와 측정(로컬).**
   ```
   F=v2/benchmark/deep_cosmos_fields_2.csv
   python v2/benchmark/faint_qso_candidates.py classify --deep DIR --fields-file $F --variant base --jobs 3
   python v2/benchmark/faint_qso_candidates.py tables   --deep DIR --fields-file $F --variants base --out OUT
   python v2/benchmark/faint_qso_candidates.py census   --deep DIR --fields-file $F --variant base --out OUT
   python v2/benchmark/faint_qso_candidates.py highconf --deep DIR --fields-file $F --base base --variant base --out OUT   # 고신뢰 순도·완전도
   ```
   `tables`의 `union_base.csv`에서 문턱 0.1 행(시험·보정)을 예측(재현율 0.33, 순도 0.21)과 비교한다. 새 분류 코드(후보 표시 기본 켬)로 `base`를 돌려도 후보 열이 같은 규칙으로 붙는다.
5. **기존 9개 영역과 합치기.** 기존 영역의 raw와 새 영역의 raw를 한 `DIR`에 두고 `--fields-file`에 두 명단을 합친 파일을 쓰면 26개 합산이 나온다(합친 파일은 새로 만들고 그 해시를 보고서에 적는다).

## 5. 이 단계에서 하지 않은 것
- 수집, 분류, 문턱 변경, 세트 C 채점.
- Euclid Q1·4XMM 같은 다른 정답: 범위 밖.

## 6. 결과 (2026-11-24)
26개 영역이 ESA Gaia 기준으로 수집됐고(`validation-data/deep_cosmos2/45322742717/`, `deep_cosmos1/45325505343/`) 안 A대로 문턱 0.1 고정으로 확인 측정을 했다. 새 17개의 순도는 예측과 맞고(ACS 영상이 덮은 곳의 후보로 쟀을 때 0.253, 구간 0.17–0.35), 재현율은 예측보다 높다(0.526, 0.42–0.63). 문턱 선택에 안 쓴 21개 영역의 합은 재현율 0.484, 순도 0.244. 표·정의·원인 후보는 `WORK_REPORT_2026-11-24.md` 1단계, 수치 표는 `deep_cosmos_confirmation/`, 스크립트는 `qso_candidate_confirmation.py`.

### 6.1 후보 순도의 정의 (ACS 덮개, 고정)
- **후보 순도는 후보가 HST/ACS가 덮은 곳에 있을 때만 센다.** 분모 = ACS 안(가장 가까운 COSMOS2020 행이 1.0″(`MATCH_ARCSEC`, 정답 맞춤과 같은 반경) 안에서 `ACSF814Wmag`를 가짐)의 후보 중 정답 등급(Chandra 1형·2형, COSMOS2020 별·은하)이 있는 것, 분자 = 그중 Chandra 1형. 재현율은 Chandra 1형 정답만 쓰므로 ACS와 무관하다. 순도 범위는 같은 곳에서 정답 등급이 없는 후보를 모두 거짓 / 모두 참으로 센 값이다.
- **이유:** COSMOS2020의 별·은하 등급(`ACSmuClass`, `lptype`)은 ACS 영상이 있는 곳에만 있고 Chandra 1형은 영역 전체에 있다. 2.58.0의 정의(1형은 전체, 거짓 후보는 ACS 쪽만)는 영역이 ACS로 거의 덮일 때(원래 9개 평균 78 %)만 맞고, 바깥의 새 17개(평균 51 %)에서는 분모에서 정답 없는 후보가 빠져 **새 17개의 순도가 0.357로 부풀려진다**(ACS 안만 세면 0.253). 원래 9개에서는 두 정의가 같다(0.333 대 0.329).
- **재현되지 않는 2.58.0 수치:** 2.58.0 보고서의 "시험 후보 43개 중 정답 등급 없는 것 10개"는 저장된 2.58.0 분류 결과에 `qso_candidate_confirmation.py`를 돌려도 40개 중 7개(범위 17.5–35 %)로 나온다. 순도 7/34 = 21 % 자체는 정확히 재현된다.
- **표시 수치(앱 툴팁·README·ALGORITHM, 2.60.2):** 문턱 선택에 쓰지 않은 21개 영역 `all26_without_orig_cal`: 순도 29/119 = 24 %(Wilson 18–33 %), 재현율 47/97 = 48 %(39–58 %). 26개 전부(0.289)는 쓰지 않는다.
- **재현:** 4절 3의 방식으로 26개 영역 원자료를 `DIR/<영역>/`에 푼 뒤(원래 9개는 `deep_cosmos1/45325505343/`, 새 17개는 `deep_cosmos2/45322742717/`):
  ```
  F=v2/benchmark/deep_cosmos_confirmation/fields_all26.csv      # SHA-256 c00298015e91573e6095726316449733f2d29495e163a03ccdb77d77c3896100
  python v2/benchmark/faint_qso_candidates.py classify --deep DIR --fields-file $F --variant base --jobs 3
  python v2/benchmark/qso_candidate_confirmation.py --deep DIR --fields-file $F --out OUT --run base
  ```
  `OUT/groups_base.csv`의 `all26_without_orig_cal` 행(`tp_acs` 29, `graded_acs` 119, `type1_claimed` 47, `n_type1` 97)이 표시 수치이고 저장소의 `deep_cosmos_confirmation/groups_base.csv`와 같다.
