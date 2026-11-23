# 작업 보고서 2026-11-23b: 아카이브 장애 대비 (2.57.0, 1단계)

## 1. 요청과 요약

검토·계획 세션이 2.56.0을 실제 세 영역에서 돌린 결과(2026-11-23)를 넘겼다. 같은 영역이 아카이브 상태에 따라 결과가 크게 달랐다(COSMOS 첫 실행은 Legacy Surveys 시간 초과로 270행·고신뢰 24, 바로 다시 돌린 실행은 3,582행·786). 사용자가 그 사실을 스스로 알 수 없고, 다시 돌려야 한다는 것도 모른다는 것이 문제다. 넘겨받은 설명은 출발점으로만 쓰고 직접 재현했다.

| # | 요청 | 결과 |
|---|---|---|
| 1-1 | 불완전한 실행을 결과 파일 안에서 알 수 있게 | `objects_summary.csv`·`classified_objects.csv`에 `run_archives_status`·`run_archives_missing` 열 |
| 1-2 | 실패한 수집기만 다시 받기 | `pipeline.py --retry-failed [key\|all]`, 앱의 "Ask failed archives again" 버튼 |
| 1-3 | Legacy Surveys 대체 경로 | **있다.** 뷰어 카탈로그 `cat.fits`(같은 Tractor 행, 값 일치). Data Lab이 늦으면 함께 묻는다(요청 헤징) |
| 1-4 | Gaia 중단 대비 | ESA 점검 안내를 알아보고 바로 VizieR 사본으로, 사본의 세 질의 병렬화, `V2_GAIA_SOURCE=vizier`. 세 영역에서 사본만 써도 **라벨 변화 0**(5,000개 천체) |
| 1-5 | Gaia가 100–138초 걸린 이유 | **ESA 아카이브가 점검 중이었다**(동기·비동기 모두 점검 안내 HTML) + VizieR 미러 순회. 동기/비동기 문제가 아니다 |

핵심 측정
- ESA 점검 중 Gaia(NGC 4522 2′, 같은 시각 A/B, 캐시 끔): **44.5 / 44.4 s → 19.8 / 18.5 s**, 행·값 같음.
- Data Lab 장애 중 Legacy Surveys(NGC 4522 0.5′ / COSMOS 2′ 912행): 이전에는 246 s 실패 → **36.7 s / 37.3 s 성공**.
- 재시도(NGC 4522 0.5′): 전체 검색 178.5 s → 실패한 둘만 **30.5 s**, 핵심 하나(LS)만 **5.6 s**(분류까지 7.9 s).
- 시험 **244 통과, 건너뜀 0**(앱 시험 포함, 이 세션에서 PySide6와 `libEGL`을 설치해 돌림).

## 2. 불완전 실행 표시 (1-1)

### 설계와 이유
- **열이지 머리 주석이 아니다.** `# …` 첫 줄은 `pd.read_csv`와 앱이 데이터로 읽는다(열 이름이 어긋남). 열은 어떤 도구로 읽어도 남는다.
- **두 열, 모든 행에 같은 값.** 행마다 같은 값을 쓰는 것은 낭비처럼 보이지만, 표를 잘라 일부 행만 전달해도 표시가 따라간다.
  - `run_archives_status`: `complete` / `key_archives_missing` / `archives_missing` / `degraded` / `unknown`
  - `run_archives_missing`: `collector:status`를 `|`로 이은 목록(핵심 아카이브 먼저). 대체 자료로 받은 수집기는 `collector:alternative_source`.
- **`unknown`은 별도 값이다.** 수집 요약이 없는(다른 곳에서 모은) 자료를 `complete`로 쓰면 거짓 안심이다.
- **`degraded`(새 값).** 실패는 없는데 Gaia·PS1이 대체 자료(VizieR 사본)로 왔을 때. 수집 요약에서는 `ok`라 지금까지 어떤 경고도 없었다(8절).
- 위치: `summary.COLUMNS`의 `catalogs` 뒤. 앞쪽 열을 밀지 않는다.
- 빈 검색 결과(`EMPTY_RESULT_COLUMNS`)에도 같은 열을 쓴다. 아카이브가 전부 내려간 검색이 바로 이 경우다.

### 실측 (NGC 4522 0.5′, 실제 아카이브)
FIRST(VizieR 미러 연결 실패)와 SDSS 분광(SkyServer 403)이 실패한 실행의 결과 표 모든 행: `archives_missing`, `first:error|sdss_spectroscopy:error`.

## 3. 실패한 수집기만 다시 받기 (1-2)

### 설계와 이유
- **정확한 원뿔을 `search.json`에 저장한다.** 폴더 이름(`ra188p4155_…`)은 소수 6자리로 반올림되고, 캐시는 원뿔이 "같다"를 1e-6′ 오차로 판정한다. 폴더 이름에서 되살린 좌표로는 이미 성공한 수집기의 캐시가 모두 빗나가 전부 다시 묻게 된다(재시도의 의미가 사라진다). 이전 버전의 검색은 `--ra/--dec/--radius`를 주면 된다.
- **재시도할 이름만 `_run_bounded`로 돌리고 요약 파일에서 그 행만 교체한다.** 대안(전체를 다시 수집해 캐시가 성공분을 재사용하게 하기)은 코드는 더 적지만, 수집기마다 캐시 판정·로그·실패 기억 갱신을 거치고 "아무것도 실패하지 않았을 때 아무것도 하지 않는다"는 보장이 어렵다.
- **사용자가 명시한 재시도라서 10분 실패 기억을 건너뛴다**(`_collect_one(retry=True)`). 기억은 "자동으로 다시 묻지 않기"를 위한 것이다.
- **예산은 기존 `RETRY_BUDGET_S` 규칙을 따른다**(Legacy Surveys 90 s). 장애 중에 다시 눌러도 5분을 기다리지 않는다. 건강한 서비스는 5–16 s에 답한다.
- **기본은 핵심 아카이브만**(`key`), `all`은 실패한 전부. 핵심이 아닌 수집기(NED 등)는 느리게 실패하는 일이 많아 기본 동작에 넣지 않았다.
- **대체 자료로 받은 핵심 수집기(Gaia·PS1)도 대상이다.** ESA가 돌아오면 사본이 아니라 원래 자료를 받아야 한다. 하루 캐시된 사본은 건너뛰고(`archive_cache.fallback`) 다시 묻는다.
- **`catalog_coverage.json`에 `raw_dir`를 기록한다.** 같은 작업 폴더에서 `--raw-dir` 실행과 하늘 검색을 번갈아 하면, "마지막 검색"이 지금 결과의 출처와 다를 수 있다.
- **앱:** 경고 띠 옆의 버튼. 결과를 읽을 때 `catalog_coverage.json`과 `search.json`이 있고 실패·대체 자료가 있을 때만 보인다. 진행률은 워커가 `[retry] asking again: …`로 알려 주는 개수로 센다.

### 실측 (NGC 4522 0.5′, 이 컨테이너, 실제 아카이브)
| 실행 | 시간 |
|---|---|
| 전체 검색(30개 수집기) | 수집 178.5 s, 전체 180.1 s |
| `--retry-failed all`(FIRST, SDSS 분광) | 재수집 30.5 s, 전체 32.3 s. FIRST 복구(빈 결과), SDSS 분광은 SkyServer 403이 계속돼 실패로 남음 |
| `--retry-failed`(핵심; LS를 시간 초과로 표시하고 raw 파일을 지운 뒤) | 재수집 5.6 s(캐시 적중), 전체 7.2 s. 요약 표 8행 라벨 변화 0, 결과 표시가 `key_archives_missing` → SDSS 분광만 남은 `archives_missing` |
| 실패한 핵심이 없을 때 | 요청 0, 분류 안 함, 기존 결과를 그대로 돌려줌 |

## 4. Legacy Surveys 두 번째 경로 (1-3)

### 조사 결과
| 후보 | 결과 |
|---|---|
| NOIRLab Data Lab TAP `ls_dr10.tractor` | 지금 쓰는 주 경로(DR10 남쪽 + DR9 북쪽) |
| **Legacy Surveys 뷰어 `…/viewer/ls-dr10/cat.fits?ralo=&rahi=&declo=&dechi=`** (NERSC) | **쓸 수 있다.** 같은 Tractor 행. 아래 일치 검증 |
| 뷰어 `cat.json` | 지도 페이지 HTML만 돌려준다(Tractor 레이어에는 상자용 JSON이 없음). 2026-11-17 보고서의 "HTML이라 못 썼다"는 이 형식을 시험한 결과이고, 모순이 아니다 |
| NERSC `portal.nersc.gov/.../dr10/south/` 의 brick·sweep 파일 | 열려 있고 전체 열을 주지만, brick 목록(`survey-bricks-…fits.gz` 104 MB)과 brick 파일(수십 MB)을 받아야 해서 2′ 원뿔에 부적합. 구현하지 않음 |
| IRSA TAP | 표 1,051개 중 `legacy`·`desi`·`decal`·`tractor`·`ls_` 이름의 표 없음(2026-11-23) |
| VizieR | DR10 Tractor 사본을 찾지 못함(웹 검색에 없음; VizieR 쪽 표 목록 질의는 이 컨테이너에서 실패해 직접 확인하지 못함) |

### 일치 검증 (`ls_id = release·2⁴⁰ + brickid·2²⁰ + objid`, 뷰어의 `dchisq`(N,5) = `dchisq_1..5`)
| 영역 | 기준(저장된 Data Lab TAP 행) | 뷰어 | 결과 |
|---|---|---|---|
| NGC 4522 0.5′ (살아 있는 TAP과 직접 비교) | 28행 | 28행 | `ls_id` 집합 같음, 공통 44열 상대오차 < 1e-5 |
| NGC 4522 2′ (프로브 원자료) | 417행 | 417행 | 같음, **45열 상대오차 < 1e-6, NaN 위치 같음** |
| COSMOS 2′ (150.1191, 2.2058; 프로브 원자료) | 1,046행 | 1,046행 | 같음, 45열 같음 |
| 은하면 1′ (프로브 원자료) | 0행 | 0행 | 양쪽 빈 결과 |
| 북쪽 (245, +43), 2′ | – | 295행, release 9011(DR9 북쪽) | **값은 비교하지 못함**(Data Lab 장애). 범위가 Data Lab과 같은 DR10 남 + DR9 북임만 확인. *검토(9절): 북쪽은 값이 달라 쓰지 않음* |

### 뷰어의 한계와 대응
- 크기: 상자 2′ 1,179행 3.0 MB 4.0 s, 10′ 31,845행 78 MB 14.5 s, 30′ 281,328행 688 MB 88.5 s. → **반경 10′ 이하**만 대상(`MAX_VIEWER_RADIUS_ARCMIN`).
- RA 0/360을 넘는 상자는 20.6 s에 일부만 돌려주는 것으로 보여 **두 상자로 나눠** 묻는다. 극(|dec|+r ≥ 89°) 근처는 쓰지 않는다.
- 푸트프린트 밖 상자는 `No catalog sources in layer and RA,Dec box`(한 줄 텍스트)를 돌려준다 → 빈 표.
- 뷰어는 시각화 서버라 TAP 같은 약속이 없다. 그래서 주 경로로 쓰지 않는다.

### 설계: 요청 헤징(request hedging)
- 대안 1, **TAP 3회 실패 뒤 뷰어**: 3 × 80 s + 대기 ≈ 246 s라 컨트롤러 예산 300 s 안에 뷰어가 들어갈 틈이 없다. 버림.
- 대안 2, **처음부터 둘 다 묻기**: 정상인 날에도 뷰어(NERSC)에 요청이 간다. 버림.
- **채택: 헤징.** Data Lab이 30초(정상 5–16 s의 약 2배) 안에 답하지 않거나 한 번 실패하면 뷰어를 함께 묻고 먼저 온 답을 쓴다. 느린 꼬리 지연을 줄이는 표준 방식이다(Dean & Barroso 2013, "The Tail at Scale", CACM 56, 74). 정상인 날은 요청이 한 번도 가지 않는다.
- 뷰어 결과는 `legacy_query_status = viewer_fallback`으로 표시하고 하루만 캐시한다(Gaia 사본과 같은 규칙). 값이 같아도 "주 경로가 아님"을 남겨 두고 싶었다.

### 실측 (Data Lab이 실제로 멈춘 시간대, 2026-11-23 약 13:40–14:40 UTC)
- 같은 시간대에 TAP 단독 호출은 3번 모두 246 s 뒤 `TapTimeout`.
- 헤징 포함 `fetch`: NGC 4522 0.5′ **28행 36.7 s**, COSMOS 2′ **912행 37.3 s**. 뷰어만: 28행 5.5 s, 417행 6.2 s, 1,046행 7.2 s.
- 이전에는 이 상황에서 LS가 시간 초과 → COSMOS 결과가 270행·고신뢰 24였다(요청 문서).

## 5. Gaia (1-4, 1-5)

### 5.1 원인 (1-5)
2026-11-23 13:32 UTC에 `https://gea.esac.esa.int/tap-server/tap/{availability,capabilities,sync}` 모두 **HTTP 200과 "ESDC Archives downtime / Archive down for maintenance" HTML**을 돌려줬다. 상태 코드가 아니라 내용으로만 판별된다. 수집기는 이를 모르고 동기 실패 뒤 비동기 재시도 4번을 한다.

NGC 4522 2′ 단독 호출을 단계별로 쟀다(수정 전 코드, V2_HTTP_LOG=1):
| 단계 | 시간 |
|---|---|
| ESA TAP(동기 4.2 s + 비동기 4번과 대기) | 37.4 s |
| VizieR 사본 3개 질의(차례로) | 118.0 s (`gaiadr3` 22.0 + `paramp` 70.5 + `vclassre` 25.5) |
| 항등성 확인(GAVO TAP) | 5.4 s |
| 합계 | 160.8 s |

사본의 시간은 거의 미러 순회다(Strasbourg 404, CfA는 `paramp`에 표 없음이라고 답했다가 확인에서 행이 나와 다음 미러로, NAOJ·China-VO 연결 실패, IUCAA 읽기 시간 초과 10 s). 같은 코드를 몇 분 뒤 다시 재면 44.5 s였다(미러 상태가 달랐다). **오늘의 100–138 s는 동기 요청이 느린 것도, 비동기로 넘어간 것도 아니고, 아카이브 쪽 사정(ESA 점검 + VizieR 미러 상태)으로 설명된다.** 검토 세션의 실제 로그는 볼 수 없어서 같은 구조가 45–161 s 범위로 재현된다는 것까지만 말할 수 있다.

### 5.2 바꾼 것과 이유
1. **점검 안내 알아보기(`archive_down_reason`).** 동기 요청이 예외로 실패했을 때만 VOSI `availability`를 한 번 묻는다. HTML이거나 `available=false`이면 비동기 재시도를 건너뛰고 VizieR 사본으로 간다. 가용성 요청 자체가 실패하면 "모름"이라 기존 재시도를 그대로 한다(느린 네트워크가 아카이브를 끄지 않음). 동기가 성공했는데 꽉 찬 페이지(2,000행)인 경우는 아카이브가 살아 있으니 묻지 않는다.
   - 대안: 매번 먼저 가용성을 묻기. 정상인 날 한 요청(3–5 s 간격 규칙 포함)을 더 쓴다. 버림.
2. **사본의 세 질의 병렬.** 서로 독립이다. `gaiadr3`가 비면 다른 둘을 기다리지 않고 돌아간다(데몬 스레드).
3. **`V2_GAIA_SOURCE=vizier`.** ESA를 아예 묻지 않는다. 알려진 중단 기간과 시험용. 잘못된 값은 조용히 대체 경로로 삼키지 않고 오류를 낸다.
4. **경고에 대체 자료와 잃는 열을 적는다**(`catalog_coverage.ALTERNATIVE`). 이전에는 Gaia가 사본으로 와도 수집 요약이 `ok`라 아무 경고도 없었다.

### 5.3 측정 (1-4)
**수집 시간(ESA 점검 중, 같은 시각 A/B, astroquery 캐시 끔):**
| NGC 4522 2′ | 수정 전 | 수정 후 |
|---|---|---|
| 1회 | 44.5 s | 19.8 s |
| 2회 | 44.4 s | 18.5 s |
행 13, 값 같음. 처음 한 번의 160.8 s는 미러 상태가 나쁜 때였다. 줄어든 25 s는 ESA 쪽 재시도와 병렬화 몫이다.

**사본만 쓸 때 바뀌는 것** (`benchmark/gaia_source_ablation.py`): ESA 정상 시점에 받은 세 영역의 원자료(프로브 실행 44176464564, `validation-data`)를 기준으로, 같은 원뿔의 Gaia만 VizieR 사본으로 바꾸고 나머지 수집기는 그대로 둔 채 현재 코드로 분류했다.

| 영역 | Gaia 행 | 천체 | 사본 수집 | 라벨 변화(1차·상태·세부·물리·변광) | 사본이 비운 열 (ESA에는 값이 있었음) |
|---|---|---|---|---|---|
| NGC 4522 2′ | 13 | 657 | 6.7 s | **0** | 광속 6, `bp_g`, `g_rp`, `flags_flame` |
| COSMOS 2′ | 18 | 3,621 | 79.0 s | **0** | 위 + `mass_flame`, `age_flame`, `evolstage_flame` |
| 은하면 1′ | 349 | 722 | 29.1 s | **0** | 위 + `rv_nb_transits` |

- 세 영역 모두 `source_id` 집합 같음. 1차 분류 합계도 같다(은하면 STAR 534·UNKNOWN 188, COSMOS GALAXY 3,294·UNKNOWN 253·STAR 63·QSO 11).
- *검토(9절) 정정: FLAME 4열과 ESP-UCD 2열은 `I/355/paramp`에 있어 사본에서도 받는다. 사본이 못 채우는 열은 18개(광속·색 9, 변광 요약 9).* 원래 기록: **사본이 구조적으로 못 채우는 열은 62개 중 24개**: 광속·색 9(`phot_{g,bp,rp}_mean_flux(_error)`, `bp_g`, `g_rp`, `rv_nb_transits`), FLAME 4, ESP-UCD 2(`teff_espucd`, `flags_espucd`), 변광 요약 9(`in_vari_*`). DSC 확률(`paramp`)·GSP-Phot·GSP-Spec·ESP-ELS·변광 분류(`I/358`)·충실도(GAVO)는 사본에서 온다.
- 1차 분류가 변하지 않는 이유: 위 24열을 읽는 곳은 `in_vari_*`(`axes/compact.py`, `axes/extragalactic.py`), FLAME(`branches/evolved_star.py`), ESP-UCD(`subclass.py`, `axes/physical.py`)이고, 광속·색은 학습 스크립트뿐이다. 1차 분류 단계(Stage 3–5)는 읽지 않는다. 그 세부 축이 달라질 수 있는 천체(변광·진화한 별·초저온 왜성)가 이 세 영역 표본에는 없었다. **"세부 분류가 항상 같다"는 증거는 아니다**: 변광성·적색 거성이 많은 영역에서는 달라질 수 있어 경고에 적는다.
- 2.56.0 보고의 "은하면 4개가 DSC 유무로 바뀜"은 다른 상황이다. 그때는 ESA의 선택 표 세 개가 실패해 DSC가 없던 실행과 사본을 비교한 것이다. 사본은 DSC를 가진다.

### 5.4 ESA 점검 일정
- 2.56.0 보고는 11월 25일–12월 2일이라 했지만, **이 컨테이너에서는 11월 23일 13:32 UTC에 이미 점검 안내 페이지였다.**
- ESA Gaia Bulletin #09(웹 검색 결과 요약)에는 DR4가 2026-12-02 예정이고 공개 직전 수 영업일 중단이 있다고만 나온다. 정확한 시작·종료일은 공지에서 확인하지 못했다.
- DR4 전환은 이전 보고대로 `check_gaia_release.py --release DR4` 확인 뒤 `V2_GAIA_RELEASE`로 한다(이번에 바꾸지 않음).

## 6. 전체 파이프라인 실행 (실제 아카이브)

`python v2/pipeline.py --ra 188.4155 --dec 9.1751 --radius 2` (새 캐시, 이 컨테이너, ESA 점검 중):
- 수집 173.4 s(30개 수집기): Gaia **17.2 s**(점검 안내 인식 → 사본, 13행), Legacy Surveys 7.2 s(417행; 이 실행에서는 Data Lab이 정상이라 뷰어는 쓰이지 않음), PS1 4.4 s. 느린 것은 `ztf_periodic` 107 s, `agb_suh2021` 104 s(VizieR 미러 순회)이다.
- 결과: 675개 천체, 요약 149행(GALAXY 123·UNKNOWN 15·STAR 11), 고신뢰 122.
- 결과 표 모든 행: `run_archives_status = degraded`, `run_archives_missing = gaia_dr3:alternative_source`.
- 콘솔·앱 경고: `Reduced alternative source — Gaia DR3 from the VizieR I/355 copy (without variability summary flags (in_vari_*), FLAME mass / age / evolutionary stage, ESP-UCD ultracool-dwarf Teff, G / BP / RP fluxes, bp_g, g_rp, rv_nb_transits)`.
- 같은 영역을 ESA 정상 시점에 돌린 기준 실행은 없어 1차 라벨 비교는 5.3절의 원자료 교체 시험으로 했다.

## 7. 바꾼 파일

| 파일 | 내용 |
|---|---|
| `catalog_coverage.py` | `annotate`/`status`/`missing`, `ALTERNATIVE`(대체 자료로 받은 수집기와 잃는 열), `message`가 둘 다 설명, `raw_dir` 기록 |
| `summary.py`, `pipeline.py` | 요약 열, 빈 결과에도 열, `--retry-failed`, `run(retry_failed=)` |
| `Get_data/controller.py` | `search.json`, `last_collection`, `failed_collectors`, `retry_failed`, `_collect_one(retry=)`, `_budget(retry=)` |
| `Get_data/desi_legacy.py` | 뷰어 경로(`_viewer_fetch`, `viewer_boxes`), 헤징(`_query_with_retries(hedge)`) |
| `Get_data/gaia_dr3.py` | `archive_down_reason`, `ArchiveDown`, `source_mode`, 병렬 사본 |
| `Get_data/archive_cache.py` | `viewer_fallback`을 대체 출처로 등록(하루 캐시) |
| `app/qt_app.py`, `app/progress.py` | 재시도 버튼, `retry_mode`, 재시도 진행률 |
| `benchmark/gaia_source_ablation.py` | 사본만 쓸 때의 열 손실·라벨 변화 측정 |
| 시험 | `test_incomplete_run_and_retry.py`(12), `test_legacy_viewer_path.py`(9), `test_gaia_outage.py`(7), `test_app.py`(+2), 기존 시험 1개 고침 |
| `README.md`, `ALGORITHM.md` | 새 열·옵션·장애 대비 |

## 8. 확인된 한계와 남은 것

- **Gaia 사본·LS 뷰어는 정상 날에는 쓰이지 않는다.** 정상 아카이브에서 결과가 바뀌지 않아야 하므로 정상 경로 코드는 건드리지 않았다. 단, 같은 영역을 세 번 이상 돌려 비교하지는 않았다(정상 ESA 접속 불가).
- *(검토 9절에서 비교함: 북쪽은 값이 달라 뷰어를 쓰지 않는다.)* **북쪽 하늘(DR9 북쪽) 뷰어 값은 TAP과 비교하지 못했다.** Data Lab이 멈춘 시간이라서다. Data Lab이 돌아오면 `compare_ls.py` 방식(저장된 TAP 행 대 뷰어)으로 한 번 더 확인하는 것이 좋다.
- **SDSS 분광은 이 컨테이너에서 SkyServer 403 페이지가 계속 와서 실패**한다(2.56.0이 5번 재시도 뒤 오류로 보고하는 것까지만 동작). 코드 문제가 아니라 접속 환경이다.
- 재시도 버튼은 2.57.0 이전 검색(`search.json` 없음)에는 보이지 않는다. 명령줄은 `--ra/--dec/--radius`로 가능하다.
- **수집 캐시는 코드 해시가 바뀌어 한 번 비워진다**(`Get_data/*.py`가 바뀜).
- 릴리스(태그)는 만들지 않았다.

## 9. 병합 전 검토 (코드 개발 세션)

검토·계획 세션의 요청으로 커밋 16e7fc1을 검토했다. 아래 수정을 더해 병합한다. 측정은 GitHub Actions(`compare-archive-alternatives.yml`)에서 실제 서비스로 했다. 이 컨테이너에서는 legacysurvey.org·Data Lab·VizieR에 닿지 않는다.

### 9.1 CI: Preprocess 시험이 실패하고 있었다
- `test_legacy_viewer_path.py`가 모듈 수준에서 `astropy.io.fits`를 쓰는데, `test-preprocess.yml`이 astropy를 설치하지 않아 수집 단계에서 오류가 났다(로컬 244 통과와 다른 결과).
- astropy는 파이프라인의 의존성이므로(`app/requirements.txt`) CI 설치 목록에 넣었다. 시험을 건너뛰게 만들면 뷰어 경로가 CI에서 검사되지 않는다.

### 9.2 Legacy Surveys 뷰어: DR10 South에서만 쓴다
`benchmark/compare_ls_viewer.py`가 같은 원뿔(2′)을 TAP만으로, 뷰어만으로 `fetch`해 같은 후처리를 거친 행을 비교한다. Data Lab이 정상이던 세 번의 실행에서 결과가 같았다.

| 원뿔 | 영역 | 행 | 결과 |
|---|---|---|---|
| NGC 4522 (188.42, +9.18) | DR10 South | 417 | 같음(45열, `ls_id`) |
| NGC, Dec 32.30 (분할선 바로 남쪽) | DR10 South | 436 | 같음 |
| SGC, Dec 33.5 (분할선 위의 남쪽 은하 반구) | DR10 South | 154 | 같음 |
| NGC, Dec 32.45 (분할선 바로 북쪽) | DR9 North | 219 | **다름** |
| (245, +43), (150, +50) | DR9 North | 219, 178 | **다름** |

북쪽에서 다른 점:
- **`ls_id`.** Data Lab의 `ls_dr10`은 DR9 North 행에 DR9의 id(`release<<40 | brickid<<16 | objid`)를 그대로 쓴다. DR10 South 행은 `brickid<<20`이다. 위치로 맞추면 219행 모두 release·brickid·objid가 같고 이 자리 이동만 달랐다. 고쳤다(이제 id 일치).
- **i 밴드.** DR9 North(BASS + MzLS)에는 i 밴드가 없어 깊은 북쪽에서는 뷰어 표에 열이 없었다(`KeyError('flux_i')`; 그래서 헤징이 늘 실패했다). 분할선 근처에서는 뷰어가 남쪽 표와 합치며 0으로 채운다. TAP은 두 경우 모두 값을 준다. 빈 열을 NaN으로 두도록 고쳤지만 TAP 값과는 다르다.
- **`fracflux_*`** 는 분할선 근처에서 최대 3 % 차이가 났고, 깊은 북쪽에서는 한쪽이 0이었다. 광속은 최대 3e-4 상대 차이가 났다. 뷰어가 읽는 북쪽 Tractor 파일과 Data Lab 표의 판이 다른 것으로 보인다(원인은 확인하지 못함).

판단:
- **`viewer_usable`은 원뿔 전체가 DR10 South일 때만 참이다.** 원뿔 북쪽 끝이 Dec 32.375 아래이거나, 은위 b < −r인 경우다(LS의 북/남 구분: Dec ≥ 32.375이고 b > 0이면 북쪽).
- 북쪽은 2.56.0과 같다(두 번째 경로 없음). i 밴드와 `fracflux`는 분류 특징으로 쓰이므로, 다른 값을 "같은 행"으로 넣지 않는다.
- 남쪽 결과는 TAP과 같으므로 `degraded`로 표시하지 않는다. 출처는 원자료의 `legacy_query_status = viewer_fallback`에 남는다.
- 시험: `test_viewer_only_for_cones_wholly_in_dr10_south`, `test_dr9_north_rows_keep_the_dr9_id_and_have_no_i_band`.

**뷰어 이용 조건.** 이 컨테이너에서는 legacysurvey.org에 접속할 수 없어 뷰어 소스(GitHub `legacysurvey/imagine`)를 읽었다.
- `cat.fits`는 뷰어의 "data for RA,Dec box" 페이지가 사용자에게 주는 "Catalog" 내려받기 링크다(`map/views.py`, `any_fits_cat`). 응답은 해당 brick의 Tractor 파일을 상자로 자른 것이다.
- URL 안내 페이지(`templates/urls.html`)에는 실려 있지 않다.
- 소스에서 요청 빈도 제한이나 이용 조건 문구는 찾지 못했다.
- 우리 사용량은 Data Lab이 30초 안에 답하지 않거나 실패한 검색마다 상자 한두 개(반경 ≤ 10′)다. 정상인 날에는 0이다.
- 대량 조회가 아니므로 유지하되, 위 사실(공식 API로 문서화되지 않음)을 여기에 남긴다.

### 9.3 Gaia 사본: ESP-UCD와 FLAME은 사본에도 있다
- 2.57.0은 FLAME 4열과 ESP-UCD 2열을 "사본이 구조적으로 못 채우는 열"로 보고 경고에 적었다. VizieR `I/355/paramp`의 열 목록(215개, 2026-11-23)에는 `Teff-UCD`, `Flags-UCD`, `Mass-Flame`, `Age-Flame`, `Flags-Flame`, `Evol`이 있다. 수집기가 요청하지 않았을 뿐이다.
- `_PARAMP`에 넣어 사본도 이 열을 채운다. 사본이 못 채우는 열은 24개에서 18개로 줄었다(광속·색 9, 변광 요약 `in_vari_*` 9). `catalog_coverage.ALTERNATIVE`의 경고 문구도 그에 맞췄다.
- **값 비교** (`benchmark/compare_gaia_copy_columns.py`): ESA에서 받은 세 영역 원자료(프로브 44176464564, `validation-data`)와 같은 원뿔의 사본을 `source_id`로 맞췄다.

| 열 | ESA·사본 둘 다 값 | 같음 / 최대 차이 |
|---|---|---|
| `evolstage_flame` | 4 + 36 | 모두 같음 |
| `flags_flame` | 1 + 6 + 40 | 모두 같음 |
| `mass_flame` | 4 + 30 | 최대 5e-4 M☉ (VizieR가 소수 셋째 자리로 반올림) |
| `age_flame` | 4 + 27 | 최대 5e-4 Gyr |
| DSC 확률 5개 | 13 + 17 + 289 | 최대 5e-9 |

- **ESP-UCD 값 비교**: 세 영역에는 초저온 왜성이 없어, ESA ESP-UCD Teff가 있는 Best+2018 왜성 641개 중 무작위 200개의 위치(5″)에서 사본을 물었다. 200개 모두 사본에 `Teff-UCD`가 있었고, Teff 차이는 최대 0.005 K(반올림), 품질 플래그는 200개 모두 같았다.

- **왜 중요한가.**
  - ESP-UCD는 초저온 왜성 표시(`ULTRACOOL_DWARF`, 세부 `STAR:M:UCD`)의 유일한 Gaia 근거다(나머지는 SIMBAD BD*). Best+2018 초저온 왜성 9,888개 중 ESA ESP-UCD로 선택되는 것은 532개다(M7–M9의 45–58 %, L0–L3의 14–32 %; `new_targets/truth/ucd_summary.json`). 2.57.0 그대로라면 Gaia 점검 기간에는 이 표시가 모두 사라진다.
  - FLAME은 거성 경로(`branches/evolved_star.py`)의 근거다. RGB 정답 203개 중 12개(2.13.0)가 FLAME으로 찾아진다.
- **남는 결손.** 변광 요약 `in_vari_agn`·`in_vari_compact_companion`(Gaia가 뽑은 AGN·밀집 동반성 후보 표시)은 VizieR에 없다. 변광 분류 자체(`I/358`)는 사본에서 온다. 영향을 받는 천체(변광 AGN 후보, 밀집 동반성 후보)는 세 영역 표본에 없어 라벨 변화를 재지 못했다. 경고 문구가 이 두 표시를 이름으로 적는다.

### 9.4 그 밖의 확인
- **`--retry-failed`가 장애 서버에 요청을 몰아주는가.**
  - 사용자가 누를 때만 묻는다. 앱 버튼은 실행 중에는 동작하지 않는다(`proc.state()` 확인).
  - 수집기마다 한 번만 묻고, `RETRY_BUDGET_S` 규칙을 따른다(LS 90 s).
  - Gaia는 점검 중이면 ESA에 동기 1건과 가용성 1건만 보내고 사본으로 간다.
  - 실패 기억을 건너뛰는 것은 이 명시적 요청뿐이다. 자동 재시도는 없다.
- **새 열 2개**(`run_archives_status`, `run_archives_missing`): `objects_summary.csv`가 26열에서 28열이 된다. 분류 코드(`v2/Classifier`, `v2/Preprocess`의 판정 경로)는 이 열을 읽지 않는다(`query_status` 열도 읽지 않음). 앱 시험 통과.
- **세트 C**: 1차 분류 판정 경로(`v2/Classifier`, `v2/Preprocess` 비시험 코드)는 바뀌지 않았고, 수집 경로는 장애 때만 바뀐다. 채점하지 않는다.
- **병합 순서**: 같은 브랜치에서 2단계(어두운 QSO 후보 A/B)가 진행 중이다. 1단계는 독립적이고 Gaia 점검(11-25부터)이 곧이라 먼저 병합한다. 작업 세션은 `git fetch origin main && git merge origin/main`으로 받으면 된다. squash 병합이라 16e7fc1과 내용이 같은 부분은 충돌 없이 합쳐진다. 검토 수정은 위 파일들에만 있다.
- **Codex 검토(PR #73) 세 건을 고쳤다.**
  - **`--retry-failed` 지름길.** 실패한 수집기가 없으면 작업 폴더의 `classified_objects.csv`를 그대로 돌려줬다. 그런데 그 파일은 폴더의 모든 검색이 함께 쓰므로, 옛 검색을 지정하면 다른 하늘의 결과가 나왔다. 이제 `catalog_coverage.json`의 `raw_dir`가 지정한 검색일 때만 돌려주고, 아니면 수집 없이 그 검색을 다시 분류한다.
  - **PS1 사본의 빈 응답.** MAST가 실패하고 VizieR 사본이 0행을 주면, 상태 열에 값이 없어 대체 출처로 알아보지 못했다(`complete`, 재시도 대상 아님). 사본은 검출 2번인 천체를 빼므로 실제로 빠진 천체가 있을 수 있다. PS1의 MAST 경로는 `ps1_query_status` 열을 쓰지 않으므로, 머리글에 그 열이 있는 빈 파일은 사본의 응답으로 본다(`catalog_coverage.EMPTY_HEADER_MARKS`, `archive_cache.HEADER_ONLY_FALLBACK`). 명시적 재시도는 캐시의 빈 사본 응답 대신 MAST를 다시 묻는다.
  - **비교 스크립트의 GSP-Spec 플래그.** 저장된 ESA 파일은 `F` + 41자리 문자열이고 사본은 변환 전 값이라 인코딩이 달랐다. 41자리를 정수로 바꾸는 비교도 자릿수를 잃는다. 사본에도 `_gspspec_quality`를 적용하고 문자열로 비교한다. 이번 세 영역에는 GSP-Spec 값이 없어 9.3절 수치는 그대로다.
- 시험 248개 통과(앱 시험 포함).
