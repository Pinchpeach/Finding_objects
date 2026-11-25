# 작업 보고서 2026-11-25 (발표 자료): 12쪽 "파이프라인·기술 스택" 덱을 2.60.2 기준으로 다시 만들고 생성기를 둠

- 버전: 2.60.4 (PATCH, 문서만. 분류·수집·결과·앱 변화 없음). **병합 세션이 번호를 다시 매겨도 된다**(같은 날 다른 세션이 1–4번 작업으로 버전을 올린다). `v2/VERSION`과 CHANGELOG 행은 마지막 커밋 하나에만 있다.
- 사용자 요청(2026-11-25): "12장짜리 덱도 새로 만들어." 문서 언어 결정(2026-11-24): README·개요·덱은 영어.
- 건드리지 않은 것: 분류 코드, 수집기, 워크플로, 벤치마크.

## 1. 무엇을 만들었나

| 파일 | 내용 |
|---|---|
| `document/PIPELINE_STACK_v2.60.2.pptx`·`.pdf`·`_preview.png` | 새 덱(영어, 12쪽, 16:9). PDF는 PPTX를 변환한 것, 미리보기는 PDF 1쪽 |
| `document/deck_content.py` | 덱의 글 전부(덱에만 있는 문장은 여기 한 곳). 표와 수치는 `overview_content.py`에서 읽는다 |
| `document/build_deck.py` | 생성기. `python v2/document/build_deck.py` → PPTX(python-pptx) → PDF(LibreOffice headless) → PNG(pdftoppm) |
| `Preprocess/tests/test_deck.py` | 시험 7개(아래 4절) |
| `document/overview_content.py`, `build_overview.py`, `README.md`, `OVERVIEW_v2.60.2.pdf`, `document/README.md` | 새 덱 링크, 옛 덱 설명 고침(README와 개요 PDF는 다시 생성) |

옛 덱(`PIPELINE_STACK_v2.44.0.*`)은 지우지 않았다. README 15절과 `document/README.md`에 "2.44.0 덱, 손으로 그린 것, 수치 낡음, 2.60.2 덱이 대신함"으로 적었다. **제안:** 다음 정리 때 옛 덱 세 파일(약 0.5 MB)을 지워도 된다. 릴리스 v2.44.0 태그에 남아 있고, 본문 수치가 지금과 달라 혼동만 준다. 지우려면 README 15절의 행과 `test_relative_links_resolve`가 보는 링크를 함께 빼야 한다.

## 2. 쪽별 구성

| 쪽 | 제목 | 내용 |
|---|---|---|
| 1 | Finding Objects | 무엇인가(영역 단위 다중 카탈로그 통합·주석 도구), 수집 대역 그림(파랑 = coarse 분류를 정하는 대역, 회색 = 태그·세부형용) |
| 2 | At a glance | 30 아카이브 · 35 규칙 · 4 답 · 29 열, "What it is"와 "What is not claimed" |
| 3 | Processing flow | 8단계 흐름도(수집 → 1–5 → 6–7 → 후처리), 산출 파일 |
| 4 | Data sources: 30 collectors | 종류별 수집기 표(개요 3절 표 그대로) |
| 5 | What decides the class | 규칙군 제거 실험 막대 그림(밝은 영역 3,428 / COSMOS 28,194), X선·전파 0 / 0 |
| 6 | From evidence to a class | 규칙군별 행 수(합 35), 융합 → 결정적 운동 → 사전확률 한 층 → 기권 |
| 7 | Provenance of every decision | CATALOG / EXTERNAL_CLASSIFIER / INFERRED / NONE, 문헌 전용 항목, UNCONFIRMED, 실행 상태 열 |
| 8 | How it is validated | 블라인드 영역, 잠근 세트 C, 하늘 칸 분할, COSMOS, 통계, 기준선, 아카이브 상태 관문 |
| 9 | Performance of the coarse classifier | 6개 시험 표: 결과와 표본·주의점(세트 C 99.65 %와 별 95 %·DSC 기준선, SDSS 93.79 %와 r > 21·QSO 재현율, COSMOS와 다수 클래스 기준선, 개발 세트, 대표성 없는 옛 벤치마크) |
| 10 | Limits at the faint end | 등급별 1형 AGN 재현율 막대(96 / 76 / 19 / 6–7 %, r ≥ 24는 33개 중 0), "QSO?" 표시 순도 29/119·재현율 47/97, 어두운 별·고신뢰 은하 한계 |
| 11 | Speed, archives and failures | 첫 검색 시간·요청 수(2.60.2 대 2.60.1), 우회 경로, 불완전 실행 표시, `--retry-failed`, 영역 판정 |
| 12 | Tech stack and code map | 앱·모델·데이터·아카이브 접근·운영 스택, 코드 지도, 작업 규칙 |

12쪽을 지켰다. "주장하지 않는 것"은 따로 한 쪽을 주면 13쪽이 되어 2쪽 오른쪽 절반에 넣었다(첫머리에서 한계를 먼저 읽게 하는 효과도 있다).

## 3. 왜 이렇게 짰나

- **생성기를 둔 이유.** 2.44.0 덱은 LibreOffice Impress에서 손으로 그려 다시 만들 수 없었고, 그래서 머리 수치 넷(29 아카이브, 36 + 2, 99.16 %, 141 시험)이 모두 낡은 채 남았다. 개요(2.60.3)와 같은 방식(글 한 곳 + 그리는 스크립트 + 시험)으로 맞췄다.
- **수치를 두 번 적지 않는다.** 덱은 개요의 축약본이므로 ① 개요에 이미 있는 표(자료원, 규칙군, 제거 실험, 시간·요청 수)는 `overview_table()`로 **읽어 온다**. ② 덱에만 있는 짧은 문장의 백분율과 천 단위 이상 개수는 **개요 본문에도 있어야** 시험이 통과한다. 개요 수치를 고치면 덱 시험이 실패하므로 덱만 낡을 수 없다. 대안이던 "덱 글을 통째로 개요 블록에서 자동 추출"은 버렸다. 슬라이드는 문단보다 훨씬 짧아야 해서 자동 축약이 안 되고, 한 쪽 한 생각 원칙이 깨진다.
- **python-pptx + LibreOffice 변환.** PPTX는 글상자·도형·표가 모두 편집 가능한 원래 객체다(그림으로 붙이지 않음). PDF는 그 PPTX를 변환하므로 두 파일의 내용이 달라질 수 없다. 대안이던 "reportlab으로 PDF를 따로 그리기"는 같은 슬라이드를 두 번 배치해야 해서 버렸다.
- **그림 두 개는 실제 수치로 그린다.** 5쪽 막대는 개요 4절 표의 "맞게 / 틀리게 바뀐 수"를 그대로 쓰고, 두 표본의 크기가 8배 달라 열마다 따로 눈금을 잡았다(그림 아래에 명시). 한 눈금으로 그리면 밝은 영역 막대가 보이지 않는다. 10쪽 막대는 값 하나짜리 계열이라 축 없이 막대마다 값을 적었다. 색은 색각 이상 검증이 된 기본 팔레트의 파랑·주황 두 칸만 쓰고 모든 막대에 숫자를 붙여 색만으로 구분하지 않는다.
- **"전 파장 분류기"로 읽히지 않게.** 옛 표지는 전파–X선 파장 막대만 보여 주었다. 새 표지는 같은 그림을 두되 coarse 분류를 **정하는** 대역(광학, WISE 중적외선, Gaia 측성·DSC)만 파랑으로 칠하고 "수집하는 것이지 분류를 정하는 것이 아니다"라고 적었다. 5쪽 결론 상자와 2쪽 "not claimed"에도 같은 말이 있다.
- **글꼴은 Arial.** 옛 덱의 Inter는 대부분의 PC에 없어 PowerPoint에서 다른 글꼴로 바뀌고 줄이 넘친다. Arial은 Windows·macOS에 있고, Linux의 LibreOffice는 폭이 같은 Liberation Sans로 바꾸므로 PDF와 PPTX의 줄바꿈이 같다. 필요한 글리프(′ ″ ≥ ≤ σ ° → −)가 두 글꼴에 모두 있다.
- **재현성.** PPTX는 문서 날짜와 zip 시각을 고정해 같은 글이면 같은 바이트가 나온다(시험이 확인). PDF는 LibreOffice가 생성 시각을 넣어 바이트 재현은 안 된다.
- **README에서의 자리.** 새 덱 링크를 맨 위 "Read first" 줄(개요 PDF 다음)에 두었다. 이유: 이제 개요와 같은 원본·같은 버전에서 나오고 시험으로 묶여 있어 "갱신 안 된 옛 자료"가 아니며, 처음 보는 사람에게 9쪽 PDF보다 빠른 입구다. 옛 덱은 15절에 그대로 둔다. 맨 위 줄은 `build_overview.py`의 README 머리에 있어 `overview_content.py`(파일 이름 `DECK_STEM`)와 함께 그 파일도 두 줄 고쳤다. README는 손으로 고치지 않고 다시 생성했다.

## 4. 확인

- **눈으로 확인.** `pdftoppm`으로 PDF 12쪽을 모두 PNG로 그려 한 쪽씩 보았다(110 dpi, 고친 쪽은 다시). 고친 것: 도형의 테마 그림자(LibreOffice가 가는 선에도 그림), 3쪽 상자 글 넘침, 5쪽 막대 순서를 숫자 순서(맞게 / 틀리게)와 맞춤, 8쪽 첫 카드 넘침, 9쪽 표 머리 높이, 10쪽 굵은 글 안의 코드 표기와 줄 끝 "%" 홀로 넘어감, 12쪽 설명 두 줄 넘침. 마지막 렌더에서 넘침·잘림·겹침·빈 글리프 없음.
- **글리프.** `pdffonts`: Liberation Sans / Mono 4종이 모두 내장. PDF 본문에서 `12′`, `10σ`, `≥`, `≤`, `3.5°`, `→`, `−40°`를 시험이 찾는다.
- **시험(`test_deck.py`, 7개).** 영어 전용·낡은 수치 없음 / 개수가 코드와 같음(수집기 30, 규칙 35와 규칙군 합, 요약 열 29, `requirements.txt`·PyInstaller·sklearn 제외, 코드 지도 경로와 단계 모듈 존재) / 덱의 모든 백분율·큰 개수가 개요에 있음 / 제거 실험 그림이 개요 표와 같음 / 파일이 커밋되어 있고 README가 링크 / PPTX가 12쪽이고 재현되며 커밋된 PPTX와 글이 같음 / 커밋된 PDF가 12쪽이고 쪽마다 제목과 글리프가 있음.
- **전체 시험.** `cd v2 && python -m pytest -q Preprocess/tests Classifier/tests app/tests` → **326 passed**(이전 319 + 7). 분류 결과 변화 없음(분류 코드를 건드리지 않음).
- **한계.** CI(`test-preprocess.yml`)에는 python-pptx와 pypdf가 없어 마지막 두 시험은 건너뛴다(개요 PDF 시험이 reportlab 없이 건너뛰는 것과 같다). 워크플로는 이 작업 범위 밖이라 고치지 않았다. PowerPoint 실물에서는 열어 보지 못했다(LibreOffice 렌더만 확인).

## 5. 개요와 저장소의 불일치

찾지 못했다. 덱에 쓴 수치를 저장소와 대조한 것: 수집기 30(`controller.COLLECTORS`), 규칙 35와 규칙군별 9/12/4/2/3/2/3(`classification_rules.csv`의 rule_id), 요약 열 29(`summary.COLUMNS`), 작업자 6, 스택(`app/requirements.txt`, `packaging/requirements-build.txt`, spec의 `excludes=["sklearn", ...]`, `Preprocess/*.npz`를 numpy로 읽음, `build-app.yml`의 3개 OS와 smoke test). 참고 두 가지(불일치는 아님): ① 개요의 "307 tests at 2.60.2"는 2.60.2 시점 값이고 지금은 326개다(덱도 "at 2.60.2"로 적음). ② 10쪽 막대의 "6–7 %"는 높이 6.5로 그렸다.
