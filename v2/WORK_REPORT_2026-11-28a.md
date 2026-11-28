# 작업 보고서 2026-11-28a — 과제 타(CI에 app 시험) · 과제 파(정답 수집의 순서 의존 전수 조사)

버전 제안: 과제 타 **2.63.1 (PATCH)**, 과제 파 **2.63.2 (PATCH)**: 둘 다 분류 결과를 바꾸지 않는다(CI 설정·시험·조사 표). 번호는 이 브랜치에서 카(2.63.0) 다음으로 이어 붙인 것이고, main이 2.62.1이므로 병합 순서에 따라 검토 세션이 다시 매긴다(차 2.62.2, 카 2.63.0과 같은 브랜치).

## 0. 내가 이해한 요청

* **과제 타**: `app/tests` 17개를 CI에 넣는다(화면 없는 러너에서 Qt가 도는지 offscreen 설정을 확인하고), CI가 돌리는 시험과 `CLAUDE.md`의 로컬 명령(`cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests`)이 같은 집합이 되게 한다.
* **과제 파**: 다른 정답 수집 워크플로·스크립트(`build-*-truth.yml`, `Build Catalog Truth Features`, 벤치마크 수집 도구)가 `ORDER BY` 없는 `TOP`/`row_limit`으로 표본을 뽑는지 전수 조사해 표로 낸다(어느 것이 커밋된 고정 목록을 쓰고 어느 것이 실행마다 달라질 수 있는지). **고치는 것은 표를 본 뒤 정한다.**

## 1. 과제 타 — CI가 `CLAUDE.md`와 같은 시험을 돈다

### 1.1 전에 CI가 돌던 것 (`Classifier/validation/reproducibility/ci_test_inventory.csv`)

| 시험 | 있는 시험 수 | CI가 도는 수 | 어느 워크플로 |
|---|---|---|---|
| `Preprocess/tests` | 423 | 423 | `test-preprocess.yml`(`v2/Preprocess/**` 등이 바뀐 push) |
| `Classifier/tests` | 97 | 97 | `v2_scientific_cross_validation.yml`의 준비 단계(main push, 정해진 경로) |
| **`app/tests`** | **17** | **0** | **없음** |
| `Classifier/test_star_diverse.py` | 4 | 4 | `validate-star-diverse.yml` |

`app/tests`는 `CLAUDE.md`가 "연관 회귀를 잡는 유일한 통합 시험"이라고 적은 것인데 어느 워크플로도 돌지 않았다(`build-app.yml`은 얼린 앱의 오프라인 스모크 시험만 한다). 또한 `Preprocess/tests`와 `Classifier/tests`도 각자의 좁은 경로가 바뀔 때만 돌아서, 예컨대 `v2/Preprocess/association_model.py`를 바꿔도 `Classifier/tests`는 돌지 않는 경우가 있었다.

### 1.2 한 일

* `.github/workflows/unit-tests.yml`: `CLAUDE.md`의 명령 그대로(`working-directory: v2`, `python -m pytest -q Preprocess/tests Classifier/tests app/tests`). `pull_request`와 main 푸시에서 `v2/**`, `CLAUDE.md`, 이 워크플로·확인 스크립트가 바뀌면 돈다. 수동 실행도 된다.
* **화면 없는 러너**: `QT_QPA_PLATFORM=offscreen`(작업 환경 변수; `app/tests`도 `os.environ.setdefault`로 같은 값을 스스로 넣는다), PySide6가 시작에 필요한 시스템 라이브러리(`libegl1 libgl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libglib2.0-0`)를 설치하고, 시험 전에 `QApplication([])`가 실제로 만들어지는지 한 단계에서 확인한다(Qt가 안 뜨면 17개가 건너뛴 것으로 조용히 지나가지 않고 이 단계에서 바로 실패).
* **건너뜀과 누락을 실패로**: `.github/scripts/assert_no_skips.py`가 JUnit 결과에서 건너뛴 시험이 있으면 실패시키고, `--require Preprocess.tests Classifier.tests app.tests`로 각 폴더에서 시험이 하나라도 수집되었는지 확인한다. `app/tests`는 `pytest.importorskip("PySide6")`를 쓰므로 PySide6가 없으면 시험이 건너뜀(통과처럼 보임)이 된다 — 이것이 가장 현실적인 조용한 실패였다.
* **집합이 어긋나지 않게**: `Preprocess/tests/test_ci_test_set.py`(시험 8개)가 (a) `CLAUDE.md`의 명령, (b) `unit-tests.yml`의 명령, (c) `v2` 아래 `tests`라는 이름의 폴더들이 같은 집합인지, (d) 다른 워크플로가 이 집합 밖의 `tests` 폴더를 돌지 않는지, (e) 확인 스크립트가 같은 폴더를 요구하는지, (f) 확인 스크립트가 건너뜀·누락 입력에서 실제로 실패하는지 검사한다. 새 `tests` 폴더가 생기면 `CLAUDE.md`와 워크플로를 같이 고치지 않는 한 이 시험이 실패한다.
* **의존성**: `v2/app/requirements.txt`(PySide6, pandas, numpy, scipy, requests, astropy, astroquery, pyvo)에 `pytest scikit-learn reportlab python-pptx pypdf`를 더한다(scikit-learn은 Classifier, 나머지는 Preprocess의 개요·덱 시험이 건너뛰지 않고 돌게). 깨끗한 가상환경에 **정확히 이 패키지만** 설치해 전체를 돌리니 566개 모두 통과하고 건너뛴 것이 없었다(52 s).
* `ci_test_inventory.py`가 `working-directory: v2`로 도는 워크플로를 알아보게 고쳐 표를 다시 냈다: 있는 시험 578개를 CI가 578개 모두 돈다.

### 1.3 설계 이유와 버린 대안

* **하나의 워크플로로 모았다**. 대안 1: `test-preprocess.yml`·교차 검증 워크플로에 `app/tests`를 덧붙이기 — 그 둘의 경로 조건(`v2/Preprocess/**` 등)은 `v2/app/**` 변경에 반응하지 않고, 교차 검증 워크플로는 main 푸시 전용이며 수 시간짜리 일을 시작하는 워크플로라 시험 관문이 되기엔 무겁다. 대안 2: `app/tests`만의 별도 워크플로 — 세 곳이 `CLAUDE.md`와 따로 어긋날 수 있다. 하나로 모으고 시험으로 일치를 지키는 편이 더 작다. 기존 두 워크플로는 그대로 두었다(빠른 경로별 피드백, 일치 시험이 이 집합 밖을 돌지 않음을 보장).
* **v2에서 돌린다**. `CLAUDE.md`가 `cd v2`로 시작하고, 일부 시험은 작업 디렉터리에 의존한다(`test_host_groups` 등). 기존 `test-preprocess.yml`은 저장소 루트에서 돌려 로컬 명령과 달랐다.
* **Python 3.12**: `test-preprocess.yml`과 같다. 이 환경(3.13)에서도 통과한다.
* **PR과 main 푸시에 건다**(경로 조건을 `v2/**`로 넓힘): 시험이 50 s대이고 설치가 pip 캐시로 짧아 매 변경에 도는 비용이 작다.
* **한계**: 이 환경에서 GitHub 러너를 돌릴 수 없어 `ubuntu-latest`에서의 실제 실행은 확인하지 못했다. 확인한 것은 (1) 의존성 집합이 충분하다는 것(가상환경), (2) 확인 스크립트·일치 시험의 동작(시험과 변이 검사: 워크플로 복사본에서 `app/tests`를 빼면 일치 시험이 실패), (3) 워크플로 YAML이 파싱된다는 것이다. **첫 실행(`workflow_dispatch` 또는 PR)을 지켜봐야 한다**: 시스템 라이브러리 이름(`libegl1` 등)과 Qt 시작이 러너에서 되는지.

## 2. 과제 파 — 정답 수집의 순서 의존 전수 조사 (조사만, 고치지 않음)

### 2.1 어떻게 조사했나, 왜 이렇게 했나

* **범위**: `v2/Classifier`의 정답 빌더 8개, `v2/benchmark`의 빌더·수집 스크립트 수십 개, 이들을 부르는 워크플로(`.github/workflows`), `v2/Get_data`의 수집기 전부. 읽기만 했고 워크플로·git·커밋된 데이터는 건드리지 않았다.
* **판정을 두 겹으로 나눴다**. (1) *구성(construct)*: 코드가 표본을 고르는 방식이 서버가 답한 행 순서에 의존하는가(`TOP`/`row_limit` + `ORDER BY` 없음, 순서 없는 프레임에 시드 `sample`/`head` 등). (2) *커밋본 고정(FIXED_BY_COMMIT)*: 소비자(검증·적합·벤치마크 스크립트)가 빌더를 다시 돌리지 않고 **커밋된 파일을 읽는가**. 질문이 "고정 목록이냐, 실행마다 달라질 수 있느냐"여서 (2)가 위험의 크기를, (1)이 "다시 만들면 무엇이 변하는가"를 정한다. 한 줄 판정으로 합치면 이 둘이 섞여서(예: "결정적"인데 목록 앞부분만 쓰는 경우) 읽는 사람이 오해하므로 나눴다.
* **세 갈래로 나눠 병렬로 읽혔다**(Classifier 빌더 / 분광·카탈로그 정답 빌더 / 변광·AGB 등 나머지). 파일이 많고 서로 독립이어서 시간이 갈래 수만큼 줄었다. 대신 에이전트 보고는 그대로 믿지 않고, 아래 "내가 직접 확인한 것"을 따로 표시했다. 고른 기준은 표의 결론을 바꿀 수 있는 주장(줄 번호가 맞는가, 측정값이 재현되는가, 자동으로 다시 돌아 덮어쓰는 워크플로가 있는가)이다.
* **서버 쪽 순서 규칙은 확인하지 못했다**. VizieR·Data Lab·SkyServer가 `ORDER BY` 없을 때 어떤 순서로 답하는지는 문서화된 보장이 없고(ADQL 2.1은 순서를 규정하지 않는다), 이 환경에서 서비스에 접속할 수 없어 실제 재현은 못 했다. 따라서 "순서에 의존"은 **코드가 그렇게 짜여 있다**는 뜻이지 "실제로 다른 행이 온다"는 증명이 아니다. 다만 커밋된 목록에 "서버가 앞에서부터 채웠다"는 흔적이 남은 경우(2.3절)는 측정으로 확인했다.

### 2.2 표 — 순서에 의존하는 구성 (다시 만들면 다른 행이 뽑힐 수 있는 것)

모든 산출물이 커밋되어 있고, 소비자는 커밋본을 읽는다(그래서 지금은 모두 FIXED_BY_COMMIT). "자동 재생성"은 빌더를 다시 돌려 **커밋된 목록을 덮어쓸 수 있는 경로**가 있는지다.

| # | 스크립트 (`v2/` 기준) | 선택 구성 (줄) | 정렬·시드 | 자동 재생성 경로 | 다시 돌리면 달라지는 것 |
|---|---|---|---|---|---|
| 1 | `benchmark/build_desi_truth.py` (desi_external 400/셀, desi_fusion 700/셀) | `row_limit=limit`(:46), 창마다 `d.sample(…, random_state=…)`(:119), `d.head(a.per_cell)`(:124) | 정렬 없음, 시드 20261008/20261015 | **`v2_desi_external_validation.yml`(수동)이 빌더를 돌리고 `cp … $d/truth.csv`로 커밋본을 덮어쓴 뒤 커밋**(:26, :74–:108). `collect-truth-radio-xray.yml`의 `fusion_truth` 잡도 같은 빌더 | 96개 셀 모두(3종 × r 4구간 × RA 창 8개)에서 어떤 행이 뽑히는지, 그리고 `benchmark_id`(위치 번호) 전체 |
| 2 | `benchmark/build_reference_objects.py` | `row_limit=limit`(:181), `fetch("VII/289/dr16q", limit=6000)`(:235), `out.sample(min(n, PER_TYPE), random_state=SEED)`(:99) | 정렬 없음, SEED=1 | **`build-reference-objects.yml`: 빌더·워크플로를 건드린 push(main·validation-data 제외)에서 자동으로 돌고 `v2/reference_objects`를 커밋**(:7–:9, :35) | 원격 유형 중 300행을 넘는 것의 표본, DR16Q는 행 우주 자체(처음 6000행) |
| 3 | `benchmark/build_sdss_sky_truth.py` | 전체 후보 질의(`ORDER BY`·`TOP` 없음, :83) 후 `rng.random(len(d))`로 `_r`을 **위치별로** 매기고 정렬(:103), `drop_duplicates("specobjid")`(:136) | 시드 2052. 서버 순서가 바뀌면 같은 시드라도 다른 `_r` | 수동. `reuse_run`을 주면 이전 정답을 재사용(워크플로 :43–:48) | 셀 안에서 고르는 객체와 마지막 라운드에 채워지는 셀 |
| 4 | `Classifier/build_lamost_star_external_truth.py` | `row_limit=per*3`(:78), `.head(n)`(:66), `.head(n)`(:124) | 정렬·시드 없음 | 수동(dispatch)만 | 정상 별 500행 전부(각 계열이 서버 앞쪽 429행 중 143개) |
| 5 | `Classifier/build_star_diverse_truth.py` | 후보 풀 `row_limit=limit`(:28, 기본 2000), 풀을 해시 정렬해 `head(n)`(:84) | 해시 시드는 고정이지만 **풀 자체가 "서버가 준 2000행"** | `refresh=true`일 때만 빌더가 돌고(워크플로 :87–:88) 그때는 커밋하지 않는다(커밋 단계는 refresh가 아닐 때 `inputs/`만, :139–:143) | 정상 별 4577행 중 2200(캡에 걸린 22/28 셀) |
| 6 | `benchmark/build_mira_truth.py`, `build_rr_ew_truth.py` | `row_limit=per_type*3`(:50/:54) 뒤 `tab.sample(…, random_state=2/1)`(:53/:57) | 정렬 없음 | 수동 | 유형별 4000/3000행 |
| 7 | `benchmark/build_bright_truth.py` (apogee, els) | RA 슬라이스마다 `row_limit=per_slice`(:149), 유형별 `row_limit=per_class`(:183) | 정렬 없음 | 수동 | 슬라이스별 첫 400행, beStar·TTauri 1500행(HerbigStar는 캡 아래라 안정) |
| 8 | `benchmark/build_desi_lines_truth.py` | `SELECT TOP {a.limit}`(:90) + `random_id < …`(:93) | `ORDER BY` 없음 | 수동 | 캡이 물릴 때만. 커밋본이 3,492행(≤4000)이지만 `zcat_primary` 필터 전에 잘렸을 수도 있어 물렸는지 알 수 없다(로그 없음) |
| 9 | `benchmark/build_desi_gbm_truth.py` | `random_id` 0.5 폭 슬라이스(:104), `g.head(a.per_class)`(:117) | `random_id`로 대부분 고정 | 수동 | 마지막 슬라이스의 잘린 꼬리만 |
| 10 | `benchmark/xray_rules/build_sample.py` | `.sample(20000, random_state=1)`(:12) | 시드 1, 입력(HamStar 내려받기)은 스크립트에 없음 | 워크플로 없음(수동) | ero-only 대조군 20,000. 커밋된 36,468행이 README(31,268행)·현 스크립트(3″ 제외)와도 어긋남 |
| 11 | `benchmark/build_radio_xray_truth.py` | 멤버십은 `ORDER BY specObjID`(결정적). X선 짝이 여럿이면 `drop_duplicates("specobjid")`가 **첫 행**(최근접 아님) | 거리 정렬 없음 | 수동 | 멤버십은 같고 `rx_*` 값이 바뀔 수 있음. XMatch 한 카탈로그가 실패하면 조용히 빠짐(:112–:114) |

### 2.3 이 가운데 "서버가 앞에서부터 채웠다"는 흔적이 커밋본에 남은 것 (내가 직접 재현)

* `desi_external/truth.csv`: (분류 × r구간 × RA 창) **96개 셀 전부**에서 그 셀 최소 RA가 창의 아래쪽 가장자리 0.2° 안에 있다. 셀 RA 폭의 중앙값 0.108°(창 폭 10°), 78 %가 0.5° 미만. 서버가 RA 오름차순으로 답하고 `row_limit`이 앞쪽만 남긴 모양이다. `desi_fusion`은 다른 창을 쓰지만 같은 모양(RA 폭 중앙값 0.22°, 71 %가 0.5° 미만). 이것은 하늘 전체 표본이 아니라 **창마다 한쪽 모서리의 작은 조각**이라는 뜻이고, 시드가 고정이어도 이 조각이 바뀌면 목록이 바뀐다.
* `reference_objects.csv.gz`: `QSO_SPECTROSCOPIC` 300행 전부가 RA 1.60–3.26°(DR16Q 전천에서 처음 6000행).
* 원인이 순서가 아니라 설계인 것(별개로 고쳐야 할 것): `lamost_star_external_truth.csv`의 정상 별은 A 143·F 143·G 143·K 71이고 M·B·O가 없다 — 계열을 `A,F,G,K,M,B,O` 순으로 이어 붙인 뒤 `.head(n)`(:124)이 뒤쪽을 잘라서다. `truth_data/ground_truth.csv`(`ORDER BY specObjID`)는 결정적이지만 가장 낮은 specObjID 몇 개 플레이트라 하늘 표본은 아니다.

### 2.4 표 — 결정적이거나 표본이 아닌 것

| 분류 | 스크립트 | 이유 |
|---|---|---|
| 결정적 (`ORDER BY` 고유 키) | `Classifier/build_star_truth.py`(`ORDER BY s.specObjID`), `benchmark/build_truth_sets.py`(`ORDER BY specObjID`), `build_radio_xray_truth.py`의 SQL 부분 | 고유 키로 정렬. DR18이 고정인 한 같다. 단 "가장 낮은 ID"라 플레이트에 몰림 |
| 결정적 (이름 정렬) | `Classifier/build_wd_subtype_truth.py`, `build_sdss_wd_subtype_external_truth.py` | `sort_values("external_id")` 뒤 `head`. 한 이름에 DA·DB 행이 둘이면 `drop_duplicates` 생존자만 서버 순서(오프라인 확인 불가) |
| 결정적 (고정 목록·전수 수집) | `benchmark/select_deep_cosmos_2.py`, `select_fields_b.py`(직접 돌려 커밋된 200개 목록과 일치 확인했다고 에이전트 보고), `collect_deep_cosmos.py`, `build_agb_chemistry/gcvs/contamination`, `build_pulsar_truth.py`, `new_targets/build_truth.py`(`ORDER BY random_index`) | 전수 질의(`row_limit=-1`) 또는 로컬 규칙. `agb_id` 같은 번호가 서버 순서를 따를 뿐 집합은 같음 |
| `Get_data/*` 수집기 | 모든 수집기 | 전수 수집(`row_limit=-1`) 또는 잘림을 실패로 처리(Gaia 동기 질의 `SYNC_MAX_ROWS`, SIMBAD MAXREC 오류) |
| 표본이 아님 | `build_spectro_truth.py`, `collect_catalog_truth.py`(최근접 `head(1)`), `augment_*`, `build_desi_galaxy_activity_truth.py`, `collect_star_gaia.py`, `collect_gaia_xp_coefficients.py`, `build_faint_*`, `build_phot_prior.py`, `build_color_reference.py`, `build_qso_photoz_reference.py` | 고정 목록의 속성을 찾거나, 가장 가까운 짝을 고르거나, 커밋된 입력의 요약 |

### 2.5 순서 의존을 키우는 공통 요인 (표의 읽는 법)

* **위치 번호로 붙인 ID**: `benchmark_id`가 행 번호다(`TRD%06d`, `DESI%06d`, `DFUS%06d`, `STARTRD%06d`, `LAMTRD%06d`, `WDSUB%05d`, `SDSSWDX%05d`, `agb_id` 등). 분할(train/보정/시험)은 `benchmark_id`의 SHA-256 해시로 정해지므로, 목록이 한 행만 달라져도 뒤따르는 모든 ID가 밀리고 **모든 객체의 분할 소속과 커밋된 `catalog_features` 열 정렬이 어긋난다**. 즉 순서 의존은 표본이 조금 바뀌는 문제가 아니라 벤치마크 전체의 분할을 다시 섞는 문제가 된다.
* **자동·반자동으로 커밋본을 덮어쓰는 경로가 있는 곳**: 표 2.2의 1번(수동 실행 한 번에 `truth.csv`와 `catalog_features`를 같이 덮음 — 같은 실행 안에서는 짝이 맞지만, 이전 목록 위에서 만든 다른 산출물과는 어긋남), 2번(브랜치 push마다). 나머지는 수동 또는 `refresh=true` 같은 명시 옵션이 필요하다.
* **독립 정답 기준 목록(`Classifier/truth/fixed`)은 이 트리에 아직 없다**: `build_independent_truth_sets.py`와 `truth/deterministic.py`는 해시 정렬이라 순서와 무관하지만(`mergesort`, `truth_id` 동점 해소), 고정 사본이 커밋되지 않아 `run_mode`가 push에서는 `skip`, 수동 실행에서는 UNFROZEN으로 돈다. 과제 자에서 만든 동결 절차를 아직 아무도 돌리지 않았다는 뜻이고, `truth/generated/*_truth.csv`는 2.61.9 이전의 옛 목록이다. (이건 자 보고서의 "워크플로 실행은 검토 세션에 요청"과 같은 사안이다.)

### 2.6 이번에 확인하지 못한 것

* 서버가 `ORDER BY` 없이 실제로 다른 순서로 답하는지(미러 전환 `throttle.install()`이 바꿀 수 있다는 것은 코드로만 확인).
* 빌더가 돌 때 후보 풀이 캡을 넘는지(예: DESI lines, ASAS-SN 개체수). 워크플로 로그가 저장소에 없다.
* 에이전트가 읽은 소비자 연결("커밋본을 읽는다")은 `grep` 결과이고, 나는 위 2.2의 줄 인용과 워크플로 트리거·커밋 단계만 직접 확인했다.
* `xray_rules`(10번)의 입력(`all.pkl`, HamStar 내려받기)과 `build_agb_*`의 서버 순서는 저장소에 없다.
* 읽지 못한 것: `validation-data` 브랜치의 묶음, `Get_data/sdss_spectroscopy.py`의 `_lines`, 요청 범위 밖 `build_*`(일부 에이전트 확인 대상 아님).

### 2.7 고치는 방향 후보 (표를 본 뒤 정할 것 — 아직 아무것도 고치지 않았다)

| 우선 | 대상 | 후보 | 비용·주의 |
|---|---|---|---|
| 1 | 표 2.2의 1·2번 (덮어쓰기 경로) | 재생성이 커밋본을 덮어쓰지 못하게 하고(예: 기존 목록과 비교해 다르면 실패, 또는 새 이름으로 저장) 산출물에 정렬·해시를 박는다 | 가장 작고 가장 효과가 크다. 빌더 자체는 안 고쳐도 사고(2026-10-14 같은)를 막는다 |
| 2 | 위치 번호 ID | 내용 해시 ID(`star_diverse`는 이미 그렇다, :125)로 바꾸고 분할을 그 해시로 | 기존 `benchmark_id`와 커밋된 `catalog_features` 이름을 모두 바꿔야 해서 크다. 한 번에 하지 않으면 두 체계가 섞인다 |
| 3 | 3·4·5·6·7번의 구성 | 서버 순서와 무관하게 정렬 키(고유 ID)로 `sort_values` 뒤 `head`/`sample` | 목록 내용이 한 번 바뀌므로 새 목록으로 모든 수치를 다시 재야 한다(목록 교체는 과제 자의 동결 절차를 통해) |
| 4 | LAMOST 정상 별의 계열 편향(2.3절) | 계열별로 `head`가 아니라 같은 수를 뽑는 구성 | 구성 오류(순서와 별개) |

번호 제안: 이 조사는 코드를 바꾸지 않으므로 PATCH(`2.63.2`). 과제 하가 같은 브랜치에서 이어지므로 그쪽은 `2.63.3` 이후로 매긴다(병합 순서에 따라 검토 세션이 다시 매긴다).
