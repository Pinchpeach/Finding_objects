# 작업 보고서 2026-11-25c — 검증 워크플로의 NED 동시 조회, SkyServer 한도, astroquery SDSS 디스크 캐시 (2.60.7)

지시서(2026-11-25) 과제 3. 2.60.0 보고서가 "다음 할 일"로 남긴 것이다(벤치마크 워크플로의 NED 동시 질의).

## 1. 한 줄 결과

- NED(초당 1회, **"동시 자동 질의 금지"**, 단일 스레드)를 **matrix 병렬로 묻던 워크플로가 6개**였다(최대 20·26개 job이 한꺼번에). 모두 고쳤다: 블라인드 채점만 하는 두 워크플로(세트 C, A/B 영역)는 NED를 **묻지 않고**(`V2_SKIP_COLLECTORS=blind`), 완전 모드도 필요한 세 워크플로는 기본이 "묻지 않음"이고 `with_ned=true`일 때만 **한 번에 한 job**(`max-parallel: 1`), 연습 점검 워크플로는 `max-parallel: 1`이다. 시험이 이 규칙을 지킨다(`test_service_limits.py`).
- **블라인드 결과는 그대로다.** NED·SIMBAD·분광·문헌 수집기를 건너뛴 수집과 건너뛰지 않은 수집에서 블라인드 입력 파일은 같고(19개 중 17개 바이트 동일, 나머지 둘은 설계상 다른 요약표와 행 순서만 다른 PS1), 블라인드 분류 625개 천체에서 1·2차 라벨·고신뢰·세부 분류 0건, 확률 최대 차이 0.0이다. 수집 시간은 61.2 → 42.4초(NGC 4522 2′).
- SkyServer(분당 60회): 한 job의 `sdss_dr18`은 검색당 3번(스레드 하나, 3–5초 간격이라 1분에 20번이 상한)이라 job 하나는 한도의 3분의 1이다. **여러 job이 같은 IP를 쓰는 경우만** 합이 한도를 넘는다(5절). 코드가 막을 일은 아니고, 러너 IP 공유 여부는 확인하지 못했다.
- astroquery의 SDSS 디스크 캐시: **끈다**(VizieR와 같은 이유, 4절). `_sdss()._request`가 `cache=False`를 강제한다.

## 2. NED를 묻는 워크플로 전체 (전·후)

표 전체: `benchmark/service_limits/workflows_2026-11-25.md`(`workflow_table.py`가 `.github/workflows/*.yml`에서 만든다).

| 워크플로 | job | matrix | max-parallel 전 → 후 | NED 전 | NED 후 | 블라인드 채점이 NED 행을 쓰나 |
|---|---|---|---|---|---|---|
| `v2_locked_set_c.yml` | `field` | 60 | 20 → 20 | 최대 20 job이 동시 | **묻지 않음**(`blind`) | 아니오(블라인드 복사에서 `ned_*` 제외) |
| `experiment-ab-fields.yml` | `field` | 89 | 20 → 20 | 최대 20 동시 | **묻지 않음**(`blind`) | 아니오 |
| `v2_independent_truth.yml` | `field` | 200 | 6 → `with_ned`면 1, 아니면 6 | 최대 6 동시 | 기본 안 묻음, `with_ned=true`면 1개씩 | 아니오(완전 모드만 씀) |
| `v2_independent_truth_b.yml` | `field` | 200 | 6 → 같음 | 최대 6 동시 | 같음 | 아니오(완전 모드만) |
| `validate-reference-objects.yml` | `run` | 26 | 26 → `with_ned`면 1, 아니면 26 | 최대 26 동시 | 기본 안 묻음, `with_ned=true`면 1개씩 | 아니오(블라인드 모드는 `ned_` 제거) |
| `v2_practical_probe.yml` | `field` | 3 | 제한 없음 → 1 | 3개 동시 | 1개씩 | (연습 점검, 채점 아님) |
| `probe-collectors.yml`, `v2_collect_parallel_probe.yml`, `v2_controller_ngc4522_test.yml`, `v2_field_validation.yml`, `v2_r_undetected_cosmos.yml` | 단일 job | 1 | – | 한 번에 한 job | 같음 | – |

- NED 행이 **블라인드 입력에 들어가지 않는다**는 것은 코드로 확인했다: 세트 C·A/B·독립 정답 워크플로의 "Blind raw" 단계가 `ned_*`(와 분광·SIMBAD·BZCAT 등 13개)를 복사하지 않는다. 그러므로 블라인드 채점이 목적인 job은 NED를 요청할 이유가 없었다. 요청은 낭비였고 NED의 "동시 질의 금지"만 어기고 있었다.
- 같은 목록이 네 곳(`controller.BLIND_DROPPED`, 세 워크플로의 `case` 목록, `benchmark/collect_deep_cosmos.py`의 `NOT_BLIND`)에 있어서 시험이 서로 같은지 비교한다.

## 3. 어떻게 고쳤나 (그리고 대안)

- **`V2_SKIP_COLLECTORS`**(`Get_data/controller.py`): 쉼표 목록 또는 `blind`. 건너뛴 수집기는 요청하지 않고 **요약표에도 없다**("실패"나 "빠짐"으로 세지 않는다). 이름 오타는 조용히 NED를 묻는 대신 `ValueError`로 멈춘다(시험).
- 대안과 버린 이유:
  - *블라인드에서 NED 파일만 지우기*: 이미 하던 일이다. 요청 자체는 막지 못한다.
  - *전부 직렬(`max-parallel: 1`)*: 세트 C 60개를 직렬로 돌리면 몇 시간이 걸리고 NED가 필요 없는 job까지 늦춘다.
  - *NED job만 따로 직렬 job으로 분리*: 블라인드 채점이 NED를 쓰지 않으므로 필요 없다. 완전 모드만 `with_ned=true`로 선택하게 했다.
- **의미가 바뀌는 곳**(검토 세션이 알아야 한다): 완전 모드를 쓰는 독립 정답(`v2_independent_truth*.yml`)과 참조 천체(`validate-reference-objects.yml`) 워크플로는 기본이 "NED 없이"라 **완전 모드의 숫자가 이전 완전 모드 숫자와 다를 수 있다**(NED 행의 주석 증거가 없어짐). 독립 검증의 공식 수치는 블라인드(`--which blind`)라 그대로다. 이전 값과 같은 조건이 필요하면 `with_ned=true`로 돌리고 대신 한 번에 job 하나라 오래 걸린다. 완전 모드 숫자가 어느 정도 바뀌는지는 이번에 재지 않았다.

## 4. astroquery SDSS 디스크 캐시

- 문제: `astroquery.sdss.SDSS`의 메서드는 `cache=True`를 **명시해서** 넘기므로 `controller._disable_astroquery_cache()`(전역 스위치)가 듣지 않는다. 그래서 SkyServer 답이 `~/.cache/astropy`에 7일간 남아 우리 `archive_cache`의 규칙(코드 해시, 부분 결과, 폴백의 짧은 수명)과 `V2_CACHE=0`을 모두 우회한다. 2.60.0이 VizieR에서 고친 것과 같은 결함이다.
- 조치: `_catalog_utils._sdss()`의 `_request`를 감싸 `cache=False`를 강제한다. **끄는 쪽을 택한 이유**: 우리 쪽에는 이미 수집기 단위 결과 캐시(`archive_cache`)가 있어 같은 원뿔 재검색은 거기서 나온다. 두 군데 캐시가 겹치면 SkyServer의 답이 갱신(DR 교체, 서버 오류 답)되어도 7일간 낡은 답을 주고 `V2_CACHE=0`의 "차가운 측정"도 깨진다.
- 시험: `test_the_sdss_client_never_uses_astroquery_disk_cache` (메서드가 `cache=True`를 넘겨도 하위에는 `False`가 간다).
- 효과(요청 수): 차가운 검색에서는 같다(검색당 SkyServer 3–6번). `archive_cache`가 있는 반복 검색은 그대로 캐시에서 나오고, 달라지는 것은 `V2_CACHE=0`과 7일 이상 지난 디스크 항목뿐이다.

## 5. 한도 계산 (집계)

공식 속도 한도를 원문으로 읽은 서비스는 **NED(초당 1회, 단일 스레드)와 SDSS SkyServer(분당 60회)**뿐이다(`Get_data/LITERATURE_ARCHIVE_LIMITS_2026-11-23.md`). 나머지(SIMBAD, VizieR, Gaia, MAST, HEASARC, DESI·Data Lab)는 수치를 읽지 못했다.

검색 한 번당 요청(2.60.2 로그 여섯 번): NED 1, SkyServer 4–6(`sdss_dr18` 3 + `sdss_spectroscopy` 1–3), SIMBAD 1–3.

**SkyServer**(분당 60회; 스레드마다 3–5초 대기 → 한 스레드의 상한 12–20회/분)
| 조건 | 계산 | 한도 대비 |
|---|---|---|
| job 하나, 블라인드(`sdss_dr18` 3번) | ≤ 3번/분 | 5 % |
| job 하나, 완전(둘 다 6번까지) | ≤ 6번/분(스레드 둘이라 상한은 40회/분) | 10 % |
| 같은 IP로 나가는 job J개가 동시 시작 | 3J(블라인드) / 6J(완전) | 3J ≤ 60 ⇒ J ≤ 20, 6J ≤ 60 ⇒ J ≤ 10 |
| 세트 C·A/B(블라인드 20 병렬) | 60번/분 | **한도와 같음(여유 없음)** |
| 참조 천체 완전 모드(26 병렬) | 156번/분 | 2.6배(IP 공유 가정에서만) |
| 독립 정답 완전 모드(6 병렬) | 36번/분 | 60 % |

- 위 합은 "한 분 안에 모든 job이 자기 요청을 다 보낸다"는 최악의 경우다. GitHub 호스트 러너가 job마다 다른 IP를 쓰면 job 하나의 계산이 맞다. **러너 IP 공유 여부는 확인하지 못했다.** 과거 워크플로 로그에서 SkyServer 한도 오류가 있었는지는 이번에 조사하지 않았다.
- 조치하지 않았다: 근거(공유 IP)가 확인되지 않았고, 줄이는 방법(`max-parallel` 10 이하, 또는 job 시작 시 0–60초 무작위 지연)은 간단해서 SkyServer 오류가 보이면 바로 쓸 수 있다.
- NED: job 수와 상관없이 **동시 질의 금지**가 한도다. 같은 wave의 job들이 같은 시각에 시작하면 NED(30개 수집기 중 29번째)는 비슷한 시각에 몰린다. 그래서 병렬이면 모두 막았다.

## 6. 블라인드 동일성 실험

NGC 4522, 반지름 2′, 같은 날 두 번 수집(`V2_CACHE=0`, 빈 사용자 캐시): 전체(`V2_SKIP_COLLECTORS` 없음) 대 `blind`(건너뜀). 각각에서 워크플로의 "Blind raw" 단계와 같게 분광·문헌 파일을 빼고 파이프라인을 돌렸다.

| 비교 | 결과 |
|---|---|
| 건너뛴 수집기 | ned, simbad, lamost_spectroscopy, sdss_spectroscopy, desi_spectroscopy, desi_fastspec, bzcat, agb_suh2021, atnf_pulsar, galaxy_clusters (10개) |
| 수집 시간 | 61.2초 → 42.4초 |
| 블라인드 입력 파일 | 19개 중 17개 바이트 동일; `collection_summary`는 다름(30행 대 20행, 설계상); `panstarrs1`은 288행 같은 값, 행 순서만 다름(어느 두 실행 사이에도 생기는 일) |
| 블라인드 분류(625개 천체) | `primary_class` 0, `secondary_class` 0, `high_confidence` 0, `subclass` 0건 다름, p_star·p_galaxy·p_qso 최대 차이 **0.0** |

→ 블라인드 결과는 바뀌지 않는다. (바뀌었다면 NED가 블라인드 입력에 새고 있었다는 발견이었을 것이다. 새지 않는다.)
- 한계: 영역 하나(2′)에서의 실험이다. 코드로는 모든 블라인드 워크플로가 같은 목록으로 같은 파일을 뺀다(시험이 비교).

## 7. 검증 항목

- `Preprocess/tests/test_service_limits.py` 7개: 건너뛰기 이름 규칙·오타 오류·네 곳의 목록 일치·`collect_all`이 건너뛴 수집기를 묻지 않음·**수집기를 돌리는 matrix job은 NED를 건너뛰거나 `max-parallel: 1`일 것**·`with_ned` 입력과 기본값·SDSS `cache=False`.
- 전체 시험은 보고서 마지막에.
- 한계: GitHub Actions에서 실제로 돌려 본 것은 아니다(워크플로 문법은 YAML 해석과 시험으로만 확인). 첫 실행에서 `with_ned` 식(`github.event.inputs.with_ned == 'true' && 1 || 26`)이 숫자로 해석되는지 보면 된다.
