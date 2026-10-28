# 어두운 은하와 성운 속 젊은 별: 문헌 근거 (2026-10-27, 2.41.0)

2.40.0의 독립 정답 검증(세트 A·B, 400개 영역)에서 남은 두 약점에 대한 문헌 근거를 모은 문서다.

1. **어두운 은하:** 은하 오류 245건 중 142건(58 %)은 같은 위치 3″ 안에 맞게 분류된 은하가 따로 있었다.
   - 틀린 쪽은 어두운 LS 원천(중앙값 r 21.9, 맞은 쪽 17.6)이거나, AllWISE/GALEX/SDSS 한 탐사에만 있는 행이었다.
   - 즉 분류보다 연관(한 은하가 여러 천체로 쪼개짐)의 문제다.
2. **성운 속 젊은 별:** 별 생성 영역의 별 오류 37건 중 21건은 근거가 하나도 없는 경우(NO_EVIDENCE)였고, 10건은 근거끼리 충돌한 경우(CONFLICT)였다.
   - 성운 빛 때문에 Gaia C*가 커져 고유운동 규칙이 막힌다.
   - DSC와 PS1 형태는 '은하'라고 판정한다.
   - 묻힌 별은 광학 검출이 아예 없다.
   - 구상성단에서도 같은 경우가 있다(2MASS·Gaia만 있고 근거 없음).

## 0. 확인 방법과 표시

- 조사는 에이전트 두 갈래로 했다. ① 교차 일치·쪼개짐 ② 2MASS·WISE·X선의 YSO 근거.
- 원문 확인은 `literature-excerpts.yml` 워크플로로 했다. 정규식 목록은 `.github/literature/faint_galaxy_yso_check.json`, 로그는 run 40500537924다.
- 표시는 `LITERATURE_QSO.md`와 같다.

| 표시 | 뜻 |
|---|---|
| **V** | 논문 본문(arXiv PDF)에서 해당 문장·수치를 직접 확인 |
| **A** | 초록·검색 요약에서 여러 출처가 일치하지만 본문은 확인하지 않음 |
| **U** | 한 출처뿐이거나 출처끼리 다름. 코드에 쓰기 전에 확인 필요 |

## 1. 성운 속 젊은 별: 밝은 2MASS 점광원은 별이다

### 1.1 하늘 밀도 비교 (Ks < 13–14)

| 종류 | 밀도 | 출처 | 표시 |
|---|---|---|---|
| 별 | 고위도 '저혼잡' 영역도 Ks < 14에서 약 1,000–1,200 deg⁻²; (l, b) = (240°, +4.5°)에서 4,500 deg⁻² | 2MASS Explanatory Supplement (Skrutskie et al. 2006, AJ 131, 1163) | A |
| 은하 | Ks < 13.5에서 약 16–22 deg⁻². 2MASS XSC가 Ks = 13.5까지 완전·신뢰 | Jarrett et al. 2000, AJ 119, 2498 | A (워크플로 PDF 404) |
| 퀘이사 | K ≤ 14.0에서 붉어지지 않은 퀘이사 **0.081 deg⁻²**, 14 < K < 15에서 0.46 deg⁻² | Maddox et al. 2008, MNRAS 386, 1605 | **V** |
| 붉은 퀘이사 | 위 값에 25–60 % 추가 | Glikman et al. 2007, ApJ 667, 673; Maddox et al. 2008 ("a further 60 per cent") | V(Maddox 문장) |

- 그래서 Ks < 13의 깨끗한 2MASS 점광원은 은하의 극 방향에서도 별 대 은하가 25:1 이상, |b| < 20°에서는 100:1 이상이다. 퀘이사에 대해서는 10⁴:1 이상이다.
- 은하는 그 밝기에서 XSC에 분해되어 PSC 항목에 `gal_contam`(VizieR `Xflg`) > 0이 붙는다. 그래서 `Xflg = 0`이 은하를 거르는 조건이다.
  - 우리 SDSS 벤치마크에서 Ks < 13인 은하 43개 중 37개가 Xflg > 0이었다.
- ONC의 X선 검출 천체 중 분자운 너머의 AGN은 근적외선 짝이 없다. 성단 구성원의 광학·근적외선 짝은 "nearly always brighter than the counterparts to extragalactic sources"다(Getman et al. 2005, ApJS 160, 353, **V**).

### 1.2 품질 조건

- `ph_qual`(Qflg)은 H와 Ks에서 A 또는 B(S/N ≥ 7)여야 한다.
- `cc_flg`(Cflg)는 Ks에서 0이어야 한다(인공물 없음).
- `gal_contam`(Xflg)은 0이어야 한다.
- 근거: 2MASS Explanatory Supplement §4.5, §4.7 (**A**).

### 1.3 WISE AGN 색 규칙이 YSO에 걸리는 문제

- 원반이 있는 Class I/II YSO는 W1−W2가 0.25–1.5 이상이다. 그래서 Assef et al. 2018 R90 기준(W1−W2 > 0.65)을 넘는다.
- 오리온·황소자리·뱀주인자리는 모두 R90 적용 하늘(|b| > 10°) 안에 있다.
- Koenig & Leisawitz 2014(ApJ 791, 131)는 AGN 후보를 **w1 > 13.0**(식 8, 10)으로 한정한다(**V**). 즉 W1 < 13인 YSO는 AGN으로 보지 않는다.
- Gutermuth et al. 2009는 [3.6] ≤ 14.5 같은 밝기 하한으로 외은하 천체를 거른다(**A**).
- 우리 적용: W1 < 13 하한을 그대로 쓰면 SDSS 벤치마크에서 실제 QSO 65개의 R90 근거가 사라진다. 그래서 같은 개수 논리의 Ks 형태를 쓴다. 깨끗한 2MASS 점광원이고 Ks < 13이면 R90을 적용하지 않는다(벤치마크 영향 5건, 정확도 변화 없음).

### 1.4 조사했지만 이번에 쓰지 않은 것

| 근거 | 내용 | 쓰지 않은 이유 |
|---|---|---|
| Meyer, Calvet & Hillenbrand 1997 CTTS locus (J−H) = 0.58(H−K) + 0.52; Indebetouw et al. 2005 적색화 기울기 1.73 | 근적외선 색으로 YSO 판별 | 은하 색(J−H 0.6–0.8)이 K/M 별과 겹친다. 밝기 조건(1.1)이 이미 결정적이라 추가 이득이 작다 |
| X선/Ks 비 log(f_X/f_Ks) < −1.2 (Chen et al. 2018) | X선 천체의 별 판정 | 플럭스 정의를 우리 자료로 확인하지 못했다. 성운 오류 대부분은 Ks < 13 조건으로 이미 해결된다 |
| MYStIX MPCM (Broos et al. 2013), Hunt & Reffert 2023/2024 성단 구성원 | 성단 소속 근거 | 새 수집기가 필요하다. 다음 작업 후보 |
| Rybizki et al. 2022 astrometric fidelity > 0.5 | 성운 안 고유운동 품질을 C* 대신 판정 | GAVO TAP 수집기가 필요하다. 다음 작업 후보 |

## 2. 어두운 은하: 쪼개진 조각과 중복 행

| 근거 | 내용 | 표시 |
|---|---|---|
| Dey et al. 2019, AJ 157, 168 §8 | "spatially large, extended sources with complex morphologies (e.g., large galaxies) … are poorly modeled by The Tractor". WISE는 광학 위치·모양에 강제 측광된다 | **V** |
| Hahn et al. 2023, AJ 165, 253 (DESI BGS) | "fragments of 'shredded' galaxies"를 섬유 등급 조건 r_fiber < 22.9 + (r − 17.8) (r < 17.8), r_fiber < 22.9 (17.8 < r < 20)로 제거한다. 각주: 밝은 천체가 여러 원천으로 모델되어도(shredding) 본래 원천이 가려지도록 했다 | **V** |
| Moustakas et al. 2023 (SGA-2020) | 은하 픽셀을 반장축의 1.5배 타원으로 정한다. SDSS는 r ≲ 14 은하가 쪼개짐 때문에 50 % 이상 불완전하다(Fukugita et al. 2007 인용) | **V** |
| Ruiz-Macías et al. 2021, MNRAS 502, 4328 | FRACMASKED, FRACFLUX, FRACIN 품질 지표. 섬유 등급 조건이 인공물과 조각을 줄인다 | **V** |
| Sullivan et al. 2006; Gupta et al. 2016, AJ 152, 154 | 빛 반경으로 정규화한 거리 d_DLR. 숙주 은하 판정에 d_DLR < 4 | A (저장소에 이미 인용) |
| Marrese et al. 2019, A&A 621, A144 | Gaia 외부 교차 일치에서 한 원천의 여분 항목을 'mates'로 남긴다 | V (세션에 저장된 본문) |
| Baldry et al. 2010, MNRAS 404, 86 (GAMA) | 큰 은하 근처 어두운 원천을 deblend 후보로 눈으로 검사한다 | V (세션에 저장된 본문) |

### 2.1 우리 적용 (`host_groups.attach_galaxy_fragments`)

**숙주:** LS 확장형(REX/EXP/DEV/SER/COMP)이고, r이 있고, `primary_class` = GALAXY인 최상위 천체.

**후보:** 숙주 중심에서 max(1.0 r_e, 1″) 안에 있는 최상위 천체. 이 반경은 d_DLR < 1로, 문헌의 d_DLR < 4보다 보수적이다. 다음 중 하나여야 한다.
- **LS 조각:** LS r이 숙주보다 2.0등급 이상 어둡다. 그리고 숙주에 없는 2MASS/AllWISE/PS1/SDSS/GALEX 행을 갖고 있다. 즉 은하의 측광 행을 조각이 가져간 경우다(Dey et al. 2019의 강제 측광, Hahn et al. 2023 각주의 논리).
- **확인되지 않은 탐사 행:** LS 측정도 Gaia 원천도 없다. 더 깊은 LS 영상에서 따로 보이지 않는 행이다. 2.30.0 `detection_quality`와 같은 전제다.

**제외:** Gaia 시차 또는 고유운동이 5σ 이상이거나, 자기 분광이 있으면 묶지 않는다.

**측정** (400개 영역, blind 재채점, 저장된 결과에 규칙만 적용):

| 설정 | 묶인 수 | 우연 비율* | 세트 A | 세트 B | 별 손실 |
|---|---|---|---|---|---|
| 기준 (2.40.0) | 0 | – | 98.26 % | 98.57 % | – |
| LS 조각 전부, 1.5 r_e | 36,530 | 0.71 | 98.48 | 98.74 | 3 |
| LS 조각 + 행 가져감, 1.5 r_e | 9,274 | 0.19 | 98.47 | 98.71 | 3 |
| 탐사 행, 1.0 r_e | 39,469 | 0.25 | 98.41 | 98.64 | 0 |
| **채택: 행 가져간 LS 조각 + 탐사 행, 1.0 r_e, Δr ≥ 2.0** | 45,262 | 0.24 | **98.62** | **98.78** | 3 |

\* 우연 비율은 대조군으로 쟀다. 숙주가 아닌 천체를 30″ 옮겨 같은 규칙을 적용했을 때 묶이는 수를 실제 묶인 수로 나눈 값이다. 은하 곁에 우연히 겹쳐 보이는 별개 천체의 비율 추정치다.
- '조각 전부'(0.71)는 대부분 은하 근처의 진짜 어두운 천체를 숨긴다. 그래서 버렸다.
- LS 원천은 1″ 안에 서로 겹치지 않으므로(Tractor 분리 한계), 작은 반경에서는 이 대조군이 우연 비율을 과대평가한다.
- 잃은 별 3개는 r 23–24.6의 LS 원천이다. 정답(2QZ/2SLAQ, b_J ≈ 20–21)의 실제 빛은 더 밝은 이웃에 있다.

## 3. SGP 띠의 어두운 은하: Gaia 별·은하 구분 (2.42.0)

| 근거 | 내용 | 표시 |
|---|---|---|
| Hahn et al. 2023, AJ 165, 253 (DESI BGS) | 별·은하 구분: 은하는 "1. object is not in the Gaia catalog; 2. object is in Gaia and has (G_Gaia − r_raw) > 0.6". r_raw는 은하 소광을 보정하지 않은 LS r. Gaia G가 점광원 PSF로 측정되어 퍼진 천체는 G가 어두워진다 | **V** |
| Ruiz-Macías et al. 2021, MNRAS 502, 4328 | 같은 BGS 파이프라인. r_raw는 은하 소광 보정을 하지 않은 값 | **V** |
| Cantat-Gaudin et al. 2023, A&A 669, A55 | Gaia DR3 완전도 모형(M10). "in crowded areas where the density exceeds ∼1,050,000 per square degree, Gaia cannot follow all" | **V** |

### 3.1 우리 적용 (`Preprocess/bgs_galaxy.py`)

**대상:** LS 확장형(REX/EXP/DEV/SER) 원천 중 다음 하나.
- Gaia 원천이 없고 r_raw < 20이다. r이 없으면 z < 19.5 또는 g < 20.5로 대신한다(이 밝기의 은하 색 r − z ≈ 0.4–0.8, g − r ≈ 0.5–1.0).
- Gaia 원천이 있고 G − r_raw > 0.6이다.

**Gaia 완전도 조건:**
- 검색 안에 Gaia 원천이 11개 이상 있어야 한다. 즉 Gaia 조회가 성공했어야 한다.
- 국소 Gaia 밀도가 10⁵ deg⁻² 이하여야 한다. 문헌의 군집 한계 10⁶보다 한 자릿수 보수적으로 잡았다.

**적용 방식:** 근거만으로 이미 0.9 이상 확신으로 분류되는 천체는 건드리지 않는다. 그 밖이면 GALAXY(확신도 0.98)로 판정하고 `classification_basis`에 기록한다. 이 경로로 분류된 천체는 사진측광 고신뢰 표시에서 뺀다.

**측정 (정답 천체 재생, 400개 영역):**
- 이 시험을 통과하는 정답 천체는 Gaia 없음 831개 중 은하 828개, G − r > 0.6 1,079개 중 은하 1,059개다.
- 규칙 적용 시 고침 31, 새 오류 1이다. SGP 띠는 94.50 → 95.95 %가 됐다.
- SDSS·DESI 벤치마크 예측 변화는 0이다.

**버린 방법:** 밴드가 빠진 곳에서 색 kNN·색 특징을 끄는 방법. 오히려 18–20건이 나빠졌다. 부분 색으로도 kNN은 쓸모가 있었다.

## 4. 성운 속 젊은 별: 구성원 목록과 Gaia 천체측정 신뢰도 (2.42.0)

| 근거 | 내용 | 표시 |
|---|---|---|
| Broos et al. 2013, ApJS 209, 32 (MYStIX) | MPCM은 X선 원천의 naive Bayes 분류(중앙 에너지, 변광, J, [4.5], IR 초과, 국소 밀도)로 고른 구성원, IR 초과 구성원(Povich et al. 2013), 그리고 B3보다 이른 분광형의 OB 별(문헌 분광)의 합집합이다 | **V** |
| Rybizki et al. 2022, MNRAS 510, 2597 | Gaia (E)DR3 천체측정 해의 신뢰도 fidelity_v2를 분류기로 계산했다. 시험 자료에서 순도 99.3 %, 완전도 97.3 %. 예시 컷으로 fidelity_v2 > 0.9를 쓴다. 제공처는 GAVO TAP `gedr3spur.main` | **V** |
| Hunt & Reffert 2023, A&A 673, A114 / 2024, A&A 686, A42 | Gaia DR3 HDBSCAN 성단 구성원 목록(열 `GaiaDR3`, `Prob`) | 열 이름은 Actions에서 확인 |

### 4.1 확인한 것 (Actions 탐침, run 40604763801)
- **MPCM 표:** `J/ApJS/209/32/mpcm`. 6′ 안 구성원 수는 ONC 1,101, NGC 2024 397, M8 595다. 선택 근거 열은 `Xind`(X선), `Iind`(IR 초과), `Olab`(OB 목록)이다.
- **Hunt & Reffert:** 같은 영역에서 구성원이 19 / 2 / 75로 적다. 게다가 Gaia 운동으로 정한 소속이라 우리 Gaia 운동 근거와 겹친다. 그래서 쓰지 않았다.
- **2.41.0 규칙에서 빠진 이유:** NGC 2024·ONC의 밝은 미분류 별 10개는 2MASS `Xflg` = 1–2였다. 2MASS 확장원 목록에 성운 자체가 들어 있어서 그렇다. 은하 오염 방지 조건이 옳게 작동한 것이므로 그 조건을 풀지 않고, 구성원 목록으로 해결했다.
- **fidelity:** GAVO에서 ONC·NGC 2024·M8의 Gaia 원천 각각 365·61·281개에 값이 있다.

### 4.2 우리 적용
- **`Get_data/mystix_mpcm.py`:** X선 또는 IR 초과로 뽑힌 구성원만 남긴다. OB 별은 문헌 분광형으로 뽑힌 것이라 blind 검증에 넣을 수 없어 뺐다.
- **Stage 5:** MPCM 행을 가진 천체는 STAR로 판정한다(확신도 0.95, 근거 표시 "young-star membership (MYStIX)"). 단, 자기 분광이 있으면 분광이 정한다.
- **Gaia 수집기:** GAVO에서 fidelity_v2를 붙인다. Stage 5에서는 fidelity_v2 ≥ 0.9이면 C*(성운 배경으로 커진 BP/RP 초과)와 상관없이 그 천체의 시차·고유운동을 쓴다.
