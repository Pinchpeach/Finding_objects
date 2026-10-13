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
결과를 발표할 때는 각 서베이의 인용·감사 문구를 따른다.

- ESA Gaia (DPAC) : https://www.cosmos.esa.int/web/gaia-users/credits
- SDSS : https://www.sdss.org/collaboration/citing-sdss/
- DESI / Legacy Surveys : https://www.legacysurvey.org/acknowledgment/
- Pan-STARRS1, GALEX (MAST) : https://archive.stsci.edu/publishing/mission-acknowledgements
- WISE / AllWISE, 2MASS (IRSA) : https://irsa.ipac.caltech.edu/data/WISE/docs/release/
- VizieR / SIMBAD (CDS) : https://cds.unistra.fr/vizier-org/licences_vizier.html
- NED : https://ned.ipac.caltech.edu/Documents/Guides/Policies/Acknowledgment
- ZTF, NVSS, FIRST, VLASS, TGSS, LoTSS, Chandra, XMM-Newton, eROSITA, ATNF, HASH 등은 각 카탈로그 논문을 인용한다(`v2/document/` 참고).
