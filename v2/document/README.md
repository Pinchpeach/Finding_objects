# v2/document — 인용 문헌 모음

v2의 분류기 코드와 문서가 근거로 인용하는 과학 논문, 카탈로그·탐사 출판물, 설명서를 한곳에 모은 폴더입니다.
작업 규칙 1(과학적 근거 우선)에 따라 규칙·임계값·모델에는 문헌 근거가 붙어 있는데, 이 인용은
코드 주석, `LITERATURE*.md`, `classification_rules.csv` 등 여러 곳에 흩어져 있습니다.
이 폴더는 그 인용을 모아 어떤 논문이 어느 규칙에 쓰이는지 한눈에 보이게 합니다.

## 파일

| 파일 | 내용 |
|---|---|
| [`PAPERS.md`](PAPERS.md) | 분야별 표. 인용, 학술지·권·쪽, ADS bibcode, 사용처(파일·규칙 ID), 용도. 끝에 "확인이 필요한 인용" 목록이 있음 |
| [`papers.csv`](papers.csv) | 같은 항목의 기계 판독용 표. 열: `category, citation, journal_ref, bibcode, used_in, purpose` (`used_in`은 `;`로 구분) |

## 구성 원칙

- **출처는 저장소 텍스트뿐입니다.** 학술지·권·쪽, DOI, ADS bibcode는 저장소에 적힌 경우에만 기록하고, 없으면 `—`로 둡니다. 기억이나 추측으로 채우지 않았습니다.
- **같은 논문은 한 행으로 합칩니다.** 예를 들어 `Koenig+2012`와 `Koenig et al. (2012)`, `Gentile Fusillo+2021`과 `Gentile Fusillo et al. (2021, MNRAS 508, 3877)`는 각각 한 행입니다. 사용처 열에 인용한 파일을 모두 적습니다.
- **모호한 인용은 원문 표기를 유지합니다.** 연도가 둘이거나(`Ciardi et al. 2010/2011`), 저자 없이 URL만 있거나, 파일마다 서지가 다른 경우에는 `(저장소 표기 그대로)`를 붙이고 `PAPERS.md` 끝에 이유를 적습니다.
- **사용처 경로는 `v2/` 기준입니다.** 규칙 ID(`PS1-MORPH-001`), 코드의 상수·함수 이름(`subclass.py` `RED_CLUMP`, `HR_GATES`)을 함께 적습니다.
- **인용으로 치지 않는 것:** 열 이름(RAJ2000, DEJ2000), 천체 이름(SN 2018oh, NGC 4522), 내부 태그, 날짜, 규칙표의 일반 참조("Gaia astrometry", "Gaia DR3").

## 분야와 항목 수

| 분야 | 항목 수 | 범위 |
|---|---:|---|
| 측성·Gaia | 20 | Gaia 데이터 릴리스, Gaia 처리·검증 논문(DSC, GSP-Phot, 변광, C*, 시차·고유운동, RUWE) |
| 측광 체계·단위 | 8 | AB/Vega 영점, 소광 계수, SDSS→Johnson 변환 |
| 탐사·카탈로그 데이터 | 22 | Legacy Surveys, Pan-STARRS1, SDSS, SGA-2020, DESI DR1, GALEX, NVSS, SIMBAD, Suh 2021, HASH, ATNF, Asiago, ASAS-SN, Acker, LAMOST·SDSS 백색왜성 목록 |
| 데이터 출처 카탈로그 (논문 인용 없음) | 13 | 코드가 VizieR ID나 서비스 이름으로만 쓰는 카탈로그(AllWISE, 2MASS, FIRST, LoTSS, VLASS, CSC 2.0, 4XMM, eRASS1, LAMOST DR5, SDSS DR18, NED, ASAS-SN 변광성, Gaia DR3 VizieR 사본) |
| 교차 대응·통계·분류 방법 | 8 | 베이즈 교차 대응, EM 사전확률, kNN·결정트리·랜덤 포레스트, PS1 형태 분리 |
| 별 분류 | 21 | 분광형·광도 계급, 백색왜성, 운동학 집단, 근거리·고유운동, 적색 거성군, 적외선 초과, 금속 결핍, 쌍성, RGB/AGB, 주기-광도 |
| 은하 분류 | 23 | BPT, WISE·GALEX 색, 녹색 계곡, Sérsic·u−r, 광도, 경사각, 은하군, Galaxy Zoo |
| 퀘이사·AGN | 14 | WISE AGN, z≈6 선택, DESI QSO 선택, 전파 세기, 광도(M_i), 가린 퀘이사, 고적색편이, 분석 우주론(Schneider+2010) |
| 전파·X선·밀집성 | 4 | 전파 스펙트럼 지수, 펄서 후보 선택 |
| 행성상성운·초신성·과도 현상 | 6 | PN 진단, 광도곡선 기반 초신성 분류 |
| 기타 문서 | 13 | 설명서(WISE/AllWISE/2MASS), SDSS·Gaia·NED·SIMBAD 문서, PS1 아카이브 안내, desitarget, Redrock |
| **합계** | **152** | |

별도의 "우주론·거리" 분야는 두지 않았습니다. 거리 계산에 쓰는 평탄 ΛCDM(H0 = 70, Ωm = 0.3)은
Schneider et al. 2010 하나에서 오며, 이 논문은 퀘이사 광도 절단에도 쓰이므로 "퀘이사·AGN"에 넣었습니다.

## 새 논문을 추가하는 방법

**규칙: 코드나 문서가 새 논문을 인용하면 같은 변경에서 이 폴더에도 추가합니다.**

1. `papers.csv`에 한 행을 추가합니다. `category`는 위 분야 이름 중 하나를 그대로 씁니다.
   - `citation`: `Author et al. Year` 형식(저자 둘이면 `A & B Year`). 괄호 안에 짧은 부제를 붙여도 됩니다.
   - `journal_ref`: 학술지·권·쪽, DOI, VizieR ID 중 **저장소에 적은 것만**. 없으면 `—`.
   - `bibcode`: ADS bibcode를 저장소에 적었을 때만. 없으면 `—`.
   - `used_in`: 인용한 파일(`v2/` 기준)과 규칙 ID·함수 이름, `;`로 구분.
   - `purpose`: 그 논문이 제공하는 것 한 구절(예: "red-clump M_G(G−Ks) 관계").
2. `PAPERS.md`의 해당 분야 표에 같은 행을 넣고, 위 항목 수 표와 `PAPERS.md` 맨 위의 개수를 고칩니다.
3. 이미 있는 논문이면 새 행을 만들지 말고 `used_in`에 사용처만 덧붙입니다.
4. 서지 정보를 코드 주석에 처음 적을 때는 학술지·권·쪽(가능하면 DOI나 bibcode)까지 적어 두면 이 표를 채우기 쉽습니다. "데이터 출처 카탈로그 (논문 인용 없음)"에 있는 카탈로그는 출판 논문을 확인하면 "탐사·카탈로그 데이터"로 옮깁니다.
5. 인용을 지운 경우에는 `used_in`에서 그 파일을 빼고, 사용처가 하나도 남지 않으면 행을 지웁니다.

## 수집 범위 (2026-10-10 기준)

다음 파일을 읽어 만들었습니다(`__pycache__`, `.pytest_cache`, `tests/`, 데이터 파일 제외).

- `v2/` 아래의 모든 `*.md` (`Preprocess/LITERATURE.md`, `Classifier/LITERATURE*.md`, 검증 보고서, `WORK_REPORT_*`, `WORK_LOG_*`, `CHANGELOG.md`, README 등)
- `v2/` 아래의 모든 `*.py` 주석과 docstring (`Get_data/*.py` 수집기의 VizieR ID 포함)
- `Preprocess/classification_rules.csv` (`reference`, `reference_section`, `notes`), `Preprocess/catalog_reliability.csv` (`source`)
- `Classifier/literature.py`의 논문 카탈로그 bibcode
