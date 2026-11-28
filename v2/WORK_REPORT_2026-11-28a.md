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

## 2. 과제 파 — 조사 결과 (아래에서 채움)
