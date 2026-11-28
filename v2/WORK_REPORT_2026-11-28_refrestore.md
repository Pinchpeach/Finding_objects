# 작업 보고서 2026-11-28 (2.62.11): 2.46.1 참조 천체 목록을 되살리고 SHA-256으로 고정

이 판은 PATCH다. 분류 코드, 모델, 검증 점수는 그대로이고, 커밋된 참조 목록 한 표만 그 검증 계획이 뽑힌 판으로 되돌린다.

## 1. 무엇을 왜

* **문제**(과제 머, `benchmark/doc_claims/README.md` 1.1):
  * 520개 검증 계획(`reference_objects/validation/plan.csv`) 중 54개가 지금 공개 목록 `reference_objects.csv.gz`에 없었다.
  * 계획은 2.46.1(85f8853)의 목록에서 뽑혔다. 그런데 2.46.2(a6d47e1) 병합에서 목록이 다시 만들어졌다. VizieR 질의가 `row_limit`만 있고 정렬이 없어서, 큰 종류 7개에서 1,686행이 다른 천체로 바뀌었다.
  * 그래서 README·개요의 "520 literature-confirmed objects"는 점수는 맞지만, 54개를 공개 목록에서 따라갈 수 없었다.
* **검토 세션의 요청 1**: 2.46.1 목록을 되살려 SHA-256으로 고정한다. 단, 먼저 git으로 그대로 되살릴 수 있는지와 그 목록을 읽는 소비자를 확인하고 판단한다.
* **판단: 되살린다.** 근거는 아래 2절이다.
  * 85f8853 뒤로 두 파일을 바꾼 커밋은 a6d47e1 하나뿐이다.
  * 내용을 읽는 소비자 중 결과가 바뀌는 것이 없다.
  * 무엇보다 계획을 뽑는 절차를 되살린 목록에 다시 돌리면 커밋된 `plan.csv`가 바이트 그대로 나온다.

## 2. 확인한 것

| 확인 | 결과 |
|---|---|
| git 이력 | `git log 85f8853..d8d9ab8 -- v2/reference_objects/reference_objects.csv.gz v2/reference_objects/REFERENCE_OBJECTS.md` = a6d47e1 하나 |
| 되살린 파일 | `git checkout 85f88537 -- …` 두 파일, gzip SHA-256 `b9cae15bdf05d356ea59681e30b7d00424b650c0470f1fcc159ee4ad117b02e2`(`git show 85f88537:…`와 같음), 355,276 바이트, 14,108행 |
| 두 목록 | 행 수·종류별 개수 같음, 1,686행이 다른 천체 |
| 계획의 재현 | `validate_reference_objects.py plan`(종류마다 10개, `random_state=7`, 26 shard)을 되살린 목록에 돌리면 `plan.csv`와 **바이트 그대로 같다**. 2.46.2 목록에 같은 절차를 돌리면 520행 중 430행만 같다. |
| 매니페스트 | `truth_manifest.py build` → `truth_tables_manifest.json`에서 `reference_objects` 항목의 `sha256`·`bytes`만 바뀜(다른 13개 표 그대로), `verify` 14개 OK |
| 문서 수치 점검 | `doc_claims_check.py` 다시 실행: `ref520_in_list`가 `differs`(466 of 520)에서 `ok`(520 of 520)로 바뀜. 나머지 29개는 그대로 |

소비자(내용을 읽는 것)는 다음과 같다.

* `validate_reference_objects.py`: plan 모드만 목록을 읽는다. run과 score는 `plan.csv`의 좌표·이름을 쓴다. 그래서 520개 검증(blind 89.5 % / 45.8 %, full 87.9 % / 55.0 %)은 이 목록이 바뀌어도 그대로다.
* `doc_claims_check.py`: 위 표처럼 판정 하나가 바뀐다. 시험 `test_reference_validation_scores_recount_exactly_and_the_plan_is_inside_the_restored_list`가 새 상태를 지킨다.
* `server_fill/server_fill_dependence.py`: 2026-11-28 날짜가 붙은 연구다. 그 보고서 3절과 `reference_footprint.csv`는 2.46.2 목록을 잰 것이다. 목록이 서버 순서에 따라 바뀐다는 것이 바로 그 연구의 요점이라 다시 돌리지 않았다.
* `document/overview_content.py`: 종류 수·개수만 쓴다(두 목록에서 같다).
* 매니페스트만 보는 것: `truth_manifest.py`, `build-reference-objects.yml`. 워크플로는 2.62.7부터 커밋된 표를 덮어쓰지 않고 `reference_objects_regenerated/`에 쓴다.

## 3. 설계 이유와 버린 대안

* **새로 뽑지 않고 되살린 이유**:
  * 목록을 지금 다시 만들면, 정렬 없는 `row_limit` 때문에 또 다른 1,686행 근처가 바뀔 수 있다. 그러면 계획 520개와의 관계가 더 나빠진다.
  * 계획·검증·점수가 모두 2.46.1 목록을 기준으로 만들어졌으므로, 그 판을 공개 목록으로 두는 것이 기록 사이의 일관성을 되찾는 가장 작은 변경이다.
* **계획을 2.46.2 목록에서 다시 뽑고 다시 검증하는 대안은 버렸다**:
  * 520개 검증을 다시 돌려야 한다. 천체별 수집이라 네트워크와 시간이 든다.
  * 점수의 비교 기준(2.47.0)도 바뀐다.
  * 2.46.2 목록이 더 나은 목록이라는 근거도 없다. 같은 질의를 다른 시각에 돌린 결과일 뿐이다.
* **고정 방식**: 2.62.7의 `truth_tables_manifest.json`을 그대로 쓴다.
  * `build`는 사람이 결정해서 같은 커밋에서 돌리는 행위다.
  * 파일이 바뀌었는데 매니페스트가 그대로이면 `test_truth_manifest.py`가 실패한다.
  * 별도의 고정 장치를 만들지 않은 이유: 이미 14개 표를 같은 방식으로 지키고 있어서, 한 표만 다른 방식을 쓰면 확인 경로가 둘이 된다.
* **문서 처리**:
  * `NEXT_RELEASE_DOCS.md` 14번과 8번은 지우지 않고 "2.62.11에서 처리"를 적었다. 문서의 "520 literature-confirmed objects"는 이제 맞으므로 다음 릴리스에서 고치지 않아도 된다.
  * `doc_claims/README.md`는 병합된 2절 표를 그대로 두고 4절을 덧붙였다. 지금 값은 `doc_claims_table.md`에 있다.

## 4. 정확도·속도 영향

분류 정확도, 처리 속도, 모델 모두 변화 없다. 바뀌는 것은 공개 목록의 1,686행(어느 천체가 목록에 있는가)과 문서 점검 판정 하나다.

## 5. 시험

`cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests` 결과와 CI는 PR에 적는다. 바뀐 시험은 `test_doc_claims_check.py`의 한 시험이다. 옛 상태(466 of 520, `differs`)를 확인하던 시험을 되살린 상태(520 of 520, `ok`)로 바꿨다.
