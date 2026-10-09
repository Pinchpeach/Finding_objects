# Finding Objects — standalone 앱 설계 초안 (2026-10-09)

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
python v2/app/finding_objects_app.py
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

