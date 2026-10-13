# Finding Objects v2 — 분류 알고리즘 설명

이 문서는 v2 분류기가 **하늘의 한 영역을 받아 각 천체를 무엇으로 판정하는지** 처음부터 끝까지 설명합니다. 각 단계의 근거 문헌은 `Preprocess/LITERATURE.md`, `Classifier/LITERATURE_*.md`, `LITERATURE_REVIEW_2026-10.md`에 있고, 버전별 측정치는 `CHANGELOG.md`에 있습니다. 숫자는 2.21.0 기준입니다.

## 0. 한눈에 보기

```
입력: (RA, Dec, 반경)  또는  이미 받은 카탈로그 폴더
 │
 ├─ 수집   26개 아카이브를 병렬 질의 (Gaia, SDSS, PS1, Legacy Surveys, WISE, 2MASS, GALEX,
 │         전파 5종, X선 3종, 분광 4종, ZTF, ATNF, Suh AGB, SGA, SIMBAD, NED) + 로컬 캐시
 ├─ 1 연관  같은 천체의 검출을 위치·시기·오차로 묶음 (고유운동 전파, 우도비, 우연 일치 확률)
 ├─ 2 통합  천체 하나 = 한 행, 카탈로그별 열 + 단위 통일(AB 등급, mJy, z)
 ├─ 3 특징  색, 형태, 신호대잡음, 품질 플래그
 ├─ 4 증거  규칙 25개(그중 학습 모델 3개: kNN 2, 그래디언트 부스팅 1)가 STAR/GALAXY/QSO 증거를 냄
 ├─ 5 1차   증거를 학습된 로지스틱 융합으로 합쳐 STAR / GALAXY / QSO / UNKNOWN
 ├─ 6 준비  분류기 입력 정리
 └─ 7 세부  세부 분류(분광형·활동성 등) + 독립 축 5개(물리 상태, 변광, 밀집성, 외부은하, 현상)
            + 축별 확신도 보정, 큰 은하 조각 묶기, 이름 붙이기, UNKNOWN 이유
출력: classified_objects.csv (앱은 표·하늘 지도·상세 패널로 표시)
```

설계 원칙 세 가지:
1. **증거는 출처별로 따로 냄**: 한 카탈로그의 판정을 그대로 믿지 않고 "이 카탈로그의 이 측정은 STAR 쪽으로 이만큼"이라는 증거로 바꾼 뒤 합칩니다.
2. **모르면 UNKNOWN**: 증거가 약하거나 서로 충돌하면 억지로 고르지 않고 기권하며, 그 이유를 기록합니다(`unknown_reason`).
3. **검증에서 분광은 정답으로만**: 벤치마크·현장 검증에서는 분광 분류를 정답으로만 쓰고 증거에서 뺍니다. 실제 실행에서는 그 자리의 분광 분류(SPC-SDSS)도 증거로 들어가며, 학습 가중치가 없어 사전 가중치(목록 판정 1.5)를 씁니다.

## 1. 수집 (`Get_data/`)

- **수집기 26개**가 각자 원뿔 검색을 하고 `catalog, catalog_object_id, object_name, ra, dec` + 카탈로그 원래 열을 CSV로 저장합니다(`controller.collect_all`).
- 병렬 6개, 아카이브당 300 s 예산입니다. 한 아카이브가 멈춰도 나머지는 계속합니다.
- 요청마다 시간 제한이 있어 멈춘 스레드가 쌓이지 않습니다. Gaia는 마감 시각이 지나면 재시도를 멈춥니다(2.19.0).
- VizieR 열 이름은 후보 목록에서 대소문자를 무시하고 고릅니다. 실제 아카이브로 확인했습니다(2.20.0).
- **로컬 캐시** (`archive_cache.py`):
  - 같은 영역이나 그 안쪽을 다시 찾으면 네트워크 없이 처리합니다.
  - 수집 코드가 바뀌면 캐시를 새로 만듭니다.
  - 부분 실패한 결과는 저장하지 않습니다.
  - 2 GB 상한이 있습니다.

## 2. 위치 연관 (`Preprocess/01_source_association.py`, `association_model.py`)

같은 천체를 서로 다른 카탈로그에서 찾아 하나로 묶는 단계입니다.

- **오차 모형**: 카탈로그마다 위치 오차·분해능(PSF)·기준 시기를 둡니다(`PROFILES`).
  - 행마다 오차 열이 있으면 그것을 씁니다.
  - 예: Gaia `ra_error`, PS1 `raMeanErr`(arcsec), Legacy Surveys `ra_ivar`, Chandra `r0`(95 % 반경 → 1σ 환산), eRASS1 `posErr`, 4XMM `ePos`.
- **고유운동 전파**: Gaia처럼 고유운동이 있는 천체는 상대 카탈로그의 관측 시기(예: PS1 `epochMean`)로 위치를 옮긴 뒤 비교합니다.
- **판정**: 두 위치가 같을 확률은 아래로 판단합니다.
  - 정규화 거리 `x = 거리/결합 σ`로 우도 `exp(−x²/2)/(2πσ²)`를 구합니다.
  - 사후확률은 `L/(L+ρ)`이고, ρ는 그 카탈로그의 원천 밀도입니다(Sutherland & Saunders 1992; Budavári & Szalay 2008).
  - 우연 일치 확률 `1 − exp(−πr²ρ)` ≤ 0.25, 그리고 반경 ≤ 상한일 때 받아들입니다.
- **앵커**: 가장 정밀한 위치(고유운동이 있는 Gaia가 우선)를 그룹의 기준 위치로 씁니다.
  - 후보가 둘 이상이고 점수가 비슷하면 "모호"로 따로 둡니다.
  - 같은 ID를 공유하면(예: DESI TARGETID ↔ Legacy Surveys ID) 위치와 무관하게 묶습니다.
- **속도**: 작은 격자 칸 + 넓은 빔(NVSS 45″ 등) 앵커 상시 확인으로, 전수 비교와 같은 결과를 냅니다. 조밀 영역 5,439 검출 기준 10.2 → 3.0 s입니다.

## 3. 통합과 특징 (`02_integrate_objects.py`, `units.py`, `03_extract_features.py`)

- **통합**: 그룹 하나를 한 행으로 만들고, 모든 원래 열을 `카탈로그__열` 이름으로 보존합니다.
- **단위 통일**: 등급은 AB, 플럭스는 mJy, 분광 적색편이는 하나의 열로 맞춥니다.
- **특징**:
  - 색(PS1, Legacy Surveys g−r, r−z, z−W1, W1−W2 등).
  - 형태: PS1 PSF−Kron, Legacy Surveys Tractor 모형.
  - 신호대잡음.
  - 품질: Gaia RUWE, 측광 플래그, WISE cc_flags.
  - 소광 보정: SFD E(B−V), 밴드별 계수.

## 4. 증거 (`04_build_evidence.py`, `classification_rules.csv`)

규칙표 한 행이 규칙 하나입니다. 각 규칙에는 목표 클래스, 읽는 카탈로그·열, 기준, 문헌, 신뢰도가 적혀 있습니다. 규칙은 0–1 점수의 증거를 냅니다.

| 종류 | 규칙 | 내용 |
|---|---|---|
| 천체측정 | AST-GAL-001/002 | Gaia 시차·고유운동이 유의함 → 별(우리은하 안). 양의 시차만 씀 |
| | AST-EXT-001/002 | 시차·고유운동이 0과 같음 → 외부은하 쪽(Klioner+2022). 시차(001)는 오차 ≤ 0.3 mas일 때만 |
| 분광(벤치마크 밖) | SPC-SDSS-001/2/3 | SDSS 분광 분류 |
| Gaia 분류기 | DSC-001 | Gaia DSC 확률에서 DSC의 사전확률을 나눠 제거한 값(Delchambre+2023 부록 C) |
| 형태 | PS1-MORPH, LS-MORPH, SDSS-PHOTO | 퍼진 천체 → 은하, 점광원 → 별 또는 QSO |
| 적외선 | WISE-AGN-001(Stern+2012), WISE-AGN-R90-001(Assef+2018) | W1−W2가 붉으면 AGN·QSO. 각 문헌의 적용 범위(S/N, 은하면 제외) 안에서만 |
| 색 | PS1-QSO-Z6-001 | z ≈ 6 QSO i-탈락 기준(Bañados+2016) |
| 목록 | SGA-001, NED/SIMBAD-TYPE-001 | 큰 은하 목록, 문헌 유형 |
| 학습 | LS-CKNN-001, PS1-CKNN-001 | 색 공간 kNN(k = 31, 등급 축 포함; Ball+2007) |
| | **LS-GBM-001** | DESI DR1 분광 15만 개로 학습한 그래디언트 부스팅(Legacy Surveys 색·형태·S/N 12개 특징). 시험 정확도 95.6 %. numpy만으로 추론 |

증거마다 두 신뢰도를 곱합니다.
- **카탈로그 품질**: 예를 들어 RUWE가 크면 Gaia 천체측정 신뢰도를 낮춥니다.
- **연관 신뢰도**: 그 카탈로그 검출이 이 천체에 속할 확률입니다.

## 5. 1차 분류 (`05_likelihood_vectors.py`, `fusion_weights.json`)

- **융합**: 증거 키(`규칙:클래스`)마다 logit(점수)를 특징으로 하는 **다항 로지스틱 회귀**로 P(STAR), P(GALAXY), P(QSO)를 냅니다.
  - 학습: SDSS·DESI 분광 벤치마크의 train split만, 클래스 균형으로 학습합니다(`benchmark/fit_fusion_weights.py`).
  - **부호 제약**: 자기 클래스를 올리지 않는 키는 빼고 다시 학습합니다. 뺀 키는 문헌 가중치를 씁니다. 공선성 때문에 "Gaia 별 증거가 은하 쪽"으로 가는 것을 막습니다.
  - **결측 보강**: 일부 카탈로그만 있는 경우(Gaia만 있는 밝은 별 등)를 학습에 보강 샘플로 넣습니다.
- **결정적 운동**: 시차나 고유운동이 10σ 이상이고 품질이 좋으면 바로 STAR입니다(외부은하 천체는 움직이지 않음).
- **기권**:
  - 최대 확률이 임계값(학습으로 정함, 현재 0.56) 미만이면 UNKNOWN입니다(Chow 1970 reject option).
  - 강한 증거끼리 충돌해도 UNKNOWN입니다.
- **측정치**(test split, 분광 정답):

  | 벤치마크 | 정확도(기권 = 오답) | 기권률 |
  |---|---:|---:|
  | SDSS | 97.69 % | 0.75 % |
  | DESI(어두운 천체) | 90.96 % | 2.6 % |

- **실제 영역**(DESI 분광 대조): 판정한 것의 정확도 96.8–100 %, 판정률 92.6–97.6 %.

## 6. 세부 분류 (`Classifier/subclass.py`)

1차 클래스별로 다른 판정을 하고, 판정마다 근거 문장과 규칙별로 측정한 정밀도를 붙입니다.

**STAR**
- **분광형**(O–M), 다음 우선순위로 정합니다.
  1. SIMBAD MK형 / LAMOST·SDSS 분광 템플릿.
  2. Gaia 소광 보정 BP−RP + 온도를 Pecaut & Mamajek 왜성 계열에 대응.
  3. PS1 i−z.
- **광도 계급**(V 왜성, IV 준거성, III 거성, VI 준왜성):
  - Gaia 시차로 구한 주계열 위 높이 ΔM.
    - 거성은 ΔM ≤ −3 또는 M_G < 4(Ruiz-Dern+2018).
    - 백색왜성 영역은 GF21 식 1.
  - 시차가 없으면 분광 log g(Ciardi+2011 경계, log g < 3.5).
  - GSP-Spec log g·[M/H]는 생산자 보정식(Recio-Blanco+2023)을 적용합니다.
- **속성 표지**:
  - 고유운동 속도로 얇은 원반·두꺼운 원반·헤일로.
  - RUWE 쌍성. AGB 별에는 쓰지 않습니다.
  - 근처 별, 고유운동 큰 별, 적색 거성단(red clump).
  - 적외선 초과, X선, 금속 결핍(분광 [Fe/H] < −1), 방출선.
- **AGB 화학형**: 탄소별(C) / 산소별(O, 규산염 먼지) / S형.
  - 근거 순서: SIMBAD·분광 → Suh 2021 → 측광 로지스틱 모형.
  - 측광 모형 입력: Wesenheit ΔW, Ks−W3, Gaia `is_cstar`(G_BP < 19일 때만).
  - 정확도 95.8 %.
  - 은하 중심 방향 저위도에서는 탄소 판정을 보류합니다.
  - 적색 거성단보다 어두우면(M_Ks > −1) AGB가 아닙니다.

**GALAXY**
- **활동성**, 다음 우선순위로 정합니다.
  1. SDSS 넓은 선.
  2. 방출선 WHAN(은퇴·수동) → BPT(Kewley/Kauffmann; Seyfert/LINER).
  3. SDSS 분류.
  4. SIMBAD 유형.
  5. WISE W1−W2 AGN.
  6. W2−W3 > 3.5 별 생성 / < 1.5 회전타원체(Jarrett+2017).
  7. GALEX NUV−r(> 5 적색 계열, 4–5 녹색 계곡).
- **빛 분포**: Tractor DEV/EXP/Sérsic n ≥ 2.5, SDSS u−r ≥ 2.22.
- **속성 표지**:
  - 1형·2형 AGN, 왜소·밝은 은하(M_B).
  - 옆면·정면, 분광 z와 거리, 전파 AGN(L1.4 > 10²³ W/Hz).
  - X선, 섬유 구경이 핵만 덮는 경우.

**QSO**
- 전파 강도 R_i > 1(Ivezić+2002).
- 고적색편이(z ≥ 2.1).
- 광도 M_i(z = 0) < −22(Schneider+2010 DR7Q 기준; M_i(z = 0) = M_i(z = 2) + 0.596), X선.

**그 밖**
- 문헌 정보(SIMBAD 참고문헌 상위 3편, "from paper").
- **UNKNOWN 이유**: 예를 들어 "PS1 한 밴드만 있음", "GALAXY와 STAR 확률이 겹침".

## 7. 독립 축 (`Classifier/axes/`)

1차 클래스와 별개로, 천체의 다른 성질을 다섯 축에서 따로 판정합니다. 각 축은 근거가 없으면 UNKNOWN입니다.

| 축 | 클래스 | 주요 근거 |
|---|---|---|
| 물리 상태 | WD, RGB, AGB, RED_GIANT | Gaia HR 위치(GF21) + DSC. Suh 2021 AGB(광도 확인). SIMBAD. 광도 계급 III + Teff < 5500 K → RED_GIANT. FLAME 거성(1 ≤ M < 2 M☉, 나이 > 1.5 Gyr) |
| 변광 | RR_LYRAE, CEPHEID, MIRA, LPV, ECLIPSING, ROTATIONAL, ERUPTIVE, PULSATING, OTHER_VARIABLE | SIMBAD 유형 → Gaia SOS(RR, 세페이드). ZTF 주기 변광성(g/r 진폭비 표시). Gaia LPV 반진폭 ≥ 0.6 mag이고 80 ≤ P < 1000 d → 미라. Gaia 변광 분류기 |
| 밀집성 | NS, PULSAR, PULSAR_CANDIDATE, XRB, COMPACT_COMPANION_CANDIDATE | ATNF, SIMBAD. 전파: TGSS–NVSS 스펙트럼 지수 ≤ −1.5이고 점광원(+유의한 편광) → 펄서 후보. 하늘 전체 사후확률(은하면·편광 우도비)이 확신도. Gaia 밀집 동반성 후보 |
| 외부은하 | GALAXY, AGN, QSO | Gaia 변광 AGN, 1차 분류 |
| 현상 | SN, PN, NOVA, MICROLENSING | HASH(T/L → PN, P → 가능, 모방체 제외). Acker PN 목록. ASAS-SN·Asiago 초신성 목록 일치(사건 시각과 관측 시각이 둘 다 있을 때만 1년 이후면 모은하로 보는데, 지금 수집기는 관측 시각을 주지 않아 목록 일치는 SN으로 남음). SIMBAD. Gaia |

**확신도 보정** (`calibration/`):
- 각 축 판정의 확신도는 그 규칙이 독립 정답(교차 검증)에서 보인 **실측 정밀도**입니다.
- 20행 이상일 때만 쓰고, Wilson 95 % 하한을 함께 둡니다.
- 점수가 있는 판정은 Platt 보정을 씁니다.

교차 검증(무작위 독립 정답, 클래스당 250개):

| 축 | 클래스 | 정확 일치 |
|---|---|---:|
| 변광 | 미라 | 94.8 % |
| | 세페이드 | 93.2 % |
| | RR Lyrae | 82.4 % |
| | LPV | 63.6 % |
| 현상 | PN | 89.2 % |
| 물리 상태 | RGB(계열 일치) | 51.7 % |
| | AGB(계열 일치) | 42.4 % |

이름 기반 블라인드 검증은 9/9입니다.

## 8. 마무리 (`host_groups.py`, `designations.py`)

- **큰 은하 묶기**:
  - SGA 은하의 D26 타원 안에 있는 다른 검출(HII 영역, 핵, 조각)은 그 은하의 부분이 됩니다(identity / nucleus / component).
  - 예외는 독립 천체로 남깁니다: 유의한 운동(전경 별), 다른 적색편이(배경), 초신성.
- **이름**: SIMBAD → NED → 주요 카탈로그 순서로 사람이 읽는 이름을 붙입니다. 같은 이름이면 구분 표시를 답니다.

## 9. 앱 (`app/`)

- PySide6 GUI 구성:
  - 왼쪽: 검색 영역·데이터 출처·옵션.
  - 가운데: 결과 표(클래스·상태·검색 필터).
  - 오른쪽: 상세 패널(확률 막대, 증거, 세부 축, 외부 링크)·하늘 지도.
- 파이프라인은 별도 작업 프로세스로 돌아 GUI가 멈추지 않고, 취소할 수 있습니다.
- 실행 로그는 사용자별 **로그 파일 하나**에 쌓이고 View > Log 창에서 봅니다.
- 배포: PyInstaller 폴더 빌드(Windows/macOS/Linux)를 GitHub Release에 올립니다.

## 10. 한계 (알고 있는 것)

- **어두운 끝**:
  - 측정이 한 카탈로그·한 밴드뿐이면 UNKNOWN이 많습니다(COSMOS 3′에서 11 %).
  - 그 대부분은 SIMBAD/NED에만 있는 문헌 항목입니다.
- **RGB와 AGB 구분**: 성진학이나 정확한 광도 없이는 둘을 가를 수 없어 RED_GIANT로 묶습니다.
- **펄서 교차 검증 0.4 %**: 정답 세트가 쓰는 수집기 조합에 TGSS·NVSS 짝이 거의 없어서입니다. 별도 펄서 벤치마크의 재현율은 21.6 %입니다.
- **X선 증거**: X선은 2.20.0에서야 실제로 수집되기 시작했습니다. 1차 분류의 X선 증거는 아직 없고, 표지로만 씁니다.
