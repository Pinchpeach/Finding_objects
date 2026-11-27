# 작업 보고서 2026-11-27g — 과학 교차 검증 워크플로의 재현성 (2.61.9)

계획 세션 지시서 과제 자(19:45 UTC) + 덧붙임(21:51 UTC: 동시 봇 커밋 충돌, "Unit tests" 단계가 모으는 시험 수). 워크플로 `v2 scientific cross validation`은 실행마다 독립 정답 표본을 서비스에서 다시 만들고, 같은 실행이 보정 계수 `models.json`을 다시 맞춰 main에 봇 커밋한다. 그래서 판 사이 수치를 비교할 수 없고, 코드가 안 바뀌어도 배포되는 계수가 바뀐다. 원인을 git 이력과 실행 로그로 확인하고 고쳤다.
**워크플로는 이 컨테이너에서 실행하지 못했다**(VizieR에 닿지 않고 Actions를 돌릴 수 없다). 동결 목록 만들기와 기준선 측정은 검토 세션이 해야 하고, 순서는 §7에 적었다.

## 1. 한 줄 결과

- **정답 표본이 흔들리는 이유**: 질의에 `ORDER BY`가 없다. VizieR에 `row_limit=250`만 걸어 "서버가 먼저 주는 250행"을 쓰고, 채점 쪽은 `DataFrame.sample(random_state=42)`로 다시 뽑는다. 시드는 입력 행의 집합·순서가 같을 때만 같은 천체를 고른다. 2026-10-26 ~ 11-27의 봇 커밋 25개 동안 **변광 4개 등급은 표본이 6~7가지**(세페이드 6, LPV 7, 미라 6, RR Lyrae 6), 펄서 3가지, 초신성 2가지였고 적색거성·PN은 1가지였다. 가장 흔한 표본이 나온 건 25회 중 14~17회다.
- **장애도 별개로 수치를 흔든다**: PN 표본은 25회 내내 **같은 집합 하나**인데 정확 일치율이 0.000 ~ 0.892로 움직였다(§2.4). 낮은 값 대부분은 수집기 오류 기록이 없는 "빈 응답"이어서 오류 상태만으로는 못 잡는다.
- **`models.json`은 예측 파일의 결정적 함수다**(커밋된 예측 파일로 재적합하면 8개 봇 커밋 모두 커밋된 파일을 그대로 재현). 그래서 계수가 바뀐다는 것은 표본이나 아카이브가 바뀐 것이다. 계수는 `*_reliability` 출력 열에만 쓰이고(주 라벨·`high_confidence`를 읽는 코드는 없다) 25개 커밋 중 19번 연속 커밋 사이에 바뀌었다(LPV, RR Lyrae 모두).
- **지금 main의 `models.json`은 장애 실행의 산출물이다**(411ba89: RR Lyrae 계수 0.309, n = 215). 가장 흔한 상태는 1.366, n = 221(9/25회). RR Lyrae 신뢰도가 점수 0.9에서 **0.153**(지금 배포) 대 0.358(흔한 상태)이다. LPV는 0.866으로 같다.
- **병합 실패(run 46050644800)의 원인**: 이 워크플로가 `push_with_retry.sh`를 쓰는데도 `models.json`과 예측 파일에서 같은 내용 충돌이 6번 연속 났다. 재시도는 푸시 경쟁은 풀지만 내용 충돌은 못 푼다. `concurrency` 그룹은 실행을 줄 세울 뿐 대기하던 실행이 앞 실행의 봇 커밋을 체크아웃하게 만들지는 않는다.
- **고침**: 동결된 정답 목록(결정적 선택 + 매니페스트 SHA-256), 수집 오류 행 재평가 + DEGRADED 판정(오류·충돌·기준선 대비 커버리지 하락)과 그 실행은 커밋하지 않음, `models.json`을 자동 커밋에서 분리(명시 실행 + `fitted_on` 출처), 충돌은 이 실행의 산출물이 이기게(`PUSH_PREFER=ours`), "Unit tests" 단계를 pytest로(**CI가 도는 Classifier 시험 6 → 97개**).
- **시험**: 전체 537개 통과(새 시험 18개 + Classifier 시험을 CI와 같은 최소 환경에서 돌려 보다가 찾은 시험 1개 수정).

## 2. 사실 확인 (지시서 1번)

### 2.1 정답 집합을 만드는 질의가 왜 다른 천체를 주는가

| 집합 | 카탈로그와 질의(2.61.8까지) | 25개 봇 커밋 동안 서로 다른 표본 |
|---|---|---|
| RGB, AGB | Vrard+2025 `J/A+A/697/A165/table4`, `row_limit=5000`, 앞에서 250 | 1, 1 (표 전체가 한 번에 와서 안정) |
| 변광 | ASAS-SN `II/366/catv2021`, 유형(RRAB, RRC, DCEP, DCEPS, M, SR)마다 `row_limit=250` | 세페이드 6, LPV 7, 미라 6, RR Lyrae 6 |
| 펄서 | ATNF `B/psr/psr`, `row_limit=250` | 3 |
| PN | Acker `V/84/main`, `row_limit=250` | 1 |
| 초신성 | Asiago `B/sn/sncat`, `row_limit=1250` 뒤 앞에서 250 | 2 |

- 질의에 정렬 키가 없다. ADQL 2.1은 "The order of the rows MAY be arbitrary unless an ORDER BY clause is specified"(2.2절, 원문 확인)이고, 일반 SQL 문서(Snowflake, Microsoft, Percona)도 같다.
- 채점 쪽 `sample_truth`는 `g.sample(n=250, random_state=42)`다. 고정 시드는 같은 입력에서만 같은 표본이다. 세페이드와 RR Lyrae는 두 유형을 합쳐 500행에서 250을 뽑는다.
- 표본이 이산 상태 몇 개로만 나온다는 사실은 "서버/미러가 몇 가지 순서 중 하나로 답한다"와 맞다. **어느 미러가 어느 순서를 줬는지는 이 컨테이너에서 VizieR에 닿지 않아 확인하지 못했다.** 집합이 안정한 카탈로그(RGB, AGB, PN)는 한 번에 표 전체를 주거나 서버 순서가 안정한 것으로 보인다.

### 2.2 봇 커밋으로 main에 들어가는 산출물 (워크플로의 `aggregate` 마지막 단계)

`v2/Classifier/validation/independent_truth/`(예측 CSV, 요약 CSV, 마크다운), `REAL_SAMPLE_VALIDATION.md`, `real_sample_validation.csv`, **`v2/Classifier/calibration/models.json`**. 2.61.9 전에는 이 넷이 한 커밋으로 나갔다.

### 2.3 `models.json`의 어느 계수가 분류 출력에 쓰이나

- 읽는 코드는 `calibration/per_axis.py` 하나(`control_axes.py`가 호출)다. Platt 계수(`coef`, `intercept`)는 표본이 충분한 클래스(n ≥ 100, 양성·음성 ≥ 20)에서 `{축}_reliability`를 `sigmoid(coef·점수 + intercept)`로 만들고, `rules`의 `precision`은 규칙별 `{축}_reliability`가 된다. 열 `*_reliability_status/_method`도 이 파일에서 정해진다(`NO_MODEL`, `INSUFFICIENT_TRUTH`, `AGREEMENT_TARGET_SET`…).
- **주 라벨·`high_confidence`·2차 라벨을 이 열에서 읽는 코드는 없다**(저장소 전체 검색: `per_axis.py`, 시험, `ALGORITHM.md`뿐). 실제 COSMOS 출력(`classified_objects.csv`)에서는 이 열이 전부 NaN, 상태 `NO_MODEL`이다.
- 그러므로 "판 번호 없이 출력이 바뀐다"는 것은 **변광 등급 객체(RR Lyrae, LPV 등)의 신뢰도 숫자**가 바뀐다는 뜻이다. 라벨은 안 바뀐다.
- Platt 입력 `n`은 `raw_score`가 있는 행 수라서(`fit`이 점수 없는 행을 버린다), 수집 실패로 점수가 없는 행이 늘면 `n`(221 → 215)과 계수가 같이 움직인다.

### 2.4 지난 봇 커밋에서 얼마나 움직였나 (`validation/reproducibility/`)

| | 값 |
|---|---|
| 봇 커밋 | 25개(2026-10-26 ~ 2026-11-27) |
| LPV Platt 계수 | 2.627 ~ 3.285, 서로 다른 적합 18개, n 197 ~ 231 |
| RR Lyrae Platt 계수 | **0.309 ~ 2.319**, 서로 다른 적합 20개, n 197 ~ 231 |
| 연속한 두 봇 커밋 사이에서 계수가 바뀐 횟수 | 24번 중 19번(LPV, RR Lyrae 모두) |
| 가장 흔한 상태 | LPV 3.181 / RR Lyrae 1.366, n = 221 (9/25 커밋) |
| 출력 신뢰도 폭(점수 0.9) | RR Lyrae **0.153 ~ 0.578**, LPV 0.818 ~ 0.899 |
| 사용 가능 여부가 오락가락 | 세페이드 Platt는 25번 중 1번만(n = 231), 미라는 5번(계수 0.0으로 퇴화) |
| 수집기가 오류를 낸 봇 커밋 | 25번 중 9번(오류 행 1~250개) |
| 정확 일치율 폭 | 세페이드 0.888~0.932, LPV 0.616~0.668, 미라 0.896~0.948, RR Lyrae 0.804~0.828, **PN 0.000~0.892** |

(정확 일치율 폭에는 그 기간의 코드 변경도 섞여 있다. PN 표본은 25회 모두 같은 집합이라 PN의 폭은 순수하게 아카이브 상태다.)
- **PN**: 같은 250개 천체인데 HASH 수집이 성공한 정도에 따라 0.468·0.500·0.612·0.632… 로 나왔고, 정확 일치율이 0.892보다 낮은 15개 실행 중 수집기 오류 기록이 있는 것은 7개뿐이다(0.468인 6006f8a는 오류 행 0). 수집기가 오류 대신 빈 응답을 주면 분류기가 기권한 것처럼 보인다.
- **결정적 함수 확인**(`refit_check.csv`): 8개 봇 커밋(8daf15d, e19159e, 411ba89, 13be466, f1f38dd, 766db6d, e6d079a, cf4ad77)에서 커밋된 예측 파일로 재적합하면 커밋된 `models.json`과 모든 수가 같다(다른 작업이 잰 `external_source` 규칙은 기존 파일에서 이어받는 규칙이라 재적합을 기존 파일 위에서 한다).

### 2.5 병합 충돌 (run 46050644800, 2026-11-27)

`aggregate` 작업의 "Commit validation products"가 4분 28초 뒤 실패했다. 로그: 매 시도마다 `Auto-merging models.json … CONFLICT (content): Merge conflict in v2/Classifier/calibration/models.json`과 같은 형태의 `independent_truth_predictions.csv` 충돌, 6번 시도 뒤 `push to main failed after 6 attempts`.
- `push_with_retry.sh`는 이미 쓰고 있었다. `git pull --rebase` 뒤 `git push`를 6번 시도하는데, 같은 파일의 같은 줄을 다른 실행의 봇 커밋이 먼저 바꿨으면 리베이스 충돌이 매번 같게 나서 재시도로 풀리지 않는다.
- `concurrency`(`v2-scientific-cross-validation-${{ github.ref }}`, `cancel-in-progress: false`)는 있었지만 실행을 줄 세울 뿐이다. 대기하던 실행은 `ref: ${{ github.sha }}`(자기를 일으킨 커밋)를 체크아웃하므로 앞 실행의 봇 커밋을 안 담고, 같은 파일을 통째로 다시 쓴다.

## 3. 고침과 설계 이유

**3.1 정답 목록: 순서와 무관한 결정적 선택 + 고정 파일 + 매니페스트** (`truth/deterministic.py`, `build_independent_truth_sets.py`, `truth/README.md`)
- 선택 규칙: 클래스마다 후보에 `SHA-256("independent-truth-v1|<truth_id>")`를 붙여 가장 작은 250개를 고른다(bottom-k). 후보의 순서를 어떻게 섞어도 같은 천체가 뽑히고, 뽑히지 않은 후보가 빠지거나 더해져도 선택이 안 바뀐다. 시드는 상수로 코드에 기록한다(Sandve et al. 2013, Rule 6: 난수 시드를 기록).
- 질의는 표 전체를 받는다(`row_limit=-1`). 서버가 임의의 지점에서 자르지 못하게 한다. 유형 질의가 실패하면 예외를 낸다(전에는 `continue`로 그 등급이 조용히 사라졌다).
- 목록은 `truth/fixed/`에 커밋하고 `truth_manifest.json`(파일 SHA-256, 클래스별 행 수와 id 집합 해시)을 둔다. 워크플로는 `--verify`로 확인한 파일을 쓰고 VizieR에 정답을 묻지 않는다. 목록 자체의 변경은 사람이 판을 올려 커밋한다(Sandve Rule 3의 취지: 쓰는 입력을 정확히 기록).
- **버린 대안**: (a) VizieR 질의에 정렬 키를 붙이기 — astroquery의 정렬 구문이 서버에서 같은 효과를 내는지 이 환경에서 확인할 수 없고 서버 판이 바뀌면 다시 흔들린다. 전체 표를 받아 로컬에서 정렬·선택하면 규격이 보장한다. (b) 시드 `sample` 유지 — 입력 집합·순서에 종속. (c) 목록을 커밋하지 않고 해시만 비교 — 틀리면 어떤 목록이어야 했는지 알 수 없다.
- **하지 못한 것**: 동결 목록 자체. 만들려면 VizieR 전체 표(ASAS-SN은 유형당 수만 행)를 받아야 하는데 이 컨테이너에서는 안 된다. 그래서 `fixed/`가 없으면 워크플로가 같은 결정적 목록을 그 자리에서 만들고 실행을 **UNFROZEN**으로 표시한다(결정적이라 나중에 동결할 목록과 같다). `truth/generated/`는 2.38.0 때 것이라 낡았고(적색거성 180행, SN 101행 vs 현재 250/203/250) 시작점으로 못 썼다.

**3.2 DEGRADED 판정과 재평가** (`validate_independent_truth_sets.py`: `archive_errors`, `retry_errors`, `run_status`, `coverage_drops`)
- 수집기가 예외를 내면 로그에 `status: error`가 남는다. 다른 수집기가 모두 비면 행은 `NO_EVIDENCE`→UNKNOWN이 되어 장애가 분류기의 기권으로 보인다. 이런 행을 같은 실행 안에서 한 번 더 평가하고(`--retry-errors 1`), 그래도 오류가 남거나 평가가 죽은 행이 있으면 실행을 **DEGRADED**로 표시한다.
- 오류 기록이 없는 빈 응답(§2.4 PN)을 잡으려고 **기준선 대비 커버리지 하락**도 DEGRADED로 본다: `truth/fixed/baseline_coverage.json`(동결 목록으로 한 번 잰 클래스별 분류 비율)보다 0.05 넘게 낮은 클래스가 있으면. 올라간 것은 문제가 아니다. 허용치 0.05는 첫 값이다(정상 실행의 변광 4개 등급 변동폭이 ±0.01이었다. PN·AGB·RGB는 이력에 코드 변경이 섞여 변동폭을 이력만으로 못 정했다). 기준선 파일이 없으면 이 판정은 건너뛴다.
- DEGRADED 실행은 **산출물을 커밋하지 않고** 아티팩트(`degraded-validation-products`)로만 올린다. 보고서 맨 위에 배너와 사유를 쓴다. `commit_degraded` 입력으로 강제할 수 있다.
- **해석 책임**: 커버리지 하락은 아카이브 장애일 수도 있고 분류기를 바꾼 결과일 수도 있다. 분류기를 바꾼 경우에는 기준선을 손으로 갱신해야 한다(판 번호와 함께). 이 마찰을 일부러 둔 것이다: 조용히 덮어쓰는 것보다 낫다고 판단했다.
- **버린 대안**: 오류가 한 행이라도 있으면 무조건 DEGRADED — 최근 세 봇 커밋 중 둘이 오류 행(5개, 2개)을 가졌으므로 거의 모든 실행이 DEGRADED가 되어 산출물이 갱신되지 않는다. 그래서 재평가 단계를 먼저 둔다.

**3.3 `models.json`을 자동 커밋에서 분리** (`.github/workflows/v2_scientific_cross_validation.yml`, `calibration/fit_axis_calibration.py`)
- 계수가 예측 파일의 결정적 함수이므로 자동 재적합은 "표본과 아카이브의 그날 상태"를 배포 계수로 옮기는 장치다. 워크플로는 이제 `models.json`을 건드리지 않는다. 입력 `refit_calibration`을 켠 명시 실행만 재적합하고, 결과를 아티팩트 `calibration-refit`와 단계 요약(기존 파일과의 차이)으로 남긴다. 사람이 판 번호와 함께 커밋한다.
- 재적합 결과에는 `fitted_on`(정답 목록 SHA-256, 예측 파일 SHA-256, 실행 상태 OK/DEGRADED, 커밋, run id)을 박는다. 어떤 입력에서 나온 계수인지 파일이 말한다.
- **버린 대안**: 자동 재적합은 두고 DEGRADED일 때만 건너뛰기 — 장애가 없는 날에도 새 표본이 들어오면 계수가 바뀌는 문제가 남는다(표본은 동결로 고쳐지지만 아카이브 상태 문제가 남는다).

**3.4 충돌: 이 실행의 산출물이 이긴다** (`.github/scripts/push_with_retry.sh`)
- `PUSH_PREFER=ours`이면 `git pull --rebase -X theirs`(리베이스에서 "theirs"는 되풀이하는 이 실행의 커밋)로 같은 파일 충돌에서 이 실행의 산출물이 이긴다. 이 워크플로의 산출물은 통째로 다시 쓰는 생성 파일이라 맞고, 줄 서는 순서상 마지막에 끝나는 실행이 가장 최근에 트리거된 것이다. 기본 동작은 그대로이고 이 워크플로만 켠다. 실제 `git` 저장소 둘로 충돌을 만들어 시험했다(`test_push_with_retry.py`).
- **버린 대안**: (a) 체크아웃을 최신 main으로 — 트리거한 커밋과 다른 코드로 검증하게 된다. (b) 파일 이름에 run id — 파일이 쌓인다. (c) 별도 브랜치에 커밋 — 검토 흐름이 바뀐다. (d) `concurrency`만 강화 — 대기 중인 실행이 앞 실행의 커밋을 못 보는 문제는 그대로.

**3.5 `aggregate`의 파이썬 조각을 스크립트로** (`aggregate_independent_truth.py`): 워크플로 안의 heredoc은 시험할 수 없어서 스크립트로 빼고 시험했다.

## 4. "Unit tests" 단계가 모으는 시험 (덧붙임 지시)

`python -m unittest discover -s v2/Classifier/tests`는 `unittest.TestCase` 클래스만 모은다. 함수형 pytest 시험은 조용히 건너뛴다.

| 대상 | 존재(pytest 수집) | 2.61.8까지 CI가 돈 수 | 2.61.9 | 어떤 워크플로 |
|---|---|---|---|---|
| `v2/Preprocess/tests` | 423 | 423 | 423 | `test-preprocess.yml` (`pytest`, 경로 `v2/Preprocess/**` 등) |
| `v2/Classifier/tests` | 79 → 97 (새 시험 +18) | **6** (`TestCase` 클래스 하나) | **97** | `v2_scientific_cross_validation.yml` (이제 `pytest`) |
| `v2/Classifier/test_star_diverse.py` | 4 | 4 | 4 | `validate-star-diverse.yml` |
| `v2/app/tests` | 17 | 0 | 0 | **어느 워크플로도 안 돌림** (CI식 최소 환경에서 6개 통과, 11개 건너뜀) |
| 합계 | 523 → 541 | **433 (83 %)** | **524 (97 %)** | |

- 로컬 508(검토 세션 기준)과의 차이 = 위 존재 수와 CI가 도는 수의 차이: CI는 Classifier 시험 73개를 한 번도 돌리지 않았다. 지금은 모두 돈다.
- **pytest로 바꾸며 발견한 결함**: `test_host_groups.py`의 한 시험이 `import host_groups`를 경로 설정 없이 해서 작업 디렉터리가 `v2`일 때만 통과했다(저장소 루트에서 돌리는 CI라면 실패). 같은 파일의 다른 시험처럼 경로로 읽게 고쳤다. CI와 같은 패키지(`pandas numpy astropy astroquery requests scikit-learn pytest`)만 깐 새 가상환경에서 저장소 루트 기준 `pytest v2/Classifier/tests`를 돌려 97개 통과를 확인했다.
- `unittest discover`로도 새 시험 모듈을 불러올 수 있다(검토 세션의 요구): 새 시험은 `pytest`를 모듈 첫머리에서 가져오지 않는다.
- 제안(구현 안 함): `app/tests` 17개를 `build-app.yml`에 넣는다(앱 요구사항이 이미 설치되는 단계). 앱 작업이므로 사용자 허락 규칙에 따라 손대지 않았다.
- **CI가 처음 도는 순간의 위험**: 새 `pytest` 단계가 CI 환경 차이로 실패할 수 있다(로컬 검증은 위 가상환경까지). 처음 한 번은 로그를 확인해 달라.

## 5. 시험 (새 18개 + 수정 1개)

`test_truth_determinism`(5: 순서 무관, 뽑히지 않은 후보는 영향 없음, 아카이브 순서·꼬리가 다른 세 번의 빌드가 같은 바이트, 매니페스트 검증과 변조 탐지, 실패한 집합 → 오류 기록), `test_validation_status`(7: 오류 상태, OK/DEGRADED, 재평가, 배너, 순서 무관 표본, 커버리지 하락, 기준선 쓰기와 읽기), `test_aggregate_independent_truth`(2), `test_calibration_provenance`(2: 행 순서가 달라도 같은 계수, `fitted_on`과 외부 규칙 보존), `test_push_with_retry`(2: 실제 git 저장소 둘로 충돌 해소와 비충돌 경쟁). 시험이 실제 결함을 하나 잡았다: 실패한 집합(빈 CSV)이 있는 목록을 `verify()`가 읽다가 죽던 것(수정함).

## 6. 하지 못한 것 / 한계

- **동결 목록과 기준선은 아직 없다**(§7). 그래서 `fixed/`가 없는 동안 워크플로는 UNFROZEN으로 돈다.
- 새 워크플로를 Actions에서 돌려 보지 못했다. 확인한 것: YAML 파싱, 각 단계의 스크립트 단위 시험, 실제 git 충돌 시험, CI식 환경의 pytest. 확인하지 못한 것: ASAS-SN 전체 표 질의가 시간 안에(`prepare` 60분) 끝나는지, `-X theirs` 가 CI 러너의 git에서 같은 결과를 내는지(로컬 git에서는 확인).
- 아카이브 순서가 흔들리는 정확한 이유(어느 미러가 어느 순서를 줬나)는 못 봤다.
- 커버리지 허용치 0.05는 첫 값이고 정상 실행 변동폭으로 검증되지 않았다(변광 4개 등급만 ±0.01).
- `validate_real_samples.py`의 산출물(`real_sample_validation.*`)은 이 판정에 들어가지 않는다. 같은 장애에 영향을 받을 수 있지만 `independent` 결과가 OK일 때만 커밋하는 것으로 갈음했다.
- 같은 방식의 `build-*-truth.yml` 워크플로 여러 개도 질의 순서 문제를 가질 수 있다(조사하지 않았다).
- `models.json`을 가장 흔한 상태(3.181 / 1.366)로 되돌리지 않았다. 입력 근거 없이 역사 속 한 상태를 고르는 일이 되기 때문이다. 동결 기준선 실행 뒤의 재적합으로 바꾸는 것이 맞다.

## 7. 검토 세션에 요청하는 워크플로 실행 (순서)

1. 이 브랜치가 main에 병합된 뒤 `v2 scientific cross validation`을 **`freeze_truth = true`**로 수동 실행한다(정답 목록만 만들고 아무것도 검증하지 않음). 아티팩트 `frozen-truth-candidate`를 `v2/Classifier/truth/fixed/`에 넣어 `python v2/Classifier/truth/build_independent_truth_sets.py --verify v2/Classifier/truth/fixed`가 통과하면 판을 올려 커밋한다(`list_sha256`을 CHANGELOG에 적는다).
2. **기준선 실행**: 같은 코드, 입력 없이 한 번 실행한다(`push`로 `fixed/` 병합 직후 자동으로 돌기도 한다). 상태가 OK이면 이 실행의 표가 "동결 목록 기준선"이다. 아티팩트 `baseline-coverage-candidate`를 `truth/fixed/baseline_coverage.json`으로 커밋하고 이 표를 보고서 §8에 옮긴다.
3. **재적합**: `refit_calibration = true`로 한 번 더 실행해 `calibration-refit/models.json`을 받아 판을 올려 커밋한다. 지금 main의 `models.json`(장애 실행 산출물)이 이때 바뀐다. 출력(`variability_reliability`)이 RR Lyrae에서 바뀐다(점수 0.9에서 0.153 → 기준선 재적합 값).
4. 기준선 이후 `real_sample_validation` 수치와 `independent_truth_*` 수치는 4개 군에서 이어서 비교할 수 있다.

## 8. 기준선 (동결 목록으로 한 번 잰 값)

**아직 없다.** §7의 2번 실행이 있어야 채울 수 있다. 채울 칸: 클래스별 행 수, 분류 비율, 정확 일치율, 실행 상태, `list_sha256`, 실행 번호.

## 9. 산출물

- 코드: `Classifier/truth/{deterministic,build_independent_truth_sets}.py`, `Classifier/{validate_independent_truth_sets,aggregate_independent_truth}.py`, `Classifier/calibration/fit_axis_calibration.py`, `.github/workflows/v2_scientific_cross_validation.yml`, `.github/scripts/push_with_retry.sh`.
- 표와 도구: `Classifier/validation/reproducibility/`(README, `history_table.py`, `refit_check.py`, `ci_test_inventory.py`, `models_history.csv`, `sample_history.csv`, `sample_states.csv`, `exact_match_range.csv`, `refit_check.csv`, `ci_test_inventory.csv`).
- 문서: `Classifier/truth/README.md`(동결 절차), `ALGORITHM.md`(`models.json` 출처).

## 10. 병합 전 검토 (2.62.0으로 병합)

작업 세션의 2.61.9 후보(e1f9f3c)에 하나를 더하고 판을 올렸다. 2.61.8(#93)을 squash 병합한 뒤 main 위에 이 브랜치를 합쳤다. 남은 변경은 d75b030..e1f9f3c의 변경과 줄 단위로 같다(CHANGELOG 행 순서만 다름).

1. **`models.json`을 411ba89 직전 판(e19159e)으로 되돌렸다**(검토 세션 권고). 그래서 MINOR다. 주 라벨과 high_confidence는 그대로이고 `variability_reliability` 열만 바뀐다.
   - 숫자: RR Lyrae 계수 0.309 → 1.366(양성 26 → 32, n 215 → 221). 점수 0.9의 신뢰도는 0.153 → 0.358이다. LPV 계수는 3.034 → 3.181이지만 점수 0.9의 신뢰도는 0.866으로 같다. PULSATING 항목(withheld)이 다시 들어가고, SOS RR Lyrae 규칙 n은 201 → 196이다.
   - 근거: `sample_history.csv`를 보면 411ba89 실행에서 RR Lyrae 정답 집합이 바뀌었다(250개 중 115개만 이전 집합). 같은 실행에서 AGB 수집기가 VizieR 404를 받았다. 그날 VizieR 스트라스부르는 모든 요청에 404였고(2.61.6 보고서), 미러가 바뀌면 `row_limit`만 있는 질의가 다른 행을 준다는 이 보고서의 진단과 맞는다.
   - e19159e의 RR Lyrae 집합(06c4b5c93f)은 25번의 봇 커밋 중 17번, LPV 집합(0cd45dd292)은 14번 나온 가장 흔한 상태다. 계수 1.366 / 3.181도 연속한 봇 커밋 여러 번에서 같은 값이다.
   - 작업 세션은 "입력 근거 없이 역사 속 한 상태를 고르는 일"이라며 되돌리지 않았다(§6). 그 지적은 맞다. 그래도 장애 실행의 값을 다음 재적합까지 쓰는 것보다 낫다고 봤다. 이 값도 동결 목록 위 재적합(§7의 ③)이 대신한다.
   - **배포 앱 v2.60.2의 `models.json`**(태그 v2.60.2, 앱은 `Classifier/`를 통째로 포함)은 또 다른 날의 표본이다: RR Lyrae 1.307 / −2.080, LPV 2.627 / −0.598, MIRA는 platt 계수 0.0(상수)이다. 다음 릴리스 노트에 "변광 축 신뢰도 보정이 그날의 정답 표본에서 나왔다"고 적을 일이다.
2. **`PUSH_PREFER=ours`의 범위.** 이 워크플로의 "Commit validation products" 단계에만 걸린다. 같은 스크립트를 쓰는 다른 워크플로 42곳은 변수를 주지 않으므로 기본 동작(`-X` 없음)이 그대로다.
   - 이 단계의 커밋에는 이 실행이 통째로 다시 쓰는 세 경로만 들어 있다(`independent_truth/`, `REAL_SAMPLE_VALIDATION.md`, `real_sample_validation.csv`). rebase는 이 커밋만 다시 얹으므로 `-X theirs`가 고르는 충돌도 이 파일들뿐이다.
   - 같은 ref의 실행은 줄을 서고(`cancel-in-progress: false`) 시작 순서대로 끝나므로, 충돌에서 이기는 것은 나중 트리거의 산출물이다.
3. **커버리지 허용치 0.05.** 근거가 약하다는 데 동의한다. 동결 뒤 CDS가 정상인 날 기준선을 3번 재고, 클래스별 분류 비율의 변동폭을 보고 정하는 것을 권한다(예: 관측 최대 폭의 2배). 지금 값은 기준선 파일에 함께 기록되므로(`tolerance`) 바꿀 때 코드를 고치지 않아도 된다.
4. **동결 전 실행의 부담.** `truth/fixed/`가 커밋될 때까지는 경로 조건에 맞는 main push마다 UNFROZEN 실행이 표 전체를 질의한다(ASAS-SN II/366 유형별, Asiago B/sn/sncat 등; 예전에는 `row_limit=250`). `prepare`의 제한은 60분이다. CDS 장애가 길면 이 단계가 시간 초과로 끝날 수 있으니 동결(§7의 ①)을 먼저 하는 편이 낫다.
5. **`real_sample_validation`**은 OK/DEGRADED 판정에 들어가지 않는다(§6에 적힘). 2.61.4 재생성에서 바뀐 것도 SIMBAD 접속 오류 문구뿐이었다. 그 수집 오류도 DEGRADED에 넣을지는 다음 과제 후보다.
6. **`app/tests`는 어느 워크플로도 돌리지 않는다**(`ci_test_inventory.csv`로 확인). 이 PR에서는 넣지 않았다(검토 세션이 따로 정함).
7. **확인**: 전체 시험 539개 통과. 워크플로의 새 "Unit tests" 단계와 같은 명령(저장소 루트에서 `python -m pytest -q v2/Classifier/tests`)은 97개 통과다. 2.61.7의 `unittest.SkipTest` 처리는 pytest로 바뀐 뒤에는 쓰이지 않지만 해가 없어 두었다.
8. **정정(이 세션의 2.61.4 후속 보고)**: 411ba89의 `models.json` 변화를 "LPV 계수 재적합"이라고만 보고했다. 같은 커밋에서 RR Lyrae 계수가 1.366 → 0.309로 크게 바뀐 것을 놓쳤다(diff를 앞부분만 읽었다). 이 보고서 §3의 진단이 맞다.

