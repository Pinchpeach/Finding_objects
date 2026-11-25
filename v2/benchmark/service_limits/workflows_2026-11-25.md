# 검증 워크플로의 NED·SkyServer 조회 (2.60.8, 2026-11-25)

`python v2/benchmark/service_limits/workflow_table.py [CHECKOUT]`로 `.github/workflows/*.yml`에서 만든 표다. 수집기를 돌리는 job만 담았다(모든 job의 matrix 크기, `max-parallel`, `V2_SKIP_COLLECTORS`, NED가 어떻게 되는지).

## 변경 전 (HEAD 0e80647)

| workflow | job | matrix | max-parallel | V2_SKIP_COLLECTORS | NED |
|---|---|---|---|---|---|
| `experiment-ab-fields.yml` | `field` | 89 | 20 | - | **NED asked by up to 20 jobs at once** |
| `probe-collectors.yml` | `probe` | 1 | - | - | single job |
| `v2_collect_parallel_probe.yml` | `probe` | 1 | - | - | single job |
| `v2_controller_ngc4522_test.yml` | `collect` | 1 | - | - | single job |
| `v2_field_validation.yml` | `field` | 1 | - | - | single job |
| `v2_independent_truth.yml` | `field` | 200 | 6 | - | **NED asked by up to 6 jobs at once** |
| `v2_independent_truth_b.yml` | `field` | 200 | 6 | - | **NED asked by up to 6 jobs at once** |
| `v2_locked_set_c.yml` | `field` | 60 | 20 | - | **NED asked by up to 20 jobs at once** |
| `v2_practical_probe.yml` | `field` | 3 | - | - | **NED asked by up to all jobs at once** |
| `v2_r_undetected_cosmos.yml` | `cosmos` | 1 | - | - | single job |
| `validate-reference-objects.yml` | `run` | 26 | 26 | - | **NED asked by up to 26 jobs at once** |

## 변경 후

| workflow | job | matrix | max-parallel | V2_SKIP_COLLECTORS | NED |
|---|---|---|---|---|---|
| `experiment-ab-fields.yml` | `field` | 89 | 20 | `blind` | NED, SIMBAD, SDSS spectra and the other blind-dropped collectors are not asked |
| `probe-collectors.yml` | `probe` | 1 | - | - | single job |
| `v2_collect_parallel_probe.yml` | `probe` | 1 | - | - | single job |
| `v2_controller_ngc4522_test.yml` | `collect` | 1 | - | - | single job |
| `v2_field_validation.yml` | `field` | 1 | - | - | single job |
| `v2_independent_truth.yml` | `field` | 200 | 1 with `with_ned`, else 6 | `ned` unless `with_ned=true` | NED not asked unless `with_ned=true` (then one job at a time) |
| `v2_independent_truth_b.yml` | `field` | 200 | 1 with `with_ned`, else 6 | `ned` unless `with_ned=true` | NED not asked unless `with_ned=true` (then one job at a time) |
| `v2_locked_set_c.yml` | `field` | 60 | 20 | `blind` | NED, SIMBAD, SDSS spectra and the other blind-dropped collectors are not asked |
| `v2_practical_probe.yml` | `field` | 3 | 1 | - | NED asked, one job at a time |
| `v2_r_undetected_cosmos.yml` | `cosmos` | 1 | - | - | single job |
| `validate-reference-objects.yml` | `run` | 26 | 1 with `with_ned`, else 26 | `ned` unless `with_ned=true` | NED not asked unless `with_ned=true` (then one job at a time) |

검색 한 번당 요청 수(2.60.2 로그, 세 영역 × 두 번, 원격 방식): NED 1, SkyServer 4–6(`sdss_dr18` 3 + `sdss_spectroscopy` 1–3), SIMBAD 1–3. 요청 앞의 3–5초 대기는 스레드마다 따로다(`throttle.py`).
