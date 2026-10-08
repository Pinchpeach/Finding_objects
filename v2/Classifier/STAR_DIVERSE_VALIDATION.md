# STAR classifier 확대 독립 검증 보고서

검증일: 2026-09-27. **외부 검증 실행은 성공했지만, 사전 정의한 안정성 기준은 통과하지 못했다. WD subtype 확장은 보류한다.**

## 1. 실제 실행과 모델 동일성

- [성공한 GitHub Actions 실행 36306280498](https://github.com/Pinchpeach/Finding_objects/actions/runs/36306280498)
- 실행 코드: `ef6635dc0a02576a9224a1db7ec5099b8b3aa9e4`
- [기존 분류 라우팅 테스트도 성공](https://github.com/Pinchpeach/Finding_objects/actions/runs/36306280471)
- 원래 실행 `36295747956`의 **저장된 모델 자체**를 사용했다. 재학습·재보정·외부 데이터에 따른 threshold 변경은 없다.
- 원래 SDSS test에서 **183/194 정답, accuracy 94.33%, WD recall 95/103 = 92.23%**를 다시 재현했다.
- 모델 입력은 원래의 Gaia 관측량·파생량·missing indicator 31개다. 분광 라벨, 좌표, Gaia ID, 표본 출처는 입력에 포함하지 않았다. 결측 관측량은 NaN으로 유지했다.
- 누출 방지, NaN 유지, source ID 중복 및 정답 충돌 처리에 대한 테스트 4개가 로컬과 Actions에서 통과했다.

## 2. 더 크고 다양한 독립 표본

이전 LAMOST 검증은 DA 전용 table6와 카탈로그 앞부분에서 선택한 일반 별을 사용했다. 이번에는 [Guo et al. (2022)](https://arxiv.org/abs/2111.04939)의 table3에서 정확한 DA/DB/DC/DQ/DZ/DO 라벨을 가진 천체를 수집했다. 일반 별은 LAMOST DR5에서 O/B/A/F/G/K/M 계열과 RA 4개 구역을 조합하여 후보를 수집한 뒤 고정 SHA256 순서로 선택했다.

원래 SDSS train/calibration/test 전체, 이전 LAMOST 외부 검증셋, 이전 DA/DB 실험셋과 2 arcsec 이내의 좌표 중복을 먼저 제외했다. Gaia 매칭 후에는 같은 source ID 중복도 제거했다. 이름이 다른 중복 관측이 실제로 발견돼 source ID 검사가 필요함을 확인했다.

| 단계 | 천체/행 수 |
|---|---:|
| 선택한 분광 truth | 4,577 |
| WD / 일반 별 truth | 2,121 / 2,456 |
| Gaia 2 arcsec 매칭 | 4,363 (95.32%) |
| 추가 발견된 기존 참조셋 Gaia ID 중복 | 0 |
| 충돌하는 binary truth 라벨 | 0 |
| 같은 Gaia ID 중복 행 제거 | 56 |
| 최종 독립 평가 천체 | **4,307** |
| 최종 WD / 일반 별 | **1,971 / 2,336** |

4,577개 중 최종 평가 비율은 94.10%다. 이 비율은 분류 정확도가 아니다. 기존 원래 SDSS Gaia 표에서도 source ID 중복은 0개임을 별도로 확인했다.

## 3. 고정 모델과 기존 HR 기준 비교

괄호는 표본 내 Wilson 95% 신뢰구간이다. Confusion matrix 행은 실제 NORMAL_STAR, WHITE_DWARF이며 열은 예측 NORMAL_STAR, WHITE_DWARF다.

| 지표 | 기존 저장 모델 | 기존 Gaia HR 기준 |
|---|---:|---:|
| Accuracy | **96.22%** (95.60–96.75%) | **98.31%** (97.87–98.65%) |
| WD recall | **98.17%** (97.48–98.68%) | **98.07%** (97.36–98.59%) |
| WD precision | **93.84%** (92.72–94.80%) | **98.22%** (97.54–98.72%) |
| 일반 별 specificity | **94.56%** (93.57–95.41%) | **98.50%** (97.92–98.92%) |
| Confusion matrix | `[[2209,127],[36,1935]]` | `[[2301,35],[38,1933]]` |

저장 모델의 balanced accuracy는 96.37%, log loss는 0.10478, WD Brier score는 0.02829다. 기존 HR 기준은 `M_G > 6 + 5(BP-RP)`, parallax/error > 1이며 직접 적용 가능한 비율은 96.68%다. 원래 baseline 정의대로 조건에 필요한 관측이 없으면 전체 표본 평가에서 NORMAL_STAR로 처리했다. 따라서 HR 결과 역시 결측 WD 회수 능력을 따로 봐야 한다.

이번 표본에서 HR 기준은 모델보다 false positive가 92개 적고 WD를 2개 더 놓쳤다. 이는 보고할 비교 결과이며, 이 평가셋으로 새 모델·정책을 선택하거나 재보정하지 않았다. 원래 SDSS 94.33%, 이전 DA 중심 LAMOST 99.59%, 이번 96.22%는 서로 다른 표본에서의 수치이므로 모델 개선량으로 해석할 수 없다.

## 4. 전체 점수에 가려진 취약 구간

### WD subtype별 WD 탐지 recall

아래는 subtype을 예측한 정확도가 아니라, 해당 subtype의 **WD 여부 탐지율**이다.

| 분광 subtype | 평가 N | WD로 탐지 | Recall | 95% CI |
|---|---:|---:|---:|---:|
| DA | 1,866 | 1,836 | 98.39% | 97.71–98.87% |
| DB | 14 | 14 | 100.00% | 78.47–100% |
| DC | 48 | 45 | 93.75% | 83.16–97.85% |
| DQ | 16 | 14 | 87.50% | 63.98–96.50% |
| DZ | 25 | 24 | 96.00% | 80.46–99.29% |
| DO | 2 | 2 | 100.00% | 34.24–100% |
| **non-DA 합계** | **105** | **99** | **94.29%** | **88.09–97.36%** |

DB/DO의 100%는 표본이 작아 안정성을 증명하지 못한다. non-DA는 매칭 전 123개에서 최종 105개로 감소했다. DB가 적은 이유 중 하나는 이미 검사한 DA/DB 실험셋을 독립성 확보를 위해 제외했기 때문이다.

### 일반 별과 결측 구간

| 구간 | 결과 |
|---|---|
| O로 표기된 일반 별 | 53개 중 **50개를 WD로 예측**; specificity 5.66% (1.94–15.37%) |
| B로 표기된 일반 별 | 367개 중 **69개를 WD로 예측**; specificity 81.20% (76.89–84.87%) |
| A로 표기된 일반 별 | 347개 중 8개를 WD로 예측 |
| F/G/K/M 표기군 | 총 1,569개에서 WD false positive 0개 |
| feature 결측이 하나 이상인 WD | **4/11 탐지**, recall 36.36% (15.17–64.62%) |
| G < 16인 WD | **110/125 탐지**, recall 88.00% (81.14–92.59%) |
| G >= 20인 WD | 3개 중 0개 탐지; 매우 작은 표본 |

일반 별 false positive 127개 중 119개가 O/B 표기군에 집중된다. HR 기준도 B 23개, O 12개를 WD로 분류했다. 일반 별 정답은 LAMOST 파이프라인 분광 라벨이므로, 이 불일치에는 실제 분류 오류와 라벨 오염이 함께 있을 수 있다. 독립적인 spectrum 검토 없이 실제 물리적 O/B 별을 모두 오분류했다고 단정하지 않는다. 모델이나 HR 결과에 맞춰 라벨을 바꾸거나 해당 행을 제외하지 않았다.

## 5. 사전 기준과 결정

[예측 전에 저장한 protocol](STAR_DIVERSE_PROTOCOL.md)은 다음을 요구했다.

1. 전체 WD recall의 95% 하한 >= 90%: **97.48%, 통과**.
2. 전체 일반 별 specificity의 95% 하한 >= 90%: **93.57%, 통과**.
3. non-DA >= 100개, WD recall의 95% 하한 >= 90%: **105개, 88.09%, 미통과**.

따라서 **안정성 gate는 실패**했다. Workflow의 success는 데이터 수집·검증·보고 코드가 정상 실행됐다는 의미이며 과학적 기준 통과를 뜻하지 않는다. O/B 및 결측 구간의 취약성도 추가적인 보류 근거다.

이번 작업에서는 WD subtype 분류기 확장이나 production 활성화를 하지 않는다. 기존 저장소의 DA/DB XP 시범 결과를 여섯 subtype의 검증 완료로 확대 해석하지 않는다. 현재 `spectral_type=UNRESOLVED` 경계를 유지한다. XP 기반 세부분류는 문헌상 타당한 다음 방향이지만, 별도 정답셋과 외부 검증이 필요하다. [Vincent et al.](https://arxiv.org/abs/2308.05572), [García-Zamora et al. (2025)](https://arxiv.org/abs/2505.05560).

다음 검증의 우선순위는 (a) O/B 불일치에 대한 독립 분광 라벨 검토, (b) 희귀 non-DA와 결측/낮은 parallax SNR 표본 보강, (c) 이 결과를 이용해 모델을 수정한다면 새로 봉인한 독립 test를 확보하는 것이다. 이번 표본으로 수정한 모델을 다시 평가해 외부 일반화 성능이 개선됐다고 주장해서는 안 된다.

## 6. 남아 있는 한계

- 28개 일반 별 조회 중 **22개가 후보 2,000행 제한**에 도달했다. 구역·계열별 선택은 집중을 줄였지만 카탈로그 순서 편향을 없애지 못했다. O 계열은 56개만 확보됐다.
- 독립 천체·독립 분광 survey라는 의미의 검증이다. 원래 LAMOST targeting과 WD 후보 선정의 색/분광 편향은 남는다. 전천의 무작위·완전 표본이 아니다.
- pure label만 포함했으므로 혼합형, 자기장 WD, WD+MS 및 다른 stellar contaminants는 충분히 검증하지 않았다.
- 2 arcsec 최근접 매칭은 proper-motion epoch propagation이나 다중 후보 확률을 사용하지 않는다. 중복 source ID 제거가 오매칭 자체까지 증명해 주지는 않는다. 고유운동이 크거나 혼잡한 천체의 누락 가능성이 있다.
- 미매칭 214행과 중복 56행은 성능 분모에서 빠진다. 성능은 최종 Gaia 매칭 표본에 조건부다. [계열별 coverage](star_diverse_validation/coverage_by_stratum.csv)를 함께 봐야 한다.
- Precision은 이 인위적인 클래스 비율에 의존한다. Wilson 구간은 표본 내 이항 불확실성으로, 라벨 오류·하늘 영역 상관·survey selection systematic을 반영하지 않는다.
- 알려진 stellar truth에 대한 binary classifier 평가다. `Preprocess -> STAR routing`의 end-to-end completeness나 galaxy/QSO 오염은 검증하지 않았다.

## 7. 재현 자료

[고정 truth](star_diverse_validation/truth.csv), [행별 예측](star_diverse_validation/predictions.csv), [제외한 매칭](star_diverse_validation/rejected_matches.csv), [전체 지표](star_diverse_validation/metrics.json), [선정 감사 기록](star_diverse_validation/selection_audit.json)을 저장소에 보존했다. 결과 숫자는 Actions artifact에서 복사한 원본에 근거한다.

전체 raw 조회 응답·Gaia 입력·기존 frozen 모델·예측은 위 성공 실행의 `star-diverse-frozen-validation` artifact에 있다. 다운로드한 ZIP의 SHA256도 GitHub artifact digest와 일치함을 확인했다. 원본 전체 ZIP은 작업 폴더 `results/star-diverse-validation.zip`에도 보존했다. 원본 모델 artifact는 2026-10-27, 이번 전체 artifact는 2026-12-26에 만료 예정이므로 이후 재현에는 보관한 ZIP을 사용해야 한다.

| 대상 | SHA256 |
|---|---|
| 원래 frozen 모델 | `22ae268a6525fc9fafbd6cff048c96512f235e75f998bdc63354610f518a9d5c` |
| 이번 truth.csv | `b152ca23a4fc1ffeb35231c5e554d66dccbb7e055eb4898368936023f4439fa0` |
| 전체 workflow ZIP | `3d8455f7e1e5d9468580556da423efb56040702eda550fda665abdad37132148` |

실행 환경은 Python 3.11.16, scikit-learn 1.9.1, NumPy 2.4.6, pandas 3.0.6이다. 실제 평가 코드는 `evaluate_star_diverse.py`, 수집 코드는 `build_star_diverse_truth.py`, workflow는 `.github/workflows/validate-star-diverse.yml`이다.
