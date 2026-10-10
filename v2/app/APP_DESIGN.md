# Finding Objects — standalone 앱 설계 (2026-10-09, 2026-10-10 정리)

> 2.5.0: Tkinter 초안(`finding_objects_app.py`)과 그 전용 실행 계층(`backend.py`)은
> Qt 앱(6절)이 모든 기능을 대신하므로 삭제했다(git 이력에 남아 있음). 1–5절은 초안 당시 기록이다.

사용자 허락을 받아 시작한 초안입니다. 목표는 PC(Windows/macOS/Linux)에서 v2 분류기를 GUI로 실행하는 것입니다.

## 1. 구조
```
v2/app/
  backend.py               GUI와 독립된 실행 계층 (Job → v2/pipeline.run, 백그라운드 스레드, 진행 콜백)
  finding_objects_app.py   Tkinter GUI (입력 폼 · 실행 · 결과 표/필터 · CSV 내보내기 · 로그)
  APP_DESIGN.md            이 문서
```
- **분류 로직은 v2 그대로 재사용**합니다(`v2/pipeline.py`). 앱은 감싸기만 하므로 분류기를 개선하면 앱에도 자동으로 반영됩니다.
- 작업 스레드는 Tk 위젯을 직접 건드리지 않고, 큐를 통해 메인 스레드로 결과를 넘깁니다(Tk는 스레드 안전하지 않음).

## 2. 기술 선택과 근거
| 항목 | 선택 | 이유 |
|---|---|---|
| GUI | Tkinter (ttk) | Python 표준 라이브러리라 추가 설치가 없습니다. Windows/macOS Python 배포판에 기본 포함되어 있습니다. 초안 단계의 의존성을 최소화하려는 선택입니다. |
| 대안 → 채택 | PySide6(Qt) | 하늘 지도, 상세 패널, 대용량 표를 위해 Qt 프론트엔드를 추가했습니다(6절). Tkinter 초안은 참고용으로 남깁니다. |
| 배포 | PyInstaller(one-folder) | 데이터 파일(`fusion_weights.json`, `color_reference.csv.gz`, `classification_rules.csv`)을 `--add-data`로 같이 묶습니다. |
| 네트워크 | 기존 수집기 그대로(아카이브당 300 s 제한) | 오프라인일 때는 "Raw catalog folder"로 미리 받은 데이터를 분류합니다. |

## 3. 현재 초안 기능
- RA/Dec/반경 입력 → 23개 아카이브 수집 → 분류. 또는 수집해 둔 폴더를 바로 분류
- 결과 표(object_id, catalogs, 판정, 확신도, 상태, p_star/p_galaxy/p_qso), 클래스 필터, 클래스별 개수
- 실행 로그, 오류 표시, CSV 내보내기, 판정 보류 임계값(min confidence) 조정

## 4. 다음 단계 (제안)
1. 단계별 진행률 표시(수집기별 완료, 1~7단계 시간) — pipeline에 콜백 훅 추가
2. 천체 상세 패널: 증거 목록(evidence_json), 확률 막대, 연관된 카탈로그 행
3. 하늘 지도(검출 위치 + 클래스 색) 및 Legacy Surveys 컷아웃 링크
4. 실행 취소 버튼, 최근 실행 목록, 설정 저장
5. PyInstaller 빌드 스크립트와 GitHub Actions에서 Windows/macOS 빌드 아티팩트 생성
6. 대상 이름 입력(SIMBAD 이름 해석, 예: "NGC 4522")

## 5. 실행
```
pip install pandas numpy requests astropy astroquery pyvo
python v2/app/qt_app.py
```

## 6. Qt(PySide6) 프론트엔드 (2026-10-09 추가, 기본 GUI)
```
v2/app/
  qt_app.py       MainWindow: 입력 패널 · 결과 표 · 상세/하늘지도 탭 · 로그 · 메뉴 · 설정 저장
  qt_models.py    pandas DataFrame 테이블 모델 + 정렬/필터 프록시(클래스·상태·검색어)
  qt_widgets.py   SkyMap(QPainter 접평면 산점도, 동쪽이 왼쪽) · DetailPanel(확률 막대·증거·세부 축·외부 링크)
  progress.py     파이프라인 로그 줄 → 진행률(수집기 23개 + 7단계), Qt 의존성 없음
  app_paths.py    v2 루트 경로(PyInstaller frozen 실행 대응)
  requirements.txt
  tests/test_app.py  offscreen GUI 테스트(QT_QPA_PLATFORM=offscreen)
```
- 파이프라인은 **QProcess 별도 프로세스**로 실행합니다(앱이 자기 자신을 `--pipeline` 모드로 다시 호출). GUI가 멈추지 않고, 취소는 프로세스 종료로 확실하게 처리되며, PyInstaller 단일 실행 파일에서도 그대로 동작합니다.
- 진행률은 수집기의 `[name] ok|empty|error|timeout` 줄과 `[pipeline] stage: s` 줄로 계산합니다. 실패한 아카이브는 완료 후 경고로 표시합니다.
- 대상 이름 해석(`SkyCoord.from_name`)은 QThreadPool에서 실행해 UI를 막지 않습니다.
- 4절의 제안 1–4번과 6번을 구현했고, 5번(PyInstaller/빌드 워크플로)은 남아 있습니다.

실행:
```
pip install -r v2/app/requirements.txt
python v2/app/qt_app.py
```


## 7. 검색 영역 입력과 카탈로그 명칭 (2026-10-09)
- **Search area**:
  - **Centre** 칸에는 천체 이름이나 좌표를 넣습니다. 이름은 CDS Sesame으로 해석합니다. 좌표는 십진 도(`188.4155 +9.1751`), `12:33:39.7 +09:10:30`, `12h33m39.7s +9d10m30s` 형식을 받으며, 네트워크 없이 바로 해석합니다.
  - RA/Dec는 직접 고칠 수 있습니다.
  - **Radius**는 단위(arcsec / arcmin / deg)를 고를 수 있습니다. 단위를 바꿔도 같은 각도가 유지됩니다.
  - 하늘 지도에 탐색 원(초록 점선)과 중심이 표시되고, 지도를 더블클릭하면 그 위치가 새 중심이 됩니다.
- **Data source**:
  - 아카이브 조회: 검색 영역으로 콘 검색을 합니다.
  - 수집된 폴더: "Keep only objects inside the search area"를 켜면 영역 안의 천체만 남깁니다(`pipeline.py --raw-dir ... --ra --dec --radius`).
- **이름**:
  - 내부 키 `object_id`(OBJ000001…)는 화면에 내보내지 않습니다. 대신 `v2/designations.py`가 실제 카탈로그 명칭을 붙입니다.
  - 우선순위: SIMBAD 주 식별자 → NED → SGA-2020 → Gaia DR3 → SDSS → Pan-STARRS1 → LS DR10 → 2MASS → AllWISE → …
  - 상세 패널의 "Catalog IDs"에는 연관된 모든 카탈로그 명칭이 나열됩니다.
  - 중심이 주어지면 `separation_arcmin`(중심까지 거리)이 추가되고, 결과는 거리순으로 정렬됩니다.

## 8. 큰 은하 통합 · 세부 분류 · 하늘 지도 아이콘/확대 (2026-10-09 밤)
- **큰 은하 통합** (`v2/host_groups.py`):
  - SGA-2020 D26 타원 안의 검출(HII 영역, 팔 조각, 핵 스펙트럼, SIMBAD/NED의 같은 은하 항목)을 SGA 은하의 '부분'으로 묶습니다(`parent_object_id`, `component_role` = identity/nucleus/component).
  - 다음은 독립 천체로 두고, 이유를 역할로 표시합니다: 전경 별(Gaia 시차·고유운동), 적색편이가 다른 천체(|cΔz| > 1500 km/s, 배경 퀘이사 등), 다른 SGA 은하, 초신성 같은 일시 천체.
  - 은하 본체(호스트)는 SIMBAD 이름과 적색편이, 핵 스펙트럼을 물려받습니다.
  - 표에서 부분은 기본으로 숨기고 "Show galaxy parts"로 펼칩니다.
  - NGC 4522 영역: 88개 항목이 10개 최상위 천체로 줄어듭니다. 본체 1개(부분 78개), 독립 판정 3개, 주변 SGA 은하 6개입니다.
- **세부 분류(2단계)** (`Classifier/subclass.py`, 근거·검증은 `Classifier/LITERATURE_SUBCLASS.md`):
  - 별: 분광형과 광도 계급(V/IV/III), 백색왜성, 탄소별, 격변변광성(CV).
  - 은하: 활동성(별 형성 / 스타버스트 / AGN / 비활동)과 광도 분포(초기형 / 원반).
  - 퀘이사: 전파 세기(Ivezić R_i), 고적색편이 여부, X선 검출, Seyfert·블레이자 유형.
  - 상세 패널에 판정 근거와, 그 규칙의 벤치마크 정밀도가 함께 표시됩니다.
- **아이콘** (`app/qt_icons.py`):
  - 별: 분광형 색의 별 모양. 거성은 크게 그리고 후광을 두르며, 백색왜성은 고리 모양입니다.
  - 은하: 활동성별 타원. 별 형성 은하는 나선팔, AGN은 밝은 핵, 큰 은하는 이중 외곽선으로 그립니다.
  - 퀘이사: 마름모. 전파가 센 경우 제트를, X선이 검출되면 표식을 붙입니다.
  - 미분류: 회색 원.
  - 표의 이름 칸과 범례에도 같은 아이콘을 씁니다.
- **하늘 지도 확대**:
  - 휠은 커서 위치를 기준으로 확대하고, 드래그는 이동, 우클릭·Home·Fit은 초기화입니다.
  - +/− 버튼, 축척 막대, 확대 배율 표시가 있습니다. 화면 안 천체가 40개 이하이면 이름을 표시합니다.
  - 큰 은하는 실제 D26 타원(크기·방위각·축비)을 함께 그립니다.
