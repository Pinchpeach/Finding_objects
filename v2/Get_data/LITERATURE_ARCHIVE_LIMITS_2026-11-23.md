# 아카이브 이용 한도: 공식 문서 원문 정리 (2026-11-23, 2.60.0)

프로젝트 규칙(2.33.0, `throttle.py`)은 모든 아카이브 요청 앞에 3–5초(평균 4.0초)를 둔다. 이 문서는 그 규칙이 각 서비스의 **공식 문서가 밝힌 한도**와 어떻게 놓이는지 보려는 판단 자료다. **대기 규칙은 바꾸지 않았다**(사용자 결정 사항). 서비스별 대기를 달리하면 얼마나 줄어드는지는 5절에서 계산만 한다.

## 1. 어떻게 모았고 얼마나 믿을 수 있나

- 각 서비스의 공식 페이지를 2026-11-23에 읽고 원문을 그대로 옮겼다. 조사는 두 보조 에이전트가 나눠 했고, 아래 표의 확인 칸으로 구분한다.
  - **✔ 직접 확인**: 작성자가 같은 날 원문 페이지를 다시 읽어 인용이 일치함을 확인했다(CDS 공지, NED 지침, SDSS 한도 페이지, Gaia 할당량 표).
  - **○ 보조 에이전트가 읽음**: 에이전트가 원문 페이지에서 옮긴 인용이며 작성자는 다시 읽지 않았다.
  - **△ 2차 자료**: 공식 페이지를 읽을 수 없어 astroquery 문서 같은 2차 자료로 대신한 것. 공식 한도로 쓰지 않는다.
- "공식 한도를 찾지 못함"은 그 페이지에 한도·시간 제한·속도·동시성 문구가 없다는 뜻이지 한도가 없다는 뜻이 아니다.
- **CDS 사고(✔)**: https://cds.unistra.fr/ 의 안내문("Last updated November 18, 2026"): "CDS is experiencing a cybersecurity incident within its network of servers located in Strasbourg. [...] access to SIMBAD, VizieR, Aladin image surveys, X-Match and other services hosted on our main site cds.unistra.fr is currently degraded." 이 때문에 Strasbourg의 SIMBAD·VizieR 공식 문서(FAQ, 안내서, TAP)가 모두 404이고, 2.54.0 이후 이 프로젝트가 본 Strasbourg 404(SIMBAD TAP `capabilities` 포함)의 원인도 이 사고로 보인다. 안내문이 거론한 미러: simbad.cfa.harvard.edu, simbad.idia.ac.za, vizier.cfa.harvard.edu, vizier.idia.ac.za(IDIA SIMBAD의 `capabilities`는 2026-11-23에 200으로 답했다. 아직 쓰지 않는다: 같은 자료인지 확인이 필요하다).

## 2. 서비스별 공식 한도

| 서비스 | 인터페이스 | 한도(원문) | 출처 | 확인 |
|---|---|---|---|---|
| NED (`ned.ipac.caltech.edu`) | 모든 자동 질의 | "Do not query NED more frequently than 1 per second; wait at least 1 second between receiving a reply and making a new query." "Do not run multiple concurrent automated queries; single-thread interactions only." "Please contact the NED Helpdesk before starting any set of queries that might extend over more than 6 hours; even those that follow these guidelines." | https://ned.ipac.caltech.edu/help/guidelines_auto.html (Latest Revision: 2015 July 20) | ✔ |
| NED | TAP | "default is set to 4 minutes (240 seconds)"(실행 시간), 프록시 5분, MAXREC 기본 1,000,000행 | https://ned.ipac.caltech.edu/Documents/Guides/Interface/TAP | ○ |
| SDSS SkyServer (`skyserver.sdss.org`) | SQL Search 등 | "Currently, you are allowed to submit 60 queries per minute, i.e., if you submit one query, you must wait at least 1 seconds before you submit the next one." SQL Search: 시간 제한 600초, 500,000행 | https://skyserver.sdss.org/dr16/en/help/docs/limits.aspx (DR17·DR18에는 같은 페이지가 없음(404). DR18 검색 도구 페이지는 "10min timeout, 500,000 returned rows"만 적음: https://skyserver.sdss.org/dr18/SearchTools) | ✔ (DR16) / ○ (DR18) |
| ESA Gaia (`gea.esac.esa.int`) | TAP+, 익명 | 동기 시간 제한 60초, 대기열 50, 활성 질의 100(익명 전체 합), 질의당 행 50 000, DataLink 50개, 보관 24시간. 서버의 `capabilities`(2026-11-23)는 실행 시간 3600초, 출력 한도 50000행, 보관 129600초 | https://www.cosmos.esa.int/web/gaia-users/archive/collaborate (표) ; https://gea.esac.esa.int/tap-server/tap/capabilities | ✔ (표) / ○ (capabilities) |
| NOIRLab Data Lab (`datalab.noirlab.edu`) | Query Manager, TAP | "A maximum value of 600 seconds is permitted"(동기 질의 `timeout`, 클라이언트 문서), 비동기 24시간. TAP 서비스 페이지와 `capabilities`에는 행·시간·속도 한도 없음 | https://datalab.noirlab.edu/docs/api/dl.queryClient.html | ○ |
| MAST (`catalogs.mast.stsci.edu`, `mast.stsci.edu`) | Mashup / Catalogs API | "The maximum result size for a MAST Query is roughly 500,000 records (rows) due to server memory limits." 릴리스 노트 v3.49(2023): "Limit API queries to 50,000 records max."(두 문서가 어긋남). 카탈로그별 원뿔 반경 상한(Gaia DR3 1°, PS1 DR2 0.45°). 요청 속도 한도는 어느 MAST 페이지에도 없음 | https://mast.stsci.edu/api/v0/ ; https://outerspace.stsci.edu/spaces/MASTDATA/pages/176435488/Catalog+List | ○ |
| IRSA (`irsa.ipac.caltech.edu`) | TAP, 원뿔 검색 | 동기 TAP: "either completes or times out within 5 minutes", 비동기 3일. 원뿔 검색 SR "0 -- 1 (Larger values may time out.)". 행 상한·속도·동시성 한도는 찾지 못함 | https://irsa.ipac.caltech.edu/docs/program_interface/TAP.html ; https://irsa.ipac.caltech.edu/docs/vo_scs.html | ○ |
| HEASARC (`heasarc.gsfc.nasa.gov`) | TAP, 원뿔 검색 | NAVO 요약 표: "100,000 row limit on results"(재정의 가능), "No limits on size of query". Xamin: "Only a limited number of queries are allowed to run concurrently."(수는 적지 않음). 속도 한도 없음 | https://heasarc.gsfc.nasa.gov/navo/summary/navo_services.html ; https://heasarc.gsfc.nasa.gov/xamin/help/release.html | ○ |
| GAVO Data Center (`dc.zah.uni-heidelberg.de`) | TAP(Gaia 천문측량 충실도 `gedr3spur`) | `capabilities`: 실행 시간 기본 20, 출력 기본 20000행(최대 16,000,000). 속도·동시성 규칙은 없음. 예시 페이지: "it's nice not to put unnecessary load on our servers" | https://dc.zah.uni-heidelberg.de/tap/capabilities ; https://dc.zah.uni-heidelberg.de/tap/examples | ○ |
| SIMBAD (미러 `simbad.cfa.harvard.edu`) | TAP | `capabilities`: 실행 시간 기본 1080초·최대 3600초, 출력 기본 50000행·최대 2,000,000행. 속도 한도 없음 | https://simbad.cfa.harvard.edu/simbad/sim-tap/capabilities | ○ |
| SIMBAD | 질의 속도·차단 | **공식 문서를 읽지 못함**(Strasbourg 404). 2차 자료: astroquery 문서 "If you spam the server with more that ~5-10 queries per second you will be blacklisted for up to an hour.", astroquery 소스 주석 "SIMBAD suggests submitting no more than 6 queries per second" | https://astroquery.readthedocs.io/en/latest/simbad/simbad.html | △ |
| VizieR (`vizier.cds.unistra.fr` 및 미러) | 원뿔 검색, ASU, TAP | **공식 한도를 읽지 못함**(Strasbourg 404, `tapvizier.cds.unistra.fr` 연결 끊김). 읽을 수 있던 미러 문서에도 속도·동시성·TAP 한도 없음. ASU: "-out.max=number: The maximal number of returned matching items. The default value depends on the server" | https://vizier.cfa.harvard.edu/vizier/doc/asu.htm | ○ |
| Legacy Surveys 뷰어 (`www.legacysurvey.org/viewer/cat.fits`, NERSC) | 카탈로그 내려받기 | 공식 페이지에 이 엔드포인트의 설명도 이용 정책도 없음. 문서화된 스크립트 접근은 cutout뿐: "The maximum size for cutouts (in number of pixels) is currently 512." 많은 양은 help@legacysurvey.org에 문의 | https://www.legacysurvey.org/dr10/description/ | ○ |

## 3. 읽는 법

- **공식으로 속도 한도가 적힌 곳은 NED(초당 1회, 단일 스레드)와 SDSS SkyServer(분당 60회, DR16 문서)뿐이다.** 둘 다 1초 간격이면 충족한다. SIMBAD의 속도 한도는 공식 문서를 읽지 못했고 2차 자료는 서로 다르다(6회/초 대 5–10회/초).
- 나머지(Data Lab, MAST, IRSA, HEASARC, GAVO, Gaia, VizieR, Legacy Surveys)는 **요청 속도·동시성을 정한 공식 문구를 찾지 못했다.** 행·시간 제한만 있다. 한도가 없다는 증거가 아니므로, 이 서비스들의 대기를 3–5초보다 줄일 근거는 문서에서 나오지 않는다.
- 프로젝트 규칙의 3–5초(스레드당 0.2–0.33회/초)는 NED·SDSS·SIMBAD의 한도보다 3–30배 보수적이다. 다만 `workers = 6`으로 서로 다른 호스트를 동시에 묻고, 같은 호스트 안의 수집기도 동시에 돈다(예: VizieR 수집기 여럿이 같은 `vizier.*` 호스트에 동시에). **NED는 "동시 자동 질의 금지"라서 NED 수집기 하나(검색당 요청 1번)만 NED를 묻는 현재 구조가 맞다**: NED를 묻는 수집기가 늘면 이 지침과 충돌한다.
- Gaia의 익명 질의당 행 한도(50 000)는 `gaia_dr3.py`의 `SYNC_MAX_ROWS`·동기 우선 설계와 맞는다. 익명 풀의 활성 질의 100, 대기열 50은 익명 사용자 전체의 합이다.
- 읽지 못한 것: SIMBAD·VizieR의 Strasbourg 공식 속도 한도(사고 복구 뒤 `https://cds.unistra.fr/help/faq/simbad/`를 다시 읽어야 한다), Data Lab의 행 상한과 동시 질의 수, HEASARC TAP 전용 도움말.

## 4. 지금의 대기가 수집 시간에서 차지하는 몫 (측정)

모든 아카이브 요청 앞의 3–5초(평균 4.0초)는 수집기 한 개의 스레드 시간에서 큰 부분이다. V2_HTTP_LOG 요청 수 × 4.0초를 수집기 경과 시간 합에 대해 보면(영역 세 곳, 차가운 VizieR, 캐시 끔, 2026-11-23 "전" 측정), 요청 대기가 **52 %(NGC 4522: 364 / 694초), 70 %(COSMOS: 384 / 547초), 70 %(은하면: 332 / 474초)** 이다. 서버가 실제로 일한 시간이 아니라 대기가 수집 시간을 정하는 구조다.

## 5. 서비스별 대기를 달리하면 (계산만, 적용하지 않음)

`v2/benchmark/request_counts.py --whatif host=초,...`는 로그에서 호스트별 요청 수를 세어 그 호스트로 가는 요청마다 평균 대기 4.0초를 주어진 초로 바꾸었을 때의 수집 시간을 구한다(수집기 경과 시간에서 요청 수 × (4.0 − 초)를 빼고, 컨트롤러가 수집기를 나눠 주는 방식인 6 스레드 목록 스케줄링으로 수집 시간을 다시 계산). 모형은 측정값과 맞는지 먼저 비교했다(차가운 세 영역: 모형 147.4 / 143.7 / 147.1초, 측정 154.7 / 151.1 / 152.4초; 모형이 약 5 % 낮다).

- **시나리오 S1: 공식 속도 한도가 있는 서비스만 1초(NED, SDSS SkyServer, SIMBAD(2차 자료 기준)).** 2절의 근거로 정당화할 수 있는 유일한 변경이다.
- **시나리오 S2: 모든 호스트 1초.** 문서가 근거를 주지 않는 상한 계산이다. 대기가 수집 시간에서 차지하는 몫을 보이려는 것이지 제안이 아니다.

| 조건 | 영역 | 수집 시간 모형(현재) | S1 | S2 |
|---|---|---|---|---|
| 차가운 VizieR, "전"(2.59.0) | NGC 4522 / COSMOS / 은하면 | 147.4 / 143.7 / 147.1초 | 140.4 / 141.8 / 142.8초 (−7.0 / −1.9 / −4.3) | 91.3 / 81.7 / 86.5초 (−38 % / −43 % / −41 %) |
| 차가운 VizieR, "후"(2.60.0, 캐시 끔) | 같은 순서 | 180.0 / 150.5 / 170.4초 | 173.3 / 147.8 / 167.0초 (−6.7 / −2.7 / −3.4) | 116.2 / 86.0 / 116.6초 |
| 따뜻한 VizieR, FastSpecFit 정상(11초)으로 둠, "후" | 같은 순서 | 36.1 / 35.2 / 26.0초 | 36.1 / 35.2 / 26.0초 (0) | 30.1 / 29.2 / 11.0초 |

읽는 법:
- 차가운 영역은 수집 시간이 VizieR 미러 순회(`agb_suh2021` 85–110초 등)로 정해지고, 이 호스트들에는 공식 속도 한도가 없다. S1은 2–7초를 줄일 뿐이다. S2도 VizieR 상태에 따라 38–43 %다.
- 정상인 날(VizieR 응답이 있고 Data Lab이 답함)에서 SIMBAD 요청을 줄인 뒤의 임계 경로는 Legacy Surveys / Data Lab(약 35초)과 Gaia(약 26–28초)다. 둘 다 공식 속도 한도를 찾지 못한 서비스라 S1은 0초를 줄이고, 줄이려면 근거 없는 S2가 필요하다. **지금 문서가 근거를 주는 범위의 대기 단축은 수집 전체 시간을 거의 줄이지 못한다.** 요청 수를 줄이는 쪽이 낫다.
- "전" / "후"의 차이는 같은 조건의 반복 측정이 아니라 한 번씩 잰 것이고 VizieR 미러 상태의 흔들림이 크다(`erosita`·`tgss`가 어떤 실행에서는 2번, 어떤 실행에서는 7번 묻는다). 5–7초 차이는 잡음 범위다.
