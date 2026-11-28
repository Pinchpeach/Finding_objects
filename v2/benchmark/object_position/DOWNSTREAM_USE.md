# 객체 좌표(`ra`, `dec`)가 하류에서 쓰이는 곳 (과제 버, 2026-11-28; `grep` 전수 + 실행 확인)

출력 좌표만 바꾸고 판정은 바꾸지 않으려면 좌표를 쓰는 모든 곳이 **앵커 좌표로 먼저 끝나야** 한다. 그래서 `V2_OBJECT_POSITION=best`는 `pipeline.py`의 후처리가 모두 끝난 뒤 `classified_objects.csv`를 쓰기 직전에 한 번만 `ra`·`dec`를 바꾼다(`object_position.apply`). 아래는 객체 좌표를 읽는 곳의 목록이다(행 번호는 이 커밋 기준).

| 어디서 | 무엇에 쓰나 | 켜면 | 이유 |
|---|---|---|---|
| `Preprocess/01_source_association.py` 전체 | 연관: **검출 행**의 좌표로 후보·점수를 계산하고 앵커의 `ra`/`dec`를 `object_ra`/`object_dec`로 내보냄 (`:685-686`) | 그대로 | 객체 좌표를 읽지 않는다(입력은 검출). `object_id`는 순번(`:590`, `OBJ%06d`)이라 좌표에서 안 만든다 |
| `Preprocess/02_integrate_objects.py:98-113` | 큰 은하(SGA) 타원 안의 객체에 `host_large_galaxy` 표지(타원 반경) | 그대로 | 앵커 좌표로 계산한 뒤 |
| `…02_integrate_objects.py:201-209` | 객체 `ra`/`dec` = 그룹의 `object_ra`/`object_dec` | 그대로 | 이것이 "앵커 좌표"의 출처 |
| `Preprocess/05_likelihood_vectors.py:479`(`latitude_factor`), `:538`·`:553`(마젤란 구름 사전확률) | 은위도·마젤란 구름 안의 사전확률(연속 함수) | 그대로 | 5단계에서 끝남 |
| `Preprocess/lowlat_qso.py:107,175`, `faint_class_prior.py:123`, `sparse_priors.py:67`, `nir_star.py:59`, `qso_options.py:227` | 저위도 QSO 제한(`|b|` < 20°), 어두운 별:은하 사전확률, 희박 사전확률, 근적외 별 규칙 | 그대로 | 3–5단계에서 끝남 |
| `Classifier/subclass.py:276`(`_galactic_lb` → 시선 방향 먼지 앞 분율), `Classifier/axes/compact.py:59`(**펄서 사후확률의 `|b| < PSR_PLANE_B` 문턱**) | 하위 분류·펄서 | 그대로 | 7단계에서 끝남. 좌표를 바꾸면 문턱 근처의 객체가 뒤집힐 수 있으므로 이 때문에 위치를 마지막에 바꾼다 |
| `host_groups.py:155,355-401,526,612-639` | 숙주 은하 묶음, PS1·LS 조각 붙이기, 밝은 별 후광 인공물(각거리 반경) | 그대로 | 앵커 좌표로 끝남 |
| `designations.py:115`(`separation_arcmin`, 원뿔 자르기, 정렬) | 검색 중심으로부터의 거리와 정렬 | **앵커 좌표 기준 그대로** | 표시 좌표와 `separation_arcmin`이 최대 `position_shift_arcsec`(깊은 영역 99백분위 < 1.5″ = 0.025′)만큼 어긋날 수 있다. 문서화한 한계 |
| `designations.py` 이름 | 대표 이름은 목록의 식별자에서 온다(`object_name`), 좌표에서 안 만든다 | 그대로 | `object_id`와 `designation`이 안 바뀐다 |
| `detection_quality.py:47`, `radio_sources.py:103`, `clusters.py:58,84`, `high_confidence.py`, `catalog_coverage.py` | PS1 단독 인공물, 전파 단독 천체, 은하단 구성원, 고신뢰, 커버리지 | 그대로 | 후처리가 끝난 뒤에 위치를 바꾼다. 커버리지는 검색 중심이지 객체 좌표가 아님 |
| `summary.py` | `objects_summary.csv`의 `ra`/`dec`(+ `position_source`) | **바뀜(의도)** | 새 열 `position_source`만 요약에 더했다(스위치를 끄면 열이 없다) |
| `app/qt_models.py`, `qt_widgets.py`(`SkyMap`), `qt_bookmarks.py` | 표 열, 하늘 지도, 책갈피에서 그 위치로 다시 검색 | **바뀜(의도)** | 지도·책갈피는 표의 `ra`/`dec`를 읽으므로 더 정밀한 위치로 그려진다. 앱은 `ra_anchor` 등을 모른다 |
| 소광 E(B−V) | `Classifier/subclass.py:240`은 `std_ebv`(목록 열)를 읽는다. 객체 좌표로 지도를 찾는 곳은 **없다** | 해당 없음 | 수집기가 검색 중심·반경으로 받아 온 열 |
| `object_id` | 순번 | 그대로 | |

확인: 스위치를 켜고 끈 전체 파이프라인의 `classified_objects.csv`를 NGC 4522 12′(89개 객체; `Preprocess/tests/test_object_position.py`)와 깊은 COSMOS 26개 영역에서 열 단위로 비교했다(결과 `results_2026-11-28/invariance.csv`).
