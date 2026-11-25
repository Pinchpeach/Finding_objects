# Third-party notices

Finding Objects 자체 코드는 MIT License(`LICENSE`)를 따른다.
아래 구성 요소는 각자의 라이선스를 따르며, 배포용 앱(PyInstaller 폴더)에 함께 들어간다.

## [1] 앱에 함께 들어가는 소프트웨어

| 구성 요소 | 라이선스 | 비고 |
|---|---|---|
| Qt 6 / PySide6 (Qt for Python) | LGPL-3.0 | 아래 [2] 참고 |
| Python 런타임 | PSF License | https://docs.python.org/3/license.html |
| NumPy | BSD-3-Clause | |
| pandas | BSD-3-Clause | |
| Astropy | BSD-3-Clause | |
| astroquery | BSD-3-Clause | |
| PyVO | BSD-3-Clause | |
| Requests | Apache-2.0 | |
| PyInstaller 부트로더 | GPL-2.0 + bootloader exception | 예외 조항으로 번들된 앱의 라이선스는 제한하지 않는다 |

각 패키지의 원문 라이선스는 해당 패키지 배포본(`*.dist-info/LICENSE*`)에 들어 있다.

## [2] Qt / PySide6 (LGPLv3)

- Qt와 PySide6는 The Qt Company Ltd.가 LGPLv3로 배포한다.
  - ㄴ 원문 : https://www.gnu.org/licenses/lgpl-3.0.html
  - ㄴ 소스 : https://code.qt.io , https://download.qt.io/official_releases/QtForPython/
- 앱은 Qt를 수정하지 않고, 별도 공유 라이브러리(`_internal/` 아래 `Qt*` / `PySide6`)로 동적 연결한다.
  - ㄴ 사용자는 이 라이브러리를 호환되는 다른 버전으로 바꿔 넣어 실행할 수 있다.
- 이 앱의 전체 소스 : https://github.com/Pinchpeach/Finding_objects

## [3] 관측 데이터

프로그램은 실행할 때 아래 아카이브에서 데이터를 받아 오며, 데이터 자체는 저장소에 포함하지 않는다(벤치마크용 특징 파일 제외).
- **사용자 PC의 작은 목록 사본(2.60.6, 기본 꺼짐):** `V2_LOCAL_LISTS=all`이면 Suh (2021) AGB 표(VizieR J/ApJS/256/43 표 9–12, 18,381행)와 Roma-BZCAT 5판(VII/274, 3,561행)을 **사용자 컴퓨터가 VizieR에서 직접 한 번 받아** 그 사용자의 캐시 폴더(`V2_CACHE_DIR`, 기본 `~/.cache/finding_objects/v2/lists/`)에 둔다. 저장소와 앱 묶음에는 이 자료가 들어가지 않고, 다른 사람에게 건네지 않는다(재배포가 아니다). 내려받은 판·날짜·행 수·해시는 그 폴더의 `manifest.json`에 적힌다. **이용 조건의 원문은 아직 읽지 못했다**(CDS 이용 조건 페이지가 2026-11-15 사고 뒤 열리지 않음; Suh 표의 DOI 메타데이터는 "Refer to CDS usage"만 적고, BZCAT은 출처 표기를 요청할 뿐 사본에 대한 문장이 없다). 그래서 기본값에서는 쓰지 않는다(`V2_LOCAL_LISTS=auto`는 이용 조건을 확인한 목록만 쓰며 지금은 없다). 이 목록을 쓴 결과를 발표할 때는 아래 CDS와 원 논문의 인용 요구를 따른다.
결과를 발표할 때는 각 서베이의 인용·감사 문구를 따른다.

- ESA Gaia (DPAC) : https://www.cosmos.esa.int/web/gaia-users/credits
- SDSS : https://www.sdss.org/collaboration/citing-sdss/
- DESI / Legacy Surveys : https://www.legacysurvey.org/acknowledgment/
- Pan-STARRS1, GALEX (MAST) : https://archive.stsci.edu/publishing/mission-acknowledgements
- WISE / AllWISE, 2MASS (IRSA) : https://irsa.ipac.caltech.edu/data/WISE/docs/release/
- VizieR / SIMBAD (CDS) : https://cds.unistra.fr/vizier-org/licences_vizier.html
- NED : https://ned.ipac.caltech.edu/Documents/Guides/Policies/Acknowledgment
- ZTF, NVSS, FIRST, VLASS, TGSS, LoTSS, Chandra, XMM-Newton, eROSITA, ATNF, HASH 등은 각 카탈로그 논문을 인용한다(`v2/document/` 참고).
- 조회를 건너뛰는 영역 경계(`v2/Get_data/footprint.py`, `desi_dr1_tiles.csv.gz`)는 각 서베이가 공개한 영역 정의에서 옮긴 값이다: DESI DR1 타일 목록(`tiles-iron.csv`), FIRST 커버리지 지도(https://sundog.stsci.edu/first/catalogs/ , Helfand et al. 2015), LoTSS DR2 커버리지 MOC(https://lofar-surveys.org/dr2_release.html , Shimwell et al. 2022), MYStIX 20개 영역의 중심과 크기(VizieR J/ApJS/209/32 `reg`·`mpcm`, Broos et al. 2013). 카탈로그 목록 자체를 담은 것이 아니라 경계 숫자와 DESI 타일 중심이다. 작고 고정된 목록(Suh 2021 AGB, Roma-BZCAT 등)의 사본은 재배포 조건을 원문에서 찾지 못해 넣지 않았다(`v2/WORK_REPORT_2026-11-24.md` 11.1절).
