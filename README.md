# Finding Objects

> 하늘의 한 영역에 있는 천체를 모두 찾고, 무엇인지 가려낸다.

노트에 정리하던 방식 그대로 적는다.
큰 줄기는 `[번호]`로, 그 아래 갈래는 `ㄴ`로, 꼭 기억할 것은 `★`로 표시한다.

---

## [0] 무엇을 하는가

- 관측 가능한 전 파장대역(전파 ~ X선)의 카탈로그를 모아 대상 천체를 식별하고 분류한다.
  - ㄴ 1차 분류 : STAR / GALAXY / QSO / UNKNOWN
  - ㄴ 세부 분류 : 분광형, 백색왜성, 뜨거운 준왜성, 초저온 왜성, 적색거성 · AGB, 변광성(Mira, 세페이드, RR Lyrae, 젊은 별 ...), 펄서, AGN, 블레이자, 행성상성운 등
- ★ 확신이 없으면 고르지 않는다 → **UNKNOWN**으로 남기고 그 이유를 적는다.
- ★ 모든 임계값과 규칙은 문헌 근거가 먼저다. 근거는 `v2/` 아래 `LITERATURE*.md`에 남긴다.

목표
1. 사람 손을 거치지 않는 완전 자동 천체 분류기
2. 내 연구 영역의 대상과 그 짝(counterpart)을 찾는 것

---

## [1] 어떻게 동작하는가

```
(RA, Dec, 반경)
  │
  ├─ 수집   아카이브 27곳을 병렬로 질의 (Gaia, SDSS, PS1, Legacy Surveys, WISE, 2MASS,
  │         GALEX, 전파 5종, X선 3종, 분광 4종, ZTF, ATNF, BZCAT, SIMBAD, NED ...)
  ├─ 연관   같은 천체의 검출끼리 묶는다 (위치 · 관측 시기 · 오차, 고유운동 보정)
  ├─ 통합   천체 하나 = 한 행, 단위 통일 (AB 등급, mJy, z)
  ├─ 증거   규칙 25개가 각자 STAR / GALAXY / QSO 쪽 증거를 낸다
  ├─ 1차    증거를 로지스틱 융합으로 합친다 → STAR / GALAXY / QSO / UNKNOWN
  └─ 세부   세부 분류 + 독립 축 5개 (물리 상태, 변광, 밀집성, 외부은하, 현상)
  ↓
classified_objects.csv
```

- [1.1] 수집 : 같은 영역을 다시 찾으면 로컬 캐시에서 바로 읽는다.
- [1.2] 연관 : 단순 최근접이 아니라 우도비로 짝을 정한다.
  - ㄴ 이름이 다른 카탈로그끼리도 위치와 특징이 맞으면 하나로 합친다.
- [1.3] 증거 : 카탈로그의 판정을 그대로 믿지 않는다.
  - ㄴ "이 측정은 STAR 쪽으로 이만큼"이라는 증거로 바꿔서 합친다.
- [1.4] 세부 : 1차 분류가 끝난 뒤에야 더 작은 갈래로 나눈다.
  - ex) STAR → K5 왜성, Mira, 탄소별 AGB ...
  - ex) GALAXY → 별 생성 은하, AGN ...

자세한 설명은 `v2/ALGORITHM.md`.

---

## [2] 얼마나 맞히는가

| 검증 | 결과 |
|---|---|
| SDSS 분광 정답, 1차 분류 | 97.59 % |
| DESI 분광 정답 (어두운 천체), 1차 분류 | 90.96 % |
| Mira / 세페이드 / RR Lyrae | 94.8 / 93.2 / 82.4 % |
| 행성상성운 | 89.2 % |
| 처음 보는 대상 맹검 | 9 / 9 |

- 분광 분류는 정답 확인에만 쓰고, 분류 증거에서는 뺀다.
- 버전별 측정치와 바뀐 이유는 `v2/CHANGELOG.md`.

---

## [3] 실행

### [3.1] 명령줄

```bash
# 한 위치 주변의 모든 서베이를 받아서 분류 (아카이브 접속 필요)
python v2/pipeline.py --ra 188.4155 --dec 9.1751 --radius 0.5 --work runs/ngc4522

# 이미 받아둔 카탈로그로만 분류
python v2/pipeline.py --raw-dir v2/rawdata --work runs/ngc4522
```

- 단계마다 CSV가 `--work`에 남는다.
  - ㄴ `pipeline_summary.csv`에 단계별 소요 시간이 함께 남는다.

### [3.2] 데스크톱 앱

- [Releases](https://github.com/Pinchpeach/Finding_objects/releases)에서 OS에 맞는 압축 파일을 받는다.
  - ㄴ 압축을 풀고 `FindingObjects`(Windows는 `FindingObjects.exe`)를 실행한다. Python은 필요 없다.
- 소스에서 실행하려면

```bash
pip install -r v2/app/requirements.txt
python v2/app/qt_app.py
```

- 실행 로그는 사용자별 로그 파일 하나에 계속 쌓인다 (View > Log, Ctrl+L).

### [3.3] 시험

```bash
cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests
```

---

## [4] 폴더

| 위치 | 내용 |
|---|---|
| `v2/Get_data/` | 아카이브별 수집기 |
| `v2/Preprocess/` | 연관 · 통합 · 특징 · 증거 · 1차 분류 |
| `v2/Classifier/` | 세부 분류와 독립 축 |
| `v2/app/` | 데스크톱 앱 (Qt) |
| `v2/benchmark/` | 정답 집합과 벤치마크 |

---

## [5] 라이선스

- 이 저장소의 코드 : MIT License → [`LICENSE`](LICENSE)
- 배포용 앱에 함께 들어가는 Qt(PySide6, LGPLv3) 등 제3자 구성 요소와 관측 데이터 이용 조건 → [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
- 이 프로그램으로 얻은 결과를 논문에 쓸 때는 사용한 각 서베이의 인용·감사 문구를 따른다.
