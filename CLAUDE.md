# Project rules

## 목적
관측 가능한 전 파장대역의 관측 데이터를 종합해 대상 천체를 식별하고 분류하는 분류기를 만든다.

## 작업 규칙
1. **과학적 근거 우선**: 파이프라인 단계, 임계값, 규칙, 모델을 만들거나 바꾸기 전에 문헌/카탈로그 문서 등 과학적 근거를 먼저 조사하고, 그 근거를 코드 주석이나 `LITERATURE*.md`에 남긴다.
2. **정확도와 속도 모두**: 대상 분류는 정확도와 처리 속도를 함께 개선하는 방향으로 설계한다. 한쪽을 희생하는 변경은 근거와 측정치를 함께 제시한다.
3. **v2 기준**: 전체 작업은 `v2/`를 기준으로 한다. `legacy/`는 참고용이다.
4. **수정·확장 우선**: v2를 수정·확장하는 것이 기본이며, 필요하면 구조를 갈아엎는 것도 허용한다.
5. **Standalone 앱은 허락 필수**: 분류기 알고리즘이 완성되면 PC에서 구동하는 standalone 앱으로 만든다. 앱 작업을 **처음 시작할 때는 반드시 사용자 허락을 먼저 받는다.**
6. **작업 보고서에는 설계 이유 포함**: 작업 보고서(`v2/WORK_REPORT_*.md`)에는 결과·오류뿐 아니라 **왜 그렇게 코드를 짰는지**(구조 선택, 대안과 버린 이유, 성능·정확도 영향)를 함께 적는다.
7. **버전별 변경 이력**: main에 병합할 때마다 `v2/VERSION`을 올리고 `v2/CHANGELOG.md`에 그 버전의 변경 사항·이유·측정치를 적는다(MINOR: 결과·기능 변화, PATCH: 결과가 같은 수정·정리).

## 작업 메모 (개발 환경)
- 테스트: `cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests` (앱 시험 포함: 연관 회귀를 잡는 유일한 통합 시험)
- Coarse 벤치마크(로컬, 네트워크 불필요): 보존된 특징 `v2/benchmark/catalog_features/*.gz` 사용
  - `python v2/benchmark/validate_catalog_truth.py --truth v2/benchmark/truth_data/ground_truth.csv --catalog-root v2/benchmark/catalog_features --out /tmp/ready`
  - `python v2/benchmark/evaluate_rule_baseline.py --truth v2/benchmark/truth_data/ground_truth.csv --catalog-root v2/benchmark/catalog_features --manifest /tmp/ready/benchmark_manifest.csv --out /tmp/eval`
  - 융합 가중치 재학습: `python v2/benchmark/fit_fusion_weights.py ...` (train split만 사용, test는 보고용)
- 클라우드 세션 컨테이너는 천문 데이터 서비스(Gaia/VizieR/MAST 등)에 직접 접속할 수 없을 수 있음 → 데이터가 필요한 검증은 GitHub Actions 워크플로로 실행하고 로그/커밋으로 결과를 받는다.
- `Build Catalog Truth Features`(13 jobs, 수 시간)는 2.6.4부터 수동 실행 전용이다(`v2/Get_data/*.py`를 바꿔도 자동 실행되지 않음). 벤치마크 재수집이 필요할 때만 workflow_dispatch로 실행한다.
- 데이터를 커밋하는 워크플로는 `.github/scripts/push_with_retry.sh <branch>`로 push한다(동시 push 경합 시 rebase 후 재시도). 실행한 브랜치(`github.ref_name`)를 checkout하고 그 브랜치에 push한다.
- 수집 결과 캐시(2.9.1): `V2_CACHE_DIR`(기본 `~/.cache/finding_objects/v2`), `V2_CACHE=0`으로 끔. Gaia 릴리스는 `V2_GAIA_RELEASE`(기본 DR3), 전환 전 `python v2/Get_data/check_gaia_release.py --release DR4`.
- 독립 정답 검증(2.35.0, 100개 영역 2.36.3): `v2_independent_truth.yml`(workflow_dispatch, mode=fields, only=영역명)을 **`validation-data` 브랜치에서** 실행해 수집하고, 원자료는 그 브랜치에만 둔다(233 MB, main에는 점수표·보고서만). 채점은 원자료를 받아(`v2/benchmark/independent_fields/README.md`) `python v2/benchmark/score_independent_fields.py --which blind --out DIR`(blind = 분광·문헌 목록 제외, 독립 검증 수치).
