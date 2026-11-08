# 비슷한 역할의 파이프라인과 비교 (2026-11-08)

사용자 요청: 비슷한 역할을 하는 파이프라인을 문헌·git 저장소에서 찾아 우리와 비교하고, 나은 점은 설계를 살펴 적용·실험한 뒤 유의미한 개선이면 선정 이유를 밝힌다.

## 1. 찾은 파이프라인

우리 파이프라인이 하는 일은 두 단계다.
- (가) 여러 파장 목록의 행을 한 천체로 묶는다(연관).
- (나) 묶인 근거로 별·은하·QSO와 세부 종류를 정한다(분류).

비슷한 일을 하는 공개 파이프라인:

| 파이프라인 | 하는 일 | 공개 코드 | 우리와 겹치는 단계 |
|---|---|---|---|
| **NWAY** (Salvato et al. 2018, MNRAS 473, 4937) | 여러 목록 동시 교차 일치. 위치 베이즈 인자 × 등급·색 사전확률, "짝 없음" 확률(p_any) | github JohannesBuchner/nway (PyPI `nway` 4.8.0, 원본 코드를 받아 읽음) | (가) |
| **MUWCLASS** (Yang et al. 2022, ApJ 941, 104; 4FGL판 2024) | Chandra 원천의 다파장 짝 찾기 + 랜덤 포레스트 8종류 분류 | github huiyang-astro/MUWCLASS_CSCv2, MUWCLASS/MUWCLASS | (가)+(나), X선 원천 한정 |
| **Tranin et al. 2022** (A&A 657, A138) | Swift·XMM 원천: NWAY로 짝 찾기 → 수정 나이브 베이즈(AGN·별·XRB·CV + 이상치) | (코드 비공개, CLAXSON 시민과학) | (가)+(나), X선 원천 |
| **Clarke et al. 2020** (A&A 639, A84) | SDSS ugriz + WISE W1–W4 + 퍼짐 정도(psf−model)로 랜덤 포레스트, 1.1억 개 분류 | github informationcake/SDSS-ML | (나), 별·은하·QSO |
| **Hughes, Bailer-Jones & Jamal 2022** (A&A 668, A99) | Gaia EDR3 + CatWISE2020, XGBoost/CatBoost·GMM, 사전확률 조정 | – | (나), 별·은하·QSO |
| **Gaia DR3 DSC** (Delchambre et al. 2023) | Gaia 저분산 분광·천체측정 분류기 결합(Combmod) | Gaia 목록 열 | (나) |
| **Logan & Fotopoulou 2020** (A&A 633, A154) | KiDS+VIKING+AllWISE 색 공간 HDBSCAN(비지도) | – | (나) |
| **ALeRCE 광도곡선 분류기** (Sánchez-Sáez et al. 2021) | ZTF 경보: 계층적 균형 랜덤 포레스트(주기·확률·과도 → 15종류) | github alercebroker/lc_classifier | (나) 변광성 세부 |

## 2. 설계 비교

| 항목 | 우리 (2.47.0) | 다른 파이프라인에서 나은 점 |
|---|---|---|
| 연관 확률 | 위치 가능도 + 배경 밀도 사후확률(Budavári & Szalay 2008), 순차 배정, 모호 비율 0.67 | **NWAY: 위치 베이즈 인자에 등급·색 사전확률을 곱한다**(secure 짝의 분포 ÷ 배경 분포). 우리는 위치만 쓴다 |
| 거짓 연관률 | 고정 문턱(score ≥ 1e-5, p_chance ≤ 0.25) | NWAY: 위치를 옮긴 목록으로 거짓 짝 비율을 재서 p_any 문턱을 정한다 |
| 분류 모형 | 규칙 근거 + 융합 GBM(벤치마크 학습) + 하늘 사전확률 | Clarke·Hughes: 같은 분포의 분광 정답으로 직접 학습한 단일 모형 |
| 기권(UNKNOWN) | 근거가 없거나 확률이 겹치면 UNKNOWN | MUWCLASS·Clarke·Hughes는 항상 한 종류를 내고 확률로 신뢰도를 표시 |
| 세부 종류 | 축별 규칙 + 하위 분류 | ALeRCE: 계층적 균형 RF. Tranin: 나이브 베이즈 + 이상치 종류 |
| 다파장 범위 | 전파~X선 30여 목록, 문헌 목록 주석 | 대부분 한두 대역 묶음(광학+IR, X선+광학) |

## 3. 실험 1: 다른 설계를 우리 정답으로 다시 학습해 비교

- 방법: 세트 A(200개 독립 영역)의 정답으로 학습하고, 세트 B(다른 200개 영역)에서 우리 결과와 같은 천체끼리 비교했다(blind, 벤치마크 천체 제외).
- 코드: `benchmark/compare_literature_designs.py`.

| 설계 | 비교 천체 | 그 설계 | 우리 | 그 설계만 맞음 | 우리만 맞음 |
|---|---|---|---|---|---|
| Clarke+2020 RF (SDSS ugriz + WISE + psf−model) | 3,788 | **99.31 %** | 99.21 % | 20 | 16 |
| Clarke+2020 설계, PS1 grizy + WISE + psf−Kron | 7,827 | 99.46 % | **99.57 %** | 19 | 27 |
| Hughes+2022 부스팅 (Gaia + WISE) | 9,280 | 99.61 % | **99.70 %** | 10 | 18 |
| Gaia DR3 DSC-Combmod | 9,268 | 98.30 % | **99.71 %** | 12 | 143 |
| LS 측광만 ML (Chaussidon+2023식) | 4,920 | 98.72 % | **99.23 %** | 11 | 36 |
| LS 형태 + WISE W1−W2 ≥ 0.8 (Stern+2012) | 5,372 | 99.03 % | **99.29 %** | 20 | 34 |

종류별 재현율(설계 / 우리):
- Clarke SDSS: 은하 98.8 / 97.9, QSO 88.1 / 94.9.
- Hughes: 은하 98.0 / 97.4, QSO 89.0 / 96.7.

**읽는 법**
- 우리보다 나은 것은 Clarke SDSS판 하나뿐이고, 차이는 4개(3,788개 중)다.
- 다른 설계들이 이기는 곳은 두 군데다.
  - 우리가 UNKNOWN으로 둔 천체: SDSS판이 12개 모두 맞힘(대부분 밝은 별 조각).
  - 어두운 은하를 우리가 별로 부른 경우: 5–6개.
- 지는 곳은 주로 QSO다.

**이 차이를 우리에게 옮길 수 있나 (시험)**
- 같은 설계(PS1 grizy + psf−Kron + WISE, RF)를 세트 A가 아닌 SDSS 벤치마크 학습 분할로 학습했다(독립 검증을 지키기 위해).
- 우리 UNKNOWN에만 적용해 보았다.
- 결과:
  - 독립 영역 전체 정확도 73.9 %(A), 71.6 %(B).
  - UNKNOWN에서는 A 15개 중 7개, B 6개 중 4개만 맞혔다.
  - 영역의 종류 비율(별 82.6 %)로 사전확률을 고쳐도 74.0 % / 72.3 %였다.
- 결론: Clarke·Hughes의 우위는 특징이나 모형이 아니라 **같은 분포의 정답으로 학습한 데서** 온다(벤치마크는 r 15–22 SDSS 분광 표적, 영역 정답은 밝은 LAMOST 별이 많다).
  - 그 이점을 얻으려면 독립 영역 정답을 학습에 써야 하고, 그러면 독립 검증 세트를 잃는다.
  - **채택하지 않는다.**

## 4. 실험 2: NWAY 색 사전확률 (연관 단계)

**NWAY 설계 (원본 `nwaylib/magnitudeweights.py`를 읽고 확인)**
- secure 짝(사후확률 > 0.9)의 등급 분포 h_sel과 전체 분포 h_all을 secure 표본의 15개 분위로 나눈 칸에서 센다.
- 비율 h_sel/h_all을 배경 가중 평균이 1이 되게 정규화한다.
- 이 값을 위치 베이즈 인자에 곱한다.

**우리에게 옮긴 것 (`Preprocess/association_model.py`, 기본은 꺼짐: `V2_ASSOC_PHOT_PRIOR=1`)**
- 성질: 광학 앵커와의 색. AllWISE는 G − W1, 2MASS는 G − Ks.
- 표(`Preprocess/phot_prior.csv`, `benchmark/build_phot_prior.py`)는 세트 A blind 결과로 만들었다.
  - h_sel: 한 천체에 Gaia와 그 목록 행이 함께 있는 경우(AllWISE 128,552, 2MASS 137,329).
  - h_all: 6–30″ 떨어진 다른 천체의 G와 짝지은 우연한 쌍(373만, 1,125만).
- 표의 모양:
  - 진짜 WISE 짝은 G − W1이 1.5–4다(가중치 2.4–8.8).
  - 5.3보다 붉은 쌍은 가중치 0.13이다.
  - 2.47 검증의 J042925 경우(탄소별 WISE 원천이 4.8″ 떨어진 다른 Gaia 별에 붙음, G − W1 ≈ 11)가 이 칸이다.
- 가중치는 점수와 사후확률에 곱해진다. 곱한 점수가 수용 문턱(1e-5) 아래면 짝을 받지 않는다.

**시험 방법 (`.github/workflows/experiment-ab-fields.yml`, `benchmark/compare_ab_fields.py`)**
- 세트 B 26개 영역을 한 번만 수집하고, 같은 blind 원자료로 base와 phot를 각각 돌렸다.
- 정답 천체별로 고침과 깨짐을 비교했다.
- NWAY 방식대로 AllWISE·2MASS 위치를 2′ 옮긴 사본에서 받아들여진 짝 수(= 거짓 연관)도 세었다.

결과: (A/B 실행 결과로 채움)
